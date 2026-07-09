"""Rule-based pre-classifier and confidence calibration.

Handles deterministic scoring paths (red flags, severity extremes)
without invoking the LLM. Also provides confidence calibration math.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shared.models import (
    ClassificationMethod,
    StructuredSymptoms,
    UrgencyLevel,
    UrgencyResult,
)


@dataclass
class PreClassifierResult:
    """Result from the rule-based pre-classifier."""

    triggered: bool
    urgency_level: Optional[UrgencyLevel] = None
    confidence: float = 0.0
    rule_fired: str = ""
    reasoning: str = ""


@dataclass
class ConfidenceAdjustment:
    """A single penalty or boost to confidence."""

    reason: str
    amount: float  # negative = penalty, positive = boost


# History modifiers: condition + symptom → elevate urgency by 1 level
HISTORY_MODIFIERS: list[dict] = [
    {
        "id": "cardiac_chest_pain",
        "conditions": ["cardiac", "cad", "chf", "heart disease", "mi", "myocardial"],
        "symptoms": ["chest pain", "shortness of breath"],
        "description": "Cardiac history + chest pain/dyspnea",
    },
    {
        "id": "immunocompromised_fever",
        "conditions": ["hiv", "chemo", "transplant", "immunocompromised", "immunosuppressed"],
        "symptoms": ["fever"],
        "description": "Immunocompromised + fever",
    },
    {
        "id": "anticoagulant_bleeding",
        "conditions": ["warfarin", "rivaroxaban", "apixaban", "anticoagulant", "blood thinner"],
        "symptoms": ["bleeding", "head injury", "fall"],
        "description": "Anticoagulant therapy + bleeding/head injury",
    },
    {
        "id": "diabetes_confusion",
        "conditions": ["diabetes", "diabetic"],
        "symptoms": ["confusion", "altered mental", "disoriented"],
        "description": "Diabetes + altered mental status",
    },
    {
        "id": "elderly_fall_head",
        "conditions": [],  # age-based, checked separately
        "symptoms": ["fall", "head injury", "hit my head"],
        "description": "Age >65 + fall with head injury",
    },
    {
        "id": "pregnancy_abdominal",
        "conditions": ["pregnant", "pregnancy"],
        "symptoms": ["abdominal pain", "bleeding", "cramping"],
        "description": "Pregnancy + abdominal pain/bleeding",
    },
    {
        "id": "asthma_breathing",
        "conditions": ["asthma", "copd"],
        "symptoms": ["breathing difficulty", "can't breathe", "shortness of breath", "wheezing"],
        "description": "Asthma/COPD + breathing difficulty",
    },
]


def pre_classify(symptoms: StructuredSymptoms) -> PreClassifierResult:
    """Apply deterministic rules for clear-cut cases.

    Returns a definitive result for obvious cases (red flags, severity extremes),
    or an untriggered result for ambiguous cases that need LLM reasoning.
    """

    # Rule 1: Red flag detected → EMERGENCY
    if symptoms.red_flag_detected:
        return PreClassifierResult(
            triggered=True,
            urgency_level=UrgencyLevel.EMERGENCY,
            confidence=0.95,
            rule_fired="red_flag_detected",
            reasoning=f"Emergency red flag detected: {symptoms.red_flag_category}. Immediate escalation required.",
        )

    # Rule 2: Severity 10 → EMERGENCY (any complaint)
    if symptoms.severity and symptoms.severity.score == 10:
        return PreClassifierResult(
            triggered=True,
            urgency_level=UrgencyLevel.EMERGENCY,
            confidence=0.92,
            rule_fired="severity_10",
            reasoning="Maximum severity score (10/10) reported. Classifying as Emergency.",
        )

    # Rule 3: Severity 9 + acute onset + concerning complaint → EMERGENCY
    if (
        symptoms.severity
        and symptoms.severity.score >= 9
        and symptoms.primary_complaint
        and symptoms.primary_complaint.category in ["chest_pain", "respiratory", "neurological"]
    ):
        return PreClassifierResult(
            triggered=True,
            urgency_level=UrgencyLevel.EMERGENCY,
            confidence=0.90,
            rule_fired="severity_9_critical_category",
            reasoning=f"Severity 9+/10 with critical complaint category ({symptoms.primary_complaint.category}). Classifying as Emergency.",
        )

    # Rule 4: Severity 1-2 + chronic + stable/improving → ROUTINE
    if (
        symptoms.severity
        and symptoms.severity.score <= 2
        and symptoms.onset
        and symptoms.onset.days_ago_estimate is not None
        and symptoms.onset.days_ago_estimate > 7
        and symptoms.duration_pattern
        and symptoms.duration_pattern.type in ("stable", "improving")
        and not symptoms.associated_symptoms
    ):
        return PreClassifierResult(
            triggered=True,
            urgency_level=UrgencyLevel.ROUTINE,
            confidence=0.90,
            rule_fired="low_severity_chronic_stable",
            reasoning="Low severity (1-2/10), chronic onset (>7 days), stable/improving pattern, no associated symptoms. Classifying as Routine.",
        )

    # No rule fired — needs LLM reasoning
    return PreClassifierResult(triggered=False)


def check_history_modifiers(symptoms: StructuredSymptoms) -> list[str]:
    """Check for medical history + symptom combinations that elevate urgency.

    Returns list of modifier descriptions that matched.
    """
    matched: list[str] = []

    if not symptoms.medical_history or not symptoms.primary_complaint:
        return matched

    history_text = " ".join(symptoms.medical_history.conditions).lower()
    complaint_text = symptoms.primary_complaint.text.lower()

    # Also check medications for condition indicators (e.g., warfarin = anticoagulant)
    med_text = ""
    if symptoms.medications:
        med_text = " ".join(symptoms.medications.current).lower()

    combined_conditions = history_text + " " + med_text

    # Check associated symptoms too
    assoc_text = " ".join(s.symptom.lower() for s in symptoms.associated_symptoms)
    combined_symptoms = complaint_text + " " + assoc_text

    for modifier in HISTORY_MODIFIERS:
        # Skip age-based modifier (would need patient age, not available in MVP)
        if modifier["id"] == "elderly_fall_head":
            continue

        conditions_match = any(
            cond in combined_conditions for cond in modifier["conditions"]
        )
        symptoms_match = any(
            symp in combined_symptoms for symp in modifier["symptoms"]
        )

        if conditions_match and symptoms_match:
            matched.append(modifier["description"])

    return matched


def elevate_urgency(level: UrgencyLevel) -> UrgencyLevel:
    """Elevate urgency by one level. Cannot go past EMERGENCY."""
    elevation_map = {
        UrgencyLevel.ROUTINE: UrgencyLevel.STANDARD,
        UrgencyLevel.STANDARD: UrgencyLevel.URGENT,
        UrgencyLevel.URGENT: UrgencyLevel.EMERGENCY,
        UrgencyLevel.EMERGENCY: UrgencyLevel.EMERGENCY,
    }
    return elevation_map[level]


def calibrate_confidence(
    base_confidence: float,
    symptoms: StructuredSymptoms,
) -> tuple[float, list[ConfidenceAdjustment]]:
    """Apply penalties and boosts to the base confidence score.

    Returns (final_confidence, list_of_adjustments).
    """
    adjustments: list[ConfidenceAdjustment] = []

    # --- Penalties ---

    # Completeness penalties
    if symptoms.completeness_score < 0.5:
        adjustments.append(ConfidenceAdjustment("Completeness < 50%", -0.30))
    elif symptoms.completeness_score < 0.7:
        adjustments.append(ConfidenceAdjustment("Completeness < 70%", -0.15))

    # Primary complaint confidence
    if symptoms.primary_complaint and symptoms.primary_complaint.confidence < 0.8:
        adjustments.append(ConfidenceAdjustment("Primary complaint low confidence", -0.10))

    # Severity source penalty
    if symptoms.severity and symptoms.severity.source == "inferred":
        adjustments.append(ConfidenceAdjustment("Severity inferred (not explicit)", -0.10))

    # Individual field confidence penalties
    low_conf_fields = 0
    for field_name in ["onset", "duration_pattern"]:
        field_val = getattr(symptoms, field_name, None)
        if field_val and hasattr(field_val, "confidence") and field_val.confidence < 0.6:
            low_conf_fields += 1
    if low_conf_fields > 0:
        adjustments.append(
            ConfidenceAdjustment(f"{low_conf_fields} field(s) with low confidence", -0.05 * low_conf_fields)
        )

    # Fast-tracked penalty (less data collected)
    if symptoms.fast_tracked:
        adjustments.append(ConfidenceAdjustment("Fast-tracked assessment", -0.05))

    # --- Boosts ---

    # Red flag boost
    if symptoms.red_flag_detected:
        adjustments.append(ConfidenceAdjustment("Red flag detected (high certainty)", +0.10))

    # EHR data corroboration
    if symptoms.medical_history and symptoms.medical_history.source in ("ehr", "both"):
        adjustments.append(ConfidenceAdjustment("EHR data corroborates history", +0.05))

    # All mandatory fields high confidence
    mandatory_high = (
        symptoms.primary_complaint
        and symptoms.primary_complaint.confidence >= 0.9
        and symptoms.severity
        and symptoms.severity.confidence >= 0.9
        and symptoms.onset
        and symptoms.onset.confidence >= 0.9
    )
    if mandatory_high:
        adjustments.append(ConfidenceAdjustment("All mandatory fields high confidence", +0.05))

    # Calculate final
    total_adjustment = sum(adj.amount for adj in adjustments)
    final_confidence = max(0.1, min(0.99, base_confidence + total_adjustment))

    return final_confidence, adjustments
