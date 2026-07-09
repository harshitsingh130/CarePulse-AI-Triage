# Domain Entities — Symptom Assessment Agent

## Entity: ConversationState

The in-memory state maintained across conversation turns. Persisted to DynamoDB after each turn.

| Field | Type | Description |
|---|---|---|
| session_id | UUID | Links to TriageSession |
| turn_count | Integer | Current turn number (0-based) |
| phase | Enum | Current conversation phase |
| structured_symptoms | StructuredSymptoms | Progressively filled output object |
| completeness_score | Float (0-1) | Current assessment completeness |
| red_flag_detected | Boolean | Whether emergency red flag triggered |
| red_flag_category | String | null | Which red flag category |
| ehr_data_available | Boolean | Whether EHR data was loaded |
| ehr_medications | List[String] | Pre-loaded medication list from EHR |
| ehr_conditions | List[String] | Pre-loaded conditions from EHR |
| pending_clarifications | List[ClarificationRequest] | Fields needing follow-up |
| last_question_asked | String | For resumption context |
| fast_tracked | Boolean | Whether fast-track rules activated |

### Conversation Phases (Enum)
```
GREETING → PRIMARY_COMPLAINT → ONSET → SEVERITY → DURATION →
ASSOCIATED_SYMPTOMS → MEDICAL_HISTORY → MEDICATIONS → ALLERGIES →
CLARIFYING → COMPLETE
```

Phase transitions are NOT strictly linear — the agent may skip phases (if EHR provides data) or return to CLARIFYING from any phase.

---

## Entity: ClarificationRequest

| Field | Type | Description |
|---|---|---|
| field_name | String | Which field needs clarification (e.g., "severity") |
| attempt_count | Integer | How many times we've asked (max 3) |
| last_response | String | Patient's last response to this question |
| confidence | Float | Current confidence for this field |

---

## Entity: StructuredSymptoms (Output)

See BR-SA-010 in business-rules.md for the complete JSON schema. This is the primary output entity — the contract between this agent and the Triage Scoring Agent.

---

## Entity: RedFlagPattern

Configuration entity (loaded at agent startup):

| Field | Type | Description |
|---|---|---|
| category | String | Cardiac, Respiratory, Neurological, etc. |
| patterns | List[String] | Regex or keyword patterns to match |
| combination_required | Boolean | Whether multiple patterns must co-occur |
| fast_track_severity | Integer | Minimum severity to assume if red flag fires |

---

## Entity: SymptomCategoryMapping

Configuration entity for context-aware questioning:

| Field | Type | Description |
|---|---|---|
| category | String | Primary complaint category |
| keywords | List[String] | Keywords that map to this category |
| follow_up_symptoms | List[String] | Associated symptoms to ask about |
| priority_order | Integer | Which symptoms to ask first |

---

## Data Flow

```
Input:
  - Patient message (text from WebSocket)
  - Session state (loaded from DynamoDB)
  - EHR data (if authenticated, loaded from EHR stub)

Processing:
  1. Load current ConversationState
  2. Extract clinical data from patient message
  3. Update StructuredSymptoms with extracted data
  4. Recalculate completeness_score
  5. Check for red flags
  6. Determine next question (or mark complete)
  7. Generate response message
  8. Save updated ConversationState to DynamoDB

Output:
  - AI response message (streamed to patient via WebSocket)
  - Updated session state (DynamoDB)
  - When complete: StructuredSymptoms JSON (passed to Supervisor → Triage Scoring)
```
