# Business Logic Model — Specialist Routing Agent

## Overview

The Specialist Routing Agent maps a patient's symptom pattern to the most appropriate specialist department, checks availability at their clinic (and alternatives), and returns a routing decision with available appointment slots. It uses a combination of rule-based symptom-to-department mapping and LLM reasoning for ambiguous cases.

---

## Routing Flow

```
Input: StructuredSymptoms + UrgencyResult + patient_clinic
         |
         v
+---------------------------+
| DEPARTMENT MATCHING       |  Map primary complaint + associated
|                           |  symptoms to specialist department
+---------------------------+
         |
         | matched department (or ambiguous)
         v
+---------------------------+
| URGENCY-BASED TIMING      |  Determine appointment window
|                           |  based on urgency level
+---------------------------+
         |
         v
+---------------------------+
| AVAILABILITY CHECK        |  Query scheduling system (stubbed)
| (stubbed for MVP)         |  for available slots at patient clinic
+---------------------------+
         |
    Available?
    /         \
   Yes         No
    |           |
    v           v
+--------+  +---------------------------+
| SELECT |  | ALTERNATIVE CLINIC        |
| SLOT   |  | SEARCH                    |
+--------+  | Check nearby clinics      |
    |       +---------------------------+
    |           |
    v           v
+---------------------------+
| RESULT ASSEMBLY           |  Build RoutingDecision JSON
+---------------------------+
         |
         v
Output: RoutingDecision JSON
```

---

## Department Matching Logic

### Primary Mapping Table

The agent uses a symptom-to-department rule table. If the primary complaint category matches, route to that department.

| Primary Complaint Category | Department | Confidence |
|---|---|---|
| Chest pain, heart palpitations, blood pressure | **Cardiology** | HIGH |
| Headache, dizziness, numbness, tingling, seizure | **Neurology** | HIGH |
| Bone pain, joint pain, back pain, fracture, sprain | **Orthopedics** | HIGH |
| Abdominal pain, nausea, vomiting, diarrhea, reflux | **Gastroenterology (GI)** | HIGH |
| Cough, shortness of breath, wheezing, asthma | **Pulmonology** | HIGH |
| Rash, skin lesion, itching, acne, mole change | **Dermatology** | MEDIUM |
| Ear pain, sore throat, sinus, hearing loss, nasal | **ENT** | MEDIUM |
| Urinary issues, kidney pain, blood in urine | **Urology** | MEDIUM |
| Anxiety, depression, insomnia, mood changes | **Psychiatry** | MEDIUM |
| General/multiple/unclear | **Internal Medicine** | LOW |

### Ambiguity Resolution

When the complaint could map to multiple departments:

1. **Check associated symptoms** — they often disambiguate
   - Headache + vision changes → Neurology (not ENT)
   - Abdominal pain + urinary frequency → Urology (not GI)
   - Chest pain + cough + fever → Pulmonology (not Cardiology)

2. **If still ambiguous** → use LLM reasoning:
   - Prompt with symptoms + department options + "which is most appropriate and why?"
   - Temperature 0.0 for consistency
   - Set `routing_confidence` to the LLM's stated confidence

3. **If LLM confidence < 0.60** → flag for nurse review
   - Set `routing_confidence < 0.60` in output
   - Supervisor may route to nurse for override (reuses same Standard workflow as triage scoring)

---

## Urgency-Based Appointment Window

| Urgency Level | Appointment Window | Scheduling Priority |
|---|---|---|
| EMERGENCY | N/A (escalated, not routed to appointment) | — |
| URGENT | Same day or next day | HIGH priority slot |
| STANDARD | Within 48 hours | Normal priority |
| ROUTINE | Within 1-2 weeks | Standard scheduling |

---

## Availability Check (Stubbed for MVP)

### Scheduling System Interface

**Request**:
```json
{
  "clinic_id": "string",
  "department": "string",
  "priority": "HIGH | NORMAL | STANDARD",
  "window_start": "ISO datetime",
  "window_end": "ISO datetime",
  "duration_minutes": 30
}
```

**Response**:
```json
{
  "status": "available | limited | unavailable",
  "slots": [
    {
      "datetime": "ISO datetime",
      "specialist_name": "string",
      "clinic_id": "string",
      "room": "string | null"
    }
  ]
}
```

### MVP Stub Behavior

| Test Scenario | Stub Returns |
|---|---|
| Department = "Cardiology" at clinic "clinic-01" | 3 available slots within window |
| Department = "Neurology" at clinic "clinic-01" | 0 slots (triggers alternative search) |
| Department = "Orthopedics" at any clinic | 2 available slots |
| Any department at clinic "clinic-unavailable" | 0 slots at primary, 2 at alternative |

---

## Alternative Clinic Search

When the patient's home clinic has no availability:

1. Identify nearby clinics (within the Healthcare Network's 15 clinics)
2. Query each for availability in the same department + window
3. Return up to 3 alternatives, sorted by:
   - Earliest available slot (first priority)
   - Geographic proximity to patient (second priority — future, use clinic metadata)

### MVP Implementation
For MVP, clinic "proximity" is simply an ordered list (hardcoded clinic priority per home clinic). Real geographic routing comes at Production level.

---

## Slot Selection Logic

When multiple slots are available, select the **first available** that meets the urgency window. Present up to 3 options to the patient via the Portal.

| Urgency | Selection Strategy |
|---|---|
| URGENT | First available slot (earliest in window) |
| STANDARD | First available slot within 48 hours |
| ROUTINE | Offer 3 options spread across the window (patient chooses) |

---

## Output Contract

```json
{
  "session_id": "string (UUID)",
  "patient_id": "string (UUID)",
  "department": "string (matched department name)",
  "department_confidence": 0.0-1.0,
  "routing_method": "rule_based | llm_reasoning | hybrid",
  "routing_reasoning": "string (why this department)",
  "specialist_name": "string | null (if known from slot)",
  "primary_clinic": {
    "clinic_id": "string",
    "clinic_name": "string",
    "available_slots": ["ISO datetime"]
  },
  "alternatives": [
    {
      "clinic_id": "string",
      "clinic_name": "string",
      "available_slots": ["ISO datetime"],
      "reason": "string (e.g., 'Primary clinic has no availability')"
    }
  ],
  "appointment_window": {
    "start": "ISO datetime",
    "end": "ISO datetime",
    "priority": "HIGH | NORMAL | STANDARD"
  },
  "status": "routed | no_availability | ambiguous_department",
  "routed_at": "ISO datetime"
}
```

Consumed by:
- **Supervisor Agent** — confirms routing success or flags no-availability
- **Clinical Summary Agent** — routing reasoning in SOAP Plan section
- **Patient Portal** — displays department, clinic, available slots
