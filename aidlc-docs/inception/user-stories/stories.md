# User Stories

## Epic 1: Patient Triage Journey
**Related Requirements**: FR-001, FR-002

---

### US-001: Patient Initiates Triage Conversation
**As a** Patient,  
**I want to** start a triage conversation from my phone or computer at any time,  
**so that** I can get immediate guidance on my symptoms without waiting on hold.

**Acceptance Criteria:**
1. **Given** a patient accesses the triage system (web or mobile), **When** they click "Start Triage", **Then** a conversational AI session begins within 3 seconds
2. **Given** the system is available 24/7, **When** a patient initiates triage at any hour, **Then** they receive an AI response without human staff being online
3. **Given** a patient has not authenticated, **When** they start a triage session, **Then** they can proceed with basic assessment but are prompted to verify identity before PHI is accessed
4. **Given** the system is under peak load (150 concurrent users), **When** a new patient starts triage, **Then** they are not queued and receive immediate response

**FR Traceability**: FR-001, FR-010  
**Persona**: Sarah (Patient)

---

### US-002: Patient Completes Symptom Assessment
**As a** Patient,  
**I want to** describe my symptoms through a guided conversation covering onset, severity, duration, and history,  
**so that** the system can accurately assess my condition.

**Acceptance Criteria:**
1. **Given** a triage session is active, **When** the AI asks assessment questions, **Then** it covers onset, severity (1-10), duration, and relevant medical history
2. **Given** the patient provides symptom information, **When** the AI has sufficient data, **Then** it completes assessment in under 3 minutes total
3. **Given** the patient provides unclear or contradictory information, **When** the AI detects ambiguity, **Then** it asks up to 3 targeted clarifying questions before escalating
4. **Given** the patient has existing records in the EHR, **When** they are authenticated, **Then** the AI references relevant medical history during assessment

**FR Traceability**: FR-001  
**Persona**: Sarah (Patient)

---

### US-003: Patient Receives Urgency Classification
**As a** Patient,  
**I want to** receive a clear urgency level after my assessment,  
**so that** I understand how quickly I need medical attention.

**Acceptance Criteria:**
1. **Given** symptom assessment is complete, **When** the AI assigns urgency (Emergency/Urgent/Standard/Routine), **Then** the patient sees a clear explanation of what the level means and next steps
2. **Given** the same symptoms are reported by different patients, **When** urgency is scored, **Then** the classification is consistent regardless of which clinic the patient belongs to
3. **Given** an urgency level is assigned, **When** the triage completes, **Then** the scoring decision and reasoning are logged to the audit trail
4. **Given** the patient disagrees with the classification, **When** they express concern, **Then** they are offered the option to speak with a triage nurse

**FR Traceability**: FR-002  
**Persona**: Sarah (Patient)

---

## Epic 2: Emergency Escalation
**Related Requirements**: FR-003

---

### US-004: Emergency Case Triggers Immediate Escalation
**As a** Triage System,  
**I want to** immediately escalate cases classified as Emergency,  
**so that** patients with life-threatening conditions receive immediate human intervention.

**Acceptance Criteria:**
1. **Given** a patient is classified as Emergency, **When** the classification is confirmed, **Then** escalation notifications are triggered within 30 seconds
2. **Given** an Emergency escalation triggers, **When** notifications are sent, **Then** all three channels activate: push notification + SMS, paging system (PagerDuty), and live transfer option
3. **Given** an Emergency escalation, **When** the patient summary is generated, **Then** it includes symptoms, severity score, medication list, and relevant history
4. **Given** the paging system is unavailable, **When** escalation fails on one channel, **Then** the remaining channels still fire and the failure is logged for follow-up

**FR Traceability**: FR-003  
**Persona**: System / Dr. Patel (On-Call Physician)

---

### US-005: On-Call Physician Receives Emergency Notification
**As an** On-Call Physician,  
**I want to** receive a structured emergency notification with full patient context,  
**so that** I can assess the situation and respond without needing to call back for details.

**Acceptance Criteria:**
1. **Given** an Emergency escalation fires, **When** Dr. Patel receives the notification, **Then** it contains: patient name, symptoms, severity, medications, history summary, and triage reasoning
2. **Given** the physician receives the notification, **When** they open it, **Then** they can acknowledge receipt (which logs response time)
3. **Given** the physician wants to speak with the patient, **When** they select "Connect", **Then** a live communication channel is established
4. **Given** no physician acknowledges within 5 minutes, **When** the timeout fires, **Then** the escalation is re-routed to the backup on-call

**FR Traceability**: FR-003  
**Persona**: Dr. Patel (On-Call Physician)

---

