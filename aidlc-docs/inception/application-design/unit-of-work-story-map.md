# Unit of Work — Story Map

## Story-to-Unit Assignment

| Story | Title | Primary Unit | Secondary Units |
|---|---|---|---|
| US-001 | Patient Initiates Triage | Unit 8 (Portal) | Unit 7 (Supervisor - session start) |
| US-002 | Patient Completes Symptom Assessment | Unit 2 (Symptom Assessment) | Unit 7 (orchestration) |
| US-003 | Patient Receives Urgency Classification | Unit 3 (Triage Scoring) | Unit 8 (Portal - display) |
| US-004 | Emergency Case Triggers Escalation | Unit 7 (Supervisor) | — |
| US-005 | On-Call Physician Receives Notification | Unit 7 (Notification Service) | — |
| US-006 | Patient Offered Live Transfer | Unit 7 (Supervisor) | Unit 8 (Portal - transfer UI) |
| US-007 | System Checks Drug Interactions | Unit 4 (Drug Interaction) | — |
| US-008 | Dangerous Interactions Alerted | Unit 4 (Drug Interaction) | Unit 6 (flags in SOAP) |
| US-009 | Patient Routed to Specialist | Unit 5 (Specialist Routing) | Unit 8 (Portal - slots display) |
| US-010 | Specialist Receives Patient Context | Unit 6 (Clinical Summary) | Unit 5 (routing reasoning) |
| US-011 | SOAP Note Generated | Unit 6 (Clinical Summary) | — |
| US-012 | Physician Reviews SOAP Note | Unit 6 (Clinical Summary) | — |
| US-013 | Patient Data Encrypted End-to-End | Unit 1 (Infrastructure) | All units (enforcement) |
| US-014 | PHI Redacted From Logs | Unit 1 (Infrastructure) | agents/shared (redaction layer) |
| US-015 | Patient Manages Consent | Unit 8 (Portal) | Unit 1 (DynamoDB consent table) |
| US-016 | Patient Views Triage Status | Unit 8 (Portal) | Unit 7 (status updates) |
| US-017 | Patient Views Appointment Details | Unit 8 (Portal) | Unit 5 (routing data) |
| US-018 | Patient Authenticates via SMS/Email | Unit 1 (Cognito) | Unit 8 (Portal - auth UI) |
| US-019 | AI Asks Clarifying Questions | Unit 2 (Symptom Assessment) | Unit 3 (confidence check) |
| US-020 | Ambiguous Case Escalated to Nurse | Unit 7 (Supervisor) | Unit 8 (nurse dashboard) |

---

## Unit-to-Story Summary

### Unit 1: Shared Infrastructure
| Stories | Role |
|---|---|
| US-013 | Primary — encryption enforcement via CDK |
| US-014 | Primary — PHI redaction log filters |
| US-018 | Primary — Cognito custom auth configuration |

### Unit 2: Symptom Assessment Agent
| Stories | Role |
|---|---|
| US-002 | Primary — conversation logic |
| US-019 | Primary — clarifying questions when uncertain |
| US-001 | Secondary — agent receives first message |

### Unit 3: Triage Scoring Agent
| Stories | Role |
|---|---|
| US-003 | Primary — urgency classification |
| US-019 | Secondary — confidence scoring triggers clarification |

### Unit 4: Drug Interaction Agent
| Stories | Role |
|---|---|
| US-007 | Primary — medication checking logic |
| US-008 | Primary — alerting for dangerous interactions |

### Unit 5: Specialist Routing Agent
| Stories | Role |
|---|---|
| US-009 | Primary — symptom-to-department mapping |
| US-010 | Secondary — provides routing reasoning for specialist |

### Unit 6: Clinical Summary Agent
| Stories | Role |
|---|---|
| US-011 | Primary — SOAP note generation |
| US-012 | Primary — note format for physician consumption |
| US-010 | Secondary — includes routing context in note |
| US-008 | Secondary — flags interactions in Assessment section |

### Unit 7: Supervisor & Notification
| Stories | Role |
|---|---|
| US-004 | Primary — emergency escalation trigger |
| US-005 | Primary — multi-channel notification delivery |
| US-006 | Primary — live transfer offer |
| US-020 | Primary — nurse handoff (Standard workflow) |
| US-001 | Secondary — session initialization |
| US-002 | Secondary — orchestrates symptom loop |

### Unit 8: Patient Portal
| Stories | Role |
|---|---|
| US-001 | Primary — triage initiation UI |
| US-015 | Primary — consent management UI |
| US-016 | Primary — real-time status display |
| US-017 | Primary — appointment details view |
| US-018 | Primary — auth UI (SMS/email + DOB) |
| US-003 | Secondary — urgency result display |
| US-006 | Secondary — live transfer UI |
| US-009 | Secondary — available slots display |
| US-020 | Secondary — nurse dashboard (separate view) |

---

## Coverage Verification

- **Total stories**: 20
- **Stories assigned to units**: 20 ✓
- **Unassigned stories**: 0 ✓
- **All units have at least 2 stories**: ✓
- **No story orphaned without a primary unit**: ✓
