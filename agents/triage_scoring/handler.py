"""Lambda handler for the Triage Scoring Agent.

Invoked by the Supervisor Agent (Step Functions) after symptom assessment
completes. Receives StructuredSymptoms, returns UrgencyResult.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.config import config
from shared.db import update_session_field, write_audit_entry
from shared.models import AuditEntry, AuditEventType, StructuredSymptoms
from shared.phi_redaction import get_logger

from .agent import score_urgency

logger = get_logger("triage-scoring", config.LOG_LEVEL)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for triage scoring.

    Event shape (from Step Functions):
    {
        "session_id": "uuid",
        "patient_id": "uuid",
        "structured_symptoms": { ... }  (StructuredSymptoms JSON)
    }

    Returns:
    {
        "session_id": "uuid",
        "urgency_level": "EMERGENCY|URGENT|STANDARD|ROUTINE",
        "confidence_score": float,
        "requires_nurse_review": bool,
        "urgency_result": { ... }  (full UrgencyResult JSON)
    }
    """
    session_id = event["session_id"]
    patient_id = event["patient_id"]
    symptoms_data = event["structured_symptoms"]

    logger.info("Scoring started", extra={"session_id": session_id})

    # Parse structured symptoms
    symptoms = StructuredSymptoms.model_validate(symptoms_data)

    # Score urgency
    result = score_urgency(symptoms)

    # Persist result to session
    result_dict = json.loads(result.model_dump_json())
    update_session_field(session_id, "urgencyResult", result_dict)
    update_session_field(session_id, "urgencyLevel", result.urgency_level.value)
    update_session_field(session_id, "confidenceScore", result.confidence_score)

    # Write audit entry
    write_audit_entry(AuditEntry(
        patient_id=UUID(patient_id),
        timestamp=datetime.now(timezone.utc),
        event_type=AuditEventType.URGENCY_ASSIGNED,
        session_id=UUID(session_id),
        actor_type="AI_AGENT",
        actor_id="triage_scoring",
        details={
            "urgency_level": result.urgency_level.value,
            "confidence_score": result.confidence_score,
            "classification_method": result.classification_method.value,
            "modifiers_applied": result.modifiers_applied,
            "requires_nurse_review": result.requires_nurse_review,
        },
        reasoning=result.reasoning,
    ))

    logger.info(
        "Scoring complete",
        extra={
            "session_id": session_id,
            "urgency": result.urgency_level.value,
            "confidence": result.confidence_score,
            "method": result.classification_method.value,
            "nurse_review": result.requires_nurse_review,
        },
    )

    return {
        "session_id": session_id,
        "urgency_level": result.urgency_level.value,
        "confidence_score": result.confidence_score,
        "requires_nurse_review": result.requires_nurse_review,
        "urgency_result": result_dict,
    }
