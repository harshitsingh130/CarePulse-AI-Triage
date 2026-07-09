# Business Logic Model — Supervisor & Notification Agent (Unit 7)

## Overview

The Supervisor Agent is the central orchestrator. It doesn't do clinical reasoning — it **sequences** the other agents, **branches** on results (emergency, low confidence), **manages** WebSocket communication with the patient, and **triggers** escalation/notifications. Implemented as two AWS Step Functions state machines (Express + Standard) plus supporting Lambdas.

---

## State Machine Architecture

### Express Workflow: `triage-pipeline-express`
Handles 95% of sessions (< 5 minutes). The happy path.

### Standard Workflow: `nurse-handoff-standard`
Handles ~5% of sessions. Triggered when AI confidence is low. Waits indefinitely for nurse callback.

```
Patient connects (WebSocket)
       |
       v
[Express Workflow starts]
       |
       v
+-- ASSESS (loop) --+
|  Symptom Agent    |←→ Patient (via WebSocket)
+-------------------+
       |
       v (assessment_complete)
+-- SCORE -----------+
|  Triage Scoring    |
+--------------------+
       |
       +--- EMERGENCY? ──→ [ESCALATE parallel branch]
       |                      ├─ Notify physician (SMS+push)
       |                      ├─ Page (PagerDuty)
       |                      ├─ Offer patient live transfer
       |                      └─ Continue pipeline (don't block)
       |
       +--- LOW CONFIDENCE? → [Trigger Standard Workflow]
       |                        Express workflow ENDS here for this path
       |                        Standard workflow takes over
       |
       v (normal: Urgent/Standard/Routine)
+-- DRUG CHECK ------+
|  Drug Interaction  |
+--------------------+
       |
       v
+-- ROUTE -----------+
|  Specialist Routing|
+--------------------+
       |
       v
+-- SUMMARIZE -------+
|  Clinical Summary  |
+--------------------+
       |
       v
+-- COMPLETE --------+
|  Update session    |
|  Notify patient    |
|  Store results     |
+--------------------+
       |
       v
[Express Workflow ends]
```

---

## Express Workflow States (ASL)

### State 1: InitSession
- **Type**: Task (Lambda)
- **Action**: Create session in DynamoDB, register WebSocket connection, load patient data
- **Output**: `{session_id, patient_id, ehr_data_available, connection_id}`
- **Next**: AssessmentLoop

### State 2: AssessmentLoop
- **Type**: Task (Lambda — invokes Symptom Assessment Agent)
- **Action**: 
  1. Send AI question to patient via WebSocket
  2. Wait for patient response (Step Functions callback with task token)
  3. Process response through Symptom Assessment Agent
  4. Check `assessment_complete`
  5. If not complete → loop (send next question)
  6. If complete → proceed
- **Timeout**: 15 minutes (session abandoned if patient stops responding)
- **Next**: ScoreUrgency

### State 3: ScoreUrgency
- **Type**: Task (Lambda — invokes Triage Scoring Agent)
- **Action**: Pass StructuredSymptoms to scoring agent, receive UrgencyResult
- **Next**: EvaluateUrgency (Choice state)

### State 4: EvaluateUrgency
- **Type**: Choice
- **Conditions**:
  - `urgency_level == "EMERGENCY"` → EmergencyEscalation
  - `requires_nurse_review == true` → TriggerNurseHandoff
  - Default → DrugCheck

