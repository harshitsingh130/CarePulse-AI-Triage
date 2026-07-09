# Business Logic Model — Triage Scoring Agent

## Overview

The Triage Scoring Agent receives the StructuredSymptoms JSON from the Symptom Assessment Agent and produces an urgency classification (Emergency/Urgent/Standard/Routine) with a confidence score. This is the critical clinical decision point — it must be **deterministic** (same inputs → same output) and **auditable** (reasoning captured for every decision).

---

## Scoring Architecture

The agent uses a **hybrid approach**:

1. **Rule-based pre-classifier** — catches clear-cut cases deterministically (red flags → Emergency, low severity + minor complaint → Routine)
2. **LLM-based clinical reasoning** — handles nuanced cases where rules alone aren't sufficient
3. **Confidence calibration** — adjusts confidence based on data completeness and ambiguity

```
Input: StructuredSymptoms JSON
         |
         v
+------------------------+
| RULE-BASED             |  Fast path for clear cases
| PRE-CLASSIFIER         |  (red flags, severity extremes)
+------------------------+
    |           |
    | Definitive   | Ambiguous
    v              v
+--------+    +------------------------+
| OUTPUT |    | LLM CLINICAL           |
| (high  |    | REASONING              |
| conf)  |    | (Bedrock Claude)       |
+--------+    +------------------------+
                   |
                   v
              +------------------------+
              | CONFIDENCE              |
              | CALIBRATION             |
              +------------------------+
                   |
                   v
              +--------+
              | OUTPUT |
              +--------+
```

---

## Rule-Based Pre-Classifier

### Immediate Emergency (confidence: 0.95+)

Classify as **EMERGENCY** immediately if ANY of:
- `red_flag_detected == true`
- `severity >= 9` AND primary complaint in [chest pain, breathing difficulty, severe bleeding, loss of consciousness]
- `severity == 10` (any complaint)

### Immediate Routine (confidence: 0.90+)

Classify as **ROUTINE** if ALL of:
- `severity <= 2`
- `onset.days_ago_estimate > 7` (chronic, not worsening)
- `duration_pattern.type == "stable" OR "improving"`
- No red flags
- No associated symptoms with severity > 3

### Pass to LLM

If neither pre-classifier fires → pass to LLM clinical reasoning.

---

## LLM Clinical Reasoning

### Prompt Structure

```
You are a clinical triage scoring system. Your ONLY job is to classify 
the urgency level of a patient's symptoms. You do NOT diagnose.

Given the following structured symptom assessment, classify urgency as:
- EMERGENCY: Life-threatening, requires immediate intervention (minutes)
- URGENT: Serious, requires same-day attention (hours)
- STANDARD: Needs medical attention soon (24-48 hours)
- ROUTINE: Non-urgent, can wait for next available appointment (days-weeks)

Consider these clinical factors:
1. Severity score (1-10) — higher = more urgent
2. Onset recency — sudden onset of severe symptoms = more urgent
3. Pattern — worsening = more urgent, improving = less urgent
4. Red flags — any emergency indicators
5. Associated symptoms — multiple concerning symptoms together = more urgent
6. Risk factors — medical history that amplifies risk (e.g., chest pain + cardiac history)
7. Medications — drug interactions or contraindications that elevate risk

IMPORTANT:
- Be conservative. When in doubt between two levels, choose the MORE urgent one.
- Provide your reasoning step by step.
- Rate your confidence (0.0-1.0) in the classification.

Patient Assessment:
{structured_symptoms_json}

Respond in this exact JSON format:
{
  "urgency_level": "EMERGENCY|URGENT|STANDARD|ROUTINE",
  "confidence": 0.0-1.0,
  "reasoning": "Step-by-step clinical reasoning",
  "risk_factors": ["list of identified risk factors"],
  "recommended_timeframe": "immediate|within 4 hours|within 24 hours|within 48 hours|within 1 week|within 2 weeks"
}
```

### Temperature Setting
- **Temperature: 0.0** — deterministic output for same input
- This ensures consistency across clinics (FR-002 requirement)

