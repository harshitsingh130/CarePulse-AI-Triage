"""SOAP note section templates and prompt construction.

Each SOAP section has a template that maps structured data to the
expected clinical prose format. The LLM fills in natural language
within the template structure.
"""

from __future__ import annotations

from typing import Any


SOAP_SYSTEM_PROMPT = """You are a clinical note writer for a digital triage system.
Your job is to write ONE section of a SOAP note using ONLY the data provided.

CRITICAL RULES:
- Use ONLY the information given. Do NOT invent, hallucinate, or assume anything.
- Do NOT diagnose. Do NOT name potential conditions.
- Do NOT suggest treatments beyond "see specialist."
- Write in concise, professional clinical note style.
- Use standard abbreviations where appropriate (NKDA, PRN, etc.).
- If data is missing, write "Not available" or "Not reported" — do NOT guess.
"""

SUBJECTIVE_PROMPT = """Write the SUBJECTIVE section of a SOAP note from this triage data.

This section captures what the patient reported in their own words.

Data:
- Primary complaint: {primary_complaint}
- Onset: {onset}
- Severity: {severity}/10 ({severity_source})
- Duration/Pattern: {duration}
- Associated symptoms: {associated_symptoms}
- Medical history: {medical_history}
- Current medications: {medications}
- Allergies: {allergies}
- Assessment notes: {notes}

Write a concise Subjective section (3-6 sentences). Start with the presenting complaint."""

OBJECTIVE_PROMPT = """Write the OBJECTIVE section of a SOAP note from this triage data.

This section captures measurable/verifiable data (not patient-reported feelings).

Data:
- Vitals: Not available (remote triage — no physical examination)
- Medications verified: {medications_verified}
- Medication source: {medication_source}
- Drug interactions found: {interactions}
- Drug interaction check status: {check_status}
- Medical history source: {history_source}
- Medical conditions: {conditions}

Write a concise Objective section. Note this was a remote triage (no vitals/exam)."""

ASSESSMENT_PROMPT = """Write the ASSESSMENT section of a SOAP note from this triage data.

This section captures the clinical assessment of urgency (NOT a diagnosis).

Data:
- Triage classification: {urgency_level}
- Confidence: {confidence}
- Classification method: {method}
- Clinical reasoning: {reasoning}
- Risk factors: {risk_factors}
- History modifiers applied: {modifiers}
- Requires nurse review: {nurse_review}
- Critical drug interactions: {critical_interactions}

Write a concise Assessment section. State the urgency classification and key reasoning.
Include any critical alerts prominently."""

PLAN_PROMPT = """Write the PLAN section of a SOAP note from this triage data.

This section captures the next steps and routing decision.

Data:
- Routing department: {department}
- Routing confidence: {routing_confidence}
- Routing reasoning: {routing_reasoning}
- Appointment status: {appointment_status}
- Specialist: {specialist}
- Clinic: {clinic}
- Scheduled time: {scheduled_time}
- Urgency timeframe: {timeframe}
- Mental health priority: {mental_health}
- Patient instructions based on urgency: {instructions}
- Follow-up items: {follow_up}

Write a concise Plan section with clear next steps and any patient instructions."""


def build_subjective_data(symptoms: dict) -> dict[str, str]:
    """Extract Subjective section data from StructuredSymptoms."""
    pc = symptoms.get("primary_complaint", {})
    onset = symptoms.get("onset", {})
    severity = symptoms.get("severity", {})
    duration = symptoms.get("duration_pattern", {})
    meds = symptoms.get("medications", {})
    history = symptoms.get("medical_history", {})
    allergies = symptoms.get("allergies", {})

    associated = symptoms.get("associated_symptoms", [])
    assoc_text = ", ".join(s.get("symptom", "") for s in associated) if associated else "None reported"

    notes = []
    if symptoms.get("fast_tracked"):
        notes.append("Fast-tracked assessment due to severity")
    if symptoms.get("conversation_turns", 0) > 12:
        notes.append("Extended assessment required")
    if symptoms.get("red_flag_detected"):
        notes.append(f"Emergency red flag: {symptoms.get('red_flag_category', 'unspecified')}")

    return {
        "primary_complaint": pc.get("text", "Not reported"),
        "onset": onset.get("description", "Not reported"),
        "severity": str(severity.get("score", "?")),
        "severity_source": severity.get("source", "unknown"),
        "duration": f"{duration.get('type', '?')} — {duration.get('description', '')}" if duration else "Not reported",
        "associated_symptoms": assoc_text,
        "medical_history": ", ".join(history.get("conditions", [])) if history else "Not reported",
        "medications": ", ".join(meds.get("current", [])) if meds else "Not reported",
        "allergies": ", ".join(allergies.get("items", [])) if allergies else "NKDA",
        "notes": "; ".join(notes) if notes else "Standard assessment",
    }


