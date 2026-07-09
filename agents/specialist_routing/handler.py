"""Lambda handler for the Specialist Routing Agent.

Invoked by the Supervisor Agent (Step Functions) after drug interaction check.
Routes patient to appropriate specialist department.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.config import config
from shared.db import update_session_field, write_audit_entry
from shared.models import (
    AuditEntry,
    AuditEventType,
    StructuredSymptoms,
    UrgencyResult,
)
from shared.phi_redaction import get_logger

from .agent import route_patient

logger = get_logger("specialist-routing", config.LOG_LEVEL)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for specialist routing.

    Event shape (from Step Functions):
    {
        "session_id": "uuid",
        "patient_id": "uuid",
        "patient_clinic_id": "string",
        "structured_symptoms": { ... },
        "urgency_result": { ... }
    }

    Returns:
    {
        "session_id": "uuid",
        "department": "string",
        "status": "routed|no_availability|ambiguous_department",
        "has_slots": bool,
        "routing_decision": { ... }
    }
    """
    session_id = event["session_id"]
    patient_id = event["patient_id"]
    patient_clinic_id = event.get("patient_clinic_id", "clinic-01")

    logger.info("Routing started", extra={"session_id": session_id, "clinic": patient_clinic_id})

    # Parse inputs
    symptoms = StructuredSymptoms.model_validate(event["structured_symptoms"])
    urgency = UrgencyResult.model_validate(event["urgency_result"])

    # Route patient
    result = route_patient(
        session_id=UUID(session_id),
        patient_id=UUID(patient_id),
        symptoms=symptoms,
        urgency_result=urgency,
        patient_clinic_id=patient_clinic_id,
    )

    # Persist to session
    result_dict = json.loads(result.model_dump_json())
    update_session_field(session_id, "routingDecision", result_dict)

    # Audit trail
    write_audit_entry(AuditEntry(
        patient_id=UUID(patient_id),
        timestamp=datetime.now(timezone.utc),
        event_type=AuditEventType.ROUTING_DECIDED,
        session_id=UUID(session_id),
        actor_type="AI_AGENT",
        actor_id="specialist_routing",
        details={
            "department": result.department,
            "confidence": result.department_confidence,
            "method": result.routing_method.value,
            "status": result.status,
            "mental_health_priority": result.mental_health_priority,
            "alternatives_offered": len(result.alternatives),
        },
        reasoning=result.routing_reasoning,
    ))

    has_slots = (
        (result.primary_clinic and bool(result.primary_clinic.available_slots))
        or any(alt.available_slots for alt in result.alternatives)
    )

    logger.info(
        "Routing complete",
        extra={
            "session_id": session_id,
            "department": result.department,
            "status": result.status,
            "has_slots": has_slots,
        },
    )

    return {
        "session_id": session_id,
        "department": result.department,
        "status": result.status,
        "has_slots": has_slots,
        "routing_decision": result_dict,
    }
