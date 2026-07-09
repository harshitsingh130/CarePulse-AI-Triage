"""Decision logic lambdas for Step Functions orchestration.

Contains: InitSession, SendAndWait, CompleteSession, NurseHandoffTrigger,
WaitForNurse, ProcessNurseDecision.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import boto3

from shared.config import config
from shared.db import (
    create_session,
    get_session,
    update_session_field,
    update_session_status,
    write_audit_entry,
)
from shared.models import (
    AuditEntry,
    AuditEventType,
    NurseOverride,
    SessionStatus,
    TriageSession,
    UrgencyLevel,
)
from shared.phi_redaction import get_logger

logger = get_logger("decision-logic", config.LOG_LEVEL)
_apigw_client = None  # Lazy init for WebSocket management API


def _get_apigw_client():
    global _apigw_client
    if _apigw_client is None:
        _apigw_client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=config.WEBSOCKET_API_ENDPOINT,
        )
    return _apigw_client


def _send_to_patient(connection_id: str, message: dict) -> bool:
    """Send a message to the patient via WebSocket."""
    try:
        client = _get_apigw_client()
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message).encode("utf-8"),
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to send to patient: {e}", extra={"connection_id": connection_id})
        return False


# --- Init Session ---

def init_session_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Initialize a new triage session."""
    session_id = event.get("session_id", str(uuid4()))
    patient_id = event["patient_id"]
    clinic_id = event.get("patient_clinic_id", "clinic-01")
    connection_id = event.get("connection_id")

    logger.info("Initializing session", extra={"session_id": session_id})

    # Create session record
    session = TriageSession(
        session_id=UUID(session_id),
        patient_id=UUID(patient_id),
        status=SessionStatus.IN_PROGRESS,
        clinic_id=clinic_id,
        connection_id=connection_id,
        started_at=datetime.now(timezone.utc),
    )
    create_session(session)

    # Audit
    write_audit_entry(AuditEntry(
        patient_id=UUID(patient_id),
        timestamp=datetime.now(timezone.utc),
        event_type=AuditEventType.TRIAGE_STARTED,
        session_id=UUID(session_id),
        actor_type="PATIENT",
        actor_id=patient_id,
        details={"clinic_id": clinic_id},
    ))

    # Load EHR data if patient is authenticated (stubbed)
    ehr_medications: list[str] = []
    ehr_conditions: list[str] = []
    patient_ehr_id = None
    # In production: look up patient → get ehrPatientId → fetch from EHR

    return {
        "session_id": session_id,
        "patient_id": patient_id,
        "patient_ehr_id": patient_ehr_id,
        "ehr_medications": ehr_medications,
        "ehr_conditions": ehr_conditions,
    }


# --- Send Response and Wait for Patient ---

def send_and_wait_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Send AI response to patient via WebSocket and store task token for callback."""
    session_id = event["session_id"]
    connection_id = event["connection_id"]
    ai_response = event["ai_response"]
    task_token = event.get("task_token")
    emergency_alert = event.get("emergency_alert", False)
    no_wait = event.get("no_wait", False)

    # Build message payload
    message = {
        "type": "emergency" if emergency_alert else "message",
        "role": "ai",
        "content": ai_response,
    }

    if event.get("show_severity_slider"):
        message["type"] = "ui_component"
        message["component"] = "severity_slider"
        message["content"] = ai_response

    if emergency_alert:
        message["offer_transfer"] = True

    # Send to patient
    _send_to_patient(connection_id, message)

    # Store task token for callback (patient's next message will resume execution)
    if task_token and not no_wait:
        update_session_field(session_id, "taskToken", task_token)

    return {"sent": True}


# --- Complete Session ---

def complete_session_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Finalize the triage session."""
    session_id = event["session_id"]
    patient_id = event["patient_id"]
    connection_id = event.get("connection_id")
    timeout = event.get("timeout", False)

    if timeout:
        update_session_status(session_id, SessionStatus.PAUSED)
        logger.info("Session timed out", extra={"session_id": session_id})
        return {"status": "paused", "reason": "timeout"}

    # Mark complete
    update_session_status(
        session_id,
        SessionStatus.COMPLETED,
        completedAt=datetime.now(timezone.utc).isoformat(),
    )

    # Send completion message to patient
    if connection_id:
        patient_summary = event.get("patient_summary", {})
        _send_to_patient(connection_id, {
            "type": "complete",
            "summary": patient_summary,
            "urgency_level": event.get("urgency_level"),
            "department": event.get("department"),
        })

    logger.info("Session completed", extra={"session_id": session_id})

    return {
        "status": "completed",
        "session_id": session_id,
    }


