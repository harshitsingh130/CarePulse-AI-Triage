# Business Logic Model — Clinical Summary Agent

## Overview

The Clinical Summary Agent aggregates all outputs from the triage pipeline (Symptom Assessment, Triage Scoring, Drug Interaction, Specialist Routing) and generates a structured SOAP note for the receiving physician. It uses Bedrock (Claude) to produce natural clinical language from structured data — not free-form generation, but **template-guided synthesis**.

---

## SOAP Note Generation Flow

```
Input: Complete triage session data (all agent outputs)
         |
         v
+---------------------------+
| DATA AGGREGATION          |  Collect all inputs:
|                           |  - StructuredSymptoms (Unit 2)
|                           |  - UrgencyResult (Unit 3)
|                           |  - InteractionResult (Unit 4)
|                           |  - RoutingDecision (Unit 5)
|                           |  - Session metadata
+---------------------------+
         |
         v
+---------------------------+
| SECTION GENERATION        |  Generate each SOAP section
| (LLM-assisted)            |  using templates + data
+---------------------------+
         |
         v
+---------------------------+
| VALIDATION                |  Verify:
|                           |  - No hallucinated data
|                           |  - All flags included
|                           |  - Readable by physician
+---------------------------+
         |
         v
+---------------------------+
| FORMAT & STORE            |  Store in DynamoDB
|                           |  Push to EHR (stubbed for MVP)
+---------------------------+
         |
         v
Output: SOAPNote JSON
```

---

## SOAP Section Definitions

### S — Subjective (Patient's Report)

**Source**: StructuredSymptoms from Unit 2

**Template**:
```
Patient is a [age/gender if available] presenting with [primary_complaint.text].

Chief Complaint: [primary_complaint.text]
Onset: [onset.description]
Severity: [severity.score]/10 ([severity.source])
Duration/Pattern: [duration_pattern.description] ([duration_pattern.type])

Associated Symptoms:
- [foreach associated_symptoms: symptom (severity X/10)]

The patient reports [medications.source == "patient_reported" ? "taking" : "confirms taking"]:
[foreach medications.current: drug_name]

Allergies: [allergies.list OR "No known drug allergies (NKDA)"]

[if conversation_turns > 12: "Note: Extended assessment required (patient needed additional clarification)"]
[if fast_tracked: "Note: Fast-tracked assessment due to severity"]
```

**LLM role**: Transform structured data into readable clinical prose. Must NOT add information not in the source data.

---

### O — Objective (Observable/Measurable Data)

**Source**: InteractionResult (Unit 4) + EHR data (if available)

**Template**:
```
Vitals: Not available (remote triage — no physical examination performed)

Medications Verified:
[foreach medications_checked: drug_name (source: pharmacy_system|patient_reported), dosage]

Drug Interaction Check: [check_status]
[if interactions_found.length > 0:]
  Interactions Detected:
  [foreach interactions_found:]
    - [drug_a] + [drug_b]: [severity] — [clinical_effect]
      Recommendation: [recommendation]
[else:]
  No significant drug-drug interactions identified.

[if check_status == "unavailable":]
  ⚠️ Automated drug interaction check unavailable — manual review required.

Medical History (from [medical_history.source]):
[foreach medical_history.conditions: condition]
```

---

### A — Assessment (Clinical Judgment)

**Source**: UrgencyResult (Unit 3) + InteractionResult flags

**Template**:
```
Triage Classification: [urgency_level] (Confidence: [confidence_score])
Classification Method: [classification_method]
Recommended Timeframe: [recommended_timeframe]

Clinical Reasoning:
[urgency_result.reasoning]

Risk Factors Identified:
[foreach risk_factors: - factor]

[if modifiers_applied.length > 0:]
History Modifiers Applied:
[foreach modifiers_applied: - modifier (elevated urgency)]

[if requires_physician_alert:]
⚠️ CRITICAL DRUG INTERACTION ALERT:
[foreach interactions where severity == "critical":]
  - [drug_a] + [drug_b]: [clinical_effect]
  Action Required: [recommendation]

[if requires_nurse_review:]
Note: AI confidence below threshold — nurse review was requested.
[if nurse overrode:] Nurse override: Reclassified from [original] to [final].
```

