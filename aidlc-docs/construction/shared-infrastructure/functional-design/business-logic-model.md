# Business Logic Model — Shared Infrastructure

## Overview

Unit 1 (Shared Infrastructure) provides the foundational AWS resources consumed by all other units. Its "business logic" is the resource configuration, access policies, and data management rules that enforce HIPAA compliance and system correctness.

---

## Logic Area 1: Data Layer Configuration

### DynamoDB Tables

| Table | PK | SK | GSIs | Encryption | TTL |
|---|---|---|---|---|---|
| Sessions | sessionId | — | patientId-startedAt, status, clinicId | KMS (phi-key) | 90 days |
| Patients | patientId | — | email, phone | KMS (phi-key) | None |
| Conversations | sessionId | timestamp | — | KMS (phi-key) | 90 days |
| Notifications | sessionId | channel | status | KMS (general-key) | 30 days |
| AuditTrail | patientId | timestamp | eventType | KMS (phi-key) | None (permanent) |
| Appointments | patientId | appointmentId | status-scheduledAt | KMS (general-key) | 365 days |

### Capacity Mode
- All tables: **On-demand** (auto-scaling, pay-per-request)
- Rationale: Triage load varies throughout the day; on-demand handles spikes without pre-provisioning

---

## Logic Area 2: Authentication Configuration

### Cognito User Pool

```
User Pool: healthcare-triage-patients
├── Custom Auth Flow (DefineAuthChallenge → CreateAuthChallenge → VerifyAuthChallenge)
├── Groups:
│   ├── patient (default group)
│   ├── nurse
│   ├── physician
│   └── admin
├── Password Policy: N/A (custom auth — no passwords)
├── MFA: SMS OTP (built into custom flow)
├── Token Validity:
│   ├── ID Token: 1 hour
│   ├── Access Token: 1 hour
│   └── Refresh Token: 30 days
└── Triggers:
    ├── DefineAuthChallenge: Lambda (defines OTP + DOB challenge sequence)
    ├── CreateAuthChallenge: Lambda (sends OTP via SNS/SES)
    └── VerifyAuthChallenge: Lambda (validates OTP + DOB against Patient record)
```

### Auth Flow Sequence

```
1. Patient → InitiateAuth(AuthFlow=CUSTOM_AUTH, AuthParameters={email|phone})
2. DefineAuthChallenge → issues CUSTOM_CHALLENGE (OTP)
3. CreateAuthChallenge → sends OTP to patient via SNS/SES
4. Patient → RespondToAuthChallenge(answer=OTP_CODE)
5. VerifyAuthChallenge → validates OTP
6. DefineAuthChallenge → issues CUSTOM_CHALLENGE (DOB)
7. Patient → RespondToAuthChallenge(answer=DOB)
8. VerifyAuthChallenge → validates DOB against Patient.dateOfBirth
9. DefineAuthChallenge → issues tokens (auth complete)
```

---

## Logic Area 3: API Gateway Configuration

### REST API (Portal)

| Resource | Method | Lambda | Auth | Purpose |
|---|---|---|---|---|
| /triage/status/{sessionId} | GET | portal-api | Cognito | Get triage status |
| /triage/history | GET | portal-api | Cognito | Patient's session history |
| /appointments | GET | portal-api | Cognito | Upcoming appointments |
| /consent | POST | portal-api | Cognito | Grant consent |
| /consent/{type} | DELETE | portal-api | Cognito | Revoke consent |
| /profile | GET | portal-api | Cognito | Patient profile |
| /nurse/queue | GET | nurse-api | Cognito (nurse group) | Get pending cases |
| /nurse/classify | POST | nurse-api | Cognito (nurse group) | Submit classification |

### WebSocket API (Chat)

| Route | Lambda | Purpose |
|---|---|---|
| $connect | chat-connect | Validate JWT, register connection |
| $disconnect | chat-disconnect | Clean up connection record |
| sendMessage | chat-message | Route patient message to Step Functions |
| (server push) | — | Send AI/nurse responses to patient |

---

## Logic Area 4: Encryption & Key Management

### KMS Keys

| Key Alias | Purpose | Rotation | Usage |
|---|---|---|---|
| `alias/triage-phi-key` | Encrypt all PHI fields in DynamoDB | Annual auto-rotation | DynamoDB SSE, application-level encryption |
| `alias/triage-general-key` | Encrypt non-PHI sensitive data | Annual auto-rotation | Notifications, appointments |

### Key Policy (phi-key)
- **Admins**: Full key management (clinic admin IAM role)
- **Encrypt/Decrypt**: Only agent execution roles + portal API role
- **No access**: Developer roles, CI/CD roles (cannot read PHI in production)

---

## Logic Area 5: Notification Infrastructure

### SNS Topics

| Topic | Purpose | Subscribers |
|---|---|---|
| `triage-emergency-escalation` | Emergency notification fanout | Notification Lambda |
| `triage-patient-updates` | Patient status notifications | (future: mobile push) |

### EventBridge Rules

| Rule | Source | Target | Purpose |
|---|---|---|---|
| `emergency-escalation` | Custom event: `triage.escalation.emergency` | Notification Lambda | Trigger multi-channel escalation |
| `session-completed` | Custom event: `triage.session.completed` | (future: analytics) | Track completion events |

---

## Logic Area 6: Monitoring & Logging

### CloudWatch Configuration

| Log Group | Source | Retention | Redaction |
|---|---|---|---|
| `/aws/lambda/symptom-assessment` | Agent Lambda | 90 days | PHI redaction filter |
| `/aws/lambda/triage-scoring` | Agent Lambda | 90 days | PHI redaction filter |
| `/aws/lambda/drug-interaction` | Agent Lambda | 90 days | PHI redaction filter |
| `/aws/lambda/specialist-routing` | Agent Lambda | 90 days | PHI redaction filter |
| `/aws/lambda/clinical-summary` | Agent Lambda | 90 days | PHI redaction filter |
| `/aws/lambda/supervisor-*` | Orchestration | 90 days | PHI redaction filter |
| `/aws/lambda/portal-api` | Portal API | 90 days | PHI redaction filter |
| `/aws/stepfunctions/triage-*` | Step Functions | 90 days | PHI redaction filter |
| `/triage/audit` | Audit events | Indefinite | No redaction (audit is authoritative) |

### Alarms

| Alarm | Threshold | Action |
|---|---|---|
| EmergencyEscalationFailure | Any failure in notification delivery | Alert clinic admin (SNS) |
| HighLatencyTriageScoring | Scoring response > 5 seconds | Alert ops team |
| UnauthorizedAuditTableAccess | Any Deny on AuditTrail operations | Alert security team |
| LambdaErrors5xx | Error rate > 5% over 5 minutes | Alert ops team |
