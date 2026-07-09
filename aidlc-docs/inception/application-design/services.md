# Service Layer Design

## Service Architecture Pattern

The system uses a **Step Functions-orchestrated multi-agent pipeline** with event-driven escalation. The Supervisor Agent is implemented as an AWS Step Functions state machine that sequences agent invocations and handles branching (emergency, low confidence, normal flow).

---

## Service 1: Triage Orchestration Service (Supervisor)

| Attribute | Detail |
|---|---|
| **Implementation** | AWS Step Functions — Hybrid: Express (primary) + Standard (nurse handoff) |
| **Trigger** | Patient starts triage → API Gateway → Step Functions StartExecution (Express) |
| **Responsibilities** | Orchestrate the triage pipeline end-to-end |

### Pipeline Stages (Express Workflow — 95% of cases):

```
1. StartSession
   → Create DynamoDB session record
   → Return WebSocket connection info

2. SymptomAssessment (loop)
   → Invoke Symptom Assessment Agent
   → Stream responses to patient via WebSocket
   → Wait for patient input (callback pattern)
   → Repeat until assessment complete

3. TriageScoring
   → Invoke Triage Scoring Agent
   → Branch on result:
     - Emergency → goto EmergencyEscalation
     - Low confidence → goto HumanHandoff (triggers Standard workflow)
     - Standard/Routine/Urgent → goto DrugCheck

4. EmergencyEscalation
   → Invoke Notification Service (all channels)
   → Notify patient of emergency status
   → Continue to DrugCheck + ClinicalSummary in parallel
   → (Physician acknowledgement tracked async — not blocking pipeline)

5. DrugCheck
   → Invoke Drug Interaction Agent
   → If critical interaction → flag in session

6. SpecialistRouting
   → Invoke Specialist Routing Agent
   → Store routing decision

7. ClinicalSummary
   → Invoke Clinical Summary Agent
   → Generate SOAP note
   → Store in DynamoDB (push to EHR stubbed)

8. Complete
   → Update session status
   → Notify patient via portal (real-time update)
```

### Nurse Handoff (Standard Workflow — ~5% of cases):

```
1. ReceiveHandoff
   → Triggered by Express workflow when confidence is low
   → Receives full session context (conversation, AI reasoning, attempted classification)

2. WaitForNurse (callback — unbounded wait)
   → Push to Triage Nurse dashboard (DynamoDB + WebSocket notification)
   → Wait for nurse classification (SendTaskSuccess callback)
   → No timeout limit (Standard workflow supports up to 1 year)
   → If no nurse responds within 5 min → default to "Urgent" + auto-resume

3. ResumeWithNurseClassification
   → Nurse provides urgency level override
   → Trigger a NEW Express workflow execution starting from DrugCheck
   → with nurse's urgency level applied

4. Complete
   → Merge results back into original session record
```

---

## Service 2: Chat Service

| Attribute | Detail |
|---|---|
| **Implementation** | API Gateway WebSocket + Lambda |
| **Purpose** | Real-time bidirectional communication between patient and AI agents |

### Responsibilities:
- Manage WebSocket connections (connect/disconnect/message)
- Route patient messages to the active Step Functions execution
- Stream AI responses back to patient in real-time
- Handle nurse takeover (seamless chat thread continuation)
- Store conversation history per session

### API:
- `$connect` — authenticate, create connection record
- `$disconnect` — clean up connection
- `sendMessage` — patient sends message → routed to Step Functions
- `receiveMessage` — server pushes AI/nurse response to patient

---

## Service 3: Authentication Service

| Attribute | Detail |
|---|---|
| **Implementation** | Amazon Cognito + Custom Lambda triggers |
| **Purpose** | Patient identity verification via SMS/email + DOB |

### Flow:
1. Patient enters phone/email → Cognito sends verification code
2. Patient enters code → Cognito verifies
3. Patient enters DOB → Custom Lambda validates against EHR record
4. Session token issued → used for all subsequent API calls
5. Emergency bypass: non-PHI endpoints accessible without auth

---

## Service 4: Notification Service

| Attribute | Detail |
|---|---|
| **Implementation** | EventBridge + Lambda + SNS + PagerDuty webhook |
| **Purpose** | Multi-channel emergency escalation |

### Channels:
| Channel | Implementation | Trigger |
|---|---|---|
| SMS to physician | SNS (SMS) | Emergency classification |
| Push notification | SNS (push) | Emergency classification |
| PagerDuty page | HTTP webhook (Lambda) | Emergency classification |
| Patient live transfer | WebSocket message | Patient accepts transfer |

### Delivery Tracking:
- Each notification attempt logged to DynamoDB
- Delivery failures trigger retry (max 3) then alert clinic admin
- Physician acknowledgement tracked with timestamp

---

## Service 5: Portal API Service

| Attribute | Detail |
|---|---|
| **Implementation** | API Gateway REST + Lambda |
| **Purpose** | Backend for Patient Portal (non-chat operations) |

### Endpoints:
| Method | Path | Purpose |
|---|---|---|
| GET | /triage/status/{sessionId} | Current triage status |
| GET | /triage/history | Patient's triage history |
| GET | /appointments | Upcoming appointments |
| POST | /consent | Grant consent |
| DELETE | /consent/{type} | Revoke consent |
| GET | /profile | Patient profile |

---

## Service 6: Data Service

| Attribute | Detail |
|---|---|
| **Implementation** | DynamoDB + DAX (cache) |
| **Purpose** | Persistent storage for all triage data |

### Tables:
| Table | Purpose | Key |
|---|---|---|
| Sessions | Active/completed triage sessions | PK: sessionId |
| Patients | Patient profiles + consent | PK: patientId |
| Conversations | Chat message history | PK: sessionId, SK: timestamp |
| Notifications | Escalation delivery tracking | PK: sessionId, SK: channel |
| AuditTrail | All triage decisions for compliance | PK: patientId, SK: timestamp |
| Appointments | Scheduled specialist visits | PK: patientId, SK: appointmentId |

### Access Patterns:
- Get session by ID (single lookup)
- Get patient's sessions (query by patientId GSI)
- Get conversation for session (query by sessionId)
- Get audit trail for patient (compliance query)
- Get upcoming appointments for patient (query + filter)