---

## Confidence Calibration

After the LLM produces its classification, confidence is adjusted based on data quality:

### Penalty Factors (reduce confidence)

| Factor | Penalty |
|---|---|
| `completeness_score < 0.7` | -0.15 |
| `completeness_score < 0.5` | -0.30 |
| Any field with confidence < 0.6 | -0.05 per field |
| Primary complaint confidence < 0.8 | -0.10 |
| Severity source = "inferred" (not explicit) | -0.10 |
| `fast_tracked == true` (reduced questioning) | -0.05 |

### Boost Factors (increase confidence)

| Factor | Boost |
|---|---|
| Red flag detected (rule-based) | +0.10 |
| EHR data available (corroborates history) | +0.05 |
| All mandatory fields HIGH confidence | +0.05 |

### Final Confidence Calculation

```
final_confidence = clamp(
  base_confidence + sum(boosts) - sum(penalties),
  min=0.1,
  max=0.99
)
```

### Confidence Threshold for Human Handoff

| Final Confidence | Action |
|---|---|
| ≥ 0.70 | Accept classification, proceed with pipeline |
| 0.50 - 0.69 | **Low confidence** → trigger nurse handoff (US-020) |
| < 0.50 | **Very low confidence** → default to URGENT + immediate nurse flag |

---

## Determinism Guarantee

To ensure same inputs → same output (consistency across clinics):

1. **Temperature 0.0** on all Bedrock calls
2. **Fixed system prompt** (no dynamic elements except the patient data)
3. **Rule-based pre-classifier checked first** — deterministic paths short-circuit the LLM entirely
4. **Confidence calibration is pure math** — no LLM involvement
5. **Model version pinned** — use specific model version ARN, not "latest"

### Consistency Testing (PBT candidate)

Property: For any given StructuredSymptoms input, calling `score_urgency()` N times produces the same UrgencyResult N times.

Property: If severity increases (all else equal), urgency level never decreases.

Property: If red_flag_detected == true, urgency is always EMERGENCY.

---

## Scoring Decision Matrix (Reference)

This matrix guides the LLM but is also used for validation:

| Severity | Onset | Pattern | Typical Classification |
|---|---|---|---|
| 9-10 | Any | Any | EMERGENCY |
| 7-8 | Sudden (< 24h) | Worsening | URGENT |
| 7-8 | Gradual (> 48h) | Stable | STANDARD |
| 5-6 | Sudden | Worsening | URGENT |
| 5-6 | Gradual | Stable | STANDARD |
| 5-6 | Gradual | Improving | ROUTINE |
| 3-4 | Any | Worsening | STANDARD |
| 3-4 | Any | Stable/Improving | ROUTINE |
| 1-2 | Any | Any | ROUTINE |

**Modifiers that ELEVATE urgency by one level:**
- Cardiac history + chest pain
- Immunocompromised + fever
- Anticoagulant therapy + bleeding
- Pregnancy + abdominal pain
- Age > 65 + fall + head injury
- Diabetes + confusion/altered mental status

---

## Output Contract

```json
{
  "session_id": "string (UUID)",
  "urgency_level": "EMERGENCY | URGENT | STANDARD | ROUTINE",
  "confidence_score": 0.0-1.0,
  "classification_method": "rule_based | llm_reasoning | hybrid",
  "reasoning": "string (step-by-step explanation)",
  "risk_factors": ["string"],
  "recommended_timeframe": "string",
  "modifiers_applied": ["string (which history modifiers elevated urgency)"],
  "data_quality_penalties": ["string (which penalties were applied to confidence)"],
  "requires_nurse_review": false,
  "scored_at": "ISO datetime"
}
```

This payload is consumed by:
- **Supervisor Agent** (Unit 7) — for branching (Emergency → escalate, low confidence → nurse)
- **Clinical Summary Agent** (Unit 6) — for SOAP note Assessment section
- **Patient Portal** (Unit 8) — for displaying urgency to patient
