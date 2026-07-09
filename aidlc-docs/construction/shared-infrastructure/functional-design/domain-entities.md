# Domain Entities — Shared Infrastructure

## Entity: TriageSession

| Field | Type | Description | Encrypted | Indexed |
|---|---|---|---|---|
| sessionId | String (UUID) | Primary key — unique session identifier | No | PK |
| patientId | String (UUID) | Patient who initiated the session | Yes | GSI-1 PK |
| status | Enum | IN_PROGRESS, AWAITING_NURSE, AWAITING_ROUTING, SCHEDULED, COMPLETED, ESCALATED | No | GSI-2 PK |
| urgencyLevel | Enum | EMERGENCY, URGENT, STANDARD, ROUTINE, null (pre-scoring) | No | — |
| confidenceScore | Number (0.0-1.0) | AI confidence in urgency classification | No | — |
| clinicId | String | Patient's home clinic | No | GSI-3 PK |
| structuredSymptoms | Map | Structured symptom data from assessment agent | Yes | — |
| urgencyResult | Map | Full scoring result with reasoning | Yes | — |
| interactionResult | Map | Drug interaction check results | Yes | — |
| routingDecision | Map | Specialist routing result | Yes | — |
| soapNote | Map | Generated SOAP note | Yes | — |
| workflowExecutionArn | String | Step Functions execution ARN | No | — |
| nurseHandoffExecutionArn | String | Standard workflow ARN (if nurse handoff) | No | — |
| startedAt | String (ISO) | Session start timestamp | No | GSI-1 SK |
| completedAt | String (ISO) | Session completion timestamp | No | — |
| createdAt | String (ISO) | Record creation time | No | — |
| updatedAt | String (ISO) | Last update time | No | — |
| ttl | Number | TTL for session expiry (90 days) | No | — |

### Access Patterns:
- Get session by ID: PK = sessionId
- Get sessions for patient (sorted by date): GSI-1 PK = patientId, SK = startedAt
- Get active sessions by status: GSI-2 PK = status
- Get sessions by clinic: GSI-3 PK = clinicId

---

## Entity: Patient

| Field | Type | Description | Encrypted | Indexed |
|---|---|---|---|---|
| patientId | String (UUID) | Primary key — unique patient identifier | No | PK |
| email | String | Patient email (for auth) | Yes | GSI-1 PK |
| phone | String | Patient phone (for auth + SMS) | Yes | GSI-2 PK |
| dateOfBirth | String (ISO date) | DOB for identity verification | Yes | — |
| firstName | String | Patient first name | Yes | — |
| lastName | String | Patient last name | Yes | — |
| clinicId | String | Primary clinic | No | — |
| consentStatus | Map | Consent grants (see Consent entity) | No | — |
| cognitoSub | String | Cognito user pool subject ID | No | — |
| ehrPatientId | String | External EHR patient identifier | Yes | — |
| createdAt | String (ISO) | Account creation time | No | — |
| updatedAt | String (ISO) | Last update time | No | — |

### Access Patterns:
- Get patient by ID: PK = patientId
- Lookup by email (auth flow): GSI-1 PK = email
- Lookup by phone (auth flow): GSI-2 PK = phone

---

## Entity: Conversation

| Field | Type | Description | Encrypted | Indexed |
|---|---|---|---|---|
| sessionId | String (UUID) | Partition key — links to TriageSession | No | PK |
| timestamp | String (ISO) | Sort key — message time | No | SK |
| role | Enum | PATIENT, AI_AGENT, TRIAGE_NURSE, SYSTEM | No | — |
| content | String | Message content | Yes | — |
| agentName | String | Which agent generated this (symptom_assessment, triage_scoring, etc.) | No | — |
| metadata | Map | Message metadata (confidence, intent, etc.) | No | — |

### Access Patterns:
- Get full conversation for session: PK = sessionId (all items, sorted by SK timestamp)
- Get messages since timestamp: PK = sessionId, SK > timestamp

---

## Entity: Notification

