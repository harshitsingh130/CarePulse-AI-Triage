# Business Rules — Symptom Assessment Agent

## BR-SA-001: Single Question Per Turn

**Rule**: The agent asks exactly ONE question per response. Never ask multiple questions in a single message.

**Rationale**: Patients in distress may be confused by multi-part questions. Single questions reduce cognitive load and produce cleaner data extraction.

**Exception**: For fast-track (severity ≥ 8), the agent may combine onset + duration into a single question to save time.

---

## BR-SA-002: Severity Validation

**Rule**: Severity must be a number between 1 and 10. If the patient provides a non-numeric response, convert it:

| Patient says | Mapped to |
|---|---|
| "mild", "a little", "not too bad" | 2-3 |
| "moderate", "noticeable", "uncomfortable" | 4-5 |
| "bad", "pretty bad", "significant" | 6-7 |
| "severe", "really bad", "awful" | 8-9 |
| "worst pain ever", "unbearable", "10/10" | 10 |
| Ambiguous | Ask: "On a scale of 1 to 10, where 1 is barely noticeable and 10 is the worst you can imagine?" |

---

## BR-SA-003: EHR Data Handling

**Rule**: If the patient is authenticated and EHR data is available:

1. **Medications**: Pre-load from EHR. Ask: "I see you're currently on [med1, med2, med3]. Is that still accurate?"
   - If yes → use EHR list
   - If no → ask what changed
   - If patient adds new meds → append to list

2. **Medical history**: Pre-load known conditions. Ask: "Your records show [condition1, condition2]. Any changes?"
   - If yes → note changes
   - If no → use EHR conditions

3. **Never assume EHR data is current** — always confirm with patient

---

## BR-SA-004: Context-Aware Associated Symptom Questions

**Rule**: The associated symptoms question adapts to the primary complaint:

| Primary Complaint Category | Ask About |
|---|---|
| Headache | Vision changes, nausea, neck stiffness, light sensitivity, recent head injury |
| Chest pain | Shortness of breath, arm/jaw pain, sweating, dizziness |
| Abdominal pain | Nausea, vomiting, diarrhea, fever, blood in stool |
| Breathing difficulty | Cough, wheezing, fever, chest tightness, recent illness |
| Musculoskeletal pain | Swelling, redness, limited range of motion, recent injury |
| Skin issue | Rash location, itching, spreading, fever, recent exposure |
| Mental health | Sleep changes, appetite changes, concentration, self-harm thoughts |
| General / Other | Fever, fatigue, weight changes, appetite changes |

---

## BR-SA-005: Emergency Red Flag Detection

**Rule**: If ANY red flag pattern is detected in patient text, set `red_flag_detected = true` and fast-track.

**Red flag patterns** (case-insensitive, partial match):

| Category | Patterns |
|---|---|
| Cardiac | "chest pain" + ("shortness of breath" OR "sweating" OR "arm pain" OR "jaw pain") |
| Respiratory | "can't breathe", "difficulty breathing", "choking", "throat closing" |
| Neurological | "face drooping", "arm weakness", "can't speak", "sudden confusion", "worst headache of my life" |
| Hemorrhage | "won't stop bleeding", "blood everywhere", "bleeding heavily" |
| Mental health | "want to kill myself", "want to die", "self-harm", "suicide" |
| Allergic | "throat swelling", "anaphylaxis", "epipen" |
| Consciousness | "passed out", "lost consciousness", "seizure" |

**When detected**:
1. Acknowledge: "I want to make sure you get help quickly."
2. Collect only: primary complaint + severity (if not already captured)
3. Mark: `red_flag_detected = true`, `red_flag_category = "<category>"`
4. Output immediately with `assessment_complete = true`
5. Do NOT continue with remaining questions

---

## BR-SA-006: Conversation Timeout Handling

**Rule**: Handle patient non-responsiveness:

| Silence Duration | Action |
|---|---|
| 2 minutes | Send: "I'm still here. Take your time — would you like to continue?" |
| 5 minutes (after prompt) | Send: "Just checking in. If you need to step away, you can come back anytime and we'll pick up where we left off." |
| 10 minutes total silence | Mark session as PAUSED in DynamoDB. Do not terminate. |
| Patient returns | Resume from last state: "Welcome back! We were talking about [last topic]. [Repeat last question]" |

---

## BR-SA-007: Language and Tone Rules

**Must**:
- Use simple, plain language (8th grade reading level)
- Acknowledge emotions ("I understand that's concerning")
- Be patient (no rushing language)
- Use encouraging language ("That's helpful information, thank you")

**Must NOT**:
- Use medical terminology unless patient used it first
- Diagnose ("It sounds like you might have...")
- Provide treatment advice ("You should take...")
- Minimize symptoms ("That doesn't sound serious")
- Express urgency/alarm ("That's very concerning, you need to go to the ER")

---

## BR-SA-008: Data Extraction Confidence

**Rule**: Every extracted field has a confidence level:

| Confidence | Meaning | Action |
|---|---|---|
| HIGH (0.9+) | Patient explicitly stated the value | Record directly |
| MEDIUM (0.6-0.9) | Inferred from context | Record with note, consider confirming |
| LOW (<0.6) | Ambiguous or contradictory | Ask clarifying question (up to 3 attempts) |

If confidence remains LOW after 3 clarification attempts → record as null with note.

---

## BR-SA-009: Conversation Resumption

**Rule**: If a patient reconnects to a paused session:

1. Load session state from DynamoDB
2. Summarize what was collected: "Let me recap — you mentioned [primary complaint] that started [onset] with severity [X/10]."
3. Ask: "Is that still accurate, or has anything changed?"
4. If unchanged → resume from next unanswered question
5. If changed → update relevant fields and continue

---

## BR-SA-010: Output Contract

**Rule**: When `assessment_complete = true`, the agent outputs the final `StructuredSymptoms` JSON exactly matching this schema:

```json
{
  "session_id": "string (UUID)",
  "patient_id": "string (UUID)",
  "assessment_complete": true,
  "completeness_score": 0.0-1.0,
  "red_flag_detected": false,
  "red_flag_category": null,
  "primary_complaint": {
    "text": "string (patient's words)",
    "category": "string (mapped category)",
    "confidence": 0.0-1.0
  },
  "onset": {
    "description": "string",
    "days_ago_estimate": null | number,
    "confidence": 0.0-1.0
  },
  "severity": {
    "score": 1-10,
    "source": "explicit | inferred",
    "confidence": 0.0-1.0
  },
  "duration_pattern": {
    "type": "constant | intermittent | worsening | improving | stable",
    "description": "string",
    "confidence": 0.0-1.0
  },
  "associated_symptoms": [
    {
      "symptom": "string",
      "severity": null | 1-10,
      "confidence": 0.0-1.0
    }
  ],
  "medical_history": {
    "conditions": ["string"],
    "source": "ehr | patient_reported | both",
    "confidence": 0.0-1.0
  },
  "medications": {
    "current": ["string"],
    "source": "ehr | patient_reported | both",
    "confidence": 0.0-1.0
  },
  "allergies": {
    "list": ["string"],
    "confidence": 0.0-1.0
  },
  "conversation_turns": number,
  "fast_tracked": false,
  "assessed_at": "ISO datetime"
}
```

This payload is passed to the Triage Scoring Agent (Unit 3) for urgency classification.
