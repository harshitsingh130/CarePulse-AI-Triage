"""Lambda handler for the Drug Interaction Agent.

Invoked by the Supervisor Agent (Step Functions) after triage scoring.
Receives patient medication data, returns interaction check results.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.config import config
from shared.db import update_session_field, write_audit_entry
from shared.models import AuditEntry, AuditEventType
from shared.phi_redaction import get_logger

from .agent import check_interactions

logger = get_logger("drug-interaction", config.LOG_LEVEL)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for drug interaction checking.

    Event shape (from Step Functions):
    {
        "session_id": "uuid",
        "patient_id": "uuid",
        "patient_ehr_id": "string" (optional — null if unauthenticated),
        "reported_medications": ["string"] (from StructuredSymptoms)
    }

    Returns:
    {
        "session_id": "uuid",
        "check_status": "complete|partial|unavailable",
        "critical_count": int,
        "moderate_count": int,
        "requires_physician_alert": bool,
        "interaction_result": { ... }  (full InteractionResult JSON)
    }
    """
    session_id = event["session_id"]
    patient_id = event["patient_id"]
    patient_ehr_id = event.get("patient_ehr_id")
    reported_medications = event.get("reported_medications", [])

    logger.info(
        "Drug interaction check started",
        extra={
            "session_id": session_id,
            "has_ehr_id": patient_ehr_id is not None,
            "reported_med_count": len(reported_medications),
        },
    )

    # Run interaction check
    result = check_interactions(
        session_id=UUID(session_id),
        patient_id=UUID(patient_id),
        patient_ehr_id=patient_ehr_id,
        reported_medications=reported_medications,
    )

    # Persist result to session
    result_dict = json.loads(result.model_dump_json())
    update_session_field(session_id, "interactionResult", result_dict)

    # Write audit entry
    write_audit_entry(AuditEntry(
        patient_id=UUID(patient_id),
        timestamp=datetime.now(timezone.utc),
        event_type=AuditEventType.DRUG_CHECK_PERFORMED,
        session_id=UUID(session_id),
        actor_type="AI_AGENT",
        actor_id="drug_interaction",
        details={
            "check_status": result.check_status.value,
            "medications_checked_count": len(result.medications_checked),
            "interactions_found_count": len(result.interactions_found),
            "critical_count": result.critical_count,
            "moderate_count": result.moderate_count,
            "requires_physician_alert": result.requires_physician_alert,
        },
    ))

    logger.info(
        "Drug interaction check complete",
        extra={
            "session_id": session_id,
            "status": result.check_status.value,
            "critical": result.critical_count,
            "alert": result.requires_physician_alert,
        },
    )

    return {
        "session_id": session_id,
        "check_status": result.check_status.value,
        "critical_count": result.critical_count,
        "moderate_count": result.moderate_count,
        "requires_physician_alert": result.requires_physician_alert,
        "interaction_result": result_dict,
    }
