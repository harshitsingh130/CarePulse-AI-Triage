# Business Rules — Supervisor & Notification Agent

## BR-SV-001: Pipeline Never Blocks on External Dependency

**Rule**: The triage pipeline MUST NOT block on external systems (pharmacy, scheduling, PagerDuty). If any external call fails or times out, the pipeline continues with degraded data.

| External Dependency | Timeout | Degraded Behavior |
|---|---|---|
| Hospital Pharmacy (Drug Check) | 3s | `check_status: unavailable`, SOAP flags it |
| Scheduling System (Routing) | 2s per clinic | `status: no_availability`, patient advised to call |
| PagerDuty (Escalation) | 5s | Retry 3x, then log failure — SMS/push still sent |
| EHR (SOAP push) | N/A (stubbed) | Store locally, log pending |

---

## BR-SV-002: Emergency Escalation Is Fire-and-Forget

**Rule**: When Emergency is detected, the pipeline fires notifications AND continues processing (drug check → routing → SOAP). It does NOT wait for physician acknowledgement.

**Rationale**: The patient still needs a SOAP note and routing even during Emergency. The physician acknowledgement is tracked asynchronously — a missed acknowledgement triggers a separate SLA alert, not a pipeline block.

---

## BR-SV-003: Nurse Handoff Terminates Express Workflow

**Rule**: When AI confidence is low (< 0.70) and nurse handoff triggers:
1. Express workflow terminates gracefully (not a failure — a deliberate branch)
2. Standard workflow starts with full session context
3. Patient stays connected via same WebSocket (no disconnection)
4. Standard workflow waits for nurse callback (up to 5 minutes)
5. If nurse responds → resume pipeline via new Express execution
6. If nurse times out → default to URGENT, resume pipeline

---

## BR-SV-004: Patient WebSocket Continuity

**Rule**: The patient MUST experience a seamless conversation regardless of which workflow or Lambda is handling their messages.

**Implementation**:
- Connection ID is stored in DynamoDB (linked to session)
- Any Lambda that needs to send a message to the patient uses the same `send_to_patient(connection_id, message)` function
- If the patient disconnects and reconnects: new connection ID is associated with the existing session
- Nurse taking over the chat uses the same WebSocket connection (patient doesn't know it's a different sender unless told)

---

## BR-SV-005: Assessment Loop Callback Pattern

**Rule**: The Symptom Assessment loop uses Step Functions task tokens (callback pattern):

1. Express workflow enters AssessmentLoop state
2. Lambda sends AI question to patient via WebSocket
3. Lambda stores the Step Functions `task_token` in DynamoDB
4. Lambda returns without completing the task (workflow pauses)
5. When patient sends a message → chat-message Lambda calls `SendTaskSuccess` with the stored token
6. Workflow resumes, processes the message, loops or exits

**Timeout**: If no `SendTaskSuccess` arrives within 15 minutes → session times out.

---

## BR-SV-006: Session State Is Always Recoverable

**Rule**: If any Lambda crashes mid-execution, the session can be recovered from DynamoDB state alone.

**Implementation**:
- Every state transition writes to DynamoDB BEFORE responding to Step Functions
- All agent outputs are persisted immediately after each agent completes
- WebSocket connection IDs are stored server-side
- On recovery: reload session from DynamoDB, determine last completed step, resume

---

## BR-SV-007: Escalation Must Log Everything

**Rule**: Every escalation attempt is logged with:
- Timestamp of trigger
- All channels attempted
- Delivery status per channel
- Response time (if acknowledged)
- Failure reasons (if failed)

This satisfies the HIPAA audit trail requirement for clinical decision escalation.

---

## BR-SV-008: 30-Second Escalation SLA

**Rule**: From the moment Triage Scoring outputs `EMERGENCY`, notifications MUST be sent within 30 seconds.

**Budget**:
| Step | Max Time |
|---|---|
| Choice state evaluation | < 100ms |
| Parallel branch start | < 200ms |
| Notification Lambda cold start | < 3000ms |
| SMS send via SNS | < 2000ms |
| PagerDuty webhook | < 5000ms |
| **Total (worst case)** | **< 10s** (well within 30s) |

The Parallel state fires all channels simultaneously — the slowest channel determines total time.

---

## BR-SV-009: Conversation Resumption After Disconnect

**Rule**: If the patient disconnects during triage:
1. Session remains IN_PROGRESS for 15 minutes (assessment loop timeout)
2. If patient reconnects within 15 minutes:
   - New connection ID associated with existing session
   - Symptom Assessment Agent resumes with: "Welcome back! [recap] Shall we continue?"
   - Pipeline continues from where it paused
3. If patient doesn't reconnect within 15 minutes:
   - Session marked PAUSED (not terminated)
   - Patient can start a NEW session later (old data still available for reference)

---

## BR-SV-010: Concurrent Session Prevention

**Rule**: A patient can only have ONE active triage session at a time.

**Implementation**:
- On session start: check DynamoDB for existing IN_PROGRESS session for this patient
- If found: resume existing session (don't create new one)
- If found but PAUSED: ask patient "You have an incomplete triage from [time]. Resume or start fresh?"
- If found and COMPLETED: allow new session

---

## BR-SV-011: Nurse Dashboard Notification

**Rule**: When a case is routed to nurse handoff, the nurse dashboard is notified via WebSocket push (if nurse is online) AND a DynamoDB record is created (for nurses not currently watching).

**Nurse sees**:
- Patient name (if authenticated)
- Primary complaint
- AI's attempted classification + confidence score
- AI's reasoning for uncertainty
- Full conversation transcript
- Button: "Classify as [Emergency/Urgent/Standard/Routine]"

---

## BR-SV-012: Pipeline Timing Tracking

**Rule**: Total session duration is tracked and logged for every triage.

| Metric | Target | Alert Threshold |
|---|---|---|
| Total triage time (assessment → completion) | < 3 minutes | > 5 minutes |
| Assessment loop only | < 2 minutes | > 3 minutes |
| Post-assessment pipeline (scoring → SOAP) | < 30 seconds | > 60 seconds |
| Escalation trigger to notification sent | < 30 seconds | > 30 seconds |

These metrics feed into CloudWatch dashboards and alarms.
