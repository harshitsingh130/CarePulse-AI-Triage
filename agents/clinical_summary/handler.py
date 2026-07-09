"""Lambda handler for the Clinical Summary Agent.

Invoked by the Supervisor Agent (Step Functions) as the final agent
in the pipeline. Aggregates all outputs and generates the SOAP note.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from shared.config import config
from shared.db import update_session_field, write_audit_entry
from shared.models import (
    AuditEntry,
    AuditEventType,
    InteractionResult,
    NurseOverride,
    RoutingDecision,
    StructuredSymptoms,
    UrgencyResult,
)
from shared.phi_redaction import get_logger

from .agent import generate_patient_summary, generate_soap_note

logger = get_logger("clinical-summary", config.LOG_LEVEL)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for clinical summary generation.

    Event shape (from Step Functions):
    {
        "session_id": "uuid",
        "patient_id": "uuid",
        "structured_symptoms": { ... },
        "urgency_result": { ... },
        "interaction_result": { ... },
        "routing_decision": { ... },
        "nurse_override": { ... } (optional)
    }

    Returns:
    {
        "session_id": "uuid",
        "soap_generated": bool,
        "generation_time_ms": int,
        "flags": { ... },
        "patient_summary": { ... },
        "soap_note": { ... }
    }
    """
    session_id = event["session_id"]
    patient_id = event["patient_id"]

    logger.info("SOAP generation started", extra={"session_id": session_id})

    # Parse all inputs
    symptoms = StructuredSymptoms.model_validate(event["structured_symptoms"])
    urgency = UrgencyResult.model_validate(event["urgency_result"])
    interactions = InteractionResult.model_validate(event["interaction_result"])
    routing = RoutingDecision.model_validate(event["routing_decision"])

    nurse_override: Optional[NurseOverride] = None
    if event.get("nurse_override"):
        nurse_override = NurseOverride.model_validate(event["nurse_override"])

    # Generate SOAP note
    soap_note = generate_soap_note(
        session_id=UUID(session_id),
        patient_id=UUID(patient_id),
        symptoms=symptoms,
        urgency_result=urgency,
        interaction_result=interactions,
        routing_decision=routing,
        nurse_override=nurse_override,
    )

    # Generate patient-facing summary
    patient_summary = generate_patient_summary(soap_note, urgency, routing)

    # Persist to session
    soap_dict = json.loads(soap_note.model_dump_json())
    summary_dict = json.loads(patient_summary.model_dump_json())
    update_session_field(session_id, "soapNote", soap_dict)

    # Audit trail
    write_audit_entry(AuditEntry(
        patient_id=UUID(patient_id),
        timestamp=datetime.now(timezone.utc),
        event_type=AuditEventType.SOAP_GENERATED,
        session_id=UUID(session_id),
        actor_type="AI_AGENT",
        actor_id="clinical_summary",
        details={
            "generation_time_ms": soap_note.metadata.generation_time_ms,
            "validation_passed": soap_note.metadata.validation_passed,
            "fallback_used": soap_note.metadata.fallback_used,
            "flags": {
                "critical_interaction": soap_note.flags.critical_interaction,
                "nurse_override": soap_note.flags.nurse_override,
                "fast_tracked": soap_note.flags.fast_tracked,
                "incomplete_data": soap_note.flags.incomplete_data,
            },
        },
    ))

    logger.info(
        "SOAP generation complete",
        extra={
            "session_id": session_id,
            "time_ms": soap_note.metadata.generation_time_ms,
            "fallback": soap_note.metadata.fallback_used,
        },
    )

    return {
        "session_id": session_id,
        "soap_generated": True,
        "generation_time_ms": soap_note.metadata.generation_time_ms,
        "flags": json.loads(soap_note.flags.model_dump_json()),
        "patient_summary": summary_dict,
        "soap_note": soap_dict,
    }
