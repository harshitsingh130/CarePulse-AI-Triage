# Units of Work

## Decomposition Strategy

**Approach**: Service-based decomposition aligned to agent boundaries  
**Deployment Model**: Serverless (Lambda + Step Functions + DynamoDB)  
**Code Organization**: Monorepo with per-unit directories  
**Language**: Python (agents) + TypeScript (CDK infrastructure + React frontend)

---

## Project Structure (Greenfield)

```
healthcare-triage/
├── infrastructure/              # Unit 1: Shared CDK infrastructure
│   ├── lib/
│   │   ├── shared-stack.ts     # DynamoDB, KMS, Cognito, API GW
│   │   ├── agents-stack.ts     # Lambda functions for all agents
│   │   ├── orchestration-stack.ts  # Step Functions state machines
│   │   └── portal-stack.ts     # CloudFront + S3 for frontend
│   ├── bin/
│   │   └── app.ts
│   ├── cdk.json
│   ├── package.json
│   └── tsconfig.json
├── agents/                      # Units 2-6: Agent source code
│   ├── shared/                  # Shared utilities across agents
│   │   ├── models.py           # Common data models (Pydantic)
│   │   ├── phi_redaction.py    # PHI redaction layer
│   │   ├── db.py               # DynamoDB access helpers
│   │   └── config.py           # Environment config
│   ├── symptom_assessment/      # Unit 2
│   │   ├── handler.py
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── tests/
│   ├── triage_scoring/          # Unit 3
│   │   ├── handler.py
│   │   ├── agent.py
│   │   ├── scoring_logic.py
│   │   └── tests/
│   ├── drug_interaction/        # Unit 4
│   │   ├── handler.py
│   │   ├── agent.py
│   │   ├── pharmacy_client.py
│   │   └── tests/
│   ├── specialist_routing/      # Unit 5
│   │   ├── handler.py
│   │   ├── agent.py
│   │   ├── department_map.py
│   │   └── tests/
│   ├── clinical_summary/        # Unit 6
│   │   ├── handler.py
│   │   ├── agent.py
│   │   ├── soap_templates.py
│   │   └── tests/
│   └── requirements.txt
├── orchestration/               # Unit 7: Supervisor + Notification
│   ├── state_machines/
│   │   ├── triage_express.asl.json
│   │   └── nurse_handoff_standard.asl.json
│   ├── lambdas/
│   │   ├── decision_logic.py
│   │   ├── notification_handler.py
│   │   ├── chat_connect.py
│   │   ├── chat_message.py
│   │   └── chat_disconnect.py
│   └── tests/
├── portal/                      # Unit 8: Patient Portal
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   └── types/
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── aidlc-docs/                  # AI-DLC documentation (not deployed)
└── README.md
```

---

## Unit 1: Shared Infrastructure

| Attribute | Detail |
|---|---|
| **Type** | CDK Infrastructure Stack |
| **Language** | TypeScript |
| **Purpose** | Provision all shared AWS resources consumed by other units |
| **Deploys** | DynamoDB tables (6), KMS keys (2), Cognito User Pool, API Gateway (REST + WebSocket), SNS topics, CloudWatch log groups with redaction filters, IAM roles |
| **Build Order** | First — all other units depend on this |
| **Estimated Effort** | 1 session |

### Resources Provisioned:
- DynamoDB: Sessions, Patients, Conversations, Notifications, AuditTrail, Appointments
- KMS: PHI encryption key (CMK), general encryption key
- Cognito: User Pool with custom auth flow (SMS/email + DOB)
- API Gateway: REST API (portal endpoints) + WebSocket API (chat)
- SNS: Emergency notification topic
- CloudWatch: Log groups with subscription filters for PHI redaction
- IAM: Per-agent execution roles (least privilege)

---

## Unit 2: Symptom Assessment Agent

| Attribute | Detail |
|---|---|
| **Type** | AI Agent (Strands SDK) |
| **Language** | Python |
| **Purpose** | Conversational symptom intake with structured clinical questions |
| **Deploys** | 1 Lambda function |
| **Dependencies** | Unit 1 (DynamoDB, KMS, Bedrock access) |
| **Key Logic** | Multi-turn conversation management, structured data extraction, completeness detection |
| **Stories** | US-001, US-002, US-019 |
| **Estimated Effort** | 1 session |

---

## Unit 3: Triage Scoring Agent

| Attribute | Detail |
|---|---|
| **Type** | AI Agent (Strands SDK) |
| **Language** | Python |
| **Purpose** | Assign urgency level using clinical guidelines + confidence scoring |
| **Deploys** | 1 Lambda function |
| **Dependencies** | Unit 1 (DynamoDB), Unit 2 (output format) |
| **Key Logic** | Urgency classification algorithm, confidence scoring, deterministic consistency across clinics |
| **Stories** | US-003, US-019 |
| **Estimated Effort** | 1 session |
| **PBT Target** | Yes — scoring function is a prime property-based testing candidate |

