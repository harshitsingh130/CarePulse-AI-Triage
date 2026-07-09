# Requirements Document: Healthcare Network Patient Triage System

## Intent Analysis

| Attribute | Value |
|---|---|
| **Customer** | Healthcare Network |
| **Request Type** | New Project (Greenfield) |
| **Scope** | System-wide — Multi-component AI healthcare platform |
| **Complexity** | Complex — Regulated healthcare, AI/LLM integration, multi-clinic, real-time escalation |
| **App Level** | MVP — 6-8 weeks, full triage + portal, 3-5 clinic rollout |
| **Industry** | Healthcare (HIPAA-regulated) |

## User Request Summary

Build a 24/7 digital patient triage system for Healthcare Network that handles 1200+ daily inquiries across 15 clinics. The system uses AI/LLM (Amazon Bedrock) to conduct conversational symptom assessment, score urgency, route to specialists, and generate clinical notes — all under strict HIPAA compliance.

---

## Functional Requirements

### FR-001: Conversational Symptom Assessment
| Attribute | Detail |
|---|---|
| **Description** | Conduct conversational symptom assessment covering onset, severity (1-10 scale), duration, and medical history |
| **Interface** | Both web and mobile (responsive web + native mobile app) |
| **Language** | English only (architecture must be extensible for future languages) |
| **AI Engine** | Amazon Bedrock LLM with structured clinical prompting |
| **Uncertainty Handling** | Ask up to 3 additional clarifying questions. If ambiguity remains, escalate to immediate human assistance |

### FR-002: Urgency Level Assignment
| Attribute | Detail |
|---|---|
| **Description** | Assign urgency level based on symptom assessment |
| **Levels** | Emergency / Urgent / Standard / Routine |
| **Consistency** | Scoring algorithm must produce consistent results across all clinics |
| **Auditability** | Every scoring decision must be logged with reasoning |

### FR-003: Emergency Escalation
| Attribute | Detail |
|---|---|
| **Description** | Immediately escalate Emergency cases to on-call staff |
| **Mechanism** | All of: Push notification + SMS to on-call physician, auto-page via paging system (PagerDuty/Opsgenie), and offer patient transfer to live call |
| **Latency** | Escalation must trigger within 30 seconds of Emergency classification |
| **Patient Summary** | Structured summary sent with escalation (symptoms, severity, history, medications) |

### FR-004: Drug Interaction Checking
| Attribute | Detail |
|---|---|
| **Description** | Check patient current medications for dangerous drug interactions |
| **Data Source** | Interface with hospital pharmacy system for real-time medication data |
| **Trigger** | Automatically during triage when patient reports medications or when EHR medication list is retrieved |
| **Alert** | Flag dangerous interactions to both patient and receiving physician |

### FR-005: Specialist Routing
| Attribute | Detail |
|---|---|
| **Description** | Route to appropriate specialist department based on symptom pattern |
| **Departments** | 5-10 departments (e.g., Cardiology, Neurology, Orthopedics, GI, Pulmonology, Dermatology, ENT, Urology, Psychiatry) |
| **Logic** | Pattern matching based on symptom clusters mapped to specialties |
| **Availability** | Check specialist availability before routing (clinic scheduling integration) |

### FR-006: SOAP Note Generation
| Attribute | Detail |
|---|---|
| **Description** | Generate structured clinical note in SOAP format for the receiving physician |
| **Format** | Subjective, Objective, Assessment, Plan |
| **Content** | Auto-populated from triage conversation, urgency score, routing decision |
| **Delivery** | Push to EHR (Epic FHIR R4 — stubbed/mocked for MVP) |

### FR-007: PHI Encryption
| Attribute | Detail |
|---|---|
| **Description** | Ensure all PHI is encrypted at rest and in transit |
| **At Rest** | AES-256 encryption on all data stores (DynamoDB, S3, etc.) |
| **In Transit** | TLS 1.2+ enforced on all connections |
| **Key Management** | AWS KMS with customer-managed keys |

### FR-008: PHI Log Redaction
| Attribute | Detail |
|---|---|
| **Description** | Redact PHI from all application logs |
| **Scope** | All CloudWatch logs, application logs, API Gateway logs |
| **Method** | Automated PII/PHI detection and redaction at write time |
| **Audit** | Redaction effectiveness must be testable |

### FR-009: Consent Tracking
| Attribute | Detail |
|---|---|
| **Description** | Maintain patient consent tracking for data processing |
| **Consent Types** | Data processing, AI-assisted triage, data sharing with specialists |
| **Revocation** | Patients must be able to revoke consent |
| **Audit Trail** | All consent grants and revocations logged with timestamp |

### FR-010: Patient Portal
| Attribute | Detail |
|---|---|
| **Description** | Provide patient-facing portal with triage status and appointment details |
| **Features** | Real-time triage status, appointment scheduling, specialist assignment, chat history |
| **Authentication** | SMS/email verification + date of birth. Emergency: generic (non-PHI) info accessible without auth; PHI always behind authentication |
| **Interface** | Web and mobile (same platform as triage chat) |

---

## Non-Functional Requirements

### NFR-001: Performance
| Attribute | Target |
|---|---|
| **Triage Time** | < 3 minutes per patient (down from 12-20 minutes) |
| **Response Latency** | < 2 seconds for AI-generated responses |
| **Escalation Latency** | < 30 seconds for Emergency classification to notification |
| **Concurrent Users** | Support 1200+ daily inquiries (peak ~150 concurrent) |

