# Business Logic Model — Drug Interaction Agent

## Overview

The Drug Interaction Agent checks a patient's current medications for dangerous drug-drug interactions. It interfaces with the hospital pharmacy system (stubbed for MVP) and classifies interaction severity. The output feeds into the Clinical Summary Agent (SOAP note flags) and is displayed to the patient if critical.

---

## Interaction Check Flow

```
Input: patient_id + reported_medications (from Symptom Assessment)
         |
         v
+---------------------------+
| MEDICATION LIST           |  Merge medications from:
| ASSEMBLY                  |  1. EHR/Pharmacy system (if available)
|                           |  2. Patient-reported during triage
|                           |  Deduplicate + normalize names
+---------------------------+
         |
         v
+---------------------------+
| PHARMACY SYSTEM           |  Query hospital pharmacy system
| QUERY                     |  for interaction data
| (stubbed for MVP)         |  Input: medication list
+---------------------------+
         |
         | interaction data
         v
+---------------------------+
| SEVERITY                  |  Classify each interaction:
| CLASSIFICATION            |  CRITICAL / MODERATE / INFORMATIONAL
+---------------------------+
         |
         v
+---------------------------+
| RESULT ASSEMBLY           |  Format InteractionResult JSON
|                           |  Flag critical interactions
+---------------------------+
         |
         v
Output: InteractionResult JSON
```

---

## Medication List Assembly

### Sources (Priority Order)

1. **Hospital Pharmacy System** (EHR medication list) — most authoritative
2. **Patient-reported during triage** (from StructuredSymptoms.medications.current)
3. **Both combined** when pharmacy system has a list AND patient reports additional meds

### Normalization Rules

| Situation | Action |
|---|---|
| Patient says "blood thinner" | Map to generic: "warfarin" (or ask agent to clarify brand) |
| Patient says brand name "Coumadin" | Map to generic: "warfarin" |
| Patient says generic "warfarin" | Use as-is |
| Duplicate entries (same drug from both sources) | Deduplicate — use pharmacy record (has dosage info) |
| Patient reports a med NOT in pharmacy system | Include it (patient may have started new med not yet in records) |

### MVP Stub Behavior

For MVP, the pharmacy system query returns a mock response:
- If patient is authenticated with an `ehrPatientId`: return a predefined test medication list
- If patient is NOT authenticated: use only patient-reported medications
- The stub returns realistic medication data to enable end-to-end testing

---

## Pharmacy System Interface (Stubbed)

### Request Format
```json
{
  "patient_id": "string (ehrPatientId)",
  "medications_to_check": ["string (normalized drug names)"],
  "check_type": "drug_drug"
}
```

### Response Format (from pharmacy system)
```json
{
  "status": "complete | partial | unavailable",
  "patient_medications": [
    {
      "drug_name": "string",
      "dosage": "string",
      "frequency": "string",
      "prescriber": "string",
      "start_date": "ISO date"
    }
  ],
  "interactions": [
    {
      "drug_a": "string",
      "drug_b": "string",
      "severity": "critical | moderate | informational",
      "mechanism": "string (pharmacological explanation)",
      "clinical_effect": "string (what could happen)",
      "recommendation": "string (what to do)"
    }
  ]
}
```

---

## Severity Classification

### CRITICAL (requires immediate attention)
Interactions that may cause:
- Life-threatening adverse effects
- Severe bleeding risk
- Cardiac arrhythmia
- Serotonin syndrome
- Respiratory depression
- Severe hypotension

**Examples**:
- Warfarin + NSAIDs (bleeding risk)
- MAOIs + SSRIs (serotonin syndrome)
- Methotrexate + NSAIDs (toxicity)
- Opioids + benzodiazepines (respiratory depression)

### MODERATE (flag for physician awareness)
Interactions that may:
- Reduce drug effectiveness
- Cause manageable side effects
- Require monitoring or dosage adjustment

**Examples**:
- ACE inhibitors + potassium supplements (hyperkalemia risk)
- Statins + grapefruit (increased statin levels)
- Antacids + antibiotics (reduced absorption)

### INFORMATIONAL (note only)
Interactions that:
- Have theoretical concern but minimal clinical significance
- Are well-managed by standard dosing
- Primarily require awareness, not action

---

## Graceful Degradation

| Scenario | Behavior |
|---|---|
| Pharmacy system available, returns complete data | Full interaction check with all medications |
| Pharmacy system returns partial data | Check what we have, flag `status: partial` in output |
| Pharmacy system unavailable (timeout/error) | Skip automated check, flag `status: unavailable`, add note to SOAP: "Drug interaction check unavailable — manual review required" |
| Patient reports no medications | Return `status: complete` with empty interactions list |
| Only 1 medication total | No drug-drug interactions possible, return empty |

---

## Output Contract

```json
{
  "session_id": "string (UUID)",
  "patient_id": "string (UUID)",
  "medications_checked": [
    {
      "drug_name": "string",
      "source": "pharmacy_system | patient_reported | both",
      "dosage": "string | null"
    }
  ],
  "interactions_found": [
    {
      "drug_a": "string",
      "drug_b": "string",
      "severity": "critical | moderate | informational",
      "mechanism": "string",
      "clinical_effect": "string",
      "recommendation": "string"
    }
  ],
  "check_status": "complete | partial | unavailable",
  "critical_count": 0,
  "moderate_count": 0,
  "informational_count": 0,
  "requires_physician_alert": false,
  "checked_at": "ISO datetime"
}
```

`requires_physician_alert` = true if `critical_count > 0`

---

## Patient Communication Rules

| Severity | Patient Sees |
|---|---|
| CRITICAL | "Important: We've detected a potential medication interaction that your doctor should know about. This has been flagged in your clinical summary." |
| MODERATE | Nothing (only in physician's SOAP note) |
| INFORMATIONAL | Nothing |
| UNAVAILABLE | "We weren't able to check your medications automatically. Your doctor will review this during your visit." |

**Never tell the patient**: specific drug names involved, the mechanism, or what could happen. That's for the physician. The patient gets a general awareness message only.
