"""Lambda handler for the Symptom Assessment Agent.

Invoked by the Supervisor Agent (Step Functions) for each turn of the
patient conversation. Receives patient message, processes it through
the agent, returns AI response + updated state.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from shared.config import config
from shared.db import (
    get_conversation,
    get_session,
    update_session_field,
    write_audit_entry,
    write_conversation_message,
)
from shared.models import AuditEntry, AuditEventType, ConversationRole
from shared.phi_redaction import get_logger

from .agent import ConversationPhase, ConversationState, process_message
from .prompts import GREETING_MESSAGE

logger = get_logger("symptom-assessment", config.LOG_LEVEL)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for symptom assessment.

    Event shape (from Step Functions):
    {
        "session_id": "uuid",
        "patient_id": "uuid",
        "patient_message": "string" (null on first invocation),
        "ehr_medications": ["string"] (optional),
        "ehr_conditions": ["string"] (optional),
        "conversation_state": {...} (null on first invocation)
    }

    Returns:
    {
        "ai_response": "string",
        "assessment_complete": bool,
        "structured_symptoms": {...} (only when complete),
        "conversation_state": {...} (serialized for next invocation),
        "show_severity_slider": bool
    }
    """
    session_id = event["session_id"]
    patient_id = event["patient_id"]
    patient_message = event.get("patient_message")
    ehr_medications = event.get("ehr_medications", [])
    ehr_conditions = event.get("ehr_conditions", [])
    serialized_state = event.get("conversation_state")

    logger.info(
        "Processing turn",
        extra={"session_id": session_id, "has_message": patient_message is not None},
    )

    # Restore or create conversation state
    if serialized_state:
        state = _deserialize_state(serialized_state, session_id, patient_id)
    else:
        state = ConversationState(
            session_id=UUID(session_id),
            patient_id=UUID(patient_id),
            ehr_medications=ehr_medications,
            ehr_conditions=ehr_conditions,
        )

    # First turn: send greeting (no patient message yet)
    if patient_message is None:
        ai_response = GREETING_MESSAGE
        state.conversation_history.append({"role": "ai", "content": ai_response})

        # Log greeting
        write_conversation_message(
            session_id=session_id,
            role=ConversationRole.AI_AGENT.value,
            content=ai_response,
            agent_name="symptom_assessment",
        )

        return {
            "ai_response": ai_response,
            "assessment_complete": False,
            "structured_symptoms": None,
            "conversation_state": _serialize_state(state),
            "show_severity_slider": False,
        }

    # Log patient message
    write_conversation_message(
        session_id=session_id,
        role=ConversationRole.PATIENT.value,
        content=patient_message,
    )

    # Process message through agent
    import asyncio
    ai_response, state = asyncio.get_event_loop().run_until_complete(
        process_message(state, patient_message)
    )

    # Log AI response
    write_conversation_message(
        session_id=session_id,
        role=ConversationRole.AI_AGENT.value,
        content=ai_response,
        agent_name="symptom_assessment",
        metadata={"phase": state.phase.value, "turn": state.turn_count},
    )

    # Build response
    result: dict[str, Any] = {
        "ai_response": ai_response,
        "assessment_complete": state.symptoms.assessment_complete,
        "conversation_state": _serialize_state(state),
        "show_severity_slider": state.phase == ConversationPhase.SEVERITY,
    }

    if state.symptoms.assessment_complete:
        # Output the structured symptoms for the Triage Scoring Agent
        result["structured_symptoms"] = json.loads(state.symptoms.model_dump_json())

        # Update session with structured symptoms
        update_session_field(
            session_id, "structuredSymptoms", result["structured_symptoms"]
        )

        # Audit entry
        write_audit_entry(AuditEntry(
            patient_id=UUID(patient_id),
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.TRIAGE_STARTED,
            session_id=UUID(session_id),
            actor_type="AI_AGENT",
            actor_id="symptom_assessment",
            details={
                "completeness_score": state.completeness_score,
                "turns": state.turn_count,
                "red_flag": state.symptoms.red_flag_detected,
                "fast_tracked": state.symptoms.fast_tracked,
            },
        ))

        logger.info(
            "Assessment complete",
            extra={
                "session_id": session_id,
                "turns": state.turn_count,
                "completeness": state.completeness_score,
                "red_flag": state.symptoms.red_flag_detected,
            },
        )

    return result


def _serialize_state(state: ConversationState) -> dict:
    """Serialize conversation state for Step Functions pass-through."""
    return {
        "phase": state.phase.value,
        "turn_count": state.turn_count,
        "symptoms_json": state.symptoms.model_dump_json(),
        "ehr_medications": state.ehr_medications,
        "ehr_conditions": state.ehr_conditions,
        "ehr_data_available": state.ehr_data_available,
        "conversation_history": state.conversation_history[-20:],  # Keep last 20 turns
        "pending_clarifications": state.pending_clarifications,
    }


def _deserialize_state(
    data: dict, session_id: str, patient_id: str
) -> ConversationState:
    """Restore conversation state from serialized form."""
    from shared.models import StructuredSymptoms

    state = ConversationState(
        session_id=UUID(session_id),
        patient_id=UUID(patient_id),
        ehr_medications=data.get("ehr_medications", []),
        ehr_conditions=data.get("ehr_conditions", []),
    )
    state.phase = ConversationPhase(data["phase"])
    state.turn_count = data.get("turn_count", 0)
    state.conversation_history = data.get("conversation_history", [])
    state.pending_clarifications = data.get("pending_clarifications", [])

    if data.get("symptoms_json"):
        state.symptoms = StructuredSymptoms.model_validate_json(data["symptoms_json"])

    return state
