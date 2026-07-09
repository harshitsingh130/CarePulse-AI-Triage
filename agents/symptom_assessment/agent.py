"""Symptom Assessment Agent — core conversation logic.

Conducts a multi-turn clinical intake conversation, extracting structured
symptom data progressively. Uses Bedrock for natural conversation and
structured data extraction.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from shared.bedrock_client import invoke_model, invoke_model_json
from shared.config import config
from shared.models import (
    AllergyInfo,
    AssociatedSymptom,
    DurationPattern,
    MedicalHistory,
    MedicationList,
    OnsetInfo,
    PrimaryComplaint,
    SeverityInfo,
    StructuredSymptoms,
)
from shared.phi_redaction import get_logger

from .prompts import (
    ASSOCIATED_SYMPTOMS_PROMPTS,
    COMPLETION_MESSAGE,
    FAST_TRACK_ACKNOWLEDGMENT,
    GREETING_MESSAGE,
    RED_FLAG_ACKNOWLEDGMENT,
    SEVERITY_PROMPT,
    SYSTEM_PROMPT,
)

logger = get_logger("symptom-assessment", config.LOG_LEVEL)


class ConversationPhase(str, Enum):
    GREETING = "GREETING"
    PRIMARY_COMPLAINT = "PRIMARY_COMPLAINT"
    ONSET = "ONSET"
    SEVERITY = "SEVERITY"
    DURATION = "DURATION"
    ASSOCIATED_SYMPTOMS = "ASSOCIATED_SYMPTOMS"
    MEDICAL_HISTORY = "MEDICAL_HISTORY"
    MEDICATIONS = "MEDICATIONS"
    ALLERGIES = "ALLERGIES"
    CLARIFYING = "CLARIFYING"
    COMPLETE = "COMPLETE"


# Red flag patterns (case-insensitive)
RED_FLAG_PATTERNS = {
    "cardiac": [
        r"chest\s*pain.*(?:breath|sweating|arm|jaw)",
        r"(?:breath|sweating|arm|jaw).*chest\s*pain",
        r"heart\s*attack",
    ],
    "respiratory": [
        r"can'?t\s*breathe",
        r"difficulty\s*breathing",
        r"throat\s*(?:closing|swelling|tight)",
        r"choking",
    ],
    "neurological": [
        r"face\s*droop",
        r"arm\s*weakness",
        r"can'?t\s*speak",
        r"sudden\s*confusion",
        r"worst\s*headache\s*(?:of\s*my\s*life|ever)",
    ],
    "hemorrhage": [
        r"(?:won'?t|can'?t|cannot|will not)\s*stop\s*bleeding",
        r"bleeding\s*(?:heavily|everywhere|a\s*lot|won'?t stop)",
    ],
    "mental_health": [
        r"(?:want|going)\s*to\s*(?:kill|hurt)\s*(?:myself|me)",
        r"suicid",
        r"self[- ]?harm",
        r"want\s*to\s*die",
    ],
    "allergic": [
        r"throat\s*swelling",
        r"anaphyla",
        r"epipen",
        r"allergic\s*reaction.*(?:breathe|swelling)",
    ],
    "consciousness": [
        r"passed\s*out",
        r"lost\s*consciousness",
        r"seizure",
        r"fainted",
    ],
}


class ConversationState:
    """Manages the state of a single triage conversation."""

    def __init__(
        self,
        session_id: UUID,
        patient_id: UUID,
        ehr_medications: Optional[list[str]] = None,
        ehr_conditions: Optional[list[str]] = None,
    ):
        self.session_id = session_id
        self.patient_id = patient_id
        self.phase = ConversationPhase.GREETING
        self.turn_count = 0
        self.symptoms = StructuredSymptoms(
            session_id=session_id,
            patient_id=patient_id,
        )
        self.ehr_medications = ehr_medications or []
        self.ehr_conditions = ehr_conditions or []
        self.ehr_data_available = bool(ehr_medications or ehr_conditions)
        self.pending_clarifications: list[str] = []
        self.last_question_asked: str = ""
        self.conversation_history: list[dict] = []

    @property
    def fast_track(self) -> bool:
        """Should we fast-track (severity >= 8)?"""
        return (
            self.symptoms.severity is not None
            and self.symptoms.severity.score >= 8
        )

    @property
    def completeness_score(self) -> float:
        """Calculate weighted completeness score."""
        score = 0.0
        if self.symptoms.primary_complaint:
            score += 0.25
        if self.symptoms.severity:
            score += 0.20
        if self.symptoms.onset:
            score += 0.15
        if self.symptoms.duration_pattern:
            score += 0.10
        if self.symptoms.associated_symptoms:
            score += 0.10
        if self.symptoms.medical_history:
            score += 0.10
        if self.symptoms.medications:
            score += 0.05
        if self.symptoms.allergies:
            score += 0.05
        return score

    def is_complete(self) -> bool:
        """Check if assessment has enough data to proceed."""
        # Mandatory fields
        has_mandatory = all([
            self.symptoms.primary_complaint,
            self.symptoms.severity,
            self.symptoms.onset,
        ])

        if not has_mandatory:
            return False

        # Red flag → complete immediately
        if self.symptoms.red_flag_detected:
            return True

        # Fast-track threshold (severity >= 8)
        if self.fast_track and self.completeness_score >= 0.60:
            return True

        # Normal threshold
        if self.completeness_score >= 0.70:
            return True

        # Max turns reached
        if self.turn_count >= 15:
            return True

        return False


def check_red_flags(text: str) -> Optional[str]:
    """Check patient message for emergency red flag patterns.

    Returns the red flag category if detected, None otherwise.
    """
    text_lower = text.lower()
    for category, patterns in RED_FLAG_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return category
    return None


def get_complaint_category(text: str) -> str:
    """Map primary complaint text to a category for context-aware follow-ups."""
    text_lower = text.lower()

    category_keywords = {
        "headache": ["headache", "migraine", "head pain", "head hurts"],
        "chest_pain": ["chest pain", "chest tight", "heart", "palpitation"],
        "abdominal": ["stomach", "abdominal", "belly", "nausea", "vomit"],
        "respiratory": ["cough", "breathing", "wheeze", "shortness of breath", "asthma"],
        "musculoskeletal": ["back pain", "joint", "knee", "shoulder", "muscle", "sprain"],
        "skin": ["rash", "itch", "skin", "mole", "lesion", "hives"],
        "mental_health": ["anxiety", "depress", "sleep", "stress", "panic", "mood"],
    }

    for category, keywords in category_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return category

    return "default"


async def process_message(
    state: ConversationState,
    patient_message: str,
) -> tuple[str, ConversationState]:
    """Process a patient message and generate the next AI response.

    Args:
        state: Current conversation state.
        patient_message: The patient's latest message.

    Returns:
        Tuple of (AI response text, updated state).
    """
    state.turn_count += 1
    state.conversation_history.append({"role": "patient", "content": patient_message})

    # Check for red flags in every message
    red_flag = check_red_flags(patient_message)
    if red_flag:
        state.symptoms.red_flag_detected = True
        state.symptoms.red_flag_category = red_flag
        logger.info(f"Red flag detected: {red_flag}", extra={"session_id": str(state.session_id)})

        # If we don't have primary complaint yet, extract it now
        if not state.symptoms.primary_complaint:
            state.symptoms.primary_complaint = PrimaryComplaint(
                text=patient_message,
                category=red_flag,
                confidence=0.9,
            )

        # Mark complete for immediate scoring
        state.symptoms.assessment_complete = True
        state.symptoms.fast_tracked = True
        state.symptoms.completeness_score = state.completeness_score
        state.symptoms.conversation_turns = state.turn_count
        state.symptoms.assessed_at = datetime.now(timezone.utc)
        state.phase = ConversationPhase.COMPLETE

        response = RED_FLAG_ACKNOWLEDGMENT
        state.conversation_history.append({"role": "ai", "content": response})
        return response, state

    # Extract data based on current phase
    response = await _handle_phase(state, patient_message)

    # Check completion after extraction
    if state.is_complete() and state.phase != ConversationPhase.COMPLETE:
        state.symptoms.assessment_complete = True
        state.symptoms.completeness_score = state.completeness_score
        state.symptoms.conversation_turns = state.turn_count
        state.symptoms.assessed_at = datetime.now(timezone.utc)
        state.phase = ConversationPhase.COMPLETE
        response = COMPLETION_MESSAGE

    state.conversation_history.append({"role": "ai", "content": response})
    return response, state


async def _handle_phase(state: ConversationState, patient_message: str) -> str:
    """Handle the current conversation phase and advance to next."""

    if state.phase == ConversationPhase.GREETING:
        # First patient message = their primary complaint
        extracted = await _extract_from_message(state, patient_message)
        state.symptoms.primary_complaint = PrimaryComplaint(
            text=patient_message,
            category=get_complaint_category(patient_message),
            confidence=0.85,
        )
        state.phase = ConversationPhase.ONSET

        # If fast-track conditions detected early
        if state.fast_track:
            return FAST_TRACK_ACKNOWLEDGMENT + " " + "When did this start?"
        return "I'm sorry to hear that. When did this first start?"

    elif state.phase == ConversationPhase.ONSET:
        state.symptoms.onset = OnsetInfo(
            description=patient_message,
            days_ago_estimate=_estimate_days_ago(patient_message),
            confidence=0.80,
        )
        state.phase = ConversationPhase.SEVERITY
        return SEVERITY_PROMPT

    elif state.phase == ConversationPhase.SEVERITY:
        severity_score = _extract_severity(patient_message)
        state.symptoms.severity = SeverityInfo(
            score=severity_score,
            source="explicit" if _is_explicit_number(patient_message) else "inferred",
            confidence=0.90 if _is_explicit_number(patient_message) else 0.70,
        )

        if severity_score >= 8:
            state.symptoms.fast_tracked = True
            state.phase = ConversationPhase.ASSOCIATED_SYMPTOMS
            category = state.symptoms.primary_complaint.category if state.symptoms.primary_complaint else "default"
            prompt = ASSOCIATED_SYMPTOMS_PROMPTS.get(category, ASSOCIATED_SYMPTOMS_PROMPTS["default"])
            return f"I understand this is quite severe. {prompt}"

        state.phase = ConversationPhase.DURATION
        return "Is it constant, or does it come and go? Has it been getting worse, better, or staying about the same?"

    elif state.phase == ConversationPhase.DURATION:
        state.symptoms.duration_pattern = DurationPattern(
            type=_classify_duration(patient_message),
            description=patient_message,
            confidence=0.75,
        )
        state.phase = ConversationPhase.ASSOCIATED_SYMPTOMS
        category = state.symptoms.primary_complaint.category if state.symptoms.primary_complaint else "default"
        return ASSOCIATED_SYMPTOMS_PROMPTS.get(category, ASSOCIATED_SYMPTOMS_PROMPTS["default"])

    elif state.phase == ConversationPhase.ASSOCIATED_SYMPTOMS:
        symptoms = _extract_associated_symptoms(patient_message)
        state.symptoms.associated_symptoms = symptoms

        if state.fast_track:
            # Skip to medications if fast-tracking
            if state.ehr_data_available:
                state.phase = ConversationPhase.MEDICATIONS
                meds = ", ".join(state.ehr_medications[:5])
                return f"Your records show you're taking {meds}. Is that still accurate?"
            state.phase = ConversationPhase.MEDICATIONS
            return "Are you currently taking any medications?"

        state.phase = ConversationPhase.MEDICAL_HISTORY
        if state.ehr_data_available and state.ehr_conditions:
            conditions = ", ".join(state.ehr_conditions)
            return f"I can see from your records that you have {conditions}. Is that still current, or has anything changed?"
        return "Do you have any medical conditions I should know about?"

    elif state.phase == ConversationPhase.MEDICAL_HISTORY:
        conditions = _extract_conditions(patient_message, state.ehr_conditions)
        state.symptoms.medical_history = MedicalHistory(
            conditions=conditions,
            source="both" if state.ehr_data_available else "patient_reported",
            confidence=0.80,
        )
        state.phase = ConversationPhase.MEDICATIONS
        if state.ehr_data_available and state.ehr_medications:
            meds = ", ".join(self.ehr_medications[:5])
            return f"Your records show you're taking {meds}. Is that still accurate, or have there been any changes?"
        return "Are you currently taking any medications?"

    elif state.phase == ConversationPhase.MEDICATIONS:
        medications = _extract_medications(patient_message, state.ehr_medications)
        state.symptoms.medications = MedicationList(
            current=medications,
            source="both" if state.ehr_data_available else "patient_reported",
            confidence=0.80,
        )
        state.phase = ConversationPhase.ALLERGIES
        return "Do you have any drug allergies?"

    elif state.phase == ConversationPhase.ALLERGIES:
        allergies = _extract_allergies(patient_message)
        state.symptoms.allergies = AllergyInfo(
            list=allergies,
            confidence=0.85,
        )
        # Assessment should now be complete
        state.phase = ConversationPhase.COMPLETE
        return COMPLETION_MESSAGE

    # Fallback
    return "Could you tell me a bit more about that?"


async def _extract_from_message(state: ConversationState, message: str) -> dict:
    """Use LLM to extract structured clinical data from a patient message."""
    extraction_prompt = f"""Extract any clinical information from this patient message.
