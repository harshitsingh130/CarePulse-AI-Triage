# Domain Entities — Clinical Summary Agent

## Entity: SOAPNote (Primary Output)

| Field | Type | Description |
|---|---|---|
| session_id | UUID | Links to triage session |
| patient_id | UUID | Patient identifier |
| generated_at | ISO DateTime | When note was generated |
| soap_note | SOAPContent | The four SOAP sections |
| flags | SOAPFlags | Clinical flags for quick scanning |
| metadata | GenerationMetadata | Generation process details |

---

## Entity: SOAPContent

| Field | Type | Description |
|---|---|---|
| subjective | String | Patient-reported symptoms, history, medications (clinical prose) |
| objective | String | Measurable data: verified meds, interaction results, EHR data |
| assessment | String | Urgency classification, reasoning, risk factors, flags |
| plan | String | Routing, appointment, patient instructions, follow-up |

---

## Entity: SOAPFlags

| Field | Type | Description |
|---|---|---|
| critical_interaction | Boolean | Drug interaction alert for physician |
| nurse_override | Boolean | Nurse changed the AI classification |
| fast_tracked | Boolean | Assessment was fast-tracked (severity ≥ 8) |
| ehr_push_status | Enum | PENDING, STUBBED, SENT, FAILED |
| incomplete_data | List[String] | Fields that were missing from input |

---

## Entity: GenerationMetadata

| Field | Type | Description |
|---|---|---|
| model_version | String | Bedrock model ARN used |
| generation_time_ms | Integer | Total generation time |
| validation_passed | Boolean | Post-generation validation result |
| retry_count | Integer | 0, 1, or 2 |
| fallback_used | Boolean | Template-only (no LLM) due to timeout/failure |

---

## Entity: TriageSessionData (Input Aggregation)

All inputs collected before generation begins:

| Field | Type | Source |
|---|---|---|
| structured_symptoms | StructuredSymptoms | Unit 2 output |
| urgency_result | UrgencyResult | Unit 3 output |
| interaction_result | InteractionResult | Unit 4 output |
| routing_decision | RoutingDecision | Unit 5 output |
| patient_info | PatientBasics | Patient table (name, DOB, clinic) |
| conversation_summary | String | Condensed conversation (not full transcript) |
| nurse_override | NurseOverride | null | If nurse reclassified |

---

## Entity: NurseOverride (conditional)

| Field | Type | Description |
|---|---|---|
| original_urgency | Enum | AI's original classification |
| override_urgency | Enum | Nurse's classification |
| nurse_id | String | Who overrode |
| reason | String | Nurse's stated reason |
| overridden_at | ISO DateTime | When |

---

## Entity: PatientSummary (Portal-Safe Version)

A redacted version of the SOAP note safe for patient viewing:

| Field | Type | Description |
|---|---|---|
| symptoms_reported | String | Simplified: "Headache, severity 7/10, started 3 days ago" |
| medications_reviewed | String | "5 medications checked — no critical interactions found" |
| urgency_level | String | "Standard — appointment recommended within 48 hours" |
| next_steps | String | "Neurology appointment scheduled: July 10, 10:30 AM, Clinic 3" |

---

## Data Flow

```
Input (from Supervisor, after all agents complete):
  - StructuredSymptoms
  - UrgencyResult
  - InteractionResult
  - RoutingDecision
  - Patient metadata
  - NurseOverride (if applicable)

Step 1: Data Aggregation
  → Load all inputs into TriageSessionData
  → Verify all required fields present
  → Note any missing data for flags

Step 2: Section Generation (LLM)
  → For each SOAP section:
    1. Build prompt = template + section data
    2. Call Bedrock (temp=0.1 — slight variation OK for natural prose)
    3. Receive generated text

Step 3: Validation
  → Cross-reference generated text against source data
  → Check for hallucinated content (medications, symptoms, diagnoses)
  → Verify flags are present and prominent
  → If validation fails: retry (max 2 times)

Step 4: Assembly
  → Combine sections into SOAPNote entity
  → Set flags based on input data
  → Record metadata

Step 5: Store
  → Write to Sessions table (soapNote field, encrypted)
  → Write to AuditTrail (SOAP_GENERATED event)

Step 6: Generate PatientSummary
  → Redact clinical details
  → Produce portal-safe version

Output:
  SOAPNote JSON → Supervisor (session completion)
  PatientSummary → Portal (patient view)
```

---

## LLM Configuration

| Parameter | Value | Rationale |
|---|---|---|
| Model | Claude 3 Sonnet (pinned version) | Balance of quality and speed |
| Temperature | 0.1 | Slight variation for natural prose, but mostly deterministic |
| Max tokens | 2000 | Enough for detailed SOAP, prevents runaway |
| System prompt | Clinical note writer role | Constrains to formatting, not diagnosing |
| Stop sequences | None needed (structured JSON response) | — |

**Note**: Temperature is 0.1 here (not 0.0 like Triage Scoring) because:
- Scoring needs exact determinism (same urgency every time)
- SOAP notes benefit from slight language variation (sounds less robotic to physicians)
- The content is validated against source data anyway — minor wording differences are acceptable
