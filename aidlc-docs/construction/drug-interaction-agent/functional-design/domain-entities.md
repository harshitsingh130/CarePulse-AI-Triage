# Domain Entities — Drug Interaction Agent

## Entity: InteractionResult (Primary Output)

| Field | Type | Description |
|---|---|---|
| session_id | UUID | Links to triage session |
| patient_id | UUID | Patient identifier |
| medications_checked | List[MedicationEntry] | All medications evaluated |
| interactions_found | List[DrugInteraction] | Detected interactions |
| check_status | Enum | COMPLETE, PARTIAL, UNAVAILABLE |
| critical_count | Integer | Number of critical interactions |
| moderate_count | Integer | Number of moderate interactions |
| informational_count | Integer | Number of informational interactions |
| requires_physician_alert | Boolean | True if any critical interaction |
| checked_at | ISO DateTime | Timestamp |

---

## Entity: MedicationEntry

| Field | Type | Description |
|---|---|---|
| drug_name | String | Normalized generic name |
| brand_name | String | null | Original brand name (if provided) |
| source | Enum | PHARMACY_SYSTEM, PATIENT_REPORTED, BOTH |
| dosage | String | null | Dosage info (from pharmacy system) |
| frequency | String | null | Dosing frequency |
| start_date | ISO Date | null | When started (from pharmacy) |

---

## Entity: DrugInteraction

| Field | Type | Description |
|---|---|---|
| drug_a | String | First drug in interaction pair |
| drug_b | String | Second drug in interaction pair |
| severity | Enum | CRITICAL, MODERATE, INFORMATIONAL |
| mechanism | String | Pharmacological explanation (for physician) |
| clinical_effect | String | What could happen to the patient |
| recommendation | String | Clinical recommendation (for physician) |

---

## Entity: PharmacySystemRequest

| Field | Type | Description |
|---|---|---|
| patient_id | String | ehrPatientId for pharmacy lookup |
| medications_to_check | List[String] | Normalized drug names |
| check_type | String | "drug_drug" (future: "drug_allergy", "drug_food") |
| timeout_ms | Integer | 3000 (hardcoded) |

---

## Entity: PharmacySystemResponse

| Field | Type | Description |
|---|---|---|
| status | Enum | COMPLETE, PARTIAL, UNAVAILABLE |
| patient_medications | List[MedicationEntry] | Full medication list from pharmacy |
| interactions | List[DrugInteraction] | Detected interactions from pharmacy system |
| response_time_ms | Integer | How long the pharmacy call took |
| error | String | null | Error message if unavailable |

---

## Entity: BrandToGenericMapping (Configuration)

Static lookup table loaded at agent startup:

| Field | Type | Description |
|---|---|---|
| brand_name | String | Brand medication name (case-insensitive) |
| generic_name | String | Corresponding generic name |
| drug_class | String | Therapeutic class (for fallback matching) |

**Size**: ~200 entries for MVP (top medications by prescribing volume)

---

## Data Flow

```
Input:
  - patient_id (UUID)
  - reported_medications (List[String] from StructuredSymptoms)
  - ehr_patient_id (String, for pharmacy system lookup)

Step 1: Medication Assembly
  → Query pharmacy system with ehr_patient_id (3s timeout)
  → Merge pharmacy list with patient-reported medications
  → Normalize all names (brand → generic)
  → Deduplicate

Step 2: Interaction Check
  → If pharmacy returned interaction data: use it directly
  → If only patient-reported meds: use internal interaction database (future)
  → For MVP stub: interaction data comes from pharmacy stub response

Step 3: Severity Classification
  → Each interaction already classified by pharmacy system
  → Agent validates classification against known critical pairs
  → Override if needed (pharmacy may underclassify)

Step 4: Result Assembly
  → Build InteractionResult JSON
  → Set requires_physician_alert = (critical_count > 0)
  → Cache result in Sessions table

Step 5: Audit
  → Write to AuditTrail (DRUG_CHECK_PERFORMED)

Output:
  InteractionResult JSON → Supervisor Agent → Clinical Summary Agent
```
