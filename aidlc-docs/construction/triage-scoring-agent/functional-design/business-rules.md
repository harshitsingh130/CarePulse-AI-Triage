# Business Rules — Triage Scoring Agent

## BR-TS-001: Conservative Bias

**Rule**: When the scoring result falls between two urgency levels, ALWAYS classify at the more urgent level.

**Rationale**: In healthcare, false negatives (undertriage) are far more dangerous than false positives (overtriage). It's safer to send a Standard case to Urgent than to send an Urgent case to Standard.

**Implementation**: The LLM prompt explicitly instructs "When in doubt between two levels, choose the MORE urgent one."

---

## BR-TS-002: Deterministic Reproducibility

**Rule**: Given identical StructuredSymptoms input, the agent MUST produce identical UrgencyResult output. Every time. Across all clinics.

**Implementation**:
- Bedrock inference: `temperature: 0.0`
- Model version: Pinned ARN (not "latest")
- No random seeds, no timestamp-dependent logic
- Rule-based pre-classifier is pure logic (no randomness)
- Confidence calibration is arithmetic only

**Testing**: Property-based test: `score_urgency(x) == score_urgency(x)` for all valid inputs.

---

## BR-TS-003: Red Flag Override

**Rule**: If `StructuredSymptoms.red_flag_detected == true`, classification is ALWAYS Emergency regardless of other factors.

**Implementation**: Rule-based pre-classifier catches this before LLM is invoked. No LLM tokens spent.

**Output**:
```json
{
  "urgency_level": "EMERGENCY",
  "confidence_score": 0.95,
  "classification_method": "rule_based",
  "reasoning": "Emergency red flag detected: [category]. Immediate escalation required."
}
```

---

## BR-TS-004: Incomplete Data Handling

**Rule**: The scoring agent MUST handle incomplete StructuredSymptoms gracefully. It cannot reject input — it must produce a best-effort classification with reduced confidence.

| Missing Data | Impact |
|---|---|
| severity is null | Cannot classify → confidence penalty -0.30, default to URGENT |
| primary_complaint is null | Cannot classify → confidence penalty -0.30, default to URGENT |
| onset is null | Reduced accuracy → confidence penalty -0.15 |
| medical_history is null | Reduced risk assessment → confidence penalty -0.05 |
| medications is null | Cannot check risk modifiers → confidence penalty -0.05 |
| associated_symptoms empty | Limited context → confidence penalty -0.05 |

If mandatory fields (severity + primary_complaint) are BOTH null: output URGENT with confidence 0.3 and `requires_nurse_review: true`.

---

## BR-TS-005: Severity Score Monotonicity

**Rule**: If only severity changes (all else equal), urgency level MUST NOT decrease as severity increases.

**Property**: `severity(x) > severity(y)` implies `urgency(x) >= urgency(y)` (given identical other fields)

This is a core PBT property to verify.

---

## BR-TS-006: History Modifier Application

**Rule**: Specific medical history + symptom combinations ELEVATE urgency by one level.

| Condition in History | Symptom Present | Elevation |
|---|---|---|
| Cardiac disease (CAD, CHF, MI) | Chest pain OR shortness of breath | +1 level |
| Immunocompromised (HIV, chemo, transplant) | Fever | +1 level |
| Anticoagulant therapy (warfarin, rivaroxaban) | Bleeding OR head injury | +1 level |
| Diabetes | Confusion, altered mental status | +1 level |
| Age > 65 | Fall + head injury | +1 level |
| Pregnancy | Abdominal pain OR bleeding | +1 level |
| Asthma/COPD | Breathing difficulty | +1 level |

**Maximum elevation**: One level (Standard → Urgent, Urgent → Emergency). Never elevates past Emergency.

**Implementation**: After LLM classification, check for modifier matches. If found, elevate and log in `modifiers_applied`.

---

## BR-TS-007: Audit Trail Requirement

**Rule**: Every scoring decision MUST be logged to the AuditTrail table with:
- `session_id`
- `urgency_level` (final classification)
- `confidence_score` (final, after calibration)
- `reasoning` (full step-by-step from LLM or rule description)
- `classification_method` (rule_based / llm_reasoning)
- `modifiers_applied` (list of history elevations)
- `data_quality_penalties` (what reduced confidence)
- `model_version` (Bedrock model ARN used)
- `scored_at` (timestamp)

This enables:
- Retrospective audit ("why was this patient classified as X?")
- Model performance monitoring ("how often does confidence < 0.7?")
- Consistency verification ("same symptoms, different classification across time?")

---

## BR-TS-008: Nurse Handoff Threshold

**Rule**: If final `confidence_score < 0.70`, set `requires_nurse_review: true`.

The Supervisor Agent reads this flag and routes to the nurse handoff Standard workflow.

| Confidence | Action | Patient Communication |
|---|---|---|
| ≥ 0.70 | Accept classification, continue pipeline | "Based on your symptoms, I'm assessing this as [level]" |
| 0.50-0.69 | Flag for nurse review | "I want to make sure we get this right — I'm connecting you with a nurse for a quick check" |
| < 0.50 | Default URGENT + nurse flag | "I'd like a nurse to review your case personally to make sure you get the right care" |

---

## BR-TS-009: No Diagnosis Output

**Rule**: The scoring agent MUST NOT produce diagnostic language. It classifies urgency only.

**Allowed**: "Symptoms suggest urgent attention needed. Severe headache with sudden onset and history of hypertension elevates risk."

**Not allowed**: "This appears to be a migraine" or "Possible stroke indicators" or "You may have appendicitis"

The reasoning field explains WHY the urgency level was chosen (symptom severity, onset, modifiers) but never names a potential diagnosis.

---

## BR-TS-010: Performance Requirement

**Rule**: Scoring MUST complete within 5 seconds end-to-end.

| Path | Expected Latency |
|---|---|
| Rule-based (red flag / severity extremes) | < 100ms |
| LLM reasoning | 2-4 seconds (Bedrock inference) |
| Confidence calibration | < 50ms |
| Total (worst case) | < 5 seconds |

If Bedrock call times out (> 5s): use rule-based fallback matrix (Scoring Decision Matrix from business-logic-model.md) to produce a result with reduced confidence (-0.15).