---

## Unit 4: Drug Interaction Agent

| Attribute | Detail |
|---|---|
| **Type** | AI Agent (Strands SDK) with tool access |
| **Language** | Python |
| **Purpose** | Check medications for dangerous interactions via pharmacy system |
| **Deploys** | 1 Lambda function |
| **Dependencies** | Unit 1 (DynamoDB, KMS), External: Hospital Pharmacy System (stubbed) |
| **Key Logic** | Pharmacy API client (stubbed for MVP), interaction severity classification, graceful degradation when pharmacy unavailable |
| **Stories** | US-007, US-008 |
| **Estimated Effort** | 0.5 session |

---

## Unit 5: Specialist Routing Agent

| Attribute | Detail |
|---|---|
| **Type** | AI Agent (Strands SDK) with tool access |
| **Language** | Python |
| **Purpose** | Map symptoms to departments and check specialist availability |
| **Deploys** | 1 Lambda function |
| **Dependencies** | Unit 1 (DynamoDB), Unit 3 (urgency level), External: Scheduling System (stubbed) |
| **Key Logic** | Symptom-to-department mapping (5-10 specialties), availability checking, alternative clinic suggestion |
| **Stories** | US-009, US-010 |
| **Estimated Effort** | 0.5 session |

---

## Unit 6: Clinical Summary Agent

| Attribute | Detail |
|---|---|
| **Type** | AI Agent (Strands SDK) |
| **Language** | Python |
| **Purpose** | Generate SOAP-format clinical notes from all triage session data |
| **Deploys** | 1 Lambda function |
| **Dependencies** | Unit 1 (DynamoDB), Units 2-5 (all agent outputs) |
| **Key Logic** | SOAP note assembly, template-driven generation, FHIR formatting (stubbed), no hallucinated clinical data |
| **Stories** | US-011, US-012 |
| **Estimated Effort** | 0.5 session |
| **PBT Target** | Yes — SOAP serialization round-trip testing |

---

## Unit 7: Supervisor & Notification (Orchestration)

| Attribute | Detail |
|---|---|
| **Type** | Step Functions + Event-driven services |
| **Language** | Python (Lambdas) + JSON (ASL state machine definitions) |
| **Purpose** | Orchestrate triage pipeline, handle escalation, manage chat WebSocket, nurse handoff |
| **Deploys** | 2 Step Functions state machines (Express + Standard) + 5 Lambda functions (decision logic, notification handler, chat connect/message/disconnect) |
| **Dependencies** | Unit 1 (all infrastructure), Units 2-6 (invokes all agents) |
| **Key Logic** | Pipeline sequencing, emergency escalation (multi-channel), nurse handoff (Standard workflow callback), WebSocket connection management, physician acknowledgement tracking |
| **Stories** | US-004, US-005, US-006, US-020 |
| **Estimated Effort** | 1.5 sessions |

---

## Unit 8: Patient Portal

| Attribute | Detail |
|---|---|
| **Type** | Web Application (React) |
| **Language** | TypeScript (React + Vite) |
| **Purpose** | Patient-facing UI for triage chat, status, appointments, consent, authentication |
| **Deploys** | Static site (CloudFront + S3 or Amplify Hosting) |
| **Dependencies** | Unit 1 (Cognito, API Gateway), Unit 7 (WebSocket for chat) |
| **Key Logic** | WebSocket chat integration, SMS/email auth flow, real-time status updates, consent management UI, appointment display |
| **Stories** | US-001, US-003, US-006, US-013, US-015, US-016, US-017, US-018 |
| **Estimated Effort** | 1.5 sessions |

---

## Summary

| Unit | Name | Language | Effort | Build Order |
|---|---|---|---|---|
| 1 | Shared Infrastructure | TypeScript (CDK) | 1 session | 1st |
| 2 | Symptom Assessment Agent | Python | 1 session | 2nd |
| 3 | Triage Scoring Agent | Python | 1 session | 3rd |
| 4 | Drug Interaction Agent | Python | 0.5 session | 4th (parallel with 5) |
| 5 | Specialist Routing Agent | Python | 0.5 session | 4th (parallel with 4) |
| 6 | Clinical Summary Agent | Python | 0.5 session | 5th |
| 7 | Supervisor & Notification | Python + ASL | 1.5 sessions | 6th |
| 8 | Patient Portal | TypeScript (React) | 1.5 sessions | 7th (last) |

**Total estimated effort**: ~7.5 sessions
