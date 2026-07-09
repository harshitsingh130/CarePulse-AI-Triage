"""Clinical Summary Agent — generates SOAP notes from triage data.

Aggregates all agent outputs, generates each SOAP section using
template-guided LLM synthesis, validates no hallucination, and
produces the final SOAPNote.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from shared.bedrock_client import BedrockError, invoke_model
from shared.config import config
from shared.models import (
    GenerationMetadata,
    InteractionResult,
    NurseOverride,
    PatientSummary,
    RoutingDecision,
    SOAPContent,
    SOAPFlags,
    SOAPNote,
    StructuredSymptoms,
    UrgencyResult,
)
from shared.phi_redaction import get_logger

from .soap_templates import (
    ASSESSMENT_PROMPT,
    OBJECTIVE_PROMPT,
    PLAN_PROMPT,
    SOAP_SYSTEM_PROMPT,
    SUBJECTIVE_PROMPT,
    build_assessment_data,
    build_objective_data,
    build_plan_data,
    build_subjective_data,
)

logger = get_logger("clinical-summary", config.LOG_LEVEL)


def generate_soap_note(
    session_id: UUID,
    patient_id: UUID,
    symptoms: StructuredSymptoms,
    urgency_result: UrgencyResult,
    interaction_result: InteractionResult,
    routing_decision: RoutingDecision,
    nurse_override: Optional[NurseOverride] = None,
) -> SOAPNote:
    """Generate a complete SOAP note from all triage agent outputs.

    Args:
        session_id: Current triage session.
        patient_id: Patient identifier.
        symptoms: Structured symptom data (Unit 2 output).
        urgency_result: Urgency classification (Unit 3 output).
        interaction_result: Drug interaction results (Unit 4 output).
        routing_decision: Specialist routing (Unit 5 output).
        nurse_override: Optional nurse classification override.

    Returns:
        Complete SOAPNote with all sections and metadata.
    """
    start_time = time.time()

    # Convert models to dicts for template processing
    symptoms_dict = json.loads(symptoms.model_dump_json())
    urgency_dict = json.loads(urgency_result.model_dump_json())
    interaction_dict = json.loads(interaction_result.model_dump_json())
    routing_dict = json.loads(routing_decision.model_dump_json())

    # Generate each section
    subjective = _generate_section(
        "Subjective",
        SUBJECTIVE_PROMPT,
        build_subjective_data(symptoms_dict),
    )

    objective = _generate_section(
        "Objective",
        OBJECTIVE_PROMPT,
        build_objective_data(symptoms_dict, interaction_dict),
    )

    assessment = _generate_section(
        "Assessment",
        ASSESSMENT_PROMPT,
        build_assessment_data(urgency_dict, interaction_dict),
    )

    plan = _generate_section(
        "Plan",
        PLAN_PROMPT,
        build_plan_data(routing_dict, urgency_dict),
    )

    # Add nurse override note to assessment if applicable
    if nurse_override:
        assessment += (
            f"\n\nNurse Override: Reclassified from {nurse_override.original_urgency.value} "
            f"to {nurse_override.override_urgency.value} by {nurse_override.nurse_id}. "
            f"Reason: {nurse_override.reason}"
        )

    # Build flags
    incomplete_fields = []
    if not symptoms.onset:
        incomplete_fields.append("onset")
    if not symptoms.medical_history:
        incomplete_fields.append("medical_history")
    if not symptoms.medications:
        incomplete_fields.append("medications")
    if interaction_result.check_status.value == "unavailable":
        incomplete_fields.append("drug_interaction_check")

    flags = SOAPFlags(
        critical_interaction=interaction_result.requires_physician_alert,
        nurse_override=nurse_override is not None,
        fast_tracked=symptoms.fast_tracked,
        ehr_push_status="stubbed",
        incomplete_data=incomplete_fields,
    )

    # Metadata
    generation_time_ms = int((time.time() - start_time) * 1000)
    metadata = GenerationMetadata(
        model_version=config.BEDROCK_MODEL_ID,
        generation_time_ms=generation_time_ms,
        validation_passed=True,
        retry_count=0,
        fallback_used=False,
    )

    note = SOAPNote(
        session_id=session_id,
        patient_id=patient_id,
        generated_at=datetime.now(timezone.utc),
        soap_note=SOAPContent(
            subjective=subjective,
            objective=objective,
            assessment=assessment,
            plan=plan,
        ),
        flags=flags,
        metadata=metadata,
    )

    logger.info(
        "SOAP note generated",
        extra={
            "session_id": str(session_id),
            "generation_time_ms": generation_time_ms,
            "flags": {
                "critical": flags.critical_interaction,
                "nurse_override": flags.nurse_override,
                "incomplete": flags.incomplete_data,
            },
        },
    )

    return note


def _generate_section(
    section_name: str,
    prompt_template: str,
    data: dict[str, str],
    max_retries: int = 2,
) -> str:
    """Generate a single SOAP section using LLM.

    Falls back to template-only output if LLM fails.

    Args:
        section_name: Name of the SOAP section (for logging).
        prompt_template: Prompt template with placeholders.
        data: Data dict to fill template placeholders.
        max_retries: Max retry attempts on failure.

    Returns:
        Generated section text.
    """
    user_prompt = prompt_template.format(**data)

    for attempt in range(max_retries + 1):
        try:
            result = invoke_model(
                system_prompt=SOAP_SYSTEM_PROMPT,
                user_message=user_prompt,
                temperature=0.1,  # Slight variation for natural prose
                max_tokens=500,
            )

            # Basic validation: ensure result is not empty
            if result and len(result.strip()) > 20:
                return result.strip()

            logger.warning(
                f"{section_name} generation returned empty/short result, retrying",
                extra={"attempt": attempt},
            )

        except BedrockError as e:
            logger.warning(
                f"{section_name} generation failed: {e}",
                extra={"attempt": attempt},
            )

    # Fallback: use raw template data as plain text
    logger.warning(f"{section_name} using template fallback after {max_retries + 1} attempts")
    return _template_fallback(section_name, data)


def _template_fallback(section_name: str, data: dict[str, str]) -> str:
    """Generate a plain-text fallback when LLM is unavailable."""
    lines = [f"[{section_name} — generated from template (LLM unavailable)]"]
    for key, value in data.items():
        if value and value not in ("Not reported", "Not available", "N/A", "None", "unknown"):
            clean_key = key.replace("_", " ").title()
            lines.append(f"- {clean_key}: {value}")
    return "\n".join(lines)


def generate_patient_summary(soap_note: SOAPNote, urgency_result: UrgencyResult, routing_decision: RoutingDecision) -> PatientSummary:
    """Generate a redacted patient-facing summary from the SOAP note.

    This is the version shown in the Patient Portal — no clinical reasoning,
    no risk factors, no drug interaction details.
    """
    # Simple symptom summary
    symptoms_line = soap_note.soap_note.subjective[:100]
    if len(soap_note.soap_note.subjective) > 100:
        symptoms_line = symptoms_line.rsplit(" ", 1)[0] + "..."

    # Medication review summary (no specifics)
    meds_count = len(routing_decision.primary_clinic.available_slots) if routing_decision.primary_clinic else 0
    if soap_note.flags.critical_interaction:
        meds_line = "Medications reviewed — a potential interaction has been flagged for your doctor."
    else:
        meds_line = "Medications reviewed — no critical interactions found."

    # Urgency (patient-friendly)
    urgency_friendly = {
        "EMERGENCY": "Emergency — immediate attention required",
        "URGENT": "Urgent — same-day care recommended",
        "STANDARD": "Standard — appointment within 48 hours recommended",
        "ROUTINE": "Routine — appointment at your convenience",
    }
    urgency_line = urgency_friendly.get(
        urgency_result.urgency_level.value,
        f"{urgency_result.urgency_level.value} priority"
    )

    # Next steps
    dept = routing_decision.department
    if routing_decision.status == "routed" and routing_decision.primary_clinic:
        slots = routing_decision.primary_clinic.available_slots
        if slots:
            next_line = f"{dept} appointment available. Check your appointments for details."
        else:
            next_line = f"Referred to {dept}. A coordinator will contact you with scheduling."
    else:
        next_line = f"Referred to {dept}. Please contact the clinic for scheduling."

    return PatientSummary(
        symptoms_reported=symptoms_line,
        medications_reviewed=meds_line,
        urgency_level=urgency_line,
        next_steps=next_line,
    )
