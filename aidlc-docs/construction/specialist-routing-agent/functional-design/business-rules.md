# Business Rules — Specialist Routing Agent

## BR-SR-001: Never Route Emergency Cases

**Rule**: If `urgency_level == EMERGENCY`, this agent is NOT invoked. Emergency cases go to escalation, not specialist appointment scheduling.

The Supervisor Agent enforces this — but the Routing Agent also validates and rejects if it somehow receives an Emergency input:
- Return immediately with `status: "rejected"` and `reason: "Emergency cases do not route to specialist appointments"`

---

## BR-SR-002: Department Must Match Available Departments

**Rule**: The routing agent can ONLY route to departments that exist in the Healthcare Network configuration.

**MVP Department List (5-10)**:
1. Cardiology
2. Neurology
3. Orthopedics
4. Gastroenterology (GI)
5. Pulmonology
6. Dermatology
7. ENT (Ear, Nose, Throat)
8. Urology
9. Psychiatry
10. Internal Medicine (catch-all)

If the LLM suggests a department NOT in this list → map to the closest match or route to Internal Medicine.

---

## BR-SR-003: Rule-Based First, LLM Second

**Rule**: Always attempt rule-based matching first. Only invoke LLM if:
- Primary complaint category doesn't clearly match a single department
- Multiple departments are plausible (ambiguous)
- Associated symptoms contradict the primary complaint mapping

**Rationale**: Rule-based matching is faster (~10ms vs 2-3s), cheaper (no tokens), and deterministic. LLM is the fallback for nuance.

---

## BR-SR-004: Urgency Dictates Window Strictness

**Rule**: The appointment window is non-negotiable based on urgency:

| Urgency | Window | Behavior if No Slots |
|---|---|---|
| URGENT | Same day / next day | Search ALL clinics. If still none: return `no_availability` with advisory "Contact clinic directly for urgent scheduling" |
| STANDARD | Within 48 hours | Search alternatives. If none in 48h: extend to 72h, then flag |
| ROUTINE | Within 2 weeks | Almost always available; if not: extend to 3 weeks |

---

## BR-SR-005: Patient's Home Clinic First

**Rule**: Always check the patient's primary clinic first before searching alternatives.

**Rationale**: Patients prefer their home clinic (familiar staff, closer to home, existing records). Only suggest alternatives when the home clinic can't accommodate the urgency window.

---

## BR-SR-006: Maximum 3 Alternatives

**Rule**: Never return more than 3 alternative clinics. Information overload harms decision-making.

**Selection criteria for alternatives** (ordered):
1. Has available slots within the urgency window
2. Earliest available slot wins (time-priority for Urgent)
3. For Routine: spread options across different days/times for patient flexibility

---

## BR-SR-007: Ambiguous Routing Transparency

**Rule**: When routing confidence is below 0.70, the output MUST include:
- Clear explanation of why routing is ambiguous
- The top 2 department candidates with reasoning for each
- A note for the physician: "Routing confidence is low — physician may redirect to [alternative dept]"

This appears in the SOAP note Plan section and the physician can override during the appointment.

---

## BR-SR-008: No Self-Referral for Psychiatry

**Rule**: If the Triage Scoring Agent assigned urgency based on mental health red flags (self-harm, suicidal ideation), routing to Psychiatry MUST include:
- A crisis resource note: "If you're in crisis, call 988 (Suicide & Crisis Lifeline)"
- `appointment_window` set to same-day/next-day regardless of scoring urgency
- Flag: `mental_health_priority: true`

---

## BR-SR-009: Scheduling System Timeout

**Rule**: Scheduling system query has a **2-second timeout** per clinic.

| Scenario | Behavior |
|---|---|
| Primary clinic responds within 2s | Use response |
| Primary clinic times out | Try next 2 alternatives (2s each) |
| All clinics time out | Return `status: "no_availability"` with note: "Scheduling system temporarily unavailable. A clinic coordinator will contact you." |

Total maximum time for availability checking: 6 seconds (3 clinics × 2s each, sequential).

---

## BR-SR-010: Audit Logging

**Rule**: Every routing decision is logged to AuditTrail:
- `eventType: ROUTING_DECIDED`
- Details: matched department, confidence, method (rule/LLM), alternatives offered, slot selected
- This enables: routing accuracy analysis, department load balancing, scheduling gap identification