def build_objective_data(symptoms: dict, interaction_result: dict) -> dict[str, str]:
    """Extract Objective section data from symptoms + interaction results."""
    meds = symptoms.get("medications", {})
    history = symptoms.get("medical_history", {})

    # Medication verification
    meds_checked = interaction_result.get("medications_checked", [])
    meds_text = ", ".join(
        f"{m.get('drug_name', '?')} ({m.get('dosage', 'dose unknown')})"
        for m in meds_checked
    ) if meds_checked else "No medications verified"

    # Interactions
    interactions = interaction_result.get("interactions_found", [])
    if interactions:
        interaction_lines = []
        for i in interactions:
            interaction_lines.append(
                f"{i['drug_a']} + {i['drug_b']}: {i['severity'].upper()} — {i['clinical_effect']}"
            )
        interactions_text = "; ".join(interaction_lines)
    else:
        interactions_text = "No significant drug-drug interactions identified"

    return {
        "medications_verified": meds_text,
        "medication_source": meds.get("source", "unknown") if meds else "N/A",
        "interactions": interactions_text,
        "check_status": interaction_result.get("check_status", "unavailable"),
        "history_source": history.get("source", "unknown") if history else "N/A",
        "conditions": ", ".join(history.get("conditions", [])) if history else "None reported",
    }


def build_assessment_data(urgency_result: dict, interaction_result: dict) -> dict[str, str]:
    """Extract Assessment section data from urgency + interactions."""
    # Critical interactions for alert
    interactions = interaction_result.get("interactions_found", [])
    critical = [i for i in interactions if i.get("severity") == "critical"]
    critical_text = "; ".join(
        f"{i['drug_a']} + {i['drug_b']}: {i['clinical_effect']}"
        for i in critical
    ) if critical else "None"

    return {
        "urgency_level": urgency_result.get("urgency_level", "UNKNOWN"),
        "confidence": f"{urgency_result.get('confidence_score', 0):.0%}",
        "method": urgency_result.get("classification_method", "unknown"),
        "reasoning": urgency_result.get("reasoning", "Not available"),
        "risk_factors": ", ".join(urgency_result.get("risk_factors", [])) or "None identified",
        "modifiers": ", ".join(urgency_result.get("modifiers_applied", [])) or "None",
        "nurse_review": "Yes" if urgency_result.get("requires_nurse_review") else "No",
        "critical_interactions": critical_text,
    }


def build_plan_data(routing_decision: dict, urgency_result: dict) -> dict[str, str]:
    """Extract Plan section data from routing + urgency."""
    primary_clinic = routing_decision.get("primary_clinic", {})
    slots = primary_clinic.get("available_slots", []) if primary_clinic else []
    first_slot = slots[0] if slots else None

    urgency = urgency_result.get("urgency_level", "STANDARD")
    instructions_map = {
        "EMERGENCY": "Seek immediate care. If symptoms worsen, call 911.",
        "URGENT": "Seek care today. If symptoms worsen, call 911 or go to nearest ER.",
        "STANDARD": "Please attend your scheduled appointment. If symptoms worsen significantly, return to triage or call the clinic.",
        "ROUTINE": "Please attend your scheduled appointment at your convenience.",
    }

    follow_up_items = []
    if routing_decision.get("mental_health_priority"):
        follow_up_items.append("Crisis resources provided: 988 Suicide & Crisis Lifeline")
    if urgency_result.get("requires_nurse_review"):
        follow_up_items.append("Physician to validate AI triage classification")

    interactions = routing_decision.get("interaction_result", {}) or {}
    if interactions.get("requires_physician_alert"):
        follow_up_items.append("Discuss medication interaction with specialist")

    return {
        "department": routing_decision.get("department", "Not determined"),
        "routing_confidence": f"{routing_decision.get('department_confidence', 0):.0%}",
        "routing_reasoning": routing_decision.get("routing_reasoning", "Not available"),
        "appointment_status": routing_decision.get("status", "unknown"),
        "specialist": first_slot.get("specialist_name", "Next available") if first_slot else "Not assigned",
        "clinic": primary_clinic.get("clinic_name", "Not determined") if primary_clinic else "Not determined",
        "scheduled_time": first_slot.get("datetime", "Not yet scheduled") if first_slot else "Not yet scheduled",
        "timeframe": urgency_result.get("recommended_timeframe", "Not specified"),
        "mental_health": "Yes" if routing_decision.get("mental_health_priority") else "No",
        "instructions": instructions_map.get(urgency, instructions_map["STANDARD"]),
        "follow_up": "; ".join(follow_up_items) if follow_up_items else "Standard follow-up with specialist",
    }
