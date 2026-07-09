# Domain Entities — Triage Scoring Agent

## Entity: UrgencyResult (Primary Output)

The main output of this agent, consumed by Supervisor, Clinical Summary, and Portal.

| Field | Type | Description |
|---|---|---|
| session_id | UUID | Links to the triage session |
| urgency_level | Enum | EMERGENCY, URGENT, STANDARD, ROUTINE |
| confidence_score | Float (0.0-1.0) | Final calibrated confidence |
| classification_method | Enum | RULE_BASED, LLM_REASONING, HYBRID |
| reasoning | String | Step-by-step explanation of why this level |
| risk_factors | List[String] | Identified risk factors from symptoms + history |
| recommended_timeframe | String | "immediate", "within 4 hours", "within 24 hours", etc. |
| modifiers_applied | List[String] | History modifiers that elevated urgency |
| data_quality_penalties | List[String] | Confidence penalties applied |
| requires_nurse_review | Boolean | True if confidence < 0.70 |
| scored_at | ISO DateTime | When scoring completed |

---

## Entity: ScoringContext (Internal)

Internal working state during scoring:

| Field | Type | Description |
|---|---|---|
| input_symptoms | StructuredSymptoms | Raw input from Symptom Assessment Agent |
| pre_classifier_result | PreClassifierResult | null | Rule-based result (if definitive) |
| llm_result | LLMResult | null | LLM classification (if invoked) |
| base_confidence | Float | Confidence before calibration |
| penalties | List[Penalty] | Applied confidence penalties |
| boosts | List[Boost] | Applied confidence boosts |
| final_confidence | Float | After calibration |
| modifiers_matched | List[HistoryModifier] | Which elevation rules fired |

---

## Entity: PreClassifierResult

| Field | Type | Description |
|---|---|---|
| triggered | Boolean | Whether pre-classifier produced a definitive result |
| urgency_level | Enum | null | Classification (if triggered) |
| confidence | Float | Pre-classifier confidence (0.90-0.99) |
| rule_fired | String | Which rule produced this result |
| reasoning | String | Rule-based reasoning text |

---

## Entity: HistoryModifier

Configuration entity — defines condition+symptom combinations that elevate urgency:

| Field | Type | Description |
|---|---|---|
| modifier_id | String | Unique identifier |
| condition_keywords | List[String] | Keywords to match in medical_history |
| symptom_keywords | List[String] | Keywords to match in primary_complaint or associated_symptoms |
| elevation_levels | Integer | How many levels to elevate (always 1) |
| description | String | Human-readable description for audit trail |

---

## Entity: ConfidencePenalty

| Field | Type | Description |
|---|---|---|
| reason | String | Why penalty was applied |
| amount | Float | Penalty magnitude (subtracted from confidence) |
| field | String | Which input field triggered the penalty |

---

## Entity: ConfidenceBoost

| Field | Type | Description |
|---|---|---|
| reason | String | Why boost was applied |
| amount | Float | Boost magnitude (added to confidence) |
| condition | String | What condition triggered the boost |

---

## Data Flow

```
Input:
  StructuredSymptoms JSON (from Unit 2 via Supervisor)

Step 1: Rule-based Pre-classifier
  → Check red_flag_detected
  → Check severity extremes (10 → Emergency, 1-2 + stable → Routine)
  → If definitive: output immediately (no LLM call)

Step 2: LLM Clinical Reasoning (if pre-classifier indeterminate)
  → Call Bedrock (Claude, temperature=0.0)
  → Parse structured JSON response
  → Extract urgency_level, confidence, reasoning

Step 3: History Modifier Check
  → Compare medical_history + medications against HistoryModifier rules
  → If match found: elevate urgency by 1 level

Step 4: Confidence Calibration
  → Apply penalties (incomplete data, low field confidence)
  → Apply boosts (red flag, EHR corroboration)
  → Calculate final confidence

Step 5: Nurse Handoff Check
  → If confidence < 0.70: set requires_nurse_review = true

Step 6: Audit Log
  → Write full decision record to AuditTrail table

Output:
  UrgencyResult JSON (to Supervisor Agent)
```

---

## PBT Properties (for Property-Based Testing)

These properties MUST hold for all valid StructuredSymptoms inputs:

1. **Determinism**: `score(x) == score(x)` always
2. **Monotonicity**: `severity(a) > severity(b)` → `urgency(a) >= urgency(b)` (all else equal)
3. **Red flag invariant**: `red_flag_detected == true` → `urgency_level == EMERGENCY`
4. **Confidence bounds**: `0.1 <= confidence_score <= 0.99`
5. **Modifier ceiling**: Modifiers never elevate past EMERGENCY
6. **No diagnosis**: `reasoning` never contains diagnostic terms (validated against blocklist)
7. **Timeframe consistency**: EMERGENCY → "immediate", ROUTINE → "within 1-2 weeks"