Return a JSON object with only the fields you can confidently extract:
- primary_complaint: string (main issue)
- severity: integer 1-10 (if mentioned)
- onset: string (when it started, if mentioned)
- medications: list of strings (if mentioned)
- associated_symptoms: list of strings (if mentioned)

Patient message: "{message}"

Return only valid JSON. If a field cannot be extracted, omit it."""

    try:
        result = invoke_model_json(
            system_prompt="You extract structured clinical data from patient messages. Return only JSON.",
            user_message=extraction_prompt,
            temperature=0.0,
        )
        return result
    except (ValueError, Exception) as e:
        logger.warning(f"Extraction failed: {e}")
        return {}


def _extract_severity(text: str) -> int:
    """Extract severity score from patient message."""
    # Direct number
    numbers = re.findall(r"\b(\d{1,2})\b", text)
    for num_str in numbers:
        num = int(num_str)
        if 1 <= num <= 10:
            return num

    # Natural language mapping
    text_lower = text.lower()
    if any(word in text_lower for word in ["unbearable", "worst", "10/10", "excruciating"]):
        return 10
    if any(word in text_lower for word in ["severe", "really bad", "awful", "terrible"]):
        return 8
    if any(word in text_lower for word in ["bad", "pretty bad", "significant", "quite"]):
        return 7
    # Check "barely" BEFORE "noticeable" to avoid false match on "barely noticeable"
    if any(word in text_lower for word in ["barely", "hardly", "minimal"]):
        return 2
    if any(word in text_lower for word in ["mild", "slight", "minor", "a little"]):
        return 3
    if any(word in text_lower for word in ["moderate", "noticeable", "uncomfortable"]):
        return 5

    return 5  # Default to middle if truly ambiguous


def _is_explicit_number(text: str) -> bool:
    """Check if the patient gave an explicit numeric severity."""
    return bool(re.search(r"\b\d{1,2}\b", text))


def _estimate_days_ago(text: str) -> Optional[int]:
    """Estimate how many days ago onset was from text description."""
    text_lower = text.lower()

    if any(w in text_lower for w in ["today", "just now", "this morning", "an hour", "few hours"]):
        return 0
    if any(w in text_lower for w in ["yesterday", "last night"]):
        return 1
    if "2 days" in text_lower or "two days" in text_lower or "couple days" in text_lower:
        return 2
    if "3 days" in text_lower or "three days" in text_lower:
        return 3
    if any(w in text_lower for w in ["a week", "1 week", "one week", "7 days"]):
        return 7
    if any(w in text_lower for w in ["two weeks", "2 weeks", "14 days"]):
        return 14
    if any(w in text_lower for w in ["a month", "1 month", "one month", "30 days", "few weeks"]):
        return 30

    # Try to find "X days" pattern
    days_match = re.search(r"(\d+)\s*days?", text_lower)
    if days_match:
        return int(days_match.group(1))

    weeks_match = re.search(r"(\d+)\s*weeks?", text_lower)
    if weeks_match:
        return int(weeks_match.group(1)) * 7

    return None


def _classify_duration(text: str) -> str:
    """Classify duration pattern from patient description."""
    text_lower = text.lower()

    if any(w in text_lower for w in ["worse", "worsening", "getting worse", "increasing"]):
        return "worsening"
    if any(w in text_lower for w in ["better", "improving", "getting better", "less"]):
        return "improving"
    if any(w in text_lower for w in ["comes and goes", "on and off", "intermittent", "sometimes"]):
        return "intermittent"
    if any(w in text_lower for w in ["constant", "all the time", "non-stop", "always"]):
        return "constant"
    return "stable"


def _extract_associated_symptoms(text: str) -> list[AssociatedSymptom]:
    """Extract associated symptoms from patient response."""
    symptoms = []
    text_lower = text.lower()

    # Common symptom keywords
    symptom_keywords = [
        "nausea", "vomiting", "dizziness", "fever", "chills",
        "fatigue", "weakness", "numbness", "tingling", "swelling",
        "redness", "bleeding", "vision changes", "hearing loss",
        "congestion", "cough", "shortness of breath",
    ]

    for keyword in symptom_keywords:
        if keyword in text_lower:
            symptoms.append(AssociatedSymptom(
                symptom=keyword,
                severity=None,
                confidence=0.75,
            ))

    # If patient said "no" or "none"
    if not symptoms and any(w in text_lower for w in ["no", "none", "nothing", "nope"]):
        return []

    return symptoms


def _extract_conditions(text: str, ehr_conditions: list[str]) -> list[str]:
    """Extract medical conditions from patient response."""
    text_lower = text.lower()

    # If patient confirms EHR data
    if any(w in text_lower for w in ["yes", "correct", "that's right", "still the same", "accurate"]):
        return ehr_conditions

    # If patient says no conditions
    if any(w in text_lower for w in ["no", "none", "nothing", "healthy"]):
        return []

    # Otherwise, try to extract mentioned conditions
    conditions = list(ehr_conditions)  # start with EHR

    common_conditions = [
        "diabetes", "hypertension", "high blood pressure", "asthma",
        "heart disease", "cancer", "arthritis", "depression", "anxiety",
        "copd", "thyroid", "kidney disease",
    ]

    for condition in common_conditions:
        if condition in text_lower and condition not in [c.lower() for c in conditions]:
            conditions.append(condition)

    return conditions


def _extract_medications(text: str, ehr_medications: list[str]) -> list[str]:
    """Extract medication list from patient response."""
    text_lower = text.lower()

    # Confirms EHR list
    if any(w in text_lower for w in ["yes", "correct", "that's right", "still the same", "accurate"]):
        return ehr_medications

    # No medications
    if any(w in text_lower for w in ["no", "none", "nothing", "not taking anything"]):
        return []

    # Start with EHR meds, add any new ones mentioned
    medications = list(ehr_medications)

    # Basic extraction — in production, would use NER or LLM
    # For MVP, this handles common patterns
    return medications if medications else [text.strip()]


def _extract_allergies(text: str) -> list[str]:
    """Extract allergies from patient response."""
    text_lower = text.lower()

    if any(w in text_lower for w in ["no", "none", "nkda", "no known", "nothing"]):
        return []

    # Split on common delimiters
    allergies = []
    parts = re.split(r"[,;]|\band\b", text)
    for part in parts:
        cleaned = part.strip()
        if cleaned and len(cleaned) > 1:
            allergies.append(cleaned)

    return allergies if allergies else [text.strip()]
