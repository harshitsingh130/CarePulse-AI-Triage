# Application Components

## Component Overview

The Healthcare Network Patient Triage System follows a **multi-agent pipeline** architecture with a **Supervisor Agent** orchestrating specialized collaborator agents. Each agent is an independent component with a single responsibility.

---

## Component 1: Symptom Assessment Agent

| Attribute | Detail |
|---|---|
| **Purpose** | Conduct conversational symptom intake with structured clinical questions |
| **Type** | AI Agent (Strands Agents SDK + Amazon Bedrock) |
| **Responsibilities** | Greet patient, ask structured questions (onset, severity 1-10, duration, history), handle follow-up clarifications, detect when assessment is complete, output structured symptom data |
| **Interface** | Input: patient message (text) + session context. Output: structured symptom payload (JSON) |
| **State** | Maintains conversation state per session (multi-turn) |
| **Deployment** | AWS Lambda (behind API Gateway WebSocket) |

---

## Component 2: Triage Scoring Agent

| Attribute | Detail |
|---|---|
| **Purpose** | Assign urgency level based on symptom data using clinical guidelines |
| **Type** | AI Agent (Strands Agents SDK + Amazon Bedrock) |
| **Responsibilities** | Receive structured symptoms, apply clinical scoring logic, assign urgency (Emergency/Urgent/Standard/Routine), produce confidence score, log reasoning |
| **Interface** | Input: structured symptom payload. Output: urgency classification + confidence score + reasoning |
| **State** | Stateless (pure function of input) |
| **Deployment** | AWS Lambda |

---

## Component 3: Drug Interaction Agent

| Attribute | Detail |
|---|---|
| **Purpose** | Check patient medications for dangerous interactions |
| **Type** | AI Agent (Strands Agents SDK) with tool access to pharmacy system |
| **Responsibilities** | Retrieve patient medication list, query pharmacy system for interactions, classify severity (critical/moderate/informational), format results |
| **Interface** | Input: patient ID + any reported medications. Output: interaction results (list of flagged interactions with severity) |
| **State** | Stateless |
| **Deployment** | AWS Lambda |

---

## Component 4: Specialist Routing Agent

| Attribute | Detail |
|---|---|
| **Purpose** | Map symptom patterns to specialist departments and check availability |
| **Type** | AI Agent (Strands Agents SDK) with tool access to scheduling system |
| **Responsibilities** | Map symptoms to department (5-10 specialties), check specialist availability, select optimal clinic/slot, handle unavailability (suggest alternatives) |
| **Interface** | Input: structured symptoms + urgency level + patient clinic. Output: routing decision (department, specialist, clinic, available slots) |
| **State** | Stateless |
| **Deployment** | AWS Lambda |

---

## Component 5: Clinical Summary Agent

| Attribute | Detail |
|---|---|
| **Purpose** | Generate SOAP-format clinical note from triage session data |
| **Type** | AI Agent (Strands Agents SDK + Amazon Bedrock) |
| **Responsibilities** | Aggregate all session data (symptoms, urgency, interactions, routing), generate structured SOAP note, format for EHR consumption, push to EHR (stubbed for MVP) |
| **Interface** | Input: complete triage session data. Output: SOAP note (structured markdown/FHIR) |
| **State** | Stateless |
| **Deployment** | AWS Lambda |

---

## Component 6: Supervisor Agent

| Attribute | Detail |
|---|---|
| **Purpose** | Orchestrate the entire triage workflow, handle escalation and human handoff |
| **Type** | Orchestrator (AWS Step Functions Hybrid + Strands Agent for decision logic) |
| **Responsibilities** | Sequence agent execution, detect Emergency → trigger escalation, detect low confidence → spawn Standard workflow for nurse handoff, manage session lifecycle, coordinate async notifications |
| **Interface** | Input: new triage session request. Output: completed triage result (or escalation event) |
| **State** | Stateful — Express workflow (primary, <5 min) + Standard workflow (nurse handoff, unbounded wait) |
| **Deployment** | AWS Step Functions (Express + Standard) + Lambda (decision logic) |

---

## Component 7: Patient Portal (Frontend)

| Attribute | Detail |
|---|---|
| **Purpose** | Patient-facing web/mobile interface for triage chat, status, and appointments |
| **Type** | Web Application (React) |
| **Responsibilities** | Triage chat UI (WebSocket), authentication (SMS/email + DOB), consent collection, real-time status display, appointment viewing, triage history |
| **Interface** | Connects to: API Gateway (REST + WebSocket), Cognito (auth) |
| **State** | Client-side session state + server-side via APIs |
| **Deployment** | AWS Amplify Hosting (static site) or CloudFront + S3 |

---

## Component 8: Shared Infrastructure

| Attribute | Detail |
|---|---|
| **Purpose** | Common AWS resources shared across all components |
| **Type** | Infrastructure (AWS CDK) |
| **Responsibilities** | DynamoDB tables (sessions, patients, consent, audit), KMS keys (PHI encryption), API Gateway (REST + WebSocket), Cognito User Pool, SNS topics (notifications), CloudWatch (logging + redaction), VPC (if needed for pharmacy integration) |
| **Interface** | Consumed by all other components via CDK imports/exports |
| **State** | Infrastructure state (CDK/CloudFormation) |
| **Deployment** | AWS CDK (TypeScript) |

---

## Component 9: Notification Service

| Attribute | Detail |
|---|---|
| **Purpose** | Handle emergency escalation notifications across multiple channels |
| **Type** | Event-driven service |
| **Responsibilities** | Send SMS (SNS), trigger PagerDuty webhook, initiate live transfer (WebSocket), handle delivery failures, log all notification attempts |
| **Interface** | Input: escalation event (from Supervisor). Output: delivery confirmations per channel |
| **State** | Stateless (fire-and-forget with delivery tracking) |
| **Deployment** | AWS Lambda + SNS + EventBridge |

---

## Component 10: PHI Redaction Layer

| Attribute | Detail |
|---|---|
| **Purpose** | Automatically redact PHI from all application logs before they reach CloudWatch |
| **Type** | Middleware / Lambda Layer |
| **Responsibilities** | Intercept log output, detect PHI patterns (names, DOB, SSN, medical terms), redact before write, maintain redaction audit |
| **Interface** | Transparent — wraps logging in all Lambda functions |
| **State** | Stateless |
| **Deployment** | Lambda Layer (shared across all functions) |