---

### P — Plan (Next Steps)

**Source**: RoutingDecision (Unit 5) + urgency

**Template**:
```
Routing Decision: [department] (Confidence: [department_confidence])
Routing Reasoning: [routing_reasoning]

[if status == "routed":]
Appointment:
  - Department: [department]
  - Clinic: [primary_clinic.clinic_name]
  - Scheduled: [selected slot datetime]
  - Specialist: [specialist_name OR "Next available"]

[if alternatives.length > 0:]
Alternative Options Offered:
[foreach alternatives: - clinic_name: available slots]

[if status == "no_availability":]
⚠️ No specialist availability within [urgency] timeframe.
Patient advised to contact clinic directly for urgent scheduling.

Patient Instructions:
[urgency-based instructions:]
  - URGENT: "Seek care today. If symptoms worsen, call 911 or go to nearest ER."
  - STANDARD: "Please attend your scheduled appointment. If symptoms worsen significantly before then, return to triage or call the clinic."
  - ROUTINE: "Please attend your scheduled appointment at your convenience."

[if mental_health_priority:]
Crisis Resources Provided: 988 Suicide & Crisis Lifeline

Follow-up:
  - [department] appointment as scheduled
  - [if critical interaction:] Discuss medication interaction with specialist
  - [if nurse_review:] Physician to validate AI triage classification
```

---

## Validation Rules

### No Hallucination Rule
The LLM MUST NOT introduce:
- Diagnoses not supported by the data
- Medications not in the patient's list
- Symptoms not reported by the patient
- Lab results or vitals (not collected in remote triage)
- Treatment recommendations beyond "see specialist"

### Validation Check (Post-Generation)
After generating the SOAP note, verify:
1. Every medication mentioned exists in `medications_checked`
2. Every symptom mentioned exists in `structured_symptoms`
3. Urgency level matches `urgency_result.urgency_level` exactly
4. Department matches `routing_decision.department` exactly
5. No diagnostic terms present (validated against a blocklist)

If validation fails → regenerate the failing section (max 2 retries). If still failing → use the raw template output without LLM prose.

---

## EHR Push (Stubbed for MVP)

### FHIR Format (Future)
The SOAP note will eventually be pushed as a FHIR `DiagnosticReport` or `DocumentReference` resource to the EHR (Epic FHIR R4).

### MVP Behavior
- Store the SOAP note in DynamoDB (Sessions table, `soapNote` field)
- Make it available via the Portal API (`GET /triage/soap/{sessionId}`)
- Log: "SOAP note generated. EHR push pending integration."

---

## Output Contract

```json
{
  "session_id": "string (UUID)",
  "patient_id": "string (UUID)",
  "generated_at": "ISO datetime",
  "soap_note": {
    "subjective": "string (formatted clinical text)",
    "objective": "string (formatted clinical text)",
    "assessment": "string (formatted clinical text)",
    "plan": "string (formatted clinical text)"
  },
  "flags": {
    "critical_interaction": true|false,
    "nurse_override": true|false,
    "fast_tracked": true|false,
    "ehr_push_status": "pending|stubbed|sent|failed",
    "incomplete_data": ["list of fields that were null/missing"]
  },
  "metadata": {
    "model_version": "string (Bedrock model ARN)",
    "generation_time_ms": number,
    "validation_passed": true|false,
    "retry_count": 0-2
  }
}
```

Consumed by:
- **Supervisor Agent** — confirms SOAP generated, session complete
- **Patient Portal** — displays summary (redacted version — no full SOAP to patient)
- **Physician (via EHR)** — reads full SOAP before appointment
