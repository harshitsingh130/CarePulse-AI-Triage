# Component Methods

## Symptom Assessment Agent

| Method | Input | Output | Purpose |
|---|---|---|---|
| `assess_symptoms(message, session_context)` | Patient text message + conversation history | AI response text + structured symptom data (when complete) | Process patient input, ask next question or mark complete |
| `is_assessment_complete(session_context)` | Current conversation state | Boolean + completeness score | Determine if enough data collected |
| `extract_structured_symptoms(conversation)` | Full conversation history | StructuredSymptoms JSON | Parse conversation into structured clinical data |

### StructuredSymptoms Schema:
```json
{
  "primary_complaint": "string",
  "onset": "string (duration description)",
  "severity": 1-10,
  "duration": "string",
  "associated_symptoms": ["string"],
  "medical_history": ["string"],
  "current_medications": ["string"],
  "allergies": ["string"],
  "assessment_complete": true
}
```

---

## Triage Scoring Agent

| Method | Input | Output | Purpose |
|---|---|---|---|
| `score_urgency(structured_symptoms)` | StructuredSymptoms JSON | UrgencyResult JSON | Classify urgency with confidence |
| `get_scoring_reasoning(result)` | UrgencyResult | String explanation | Human-readable explanation of why this score was assigned |

### UrgencyResult Schema:
```json
{
  "urgency_level": "Emergency|Urgent|Standard|Routine",
  "confidence_score": 0.0-1.0,
  "reasoning": "string",
  "risk_factors": ["string"],
  "recommended_timeframe": "string (e.g., 'immediate', 'within 4 hours', 'within 48 hours')"
}
```

---

## Drug Interaction Agent

| Method | Input | Output | Purpose |
|---|---|---|---|
| `check_interactions(patient_id, reported_medications)` | Patient ID + any new meds reported in chat | InteractionResult JSON | Query pharmacy system and check for dangerous combinations |
| `classify_severity(interactions)` | Raw interaction data | Classified list | Assign critical/moderate/informational to each interaction |

### InteractionResult Schema:
```json
{
  "medications_checked": ["string"],
  "interactions_found": [
    {
      "drug_a": "string",
      "drug_b": "string",
      "severity": "critical|moderate|informational",
      "description": "string",
      "recommendation": "string"
    }
  ],
  "check_status": "complete|partial|unavailable",
  "source": "pharmacy_system|reported"
}
```

---

## Specialist Routing Agent

| Method | Input | Output | Purpose |
|---|---|---|---|
| `route_patient(structured_symptoms, urgency_level, patient_clinic)` | Symptoms + urgency + home clinic | RoutingDecision JSON | Determine best specialist department and availability |
| `find_alternatives(department, patient_clinic)` | Dept + clinic | Alternative slots at nearby clinics | Fallback when primary clinic has no availability |

### RoutingDecision Schema:
```json
{
  "department": "string",
  "specialist_name": "string (if available)",
  "clinic": "string",
  "available_slots": ["ISO datetime"],
  "routing_confidence": 0.0-1.0,
  "routing_reasoning": "string",
  "alternatives": [{"clinic": "string", "slots": ["ISO datetime"]}]
}
```

---

## Clinical Summary Agent

| Method | Input | Output | Purpose |
|---|---|---|---|
| `generate_soap_note(triage_session)` | Complete triage session data (all agent outputs) | SOAPNote JSON | Generate structured clinical note |
| `format_for_ehr(soap_note)` | SOAPNote | FHIR-compatible format | Transform to EHR-ready format (stubbed for MVP) |

### SOAPNote Schema:
```json
{
  "session_id": "string",
  "patient_id": "string",
  "generated_at": "ISO datetime",
  "subjective": "string (patient-reported symptoms)",
  "objective": "string (medications, vitals if available, interaction results)",
  "assessment": "string (urgency, reasoning, risk factors, interactions)",
  "plan": "string (routing decision, specialist, timeframe, instructions)",
  "flags": ["string (drug interactions, emergency indicators)"]
}
```

---

## Supervisor Agent (Step Functions + Decision Lambda)

| Method | Input | Output | Purpose |
|---|---|---|---|
| `start_triage_session(patient_id, connection_id)` | Patient ID + WebSocket connection | Session ID | Initialize session, start Step Functions execution |
| `evaluate_escalation(urgency_result)` | UrgencyResult from Triage Scoring | EscalationDecision | Decide: emergency → escalate, low confidence → nurse, else continue |
| `trigger_emergency_escalation(session_id, patient_summary)` | Session + summary | Notification events | Fire all escalation channels |
| `route_to_nurse(session_id, context)` | Session + AI context | Nurse queue entry | Push to nurse dashboard with full context |
| `complete_session(session_id, all_results)` | Session + all agent outputs | CompletedSession | Finalize, store, notify patient |

---

## Notification Service

| Method | Input | Output | Purpose |
|---|---|---|---|
| `send_escalation(escalation_event)` | EscalationEvent (patient summary, channels, recipients) | DeliveryResults | Fire all notification channels |
| `send_sms(phone, message)` | Phone number + content | Delivery status | Send SMS via SNS |
| `page_oncall(summary)` | Patient summary | PagerDuty incident ID | Create PagerDuty incident |
| `track_acknowledgement(session_id, physician_id)` | Session + physician | Timestamp | Record when physician acknowledges |

---

## Patient Portal (Frontend)

| Method/Route | Purpose |
|---|---|
| `connectWebSocket(sessionId)` | Establish chat connection |
| `sendMessage(text)` | Send patient message to AI |
| `onMessage(handler)` | Receive AI/nurse responses |
| `getTriageStatus(sessionId)` | Poll/subscribe to status updates |
| `getAppointments()` | Fetch upcoming appointments |
| `grantConsent(types[])` | Record consent grants |
| `revokeConsent(type)` | Revoke specific consent |
| `authenticate(phone/email, code, dob)` | Complete SMS/email + DOB auth |

---

## PHI Redaction Layer

| Method | Input | Output | Purpose |
|---|---|---|---|
| `redact(log_entry)` | Raw log string | Redacted log string | Remove PHI patterns before CloudWatch write |
| `detect_phi(text)` | Any text | List of detected PHI spans | Identify PHI in text (names, DOB, SSN, medical IDs) |
| `configure_patterns(custom_patterns)` | Regex patterns | Updated config | Add domain-specific PHI patterns |

---

## Note

Detailed business rules (e.g., exact urgency scoring algorithm, department-to-symptom mapping tables, SOAP note templates) will be defined in **Functional Design** during the Construction phase per unit.
