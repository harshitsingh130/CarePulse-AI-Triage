# Component Dependencies

## Dependency Matrix

```
                         Shared   Symptom  Triage   Drug     Specialist  Clinical  Supervisor  Portal  Notification  PHI
                         Infra    Assess   Scoring  Interact Routing     Summary   Agent       App     Service       Redaction
Shared Infrastructure     -        -        -        -        -           -         -           -       -             -
Symptom Assessment Agent  ✓        -        -        -        -           -         -           -       -             ✓
Triage Scoring Agent      ✓        -        -        -        -           -         -           -       -             ✓
Drug Interaction Agent    ✓        -        -        -        -           -         -           -       -             ✓
Specialist Routing Agent  ✓        -        -        -        -           -         -           -       -             ✓
Clinical Summary Agent    ✓        -        -        -        -           -         -           -       -             ✓
Supervisor Agent          ✓        ✓        ✓        ✓        ✓           ✓         -           -       ✓             ✓
Patient Portal            ✓        -        -        -        -           -         -           -       -             -
Notification Service      ✓        -        -        -        -           -         -           -       -             ✓
PHI Redaction Layer       -        -        -        -        -           -         -           -       -             -
```

Legend: ✓ = depends on (calls or uses)

---

## Communication Patterns

### Synchronous (Request/Response)
| From | To | Pattern | Protocol |
|---|---|---|---|
| Portal → API Gateway | Chat Service | WebSocket | WSS |
| Portal → API Gateway | Portal API | REST | HTTPS |
| Supervisor → Symptom Assessment | Agent invocation | Lambda invoke | AWS SDK |
| Supervisor → Triage Scoring | Agent invocation | Lambda invoke | AWS SDK |
| Supervisor → Drug Interaction | Agent invocation | Lambda invoke | AWS SDK |
| Supervisor → Specialist Routing | Agent invocation | Lambda invoke | AWS SDK |
| Supervisor → Clinical Summary | Agent invocation | Lambda invoke | AWS SDK |
| Drug Interaction → Pharmacy System | External API | REST/HL7 | HTTPS (stubbed) |
| Specialist Routing → Scheduling | External API | REST | HTTPS (stubbed) |

### Asynchronous (Event-Driven)
| From | To | Pattern | Protocol |
|---|---|---|---|
| Supervisor → Notification Service | Emergency escalation | EventBridge event | JSON |
| Notification → PagerDuty | Paging | Webhook | HTTPS |
| Notification → SNS | SMS/Push | SNS Publish | AWS SDK |
| Supervisor → Portal | Status update | WebSocket push | WSS |
| Nurse Dashboard → Supervisor | Classification override | Step Functions callback | AWS SDK |

---

## Data Flow Diagram

```
+--------+     WebSocket      +-------------+     Start       +------------------+
| Patient| ←──────────────→  | Chat Service | ────────────→  | Supervisor       |
| Portal |                    | (API GW WS) |                | (Step Functions) |
+--------+                    +-------------+                +------------------+
    |                                                              |
    | REST (status,                                    Invokes sequentially:
    | appointments)                                        |
    v                                                      v
+--------+                                    +------------------------+
| Portal |                                    | 1. Symptom Assessment  |
| API    |                                    |    Agent (Lambda)      |
| (REST) |                                    +------------------------+
+--------+                                              |
                                                        v
                                              +------------------------+
                                              | 2. Triage Scoring      |
                                              |    Agent (Lambda)      |
                                              +------------------------+
                                                   |         |
                                          Emergency|         |Low confidence
                                                   v         v
                                    +------------+   +--------------+
                                    | Notification|  | Nurse Queue  |
                                    | Service     |  | (DynamoDB +  |
                                    | (Lambda+SNS)|  |  WebSocket)  |
                                    +------------+   +--------------+
                                                        |
                                              Normal flow continues:
                                                        v
                                              +------------------------+
                                              | 3. Drug Interaction    |
                                              |    Agent (Lambda)      |
                                              +------------------------+
                                                        |
                                                        v
                                              +------------------------+
                                              | 4. Specialist Routing  |
                                              |    Agent (Lambda)      |
                                              +------------------------+
                                                        |
                                                        v
                                              +------------------------+
                                              | 5. Clinical Summary    |
                                              |    Agent (Lambda)      |
                                              +------------------------+
                                                        |
                                                        v
                                              +------------------------+
                                              |    DynamoDB            |
                                              |  (Sessions, SOAP,     |
                                              |   Audit, Appointments) |
                                              +------------------------+
```

---

## Build Order (Dependency-Driven)

| Order | Component | Rationale |
|---|---|---|
| 1 | Shared Infrastructure | All components depend on it (DynamoDB, KMS, Cognito, API GW) |
| 2 | PHI Redaction Layer | Must exist before any agent writes logs |
| 3 | Symptom Assessment Agent | First in pipeline, independent logic |
| 4 | Triage Scoring Agent | Depends on Symptom Assessment output format |
| 5 | Drug Interaction Agent | Independent (parallel with Routing) |
| 6 | Specialist Routing Agent | Independent (parallel with Drug Check) |
| 7 | Clinical Summary Agent | Depends on all agent output formats |
| 8 | Notification Service | Independent, consumed by Supervisor |
| 9 | Supervisor Agent | Orchestrates all above — must be built after them |
| 10 | Patient Portal | Frontend consumes all backend services |