# --- Nurse Handoff Trigger ---

def nurse_handoff_trigger_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Trigger the Standard workflow for nurse handoff."""
    session_id = event["session_id"]
    patient_id = event["patient_id"]
    connection_id = event.get("connection_id")

    logger.info("Triggering nurse handoff", extra={"session_id": session_id})

    # Update session status
    update_session_status(session_id, SessionStatus.AWAITING_NURSE)

    # Notify patient
    if connection_id:
        _send_to_patient(connection_id, {
            "type": "status",
            "status": "AWAITING_NURSE",
            "content": "I want to make sure we get this right — I'm connecting you with a nurse for a quick review.",
        })

    # Start Standard workflow (done by CDK — Step Functions starts child execution)
    # The Express workflow ends here; the ASL triggers the Standard workflow
    return {
        "handoff_triggered": True,
        "session_id": session_id,
    }


# --- Wait For Nurse (stores task token for nurse callback) ---

def wait_for_nurse_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Store task token for nurse dashboard callback."""
    session_id = event["session_id"]
    task_token = event.get("task_token")

    # Store nurse task token (different from patient chat token)
    update_session_field(session_id, "nurseTaskToken", task_token)

    logger.info("Waiting for nurse response", extra={"session_id": session_id})
    return {"waiting": True}


# --- Process Nurse Decision ---

def process_nurse_decision_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process the nurse's urgency classification override."""
    session_id = event["session_id"]
    patient_id = event["patient_id"]
    nurse_urgency = event["nurse_urgency"]
    nurse_id = event.get("nurse_id", "unknown")
    nurse_reason = event.get("nurse_reason", "")
    original_urgency = event.get("original_urgency", "STANDARD")
    timeout = event.get("timeout", False)

    logger.info(
        "Nurse decision received",
        extra={
            "session_id": session_id,
            "nurse_urgency": nurse_urgency,
            "timeout": timeout,
        },
    )

    # Build nurse override
    override = NurseOverride(
        original_urgency=UrgencyLevel(original_urgency),
        override_urgency=UrgencyLevel(nurse_urgency),
        nurse_id=nurse_id,
        reason=nurse_reason,
        overridden_at=datetime.now(timezone.utc),
    )

    # Persist override
    update_session_field(session_id, "nurseOverride", json.loads(override.model_dump_json()))
    update_session_status(session_id, SessionStatus.IN_PROGRESS)

    # Audit
    write_audit_entry(AuditEntry(
        patient_id=UUID(patient_id),
        timestamp=datetime.now(timezone.utc),
        event_type=AuditEventType.NURSE_OVERRIDE,
        session_id=UUID(session_id),
        actor_type="NURSE" if not timeout else "SYSTEM",
        actor_id=nurse_id,
        details={
            "original_urgency": original_urgency,
            "override_urgency": nurse_urgency,
            "timeout": timeout,
        },
        reasoning=nurse_reason,
    ))

    # Build updated urgency result for pipeline resumption
    updated_urgency_result = {
        "session_id": session_id,
        "urgency_level": nurse_urgency,
        "confidence_score": 0.90 if not timeout else 0.65,
        "classification_method": "hybrid",
        "reasoning": f"Nurse override: {nurse_reason}" if not timeout else "System timeout — defaulted to URGENT",
        "risk_factors": [],
        "recommended_timeframe": "within 4 hours" if nurse_urgency == "URGENT" else "within 48 hours",
        "modifiers_applied": [],
        "data_quality_penalties": [],
        "requires_nurse_review": False,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "session_id": session_id,
        "updated_urgency_result": updated_urgency_result,
        "nurse_override": json.loads(override.model_dump_json()),
    }
