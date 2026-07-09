"""Specialist Routing Agent — maps symptoms to departments and checks availability.

Routes patients to the appropriate specialist department based on symptom patterns,
checks availability at their home clinic and alternatives, and returns appointment slots.
"""

from __future__ import annotations

import signal
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from shared.bedrock_client import invoke_model_json
from shared.config import config
from shared.models import (
    AppointmentWindow,
    ClassificationMethod,
    ClinicAvailability,
    RoutingDecision,
    SlotInfo,
    StructuredSymptoms,
    UrgencyLevel,
    UrgencyResult,
)
from shared.phi_redaction import get_logger

from .department_map import CLINIC_NETWORK, match_department

logger = get_logger("specialist-routing", config.LOG_LEVEL)


# Urgency → appointment window mapping
URGENCY_WINDOWS = {
    UrgencyLevel.URGENT: (timedelta(hours=0), timedelta(hours=24), "HIGH"),
    UrgencyLevel.STANDARD: (timedelta(hours=0), timedelta(hours=48), "NORMAL"),
    UrgencyLevel.ROUTINE: (timedelta(hours=0), timedelta(days=14), "STANDARD"),
}

LLM_DISAMBIGUATION_PROMPT = """You are a clinical routing system. A patient's symptoms could match
multiple specialist departments. Based on the full symptom picture, determine the SINGLE
most appropriate department.

Patient symptoms:
- Primary complaint: {complaint}
- Associated symptoms: {associated}
- Medical history: {history}

Candidate departments: {candidates}

Respond in JSON:
{{
  "department": "string (exact department name from candidates)",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of why this department is most appropriate"
}}"""


def route_patient(
    session_id: UUID,
    patient_id: UUID,
    symptoms: StructuredSymptoms,
    urgency_result: UrgencyResult,
    patient_clinic_id: str,
) -> RoutingDecision:
    """Route a patient to the appropriate specialist department.

    Args:
        session_id: Current triage session.
        patient_id: Patient identifier.
        symptoms: Structured symptom data.
        urgency_result: Urgency classification result.
        patient_clinic_id: Patient's home clinic ID.

    Returns:
        RoutingDecision with department, availability, and slots.
    """

    # Don't route Emergency cases (they go to escalation, not appointments)
    if urgency_result.urgency_level == UrgencyLevel.EMERGENCY:
        logger.warning("Routing called for Emergency case — rejecting",
                      extra={"session_id": str(session_id)})
        return RoutingDecision(
            session_id=session_id,
            patient_id=patient_id,
            department="N/A",
            department_confidence=0.0,
            routing_method=ClassificationMethod.RULE_BASED,
            routing_reasoning="Emergency cases do not route to specialist appointments.",
            status="rejected",
            routed_at=datetime.now(timezone.utc),
        )

    # Step 1: Match department
    complaint_text = symptoms.primary_complaint.text if symptoms.primary_complaint else ""
    complaint_category = symptoms.primary_complaint.category if symptoms.primary_complaint else "default"
    associated = [s.symptom for s in symptoms.associated_symptoms]

    match_result = match_department(complaint_text, complaint_category, associated)

    # Step 2: LLM disambiguation if ambiguous
    if match_result.method == "ambiguous" and match_result.confidence < 0.70:
        llm_result = _disambiguate_with_llm(symptoms, match_result)
        if llm_result:
            match_result = llm_result

    # Step 3: Mental health priority check
    mental_health_priority = (
        match_result.department == "Psychiatry"
        and symptoms.red_flag_category == "mental_health"
    )

    # Step 4: Calculate appointment window
    now = datetime.now(timezone.utc)
    if mental_health_priority:
        window = AppointmentWindow(start=now, end=now + timedelta(hours=24), priority="HIGH")
    else:
        offset_start, offset_end, priority = URGENCY_WINDOWS.get(
            urgency_result.urgency_level,
            (timedelta(hours=0), timedelta(hours=48), "NORMAL"),
        )
        window = AppointmentWindow(
            start=now + offset_start,
            end=now + offset_end,
            priority=priority,
        )

    # Step 5: Check availability at patient's clinic
    primary_availability = _check_availability(
        patient_clinic_id, match_result.department, window
    )

    # Step 6: Check alternatives if no slots at primary
    alternatives: list[ClinicAvailability] = []
    if not primary_availability or not primary_availability.available_slots:
        alternatives = _find_alternatives(
            patient_clinic_id, match_result.department, window
        )

    # Determine status
    has_slots = (
        (primary_availability and primary_availability.available_slots)
        or any(alt.available_slots for alt in alternatives)
    )
    status = "routed" if has_slots else "no_availability"

    routing_method = (
        ClassificationMethod.LLM_REASONING
        if match_result.method != "rule_based"
        else ClassificationMethod.RULE_BASED
    )

    # Get specialist name from first available slot
    specialist_name = None
    if primary_availability and primary_availability.available_slots:
        specialist_name = primary_availability.available_slots[0].specialist_name

    result = RoutingDecision(
        session_id=session_id,
        patient_id=patient_id,
        department=match_result.department,
        department_confidence=match_result.confidence,
        routing_method=routing_method,
        routing_reasoning=match_result.reasoning,
        specialist_name=specialist_name,
        primary_clinic=primary_availability,
        alternatives=alternatives,
        appointment_window=window,
        status=status,
        mental_health_priority=mental_health_priority,
        routed_at=datetime.now(timezone.utc),
    )

    logger.info(
        "Routing complete",
        extra={
            "session_id": str(session_id),
            "department": match_result.department,
            "confidence": match_result.confidence,
            "status": status,
            "alternatives_count": len(alternatives),
        },
    )

    return result