### NFR-002: Availability
| Attribute | Target |
|---|---|
| **Uptime** | 99.9% (single region with robust auto-scaling) |
| **Architecture** | Single AWS region, multi-AZ |
| **Recovery** | Auto-scaling, health checks, automatic failover within AZs |
| **24/7 Operation** | No maintenance windows that affect triage availability |

### NFR-003: Security & Compliance
| Attribute | Target |
|---|---|
| **Standard** | HIPAA compliant (PHI protection end-to-end) |
| **Encryption** | AES-256 at rest, TLS 1.2+ in transit |
| **Access Control** | Role-based (patient, nurse, physician, admin) |
| **Audit** | Full audit trail for all triage decisions |
| **BAA** | AWS BAA required for all services processing PHI |

### NFR-004: Scalability
| Attribute | Target |
|---|---|
| **Current** | 1200+ daily inquiries, 15 clinics |
| **MVP Scope** | 3-5 clinic rollout |
| **Design** | Architecture must support scale to 15 clinics without redesign |

### NFR-005: Extensibility
| Attribute | Target |
|---|---|
| **Languages** | English now; architecture supports adding languages |
| **Departments** | 5-10 now; extensible to 20+ |
| **Clinics** | 3-5 MVP; scalable to 15+ |
| **EHR Integration** | Epic FHIR R4 stubbed for MVP; real integration path clear |

---

## Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Cloud Platform** | AWS | Customer preference, HIPAA-eligible services |
| **AI/LLM** | Amazon Bedrock | Managed, HIPAA-eligible, no PHI in model training |
| **IaC** | AWS CDK (TypeScript) | Customer preference |
| **EHR Integration** | Epic FHIR R4 (mock/stub for MVP) | Most common healthcare EHR, clean API |
| **Drug Interactions** | Hospital pharmacy system interface | Real-time, authoritative source |
| **Availability** | Single region, multi-AZ, 99.9% | Cost-optimized for MVP |
| **Authentication** | SMS/email + DOB verification | Simple, accessible; emergency bypass for non-PHI |

---

## Integration Points

| System | Direction | Protocol | MVP Status |
|---|---|---|---|
| EHR (Epic) | Bidirectional | FHIR R4 REST API | Stubbed/mocked |
| Clinic Scheduling | Read + Write | REST API | Stubbed (scheduling queries) |
| Specialist Routing | Internal | Event-driven | Real implementation |
| Hospital Pharmacy | Read | HL7/FHIR | Stubbed/mocked |
| Paging System (PagerDuty) | Write | Webhook/API | Real implementation |
| SMS Gateway (SNS) | Write | AWS SNS | Real implementation |

---

## Extension Configuration

| Extension | Enabled | Rationale |
|---|---|---|
| Resiliency Baseline | Yes | Healthcare 24/7 system — resiliency design guidance critical |
| Security Baseline | Partial (MVP-scoped) | HIPAA requires strong security; enforce core rules (encryption, access control, logging, input validation) but defer full supply-chain and CI/CD hardening to Production |
| Property-Based Testing | Partial | PBT for urgency scoring algorithm and SOAP serialization; skip for UI and integration layers |

### Security Rules Enforcement for MVP

| Rule | Enforced | Rationale |
|---|---|---|
| SECURITY-01: Encryption at rest/transit | Yes | HIPAA mandatory |
| SECURITY-02: Access logging | Yes | HIPAA audit requirement |
| SECURITY-03: Application-level logging | Yes | HIPAA audit requirement |
| SECURITY-04: HTTP security headers | Yes | Web application baseline |
| SECURITY-05: Input validation | Yes | Healthcare data integrity |
| SECURITY-06: Least-privilege IAM | Yes | HIPAA minimum necessary |
| SECURITY-07: Network configuration | Yes | PHI network segmentation |
| SECURITY-08: Application access control | Yes | PHI access control |
| SECURITY-09: Hardening/misconfiguration | Yes | Healthcare compliance |
| SECURITY-10: Supply chain security | Deferred | Full SBOM/scanning for Production phase |
| SECURITY-11: Secure design principles | Yes | Core architecture |
| SECURITY-12: Auth/credential management | Yes | Patient authentication |
| SECURITY-13: Integrity verification | Deferred | Full SRI/pipeline for Production phase |
| SECURITY-14: Alerting and monitoring | Yes | HIPAA breach detection |
| SECURITY-15: Exception handling | Yes | Fail-safe for healthcare |

---

## Constraints

- HIPAA compliant (PHI protection end-to-end)
- 24/7 availability (99.9% uptime target)
- Consistent urgency scoring across all clinics
- Full audit trail for all triage decisions
- Reduce triage time from 12-20 minutes to under 3 minutes
- MVP: 6-8 week timeline, 3-5 clinic rollout
- All AWS services must be HIPAA-eligible and covered under BAA

---

## Acceptance Criteria Summary

| Criteria | Verification |
|---|---|
| Patient completes triage in < 3 minutes | End-to-end timing test |
| Emergency cases escalated within 30 seconds | Latency measurement |
| Urgency scoring is consistent (same inputs = same output) | Deterministic test suite |
| All PHI encrypted at rest and in transit | Infrastructure audit |
| No PHI in application logs | Log scanning test |
| SOAP note generated for every completed triage | Integration test |
| Patient portal shows real-time triage status | UI functional test |
| Drug interactions flagged when present | Clinical scenario test |
| System available 99.9% over measurement period | Uptime monitoring |