### US-006: Patient Offered Live Transfer During Emergency
**As a** Patient classified as Emergency,  
**I want to** be offered an immediate connection to medical staff,  
**so that** I can receive live guidance while waiting for in-person care.

**Acceptance Criteria:**
1. **Given** the patient is classified as Emergency, **When** escalation triggers, **Then** the patient is immediately offered "Connect to medical staff now"
2. **Given** the patient accepts live transfer, **When** connection is established, **Then** the on-call staff sees the full triage conversation and patient summary
3. **Given** the patient declines live transfer, **When** they choose to wait, **Then** they see clear instructions (e.g., "Call 911 if symptoms worsen") and the escalation still proceeds

**FR Traceability**: FR-003  
**Persona**: Sarah (Patient), Dr. Patel (On-Call Physician)

---

## Epic 3: Clinical Safety Checks
**Related Requirements**: FR-004

---

### US-007: System Checks Drug Interactions During Triage
**As a** Triage System,  
**I want to** check the patient's current medications for dangerous interactions,  
**so that** clinical safety risks are identified before routing to a specialist.

**Acceptance Criteria:**
1. **Given** the patient is authenticated and their medication list is available, **When** triage assessment runs, **Then** the system queries the hospital pharmacy system for interaction checks
2. **Given** the patient reports taking new medications not in their record, **When** they provide medication names, **Then** those are included in the interaction check
3. **Given** the pharmacy system is unavailable, **When** the check fails, **Then** the SOAP note flags "drug interaction check unavailable — manual review required"
4. **Given** no dangerous interactions are found, **When** the check completes, **Then** the result is logged but not surfaced to the patient (no unnecessary alarm)

**FR Traceability**: FR-004  
**Persona**: Sarah (Patient), Dr. Kim (Specialist)

---

### US-008: Patient and Physician Alerted to Dangerous Interactions
**As a** Patient and Receiving Physician,  
**I want to** be alerted when a dangerous drug interaction is detected,  
**so that** appropriate precautions are taken before prescribing or administering treatment.

**Acceptance Criteria:**
1. **Given** a dangerous interaction is detected, **When** the check returns a critical flag, **Then** the patient is informed in clear, non-alarming language with instructions to discuss with their provider
2. **Given** a dangerous interaction is detected, **When** the SOAP note is generated, **Then** it prominently flags the interaction in the Assessment section
3. **Given** the interaction is moderate (not critical), **When** the note is generated, **Then** it appears as an advisory note rather than a critical flag

**FR Traceability**: FR-004  
**Persona**: Sarah (Patient), Dr. Kim (Specialist)

---

## Epic 4: Specialist Routing
**Related Requirements**: FR-005

---

### US-009: Patient Routed to Appropriate Specialist
**As a** Patient,  
**I want to** be automatically routed to the right specialist based on my symptoms,  
**so that** I don't have to figure out which department to contact.

**Acceptance Criteria:**
1. **Given** triage assessment is complete with urgency Standard or Routine, **When** routing logic runs, **Then** the patient is matched to one of 5-10 specialist departments based on symptom pattern
2. **Given** the matched specialist has availability, **When** routing completes, **Then** the patient sees available appointment slots
3. **Given** the matched specialist has no availability at the patient's clinic, **When** routing finds no slots, **Then** alternative clinics with availability are suggested
4. **Given** the symptom pattern doesn't clearly match a single specialty, **When** routing is ambiguous, **Then** the case is flagged for triage nurse review

**FR Traceability**: FR-005  
**Persona**: Sarah (Patient)

---

### US-010: Specialist Receives Patient With Context
**As a** Specialist,  
**I want to** receive routed patients with a complete clinical summary,  
**so that** I can prepare for the appointment without redundant questioning.

**Acceptance Criteria:**
1. **Given** a patient is routed to a specialist, **When** the referral appears in the EHR, **Then** it includes the SOAP note, urgency level, routing reasoning, and drug interaction results
2. **Given** the specialist reviews the referral, **When** they open the patient record, **Then** the triage conversation summary is accessible (not the full transcript)
3. **Given** the specialist believes the routing is incorrect, **When** they flag the case, **Then** the routing decision is logged for system improvement

**FR Traceability**: FR-005, FR-006  
**Persona**: Dr. Kim (Specialist)

---

## Epic 5: Clinical Documentation
**Related Requirements**: FR-006

---

### US-011: SOAP Note Generated After Triage
**As a** Triage System,  
**I want to** generate a structured SOAP note from the triage conversation,  
**so that** the receiving physician has a standardized clinical document.

