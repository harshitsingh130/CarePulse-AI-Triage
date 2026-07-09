# Unit of Work — Dependency Matrix

## Dependency Graph

```
Unit 1: Shared Infrastructure
    |
    +-------+-------+-------+-------+
    |       |       |       |       |
    v       v       v       v       v
  Unit 2  Unit 3  Unit 4  Unit 5  Unit 6
  Symptom  Triage  Drug    Routing Clinical
  Assess   Score   Interact        Summary
    |       |       |       |       |
    |       v       |       |       |
    +-----> Unit 3  |       |       |
    |    (needs U2  |       |       |
    |     output    |       |       |
    |     format)   v       v       v
    |               |       |       |
    +-------+-------+-------+-------+
            |
            v
        Unit 7: Supervisor & Notification
        (invokes all agents, orchestrates pipeline)
            |
            v
        Unit 8: Patient Portal
        (consumes all backend services)
```

## Dependency Table

| Unit | Depends On | Dependency Type | What It Needs |
|---|---|---|---|
| 1. Shared Infrastructure | None | — | — |
| 2. Symptom Assessment | Unit 1 | Infrastructure | DynamoDB, KMS, Bedrock IAM role |
| 3. Triage Scoring | Unit 1, Unit 2 | Infrastructure + Data contract | DynamoDB + StructuredSymptoms JSON schema from Unit 2 |
| 4. Drug Interaction | Unit 1 | Infrastructure | DynamoDB, KMS, external pharmacy stub |
| 5. Specialist Routing | Unit 1, Unit 3 | Infrastructure + Data contract | DynamoDB + UrgencyResult JSON from Unit 3 |
| 6. Clinical Summary | Unit 1, Units 2-5 | Infrastructure + Data contracts | All agent output schemas |
| 7. Supervisor & Notification | Unit 1, Units 2-6 | Infrastructure + All agents | Lambda ARNs, DynamoDB, SNS, WebSocket API |
| 8. Patient Portal | Unit 1, Unit 7 | Infrastructure + APIs | Cognito, REST API, WebSocket API |

## Critical Path

```
Unit 1 → Unit 2 → Unit 3 → Unit 7 → Unit 8
                      ↓
               (Units 4, 5 parallel)
                      ↓
                   Unit 6
```

**Longest path**: 1 → 2 → 3 → 7 → 8 (~5.5 sessions)  
**With parallelization** (Units 4+5 parallel, Unit 6 after): ~7.5 sessions total

## Shared Data Contracts (Cross-Unit Interfaces)

These JSON schemas are defined in `agents/shared/models.py` and consumed by multiple units:

| Schema | Producer | Consumers |
|---|---|---|
| `StructuredSymptoms` | Unit 2 (Symptom Assessment) | Unit 3, Unit 6, Unit 7 |
| `UrgencyResult` | Unit 3 (Triage Scoring) | Unit 5, Unit 6, Unit 7 |
| `InteractionResult` | Unit 4 (Drug Interaction) | Unit 6, Unit 7 |
| `RoutingDecision` | Unit 5 (Specialist Routing) | Unit 6, Unit 7, Unit 8 |
| `SOAPNote` | Unit 6 (Clinical Summary) | Unit 7, Unit 8 |
| `EscalationEvent` | Unit 7 (Supervisor) | Notification Service (within Unit 7) |
| `TriageSession` | Unit 7 (Supervisor) | Unit 8 (Portal) |

## Build & Integration Strategy

| Phase | Units Built | Integration Test |
|---|---|---|
| Phase 1 | Unit 1 (infrastructure) | CDK deploy succeeds, resources accessible |
| Phase 2 | Unit 2 (symptom agent) | Agent responds to sample conversation |
| Phase 3 | Unit 3 (scoring agent) | Scoring produces consistent urgency from same input |
| Phase 4 | Units 4 + 5 (drug + routing) | Both agents callable with stubbed external services |
| Phase 5 | Unit 6 (clinical summary) | SOAP note generated from all agent outputs |
| Phase 6 | Unit 7 (supervisor) | Full pipeline runs end-to-end (Express workflow completes) |
| Phase 7 | Unit 8 (portal) | Patient can chat, see status, view appointments |
| Final | All units | End-to-end: patient starts triage → receives appointment |

## Parallelization Opportunities

| Parallel Group | Units | Why Possible |
|---|---|---|
| Group A | Unit 4 (Drug) + Unit 5 (Routing) | Independent agents, both only depend on Unit 1 infrastructure. Unit 5 needs Unit 3's output format (schema) but not its running code. |
| Group B | Unit 6 (Summary) + Unit 7 start | Summary only needs output schemas; Supervisor scaffolding can begin before Summary is complete |
