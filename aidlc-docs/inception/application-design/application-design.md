# Application Design — Healthcare Network Patient Triage System

## Architecture Summary

**Pattern**: Multi-agent pipeline with supervisor orchestration  
**Orchestration**: AWS Step Functions (Hybrid: Express for 95% of sessions + Standard for nurse handoff)  
**Agent Framework**: Strands Agents SDK (Python) on AWS Lambda  
**AI Model**: Amazon Bedrock (Claude)  
**Frontend**: React (web + mobile responsive)  
**Infrastructure**: AWS CDK (TypeScript)  
**Data**: DynamoDB (encrypted, single-table-per-concern)  

---

## System Architecture

```
+------------------------------------------------------------------+
|                         PATIENT PORTAL                             |
|          (React — Web + Mobile Responsive)                        |
|   [ Triage Chat ]  [ Status ]  [ Appointments ]  [ Consent ]     |
+------------------------------------------------------------------+
         |  WebSocket (chat)              |  REST (status, appts)
         v                                v
+------------------+           +--------------------+
| API Gateway      |           | API Gateway        |
| (WebSocket API)  |           | (REST API)         |
+------------------+           +--------------------+
         |                                |
         v                                v
+------------------+           +--------------------+
| Chat Service     |           | Portal API         |
| (Lambda)         |           | (Lambda)           |
+------------------+           +--------------------+
         |
         | StartExecution / SendTaskSuccess
         v
+===================================================================+
|              SUPERVISOR AGENT (Step Functions Express)              |
|                                                                    |
|  +-----------+  +--------+  +------+  +---------+  +----------+  |
|  | Symptom   |→ | Triage |→ | Drug |→ | Routing |→ | Clinical |  |
|  | Assessment|  | Scoring|  | Check|  | Agent   |  | Summary  |  |
|  | Agent     |  | Agent  |  | Agent|  |         |  | Agent    |  |
|  +-----------+  +--------+  +------+  +---------+  +----------+  |
|       ↕               |                                           |
|  (multi-turn     Emergency → [ Notification Service ]             |
|   patient chat)  Low conf → [ Nurse Queue ]                       |
+===================================================================+
         |                    |                    |
         v                    v                    v
+------------------+  +--------------+  +-------------------+
| DynamoDB         |  | SNS + PagerDuty| | External Systems |
| (Sessions, SOAP, |  | (Escalation)   | | (EHR, Pharmacy,  |
|  Audit, Consent) |  +--------------+  |  Scheduling)     |
+------------------+                    +-------------------+
         |                                     (stubbed for MVP)
         v
+------------------+
| KMS (Encryption) |
| CloudWatch (Logs)|
| PHI Redaction    |
+------------------+
```

---

## Key Architecture Decisions

| Decision | Choice | Why |
|---|---|---|
| Agent orchestration | Step Functions Hybrid (Express + Standard) | Express for 95% of sessions (<5 min, cheaper). Standard triggered only for nurse handoff (unbounded wait). Explicit control over escalation branching, callback patterns, audit trail |
| Agent framework | Strands Agents SDK | Full control, custom tools, any Bedrock model, deployable to Lambda |
| State machine type | Hybrid: Express primary + Standard for nurse path | Express is ~6x cheaper at scale for short sessions; Standard handles unbounded nurse wait without timeout risk |
| Chat protocol | API Gateway WebSocket | Real-time bidirectional needed for streaming AI responses |
| Data store | DynamoDB | Serverless, encrypted by default, single-digit ms latency, HIPAA-eligible |
| Auth | Cognito Custom Auth + SMS | Matches patient preference (no password to remember), HIPAA-eligible |
| Frontend hosting | Amplify Hosting or CloudFront+S3 | Static site, no server needed, global CDN |
| PHI redaction | Lambda Layer (shared) | Consistent across all functions, single point of maintenance |
| Notifications | EventBridge → Lambda → SNS/PagerDuty | Decoupled, retryable, auditable |
| IaC | CDK TypeScript | Matches frontend language, strong typing for infra |

---

## Security Architecture

| Layer | Control |
|---|---|
| Network | API Gateway (public endpoints only), no VPC needed for MVP (all serverless) |
| Transport | TLS 1.2+ enforced on all APIs |
| Authentication | Cognito (SMS/email OTP + DOB), JWT token validation on every request |
| Authorization | Cognito groups (patient, nurse, physician, admin) + Lambda authorizer |
| Encryption at rest | DynamoDB encryption (KMS CMK), S3 encryption (KMS CMK) |
| Encryption in transit | TLS everywhere, WebSocket over WSS |
| Logging | CloudWatch with PHI Redaction Layer applied to all functions |
| Audit | DynamoDB AuditTrail table — immutable append-only |
| Key management | AWS KMS customer-managed keys, separate keys per data classification |

---

## Components Summary

| # | Component | Type | Deployment |
|---|---|---|---|
| 1 | Shared Infrastructure | CDK Stack | CloudFormation |
| 2 | Symptom Assessment Agent | Strands Agent | Lambda |
| 3 | Triage Scoring Agent | Strands Agent | Lambda |
| 4 | Drug Interaction Agent | Strands Agent | Lambda |
| 5 | Specialist Routing Agent | Strands Agent | Lambda |
| 6 | Clinical Summary Agent | Strands Agent | Lambda |
| 7 | Supervisor Agent | Step Functions + Lambda | Step Functions |
| 8 | Patient Portal | React App | Amplify/CloudFront |
| 9 | Notification Service | Event-driven | Lambda + SNS + EventBridge |
| 10 | PHI Redaction Layer | Lambda Layer | Shared Layer |

---

## AWS Services Used (HIPAA-Eligible)

| Service | Purpose | HIPAA Eligible |
|---|---|---|
| Amazon Bedrock | LLM inference (Claude) | Yes |
| AWS Lambda | Agent execution, API handlers | Yes |
| AWS Step Functions | Triage orchestration | Yes |
| Amazon DynamoDB | Data persistence | Yes |
| Amazon API Gateway | REST + WebSocket APIs | Yes |
| Amazon Cognito | Patient authentication | Yes |
| Amazon SNS | SMS notifications | Yes |
| Amazon EventBridge | Event routing | Yes |
| AWS KMS | Encryption key management | Yes |
| Amazon CloudWatch | Logging + monitoring | Yes |
| Amazon S3 / CloudFront | Frontend hosting | Yes |

---

## Detailed Design References

- **Components**: `components.md` — full component definitions
- **Methods**: `component-methods.md` — method signatures and schemas
- **Services**: `services.md` — service layer and orchestration patterns
- **Dependencies**: `component-dependency.md` — dependency matrix and data flow

---

## What's NOT in This Design (Deferred to Construction)

- Exact urgency scoring algorithm (Functional Design — Triage Scoring unit)
- Symptom-to-department mapping table (Functional Design — Specialist Routing unit)
- SOAP note prompt templates (Functional Design — Clinical Summary unit)
- CDK construct details (Infrastructure Design — per unit)
- NFR implementation patterns (NFR Design — per unit)
- Detailed API request/response schemas (Code Generation — per unit)