**Acceptance Criteria:**
1. **Given** triage assessment completes (any urgency level), **When** the conversation ends, **Then** a SOAP note is generated with Subjective, Objective, Assessment, and Plan sections
2. **Given** the SOAP note is generated, **When** it is stored, **Then** it is linked to the patient record and the triage session ID
3. **Given** the AI generates the note, **When** content is produced, **Then** it uses only information provided during the conversation (no hallucinated clinical data)
4. **Given** the EHR integration is stubbed for MVP, **When** the note is generated, **Then** it is stored in the system database and available via the portal/API (EHR push is mocked)

**FR Traceability**: FR-006  
**Persona**: Dr. Patel (On-Call Physician), Dr. Kim (Specialist)

---

### US-012: Physician Reviews SOAP Note
**As a** Physician,  
**I want to** review the AI-generated SOAP note before seeing the patient,  
**so that** I can validate the triage assessment and prepare for the consultation.

**Acceptance Criteria:**
1. **Given** a SOAP note exists for a patient, **When** the physician opens the patient's record, **Then** the note is displayed in standard clinical format
2. **Given** the physician reviews the note, **When** they identify corrections needed, **Then** they can annotate or flag the note (corrections logged for AI improvement)
3. **Given** the note was generated for an Emergency case, **When** it is viewed, **Then** it prominently shows the escalation reason and response timeline

**FR Traceability**: FR-006  
**Persona**: Dr. Patel (On-Call Physician), Dr. Kim (Specialist)

---

## Epic 6: Security & Compliance
**Related Requirements**: FR-007, FR-008, FR-009

---

### US-013: Patient Data Encrypted End-to-End
**As a** Compliance Officer,  
**I want** all patient data encrypted at rest and in transit,  
**so that** the system meets HIPAA requirements for PHI protection.

**Acceptance Criteria:**
1. **Given** any data store in the system, **When** PHI is written, **Then** it is encrypted with AES-256 using AWS KMS customer-managed keys
2. **Given** any network communication, **When** data is transmitted, **Then** TLS 1.2+ is enforced (no plaintext fallback)
3. **Given** a new service is added, **When** it handles PHI, **Then** encryption configuration is mandatory before deployment (CDK enforces this)

**FR Traceability**: FR-007  
**Persona**: James (Clinic Administrator)

---

### US-014: PHI Redacted From Logs
**As a** Compliance Officer,  
**I want** all PHI automatically redacted from application logs,  
**so that** log access does not constitute PHI exposure.

**Acceptance Criteria:**
1. **Given** the application writes a log entry, **When** the entry contains PHI (names, DOB, symptoms, medications), **Then** the PHI is redacted before reaching CloudWatch
2. **Given** PHI redaction is configured, **When** tested against a sample dataset, **Then** redaction achieves 99%+ recall on PHI patterns
3. **Given** a developer accesses logs for debugging, **When** they view log entries, **Then** no patient-identifiable information is visible
4. **Given** emergency debugging requires PHI context, **When** authorized personnel need it, **Then** unredacted logs are available only via a separate, audited access path

**FR Traceability**: FR-008  
**Persona**: James (Clinic Administrator)

---

### US-015: Patient Manages Consent Preferences
**As a** Patient,  
**I want to** control what my data is used for and revoke consent at any time,  
**so that** I maintain control over my personal health information.

**Acceptance Criteria:**
1. **Given** a patient starts triage, **When** they are asked for consent, **Then** they see clear explanations of data processing, AI-assisted triage, and data sharing with specialists
2. **Given** a patient grants consent, **When** the grant is recorded, **Then** it is timestamped and linked to the specific consent version
3. **Given** a patient wants to revoke consent, **When** they access their portal settings, **Then** they can revoke and the system stops processing their data within 24 hours
4. **Given** consent is revoked, **When** the patient attempts triage, **Then** the system informs them that triage requires data processing consent and offers alternatives (e.g., call the clinic)

**FR Traceability**: FR-009  
**Persona**: Sarah (Patient)

---

## Epic 7: Patient Portal
**Related Requirements**: FR-010

---

### US-016: Patient Views Triage Status in Real-Time
**As a** Patient,  
**I want to** see my triage status update in real-time,  
**so that** I know what's happening with my case without having to call.

**Acceptance Criteria:**
1. **Given** a patient has an active or completed triage, **When** they open the portal, **Then** they see the current status (In Progress / Awaiting Routing / Scheduled / Complete)
2. **Given** the triage status changes (e.g., specialist assigned), **When** the update occurs, **Then** the portal reflects it within 5 seconds (real-time push)
3. **Given** the patient has multiple triage sessions, **When** they view history, **Then** they see a chronological list with dates, urgency levels, and outcomes

