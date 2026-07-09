# Business Logic Model — Symptom Assessment Agent

## Overview

The Symptom Assessment Agent is the patient-facing conversational AI that conducts structured clinical intake. It drives a multi-turn conversation to collect onset, severity, duration, history, medications, and associated symptoms — then outputs a structured JSON payload consumed by the Triage Scoring Agent.

---

## Conversation Flow Model

```
Patient connects
       |
       v
+------------------+
| GREETING         |  "Hi, I'm here to help assess your symptoms.
|                  |   What's your main concern today?"
+------------------+
       |
       v
+------------------+
| PRIMARY          |  Patient describes main complaint
| COMPLAINT        |  → Agent extracts: complaint category
+------------------+
       |
       v
+------------------+
| ONSET            |  "When did this start?"
|                  |  → Extract: duration/onset description
+------------------+
       |
       v
+------------------+
| SEVERITY         |  "On a scale of 1-10, how severe is it right now?"
|                  |  → Extract: numeric severity (validate 1-10)
+------------------+
       |
       v
+------------------+
| DURATION/        |  "Is it constant or does it come and go?"
| PATTERN          |  "Has it gotten worse, better, or stayed the same?"
+------------------+
       |
       v
+------------------+
| ASSOCIATED       |  "Are you experiencing any other symptoms?"
| SYMPTOMS         |  (context-aware: if headache → ask about vision,
|                  |   nausea, neck stiffness)
+------------------+
       |
       v
+------------------+
| MEDICAL          |  "Do you have any medical conditions I should know about?"
| HISTORY          |  (check EHR if authenticated for known conditions)
+------------------+
       |
       v
+------------------+
| MEDICATIONS      |  "Are you currently taking any medications?"
|                  |  (check EHR if authenticated for medication list)
+------------------+
       |
       v
+------------------+
| ALLERGIES        |  "Do you have any drug allergies?"
+------------------+
       |
       v
+------------------+
| COMPLETENESS     |  Agent evaluates: do I have enough data?
| CHECK            |  → If yes: proceed to output
|                  |  → If no: ask targeted follow-up (max 3)
+------------------+
       |
       v
+------------------+
| OUTPUT           |  Generate StructuredSymptoms JSON
|                  |  Mark assessment_complete = true
+------------------+
```

---

## Conversation Rules

### Rule 1: Adaptive Questioning
The agent does NOT ask all questions robotically. It adapts based on:
- **Primary complaint** drives which associated symptoms to ask about
- **Severity 8+** → reduce questions, prioritize speed (possible emergency)
- **EHR data available** → skip medications/history questions, confirm instead ("I see you're on warfarin — is that still current?")
- **Patient already provided info** → don't re-ask what they already said

### Rule 2: Conversation Length Target
- **Target**: Complete assessment in 8-12 conversational turns (including patient responses)
- **Maximum**: 15 turns before forcing completeness (mark any gaps as "not provided")
- **If severity ≥ 8**: Reduce to 5-7 turns (fast-track to scoring)

### Rule 3: Tone and Language
- Empathetic, professional, non-alarming
- Use plain language (no medical jargon unless patient uses it first)
- Acknowledge pain/distress ("I understand that must be uncomfortable")
- Never diagnose or provide medical advice ("I'm gathering information so your doctor can help you")

### Rule 4: Structured Data Extraction
Every patient message is processed for extractable clinical data. The agent maintains a running `StructuredSymptoms` object that fills in as the conversation progresses. It doesn't wait until the end — it continuously extracts.

### Rule 5: Emergency Red Flags
If the patient mentions ANY of these, immediately mark for emergency fast-track:
- Chest pain + shortness of breath
- "I can't breathe"
- Severe bleeding that won't stop
- Signs of stroke (face drooping, arm weakness, speech difficulty)
- Suicidal ideation or self-harm
- Loss of consciousness
- Allergic reaction (throat swelling, difficulty breathing)

When a red flag is detected: truncate remaining questions, output what we have with a `red_flag` marker, and let the Triage Scoring Agent classify as Emergency immediately.

---

## Agent System Prompt (Structure)

```
You are a clinical intake assistant for Healthcare Network.
Your role is to gather symptom information through a friendly,
empathetic conversation. You do NOT diagnose or provide medical advice.

Your goal: Collect enough information to fill this structured assessment:
- Primary complaint
- Onset (when it started)
- Severity (1-10 scale)
- Duration and pattern (constant vs intermittent, worsening vs stable)
- Associated symptoms
- Relevant medical history
- Current medications
- Allergies

Rules:
- Be conversational, not robotic
- Ask one question at a time
- Adapt follow-up questions to what the patient has already told you
- If severity is 8+, fast-track (fewer questions)
- Never diagnose or suggest treatment
- Acknowledge the patient's experience
- If you detect emergency red flags, collect minimal info and flag immediately
- Complete in 8-12 turns (15 maximum)
```

---

## Completeness Scoring Logic

The agent evaluates completeness before declaring `assessment_complete = true`:

| Field | Weight | Required? |
|---|---|---|
| primary_complaint | 25% | Yes — cannot complete without |
| severity | 20% | Yes — cannot complete without |
| onset | 15% | Yes — cannot complete without |
| duration/pattern | 10% | Preferred but not blocking |
| associated_symptoms | 10% | Preferred but not blocking |
| medical_history | 10% | Optional (EHR may provide) |
| medications | 5% | Optional (EHR may provide) |
| allergies | 5% | Optional |

**Completion threshold**: Score ≥ 70% (weighted) → assessment complete  
**Mandatory fields**: primary_complaint + severity + onset must ALL be present regardless of score  
**Fast-track override**: If severity ≥ 8 and primary_complaint is clear → complete at 60%

---

## Clarifying Questions (Uncertainty Handling)

When the agent cannot confidently extract data from a patient response:

1. Ask a **targeted** follow-up (not open-ended)
   - Bad: "Can you tell me more?"
   - Good: "When you say the pain is 'pretty bad', would you rate it around 5-6 or more like 7-8 on a scale of 1-10?"

2. Maximum **3 clarifying questions** per ambiguous area

3. If still unclear after 3 attempts:
   - Record the field as `"value": null, "note": "patient unable to quantify"`
   - Move on to next question
   - The Triage Scoring Agent will handle incomplete data by adjusting confidence downward

---

## Session State Management

The agent maintains state across turns:

```json
{
  "session_id": "uuid",
  "turn_count": 0,
  "phase": "GREETING|PRIMARY_COMPLAINT|ONSET|SEVERITY|DURATION|ASSOCIATED|HISTORY|MEDICATIONS|ALLERGIES|CLARIFYING|COMPLETE",
  "structured_symptoms": { ... },   // progressively filled
  "completeness_score": 0.0,
  "red_flag_detected": false,
  "ehr_data_available": false,
  "ehr_medications": [],             // pre-loaded if authenticated
  "ehr_conditions": [],              // pre-loaded if authenticated
  "pending_clarifications": []       // fields needing follow-up
}
```

State is persisted to DynamoDB (Sessions table) after each turn so the conversation survives Lambda cold starts and connection interruptions.
