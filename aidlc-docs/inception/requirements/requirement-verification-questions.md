# Requirements Verification Questions

Please answer the following questions to clarify requirements for the Healthcare Network Patient Triage System. Fill in the letter choice after each [Answer]: tag.

---

## Question 1
What is the primary user interface for patient symptom assessment?

A) Web-based chat interface (browser)

B) Mobile app (native iOS/Android)

C) Both web and mobile

D) Voice-based (phone/IVR) with web fallback

E) Other (please describe after [Answer]: tag below)

[Answer]: C

---

## Question 2
How should the AI triage agent handle cases where it cannot confidently assess urgency (e.g., ambiguous symptoms, conflicting information)?

A) Default to "Urgent" and flag for human nurse review within 5 minutes

B) Default to "Standard" and notify the patient that a clinician will follow up

C) Immediately transfer to a live triage nurse via chat/call

D) Ask additional clarifying questions (up to a maximum limit) before escalating

E) Other (please describe after [Answer]: tag below)

[Answer]: D (consider this few quick follow up questions and if the ambiguity is not cleared rhen we can mark it for immediate assistance)

---

## Question 3
What EHR system(s) does Healthcare Network currently use?

A) Epic

B) Cerner (Oracle Health)

C) Allscripts

D) Custom/proprietary EHR

E) Other (please describe after [Answer]: tag below)

[Answer]: E) Other  "assume Epic FHIR R4" or "mock/stub EHR interface for PoC

---

## Question 4
How should Emergency escalation work (FR-003)?

A) Push notification + SMS to on-call physician with patient summary

B) Auto-page the on-call team via existing paging system (PagerDuty, Opsgenie, etc.)

C) Transfer patient to live call with on-call staff immediately

D) All of the above (notification + page + transfer option)

E) Other (please describe after [Answer]: tag below)

[Answer]: D 

---

## Question 5
What is the drug interaction checking source for FR-004?

A) Integrate with an existing drug interaction API (e.g., DrugBank, RxNorm, First Databank)

B) Pull medication data from the EHR and use a third-party interaction checker

C) Use an AI/LLM-based approach with a curated drug interaction knowledge base

D) Interface with the hospital pharmacy system for real-time checks

E) Other (please describe after [Answer]: tag below)

[Answer]: D

---

## Question 6
How many specialist departments need to be supported for routing (FR-005)?

A) 5-10 departments (e.g., Cardiology, Neurology, Orthopedics, GI, Pulmonology)

B) 10-20 departments (comprehensive specialty coverage)

C) 20+ departments (full academic medical center coverage)

D) Variable per clinic (each clinic has different specialties available)

E) Other (please describe after [Answer]: tag below)

[Answer]: A

---

## Question 7
What patient authentication method should be used?

A) Patient portal login (username/password + MFA)

B) Integration with existing healthcare SSO (e.g., MyChart patient login)

C) SMS/email verification with date of birth confirmation

D) No authentication required (anonymous triage) with optional identification

E) Other (please describe after [Answer]: tag below)

[Answer]: C (go with sms/email but in case it's not accessible and urgency consider skipping authentication -> consier peronakl identifiable data access always behind authentication generic info can go unauthenticated in emergency cases)

---

## Question 8
What is the target availability architecture?

A) Multi-AZ within a single AWS region (99.99% target)

B) Multi-region active-passive (disaster recovery with RTO < 15 minutes)

C) Multi-region active-active (near-zero downtime)

D) Single region with robust auto-scaling (cost-optimized, 99.9% target)

E) Other (please describe after [Answer]: tag below)

[Answer]: D

---

## Question 9
What languages must the triage system support?

A) English only

B) English and Spanish

C) English, Spanish, and top 5 languages by patient population

D) Full multilingual with real-time translation (10+ languages)

E) Other (please describe after [Answer]: tag below)

[Answer]: A (go with english but should be extendable)

---

## Question 10
What is the expected timeline/app level for this build?

A) PoC (Proof of Concept) — 2-4 weeks, core triage flow only, single clinic pilot

B) MVP (Minimum Viable Product) — 6-8 weeks, full triage + portal, 3-5 clinic rollout

C) Production — 12+ weeks, all features, all 15 clinics, full HIPAA audit

D) Phased: PoC first, then iterate to MVP, then Production

E) Other (please describe after [Answer]: tag below)

[Answer]: b - MVP

---

## Question 11: Resiliency Extensions
Should the resiliency baseline be applied to this project?

**What this extension is.** Enabling it applies a set of directional, design-time best practices for building resilient systems, derived from the AWS Well-Architected Framework (Reliability Pillar) and resilience-review guidance. It steers requirements, design, and code toward fault tolerance, high availability, observability, and recoverability.

**What this extension is NOT.** Enabling it does not make your workload production-ready, nor does it certify or guarantee any availability, RTO, or RPO target. It is a starting point that scaffolds good resiliency decisions early.

A) Yes — apply the resiliency baseline as directional best practices and design-time guidance (recommended for business-critical workloads)

B) No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: 

---

## Question 12: Security Extensions
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: x - LET'S KEEP THE NECESSARY ONES ONLY for an MVP

---

## Question 13: Property-Based Testing Extension
Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic, data transformations, serialization, or stateful components)

B) Partial — enforce PBT rules only for pure functions and serialization round-trips (suitable for projects with limited algorithmic complexity)

C) No — skip all PBT rules (suitable for simple CRUD applications, UI-only projects, or thin integration layers with no significant business logic)

X) Other (please describe after [Answer]: tag below)

[Answer]: b

---
