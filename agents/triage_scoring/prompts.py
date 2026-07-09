"""Prompts for LLM-based clinical reasoning in triage scoring."""

SCORING_SYSTEM_PROMPT = """You are a clinical triage scoring system. Your ONLY job is to classify
the urgency level of a patient's symptoms. You do NOT diagnose.

Classify urgency as one of:
- EMERGENCY: Life-threatening, requires immediate intervention (minutes)
- URGENT: Serious, requires same-day attention (hours)
- STANDARD: Needs medical attention soon (24-48 hours)
- ROUTINE: Non-urgent, can wait for next available appointment (days-weeks)

Consider these clinical factors in order of importance:
1. Severity score (1-10) — higher = more urgent
2. Onset recency — sudden onset of severe symptoms = more urgent
3. Pattern — worsening = more urgent, improving = less urgent
4. Red flags — any emergency indicators
5. Associated symptoms — multiple concerning symptoms together = more urgent
6. Risk factors from medical history — conditions that amplify risk
7. Medications — interactions or contraindications that elevate risk

IMPORTANT RULES:
- Be conservative. When in doubt between two levels, ALWAYS choose the MORE urgent one.
- Provide step-by-step reasoning.
- Rate your confidence (0.0-1.0) in the classification.
- Do NOT diagnose. Do NOT name potential conditions.
- Focus only on urgency classification.

You MUST respond in this exact JSON format:
{
  "urgency_level": "EMERGENCY|URGENT|STANDARD|ROUTINE",
  "confidence": 0.0-1.0,
  "reasoning": "Step-by-step clinical reasoning without naming diagnoses",
  "risk_factors": ["list of identified risk factors"],
  "recommended_timeframe": "immediate|within 4 hours|within 24 hours|within 48 hours|within 1 week|within 2 weeks"
}"""


SCORING_USER_PROMPT_TEMPLATE = """Classify the urgency of the following patient assessment:

Patient Assessment:
- Primary Complaint: {primary_complaint} (category: {complaint_category})
- Severity: {severity}/10 ({severity_source})
- Onset: {onset} ({days_ago} days ago)
- Duration/Pattern: {duration_pattern}
- Associated Symptoms: {associated_symptoms}
- Medical History: {medical_history}
- Current Medications: {medications}
- Allergies: {allergies}
- Assessment Completeness: {completeness}%
- Fast-tracked: {fast_tracked}

Provide your urgency classification in the required JSON format."""


def build_scoring_prompt(symptoms_dict: dict) -> str:
    """Build the user prompt from structured symptoms data."""

    primary_complaint = "Not provided"
    complaint_category = "unknown"
    if symptoms_dict.get("primary_complaint"):
        primary_complaint = symptoms_dict["primary_complaint"].get("text", "Not provided")
        complaint_category = symptoms_dict["primary_complaint"].get("category", "unknown")

    severity = "Not provided"
    severity_source = "N/A"
    if symptoms_dict.get("severity"):
        severity = str(symptoms_dict["severity"].get("score", "?"))
        severity_source = symptoms_dict["severity"].get("source", "unknown")

    onset = "Not provided"
    days_ago = "unknown"
    if symptoms_dict.get("onset"):
        onset = symptoms_dict["onset"].get("description", "Not provided")
        days_ago = str(symptoms_dict["onset"].get("days_ago_estimate", "unknown"))

    duration_pattern = "Not provided"
    if symptoms_dict.get("duration_pattern"):
        dp = symptoms_dict["duration_pattern"]
        duration_pattern = f"{dp.get('type', '?')} — {dp.get('description', '')}"

    associated = "None reported"
    if symptoms_dict.get("associated_symptoms"):
        assoc_list = [s.get("symptom", "") for s in symptoms_dict["associated_symptoms"]]
        associated = ", ".join(assoc_list) if assoc_list else "None reported"

    history = "Not available"
    if symptoms_dict.get("medical_history"):
        conditions = symptoms_dict["medical_history"].get("conditions", [])
        history = ", ".join(conditions) if conditions else "No known conditions"

    medications = "Not available"
    if symptoms_dict.get("medications"):
        meds = symptoms_dict["medications"].get("current", [])
        medications = ", ".join(meds) if meds else "No current medications"

    allergies = "Not available"
    if symptoms_dict.get("allergies"):
        allergy_list = symptoms_dict["allergies"].get("items", [])
        allergies = ", ".join(allergy_list) if allergy_list else "NKDA"

    completeness = int(symptoms_dict.get("completeness_score", 0) * 100)
    fast_tracked = "Yes" if symptoms_dict.get("fast_tracked") else "No"

    return SCORING_USER_PROMPT_TEMPLATE.format(
        primary_complaint=primary_complaint,
        complaint_category=complaint_category,
        severity=severity,
        severity_source=severity_source,
        onset=onset,
        days_ago=days_ago,
        duration_pattern=duration_pattern,
        associated_symptoms=associated,
        medical_history=history,
        medications=medications,
        allergies=allergies,
        completeness=completeness,
        fast_tracked=fast_tracked,
    )