| Field | Type | Description | Encrypted | Indexed |
|---|---|---|---|---|
| sessionId | String (UUID) | Partition key — links to escalated session | No | PK |
| channel | String | Sort key — SMS, PUSH, PAGERDUTY, LIVE_TRANSFER | No | SK |
| recipientId | String | Physician or staff ID | No | — |
| status | Enum | SENT, DELIVERED, ACKNOWLEDGED, FAILED, TIMEOUT | No | GSI-1 PK |
| sentAt | String (ISO) | When notification was sent | No | — |
| acknowledgedAt | String (ISO) | When recipient acknowledged | No | — |
| failureReason | String | Reason for failure (if FAILED) | No | — |
| retryCount | Number | Number of retry attempts | No | — |
| patientSummary | Map | Summary sent with notification | Yes | — |

### Access Patterns:
- Get all notifications for session: PK = sessionId
- Get specific channel: PK = sessionId, SK = channel
- Get failed notifications (for retry): GSI-1 PK = FAILED

---

## Entity: AuditTrail

| Field | Type | Description | Encrypted | Indexed |
|---|---|---|---|---|
| patientId | String (UUID) | Partition key — patient whose data was accessed/decided | No | PK |
| timestamp | String (ISO) | Sort key — when the event occurred | No | SK |
| eventType | Enum | TRIAGE_STARTED, URGENCY_ASSIGNED, ESCALATION_TRIGGERED, NURSE_OVERRIDE, ROUTING_DECIDED, SOAP_GENERATED, CONSENT_GRANTED, CONSENT_REVOKED, PHI_ACCESSED | No | GSI-1 PK |
| sessionId | String (UUID) | Related triage session (if applicable) | No | — |
| actorType | Enum | AI_AGENT, PATIENT, NURSE, PHYSICIAN, SYSTEM | No | — |
| actorId | String | Who performed the action | No | — |
| details | Map | Event-specific details | Yes | — |
| reasoning | String | Why this decision was made (for AI decisions) | Yes | — |

### Access Patterns:
- Get full audit trail for patient: PK = patientId (sorted by timestamp)
- Get audit events by type: GSI-1 PK = eventType
- Get events for session: Filter on sessionId

---

## Entity: Appointment

| Field | Type | Description | Encrypted | Indexed |
|---|---|---|---|---|
| patientId | String (UUID) | Partition key | No | PK |
| appointmentId | String (UUID) | Sort key | No | SK |
| sessionId | String (UUID) | Originating triage session | No | — |
| department | String | Specialist department | No | — |
| specialistName | String | Assigned specialist (if known) | No | — |
| clinicId | String | Clinic location | No | — |
| scheduledAt | String (ISO) | Appointment date/time | No | GSI-1 SK |
| status | Enum | SCHEDULED, CONFIRMED, CANCELLED, COMPLETED | No | GSI-1 PK |
| preparationNotes | String | Instructions for the patient | No | — |
| createdAt | String (ISO) | When appointment was created | No | — |

### Access Patterns:
- Get appointments for patient: PK = patientId
- Get upcoming appointments (for reminders): GSI-1 PK = SCHEDULED, SK > now

---

## Enumerations

### SessionStatus
```
IN_PROGRESS | AWAITING_NURSE | AWAITING_ROUTING | SCHEDULED | COMPLETED | ESCALATED
```

### UrgencyLevel
```
EMERGENCY | URGENT | STANDARD | ROUTINE
```

### NotificationChannel
```
SMS | PUSH | PAGERDUTY | LIVE_TRANSFER
```

### NotificationStatus
```
SENT | DELIVERED | ACKNOWLEDGED | FAILED | TIMEOUT
```

### ConversationRole
```
PATIENT | AI_AGENT | TRIAGE_NURSE | SYSTEM
```

### AuditEventType
```
TRIAGE_STARTED | URGENCY_ASSIGNED | ESCALATION_TRIGGERED | NURSE_OVERRIDE |
ROUTING_DECIDED | SOAP_GENERATED | CONSENT_GRANTED | CONSENT_REVOKED | PHI_ACCESSED
```

### ActorType
```
AI_AGENT | PATIENT | NURSE | PHYSICIAN | SYSTEM
```