**FR Traceability**: FR-010  
**Persona**: Sarah (Patient)

---

### US-017: Patient Views Appointment Details
**As a** Patient,  
**I want to** see my scheduled appointment details after triage,  
**so that** I know where and when to go for my specialist visit.

**Acceptance Criteria:**
1. **Given** a specialist appointment is scheduled, **When** the patient views the portal, **Then** they see: specialist name/department, clinic location, date/time, and preparation instructions
2. **Given** the appointment is upcoming, **When** it's within 24 hours, **Then** the patient receives a reminder notification (SMS or push)
3. **Given** the patient needs to reschedule, **When** they select "Reschedule", **Then** they see available alternative slots (scheduling integration)

**FR Traceability**: FR-010  
**Persona**: Sarah (Patient)

---

### US-018: Patient Authenticates via SMS/Email
**As a** Patient,  
**I want to** verify my identity via SMS or email code with date of birth confirmation,  
**so that** I can access my health information securely without remembering complex passwords.

**Acceptance Criteria:**
1. **Given** a patient wants to access PHI (triage history, appointment details), **When** they request access, **Then** they must complete SMS/email verification + DOB confirmation
2. **Given** an emergency situation, **When** the patient cannot authenticate, **Then** they can still access generic triage guidance (non-PHI) without identity verification
3. **Given** the verification code is sent, **When** it is not used within 10 minutes, **Then** it expires and a new one must be requested
4. **Given** 5 failed verification attempts, **When** the threshold is hit, **Then** the account is temporarily locked and the patient is directed to call the clinic

**FR Traceability**: FR-010  
**Persona**: Sarah (Patient)

---

## Epic 8: AI Uncertainty & Human Handoff
**Related Requirements**: FR-001, FR-002 (derived from Q2 answer)

---

### US-019: AI Asks Clarifying Questions When Uncertain
**As a** Triage AI Agent,  
**I want to** ask up to 3 targeted clarifying questions when I cannot confidently assess urgency,  
**so that** I can resolve ambiguity before escalating to a human.

**Acceptance Criteria:**
1. **Given** the AI's confidence in urgency classification is below threshold, **When** it detects ambiguity, **Then** it asks up to 3 focused follow-up questions (not open-ended)
2. **Given** the patient answers all 3 follow-up questions, **When** confidence is still below threshold, **Then** the case is immediately escalated to a triage nurse
3. **Given** the patient stops responding during follow-up, **When** 2 minutes pass with no response, **Then** the system sends a "Still there?" prompt; after 5 more minutes of silence, escalates to nurse
4. **Given** the AI asks clarifying questions, **When** the conversation is logged, **Then** the uncertainty reason and follow-up answers are included in the SOAP note

**FR Traceability**: FR-001, FR-002  
**Persona**: Sarah (Patient), System

---

### US-020: Ambiguous Case Escalated to Triage Nurse
**As a** Triage Nurse,  
**I want to** receive escalated cases with full AI conversation context and uncertainty reasoning,  
**so that** I can quickly assess the situation and make a clinical judgment.

**Acceptance Criteria:**
1. **Given** the AI escalates an ambiguous case, **When** it appears on the nurse dashboard, **Then** it includes: full conversation transcript, AI confidence score, attempted classification, and reason for uncertainty
2. **Given** the nurse reviews the case, **When** they assign a final urgency level, **Then** the patient is notified and the triage proceeds with the nurse's classification
3. **Given** the nurse takes over, **When** they communicate with the patient, **Then** they can continue in the same chat thread (seamless handoff)
4. **Given** no nurse responds within 5 minutes, **When** the timeout fires, **Then** the case defaults to "Urgent" and the patient is notified that a clinician will follow up shortly

**FR Traceability**: FR-001, FR-002  
**Persona**: Maria (Triage Nurse)

---

## Story Summary

| Epic | Stories | Personas Involved |
|---|---|---|
| Patient Triage Journey | US-001, US-002, US-003 | Patient |
| Emergency Escalation | US-004, US-005, US-006 | Patient, On-Call Physician |
| Clinical Safety Checks | US-007, US-008 | Patient, Specialist |
| Specialist Routing | US-009, US-010 | Patient, Specialist |
| Clinical Documentation | US-011, US-012 | On-Call Physician, Specialist |
| Security & Compliance | US-013, US-014, US-015 | Patient, Clinic Admin |
| Patient Portal | US-016, US-017, US-018 | Patient |
| AI Uncertainty & Handoff | US-019, US-020 | Patient, Triage Nurse |

**Total**: 20 user stories across 8 epics covering 5 personas  
**All stories comply with INVEST criteria**  
**All stories map to FR-001 through FR-010**
