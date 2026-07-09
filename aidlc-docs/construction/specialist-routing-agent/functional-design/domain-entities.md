# Domain Entities — Specialist Routing Agent

## Entity: RoutingDecision (Primary Output)

| Field | Type | Description |
|---|---|---|
| session_id | UUID | Links to triage session |
| patient_id | UUID | Patient identifier |
| department | String | Matched specialist department |
| department_confidence | Float (0-1) | Confidence in department match |
| routing_method | Enum | RULE_BASED, LLM_REASONING, HYBRID |
| routing_reasoning | String | Why this department was selected |
| specialist_name | String | null | Specific specialist (if from slot) |
| primary_clinic | ClinicAvailability | Home clinic results |
| alternatives | List[ClinicAvailability] | Alternative clinic options (max 3) |
| appointment_window | AppointmentWindow | Required scheduling window |
| status | Enum | ROUTED, NO_AVAILABILITY, AMBIGUOUS_DEPARTMENT |
| mental_health_priority | Boolean | If true, same-day routing for mental health |
| routed_at | ISO DateTime | Timestamp |

---

## Entity: ClinicAvailability

| Field | Type | Description |
|---|---|---|
| clinic_id | String | Clinic identifier |
| clinic_name | String | Display name |
| available_slots | List[SlotInfo] | Available appointment times |
| reason | String | null | Why this alternative (e.g., "Primary has no availability") |

---

## Entity: SlotInfo

| Field | Type | Description |
|---|---|---|
| datetime | ISO DateTime | Appointment date and time |
| specialist_name | String | Assigned specialist |
| duration_minutes | Integer | Appointment length (default: 30) |
| room | String | null | Room assignment (future) |

---

## Entity: AppointmentWindow

| Field | Type | Description |
|---|---|---|
| start | ISO DateTime | Earliest acceptable appointment |
| end | ISO DateTime | Latest acceptable appointment |
| priority | Enum | HIGH, NORMAL, STANDARD |

---

## Entity: DepartmentMapping (Configuration)

Static rule table loaded at agent startup:

| Field | Type | Description |
|---|---|---|
| department_name | String | Official department name |
| primary_keywords | List[String] | Keywords from primary_complaint that match |
| associated_keywords | List[String] | Keywords from associated_symptoms that confirm |
| exclusion_keywords | List[String] | Keywords that rule OUT this department |
| confidence_when_matched | Float | Default confidence for rule-based match |

### MVP Configuration (10 departments):

```yaml
- department: Cardiology
  primary_keywords: [chest pain, heart, palpitations, blood pressure, hypertension]
  associated_keywords: [shortness of breath, sweating, arm pain, jaw pain]
  exclusion_keywords: [cough, fever, wheezing]
  confidence: 0.85

- department: Neurology
  primary_keywords: [headache, migraine, dizziness, numbness, tingling, seizure, vision]
  associated_keywords: [confusion, weakness, speech difficulty]
  exclusion_keywords: [ear pain, sinus]
  confidence: 0.85

- department: Orthopedics
  primary_keywords: [joint pain, back pain, knee, shoulder, fracture, sprain, bone]
  associated_keywords: [swelling, limited movement, injury, fall]
  exclusion_keywords: [rash, fever]
  confidence: 0.90

- department: Gastroenterology
  primary_keywords: [stomach pain, abdominal pain, nausea, vomiting, diarrhea, reflux, bloating]
  associated_keywords: [blood in stool, weight loss, appetite loss]
  exclusion_keywords: [urinary, kidney]
  confidence: 0.85

- department: Pulmonology
  primary_keywords: [cough, shortness of breath, wheezing, asthma, breathing difficulty]
  associated_keywords: [chest tightness, sputum, fever, night sweats]
  exclusion_keywords: [chest pain without cough, palpitations]
  confidence: 0.85

- department: Dermatology
  primary_keywords: [rash, skin, itching, acne, mole, lesion, eczema, psoriasis]
  associated_keywords: [spreading, color change, bleeding mole]
  exclusion_keywords: []
  confidence: 0.90

- department: ENT
  primary_keywords: [ear pain, sore throat, sinus, hearing loss, nasal, tinnitus, hoarse]
  associated_keywords: [congestion, post-nasal drip, dizziness]
  exclusion_keywords: [headache without ear/throat]
  confidence: 0.85

- department: Urology
  primary_keywords: [urinary, bladder, kidney pain, blood in urine, frequent urination]
  associated_keywords: [burning sensation, lower back pain, groin pain]
  exclusion_keywords: [abdominal bloating]
  confidence: 0.85

- department: Psychiatry
  primary_keywords: [anxiety, depression, insomnia, mood, panic, stress, mental health]
  associated_keywords: [sleep changes, appetite changes, concentration, self-harm]
  exclusion_keywords: []
  confidence: 0.80

- department: Internal Medicine
  primary_keywords: [fatigue, fever, weight loss, general, multiple symptoms, unclear]
  associated_keywords: [any]
  exclusion_keywords: []
  confidence: 0.60
```

Internal Medicine is the **catch-all** — lowest confidence, used when no other department matches clearly.

---

## Entity: ClinicNetwork (Configuration)

Static clinic metadata:

| Field | Type | Description |
|---|---|---|
| clinic_id | String | Unique clinic identifier |
| clinic_name | String | Display name |
| departments_available | List[String] | Which departments this clinic has |
| alternative_priority | List[String] | Ordered list of nearby clinics (for fallback) |

---

## Data Flow

```
Input:
  - StructuredSymptoms (from Unit 2)
  - UrgencyResult (from Unit 3)
  - patient_clinic (from Patient record)

Step 1: Department Matching
  → Load DepartmentMapping config
  → Match primary_complaint keywords against departments
  → Check associated_symptoms for confirmation/exclusion
  → If single clear match (confidence ≥ 0.70): use it
  → If ambiguous: invoke LLM for disambiguation

Step 2: Appointment Window Calculation
  → Map urgency_level to window (URGENT=same day, STANDARD=48h, ROUTINE=2 weeks)
  → Set start = now, end = now + window

Step 3: Availability Check
  → Query scheduling system for patient's primary clinic
  → If slots available: select best slot(s)
  → If no slots: query alternative clinics (max 3, 2s timeout each)

Step 4: Result Assembly
  → Build RoutingDecision JSON
  → Set status based on outcome

Step 5: Audit
  → Write to AuditTrail (ROUTING_DECIDED)

Output:
  RoutingDecision JSON → Supervisor → Clinical Summary → Portal
```
