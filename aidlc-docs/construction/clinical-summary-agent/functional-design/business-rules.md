# Business Rules — Clinical Summary Agent

## BR-CS-001: No Hallucinated Content

**Rule**: The SOAP note MUST contain ONLY information that exists in the input data. The LLM's role is to format and synthesize — never to invent.

**Specifically prohibited**:
- Adding diagnoses ("likely pneumonia") ❌
- Adding lab results or vitals not collected ❌
- Adding symptoms not reported ❌
- Suggesting treatments ("prescribe antibiotics") ❌
- Adding medications not in the patient's list ❌
- Interpolating information ("patient appears anxious") ❌

**Enforcement**: Post-generation validation cross-references every clinical claim against source data.

---

## BR-CS-002: Critical Flags Must Be Prominent

**Rule**: If `InteractionResult.requires_physician_alert == true` OR `UrgencyResult.requires_nurse_review == true`, these MUST appear in the Assessment section with a ⚠️ prefix.

A physician scanning the note quickly MUST see these flags without reading every line.

---

## BR-CS-003: Template-Guided, Not Free-Form

**Rule**: The LLM receives a structured template with placeholders. It fills them with natural clinical language. It does NOT generate a SOAP note from scratch.

**Why**: Free-form generation risks hallucination and inconsistency. Templates ensure every note covers the same sections in the same order, making physician workflow predictable.

---

## BR-CS-004: Physician-Readable Language

**Rule**: The SOAP note uses standard clinical language appropriate for a physician audience.

**Allowed**: Medical terminology, abbreviations common in clinical notes (NKDA, PRN, QD)
**Required**: Complete sentences in Subjective; structured lists in Objective/Plan
**Tone**: Professional, concise, factual

---

## BR-CS-005: Patient Portal Version (Redacted)

**Rule**: The Patient Portal shows a SIMPLIFIED summary, NOT the full SOAP note.

| SOAP Section | Patient Sees |
|---|---|
| Subjective | "Your reported symptoms: [complaint], severity [X/10]" |
| Objective | "Medications reviewed: [count] medications checked" |
| Assessment | "Urgency: [level]. Next steps determined." |
| Plan | "Department: [dept]. Appointment: [date/time]." |

The patient NEVER sees: clinical reasoning, risk factors, drug interaction mechanisms, or nurse override notes. Those are physician-only.

---

## BR-CS-006: Generation Timeout

**Rule**: SOAP note generation MUST complete within 8 seconds total.

| Step | Budget |
|---|---|
| Data aggregation | < 500ms |
| LLM generation (Bedrock) | < 5000ms |
| Validation | < 1000ms |
| Retry (if needed) | < 5000ms |
| DynamoDB write | < 500ms |
| **Total (no retry)** | **< 7000ms** |
| **Total (with retry)** | **< 12000ms** |

If timeout hit: use template-only output (no LLM prose) with a flag `metadata.fallback_used: true`.

---

## BR-CS-007: Idempotency

**Rule**: If called again for the same session, return the cached SOAP note from DynamoDB. Do NOT regenerate.

**Exception**: If any input data has changed since last generation (e.g., nurse override changed urgency), regenerate and overwrite.

---

## BR-CS-008: Incomplete Data Handling

**Rule**: If any input is missing (e.g., Drug Interaction returned `unavailable`), the SOAP note explicitly states what's missing rather than omitting the section.

| Missing Input | SOAP Impact |
|---|---|
| InteractionResult unavailable | Objective: "⚠️ Drug interaction check unavailable — manual review required" |
| RoutingDecision has no slots | Plan: "⚠️ No specialist availability. Patient advised to contact clinic." |
| StructuredSymptoms.allergies is null | Subjective: "Allergies: Not reported during triage" |
| Medical history not available | Objective: "Medical history: Not available (patient not authenticated with EHR)" |

---

## BR-CS-009: Audit Trail

**Rule**: Every SOAP note generation is logged:
- `eventType: SOAP_GENERATED`
- Details: generation time, model version, validation result, retry count
- The SOAP note content itself is stored in the Sessions table (encrypted with PHI key)

---

## BR-CS-010: PBT Property — Serialization Round-Trip

**Rule**: The SOAP note JSON can be serialized to string and deserialized back to the same object without data loss.

**Property**: `deserialize(serialize(soap_note)) == soap_note`

This ensures:
- No encoding issues with special characters in patient text
- JSON structure is always valid
- Unicode handling is correct (patient names, multilingual content in future)

This is a Property-Based Testing candidate (extension enabled for this unit).
