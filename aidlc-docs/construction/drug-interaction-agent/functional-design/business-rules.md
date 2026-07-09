# Business Rules — Drug Interaction Agent

## BR-DI-001: Never Skip the Check

**Rule**: The drug interaction check MUST be attempted for every triage session where the patient has 2+ medications (from any source). It is never optional.

**Exception**: If the patient has 0 or 1 medication, skip the check (no drug-drug interaction possible) and return `status: complete` with empty interactions.

---

## BR-DI-002: Pharmacy System Timeout

**Rule**: The pharmacy system query has a **3-second timeout**. If no response within 3 seconds:
- Return `check_status: unavailable`
- Log the timeout with error details
- Do NOT block the triage pipeline — the Supervisor continues to the next stage
- Flag in SOAP note: "Drug interaction check unavailable — manual review required"

---

## BR-DI-003: Medication Normalization

**Rule**: All medication names MUST be normalized to generic names before interaction checking.

**Process**:
1. Convert brand names to generics (Coumadin → warfarin, Lipitor → atorvastatin)
2. Standardize casing (lowercase)
3. Remove dosage from the name string ("warfarin 5mg" → "warfarin")
4. Deduplicate (same generic from multiple sources = 1 entry)

**MVP approach**: Use a lookup table of common brand-to-generic mappings (~200 most common medications). If a drug name isn't in the table, use it as-is.

---

## BR-DI-004: Source Priority

**Rule**: When the same medication appears from both pharmacy system and patient report:
- Use the **pharmacy system** version (includes dosage, prescriber, start date)
- Mark source as "both"
- If the patient reports DIFFERENT information (e.g., "I stopped taking that"), note the discrepancy in the output for physician review

---

## BR-DI-005: Critical Interaction Handling

**Rule**: When a CRITICAL interaction is detected:
1. Set `requires_physician_alert: true`
2. The Clinical Summary Agent will prominently flag it in the SOAP Assessment section
3. The patient receives a **general** awareness message (no specifics)
4. The interaction is logged to AuditTrail with full details
5. If the triage was classified as ROUTINE or STANDARD, the Supervisor MAY elevate to STANDARD (but does NOT override the Triage Scoring Agent's classification — it adds an advisory note)

---

## BR-DI-006: No Clinical Recommendations to Patient

**Rule**: The Drug Interaction Agent MUST NOT provide clinical recommendations directly to the patient. It does NOT say:
- "Stop taking warfarin" ❌
- "You should avoid NSAIDs" ❌
- "Ask your doctor about switching medications" ❌

It says only:
- "We've noted a potential medication interaction for your doctor to review." ✓

Clinical recommendations are the physician's responsibility after reviewing the SOAP note.

---

## BR-DI-007: Stub Fidelity for MVP

**Rule**: The pharmacy system stub MUST return realistic data that exercises all code paths:

| Test Patient | Stub Returns |
|---|---|
| Patient with ehrPatientId "test-cardiac" | warfarin + aspirin → CRITICAL interaction |
| Patient with ehrPatientId "test-clean" | lisinopril + atorvastatin → no interactions |
| Patient with ehrPatientId "test-moderate" | ACE inhibitor + potassium → MODERATE interaction |
| Patient with ehrPatientId "test-unavailable" | Simulated timeout (3s+) → UNAVAILABLE |
| Unauthenticated patient | No pharmacy data; use patient-reported only |

This ensures end-to-end testing covers all severity paths and the unavailable path.

---

## BR-DI-008: Idempotency

**Rule**: The drug interaction check is **idempotent**. Calling it multiple times for the same session with the same medication list produces the same result.

**Implementation**: Results are cached in the Sessions table after first check. If the Supervisor retries (e.g., after a transient failure), it checks the cache first.

---

## BR-DI-009: Audit Logging

**Rule**: Every interaction check is logged to AuditTrail:
- `eventType: DRUG_CHECK_PERFORMED`
- Details: medications checked, interactions found, severity classifications, pharmacy system status
- This enables retrospective analysis ("how many patients had undetected interactions?")

---

## BR-DI-010: Performance Budget

**Rule**: Total Drug Interaction Agent execution MUST complete within 5 seconds:

| Step | Budget |
|---|---|
| Medication assembly + normalization | < 200ms |
| Pharmacy system query (or timeout) | < 3000ms |
| Severity classification | < 200ms |
| Result assembly + DynamoDB write | < 500ms |
| **Total** | **< 4000ms** (buffer: 1000ms) |