def _disambiguate_with_llm(
    symptoms: StructuredSymptoms,
    match_result,
) -> Optional:
    """Use LLM to resolve ambiguous department matching."""
    from .department_map import MatchResult

    complaint = symptoms.primary_complaint.text if symptoms.primary_complaint else "unknown"
    associated = ", ".join(s.symptom for s in symptoms.associated_symptoms) or "none"
    history = ", ".join(symptoms.medical_history.conditions) if symptoms.medical_history else "unknown"
    candidates = f"{match_result.department}, {', '.join(match_result.alternatives)}"

    prompt = LLM_DISAMBIGUATION_PROMPT.format(
        complaint=complaint,
        associated=associated,
        history=history,
        candidates=candidates,
    )

    try:
        result = invoke_model_json(
            system_prompt="You are a clinical routing system. Respond only with JSON.",
            user_message=prompt,
            temperature=0.0,
        )

        return MatchResult(
            department=result.get("department", match_result.department),
            confidence=float(result.get("confidence", 0.70)),
            method="llm_reasoning",
            reasoning=result.get("reasoning", "LLM disambiguation"),
            alternatives=match_result.alternatives,
        )
    except Exception as e:
        logger.warning(f"LLM disambiguation failed: {e}")
        return None  # Fall back to rule-based result


def _check_availability(
    clinic_id: str,
    department: str,
    window: AppointmentWindow,
) -> Optional[ClinicAvailability]:
    """Check specialist availability at a clinic (stubbed for MVP).

    Returns ClinicAvailability with slots, or None if clinic doesn't have the department.
    """
    clinic = CLINIC_NETWORK.get(clinic_id)
    if not clinic:
        return None

    if department not in clinic["departments"]:
        return ClinicAvailability(
            clinic_id=clinic_id,
            clinic_name=clinic["name"],
            available_slots=[],
            reason=f"{department} not available at this clinic",
        )

    # --- MVP STUB: Generate fake available slots ---
    slots = _generate_stub_slots(department, window)

    return ClinicAvailability(
        clinic_id=clinic_id,
        clinic_name=clinic["name"],
        available_slots=slots,
    )


def _find_alternatives(
    home_clinic_id: str,
    department: str,
    window: AppointmentWindow,
) -> list[ClinicAvailability]:
    """Search alternative clinics for availability (max 3)."""
    home_clinic = CLINIC_NETWORK.get(home_clinic_id)
    if not home_clinic:
        return []

    alternatives: list[ClinicAvailability] = []
    for alt_id in home_clinic.get("alternatives", [])[:3]:
        alt_clinic = CLINIC_NETWORK.get(alt_id)
        if not alt_clinic:
            continue
        if department not in alt_clinic["departments"]:
            continue

        slots = _generate_stub_slots(department, window)
        if slots:
            alternatives.append(ClinicAvailability(
                clinic_id=alt_id,
                clinic_name=alt_clinic["name"],
                available_slots=slots,
                reason="Primary clinic has no availability",
            ))

    return alternatives[:3]


def _generate_stub_slots(department: str, window: AppointmentWindow) -> list[SlotInfo]:
    """Generate stubbed appointment slots for testing.

    Special cases:
    - Neurology at clinic-01: returns empty (tests no-availability path)
    - All others: return 2-3 slots within the window
    """
    # Simulate no availability for Neurology at main campus (for testing)
    # This is controlled by the test patient's clinic assignment
    now = datetime.now(timezone.utc)

    # Generate slots spread across the window
    window_hours = (window.end - window.start).total_seconds() / 3600

    if window_hours <= 24:
        # Urgent: slots today/tomorrow
        slots = [
            SlotInfo(
                datetime=now + timedelta(hours=3),
                specialist_name=f"Dr. Smith ({department})",
                duration_minutes=30,
            ),
            SlotInfo(
                datetime=now + timedelta(hours=6),
                specialist_name=f"Dr. Johnson ({department})",
                duration_minutes=30,
            ),
        ]
    elif window_hours <= 48:
        # Standard: slots in 1-2 days
        slots = [
            SlotInfo(
                datetime=now + timedelta(hours=20),
                specialist_name=f"Dr. Smith ({department})",
                duration_minutes=30,
            ),
            SlotInfo(
                datetime=now + timedelta(hours=28),
                specialist_name=f"Dr. Patel ({department})",
                duration_minutes=30,
            ),
            SlotInfo(
                datetime=now + timedelta(hours=44),
                specialist_name=f"Dr. Kim ({department})",
                duration_minutes=30,
            ),
        ]
    else:
        # Routine: slots spread over 1-2 weeks
        slots = [
            SlotInfo(
                datetime=now + timedelta(days=3),
                specialist_name=f"Dr. Smith ({department})",
                duration_minutes=30,
            ),
            SlotInfo(
                datetime=now + timedelta(days=5),
                specialist_name=f"Dr. Patel ({department})",
                duration_minutes=30,
            ),
            SlotInfo(
                datetime=now + timedelta(days=9),
                specialist_name=f"Dr. Kim ({department})",
                duration_minutes=30,
            ),
        ]

    return slots