### State 5: EmergencyEscalation
- **Type**: Parallel
- **Branches**:
  - Branch 1: SendNotifications (invoke Notification Lambda)
  - Branch 2: OfferLiveTransfer (WebSocket message to patient)
  - Branch 3: ContinuePipeline (proceeds to DrugCheck — doesn't wait for physician)
- **Note**: Escalation is fire-and-forget from the Express workflow's perspective. Physician acknowledgement is tracked async.
- **Next**: DrugCheck (after parallel completes)

### State 6: TriggerNurseHandoff
- **Type**: Task (Lambda)
- **Action**:
  1. Start Standard workflow `nurse-handoff-standard` with session context
  2. Notify patient: "I'm connecting you with a nurse for a quick review"
  3. Express workflow ENDS (Standard takes over)
- **Terminal**: Yes (Express ends here for this branch)

### State 7: DrugCheck
- **Type**: Task (Lambda — invokes Drug Interaction Agent)
- **Action**: Check medications, receive InteractionResult
- **Catch**: On timeout/error → set `check_status: unavailable`, continue
- **Next**: SpecialistRouting

### State 8: SpecialistRouting
- **Type**: Task (Lambda — invokes Specialist Routing Agent)
- **Action**: Route patient, receive RoutingDecision
- **Next**: GenerateSummary

### State 9: GenerateSummary
- **Type**: Task (Lambda — invokes Clinical Summary Agent)
- **Action**: Generate SOAP note from all collected data
- **Next**: CompleteSession

### State 10: CompleteSession
- **Type**: Task (Lambda)
- **Action**:
  1. Update session status → COMPLETED
  2. Send completion message to patient via WebSocket
  3. Create appointment record in DynamoDB
  4. Write audit trail entry
- **Terminal**: Yes

---

## Standard Workflow States (Nurse Handoff)

### State 1: ReceiveHandoff
- **Type**: Task (Lambda)
- **Action**:
  1. Load full session context from DynamoDB
  2. Push case to nurse queue (write to DynamoDB with status AWAITING_NURSE)
  3. Send WebSocket notification to nurse dashboard
  4. Send patient message: "A nurse will review your case shortly"
- **Next**: WaitForNurse

### State 2: WaitForNurse
- **Type**: Task (Lambda with callback)
- **Action**: Wait for `SendTaskSuccess` callback from nurse dashboard
- **Heartbeat**: 60 seconds (keeps execution alive)
- **Timeout**: 300 seconds (5 minutes)
- **On Timeout**: → DefaultToUrgent

### State 3: DefaultToUrgent (timeout path)
- **Type**: Task (Lambda)
- **Action**:
  1. Set urgency_level = URGENT (conservative default)
  2. Set `nurse_timeout: true` in session
  3. Notify patient: "We're prioritizing your case — proceeding with our assessment"
- **Next**: ResumePipeline

### State 4: ProcessNurseDecision (callback received)
- **Type**: Task (Lambda)
- **Action**:
  1. Receive nurse's classification from callback payload
  2. Update UrgencyResult with nurse override
  3. Log override in AuditTrail
  4. Notify patient: "Your nurse has confirmed your assessment"
- **Next**: ResumePipeline

### State 5: ResumePipeline
- **Type**: Task (Lambda)
- **Action**:
  1. Start a NEW Express workflow execution from DrugCheck onward
  2. Pass updated UrgencyResult (with nurse override if applicable)
  3. Standard workflow ENDS
- **Terminal**: Yes

---

## WebSocket Communication Logic

### Connection Management (chat-connect Lambda)
```
On $connect:
  1. Extract JWT from query string parameter
  2. Validate token with Cognito
  3. Extract patient_id from token claims
  4. Store in DynamoDB: {connection_id, patient_id, connected_at}
  5. Return 200
```

### Message Routing (chat-message Lambda)
```
On sendMessage:
  1. Load connection record → get session_id
  2. Load session state → get workflow_execution_arn
  3. Call Step Functions SendTaskSuccess with:
     - task_token (stored in session state)
     - output: {patient_message: message.body}
  4. This resumes the AssessmentLoop state
```

### Sending Messages to Patient
```
Function: send_to_patient(connection_id, message)
  1. Call API Gateway Management API: PostToConnection
  2. If connection stale (410 GoneException):
     - Mark session as PAUSED
     - Patient will resume on reconnect
```

### Disconnect (chat-disconnect Lambda)
```
On $disconnect:
  1. Delete connection record from DynamoDB
  2. If session IN_PROGRESS:
     - Don't terminate workflow
     - Session will timeout via assessment loop timeout (15 min)
     - Patient can reconnect and resume
```

---

## Notification Logic

### Emergency Notification Lambda
```
Input: EscalationEvent {session_id, patient_summary, channels[], recipients[]}

For each channel:
  SMS:
    → SNS.publish(phone, formatted_message)
    → Record: {session_id, channel: SMS, status: SENT, sent_at}

  PUSH:
    → SNS.publish(platform_endpoint, formatted_payload)
    → Record: {session_id, channel: PUSH, status: SENT, sent_at}

  PAGERDUTY:
    → HTTP POST to PagerDuty Events API v2
    → Include: urgency, patient summary, session link
    → Record: {session_id, channel: PAGERDUTY, status: SENT, sent_at}

  LIVE_TRANSFER:
    → Send WebSocket message to patient: "Would you like to speak with medical staff now?"
    → Record: {session_id, channel: LIVE_TRANSFER, status: OFFERED}

On failure for any channel:
  → Retry up to 3 times (30s interval for SMS/PUSH, 60s for PagerDuty)
  → If all retries fail: log FAILED, alert clinic admin
  → Other channels continue regardless of one failure
```

### Physician Acknowledgement (async)
```
POST /physician/acknowledge {session_id, physician_id}
  → Update Notifications record: status: ACKNOWLEDGED, acknowledged_at
  → If response_time > 5 minutes: log SLA_BREACH in audit
  → This does NOT affect the triage pipeline (fire-and-forget)
```

---

## Output Contract

The Supervisor doesn't produce a single output entity — it orchestrates the pipeline and stores results in DynamoDB. But it does produce session completion events:

```json
{
  "event_type": "triage.session.completed",
  "session_id": "UUID",
  "patient_id": "UUID",
  "urgency_level": "EMERGENCY|URGENT|STANDARD|ROUTINE",
  "department_routed": "string",
  "appointment_scheduled": true|false,
  "escalation_triggered": true|false,
  "nurse_handoff_triggered": true|false,
  "total_duration_seconds": number,
  "completed_at": "ISO datetime"
}
```

This event is published to EventBridge for:
- Analytics (future)
- Operational dashboards (future)
- Triggering appointment reminders (future)
