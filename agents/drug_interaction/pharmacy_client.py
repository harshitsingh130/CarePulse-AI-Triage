"""Hospital Pharmacy System client (stubbed for MVP).

Provides a consistent interface for medication data and interaction checking.
The stub returns realistic test data to enable end-to-end testing of all
severity paths and the unavailability path.
"""

from __future__ import annotations

import time
from typing import Optional

from shared.config import config
from shared.models import CheckStatus, DrugInteraction, InteractionSeverity, MedicationEntry
from shared.phi_redaction import get_logger
from shared.secrets import get_secret

logger = get_logger("drug-interaction-pharmacy", config.LOG_LEVEL)


# Brand-to-generic mapping (top ~50 medications for MVP)
BRAND_TO_GENERIC: dict[str, str] = {
    "coumadin": "warfarin",
    "lipitor": "atorvastatin",
    "zocor": "simvastatin",
    "norvasc": "amlodipine",
    "prinivil": "lisinopril",
    "zestril": "lisinopril",
    "glucophage": "metformin",
    "synthroid": "levothyroxine",
    "prilosec": "omeprazole",
    "nexium": "esomeprazole",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "tylenol": "acetaminophen",
    "xanax": "alprazolam",
    "valium": "diazepam",
    "ambien": "zolpidem",
    "prozac": "fluoxetine",
    "zoloft": "sertraline",
    "lexapro": "escitalopram",
    "plavix": "clopidogrel",
    "eliquis": "apixaban",
    "xarelto": "rivaroxaban",
    "lasix": "furosemide",
    "metoprolol": "metoprolol",
    "atenolol": "atenolol",
    "amoxil": "amoxicillin",
    "augmentin": "amoxicillin-clavulanate",
    "cipro": "ciprofloxacin",
    "prednisone": "prednisone",
    "ventolin": "albuterol",
    "proair": "albuterol",
    "flovent": "fluticasone",
    "singulair": "montelukast",
    "metformin": "metformin",
    "januvia": "sitagliptin",
    "lantus": "insulin glargine",
    "humalog": "insulin lispro",
}

# Known critical interaction pairs for MVP stub
KNOWN_INTERACTIONS: list[dict] = [
    {
        "drug_a": "warfarin",
        "drug_b": "ibuprofen",
        "severity": "critical",
        "mechanism": "NSAIDs inhibit platelet function and may displace warfarin from protein binding sites",
        "clinical_effect": "Significantly increased risk of bleeding, including GI hemorrhage",
        "recommendation": "Avoid combination. Use acetaminophen for pain if anticoagulation required.",
    },
    {
        "drug_a": "warfarin",
        "drug_b": "aspirin",
        "severity": "critical",
        "mechanism": "Dual antiplatelet and anticoagulant effect",
        "clinical_effect": "Markedly increased risk of major bleeding events",
        "recommendation": "Use only under specialist supervision with documented indication.",
    },
    {
        "drug_a": "fluoxetine",
        "drug_b": "sertraline",
        "severity": "critical",
        "mechanism": "Combined serotonergic activity",
        "clinical_effect": "Risk of serotonin syndrome (agitation, hyperthermia, tachycardia)",
        "recommendation": "Never combine two SSRIs. Taper one before starting another.",
    },
    {
        "drug_a": "metformin",
        "drug_b": "contrast dye",
        "severity": "moderate",
        "mechanism": "Contrast media may cause acute kidney injury, impairing metformin clearance",
        "clinical_effect": "Risk of lactic acidosis if renal function declines",
        "recommendation": "Hold metformin 48 hours before and after contrast procedures.",
    },
    {
        "drug_a": "lisinopril",
        "drug_b": "potassium",
        "severity": "moderate",
        "mechanism": "ACE inhibitors reduce potassium excretion",
        "clinical_effect": "Hyperkalemia risk (cardiac arrhythmia at extreme levels)",
        "recommendation": "Monitor serum potassium regularly. Avoid potassium supplements unless prescribed.",
    },
    {
        "drug_a": "simvastatin",
        "drug_b": "amiodarone",
        "severity": "moderate",
        "mechanism": "Amiodarone inhibits CYP3A4, increasing statin levels",
        "clinical_effect": "Increased risk of myopathy and rhabdomyolysis",
        "recommendation": "Limit simvastatin to 20mg daily when combined with amiodarone.",
    },
    {
        "drug_a": "metoprolol",
        "drug_b": "verapamil",
        "severity": "moderate",
        "mechanism": "Both agents slow cardiac conduction",
        "clinical_effect": "Risk of severe bradycardia and heart block",
        "recommendation": "Avoid combination or use with close cardiac monitoring.",
    },
    {
        "drug_a": "omeprazole",
        "drug_b": "clopidogrel",
        "severity": "moderate",
        "mechanism": "Omeprazole inhibits CYP2C19, reducing clopidogrel activation",
        "clinical_effect": "Reduced antiplatelet effect, increased cardiovascular event risk",
        "recommendation": "Use pantoprazole instead of omeprazole with clopidogrel.",
    },
]

# Test patient configurations for stub
STUB_PATIENTS: dict[str, dict] = {
    "test-cardiac": {
        "medications": [
            MedicationEntry(drug_name="warfarin", source="pharmacy_system", dosage="5mg daily", frequency="once daily"),
            MedicationEntry(drug_name="aspirin", source="pharmacy_system", dosage="81mg", frequency="once daily"),
            MedicationEntry(drug_name="lisinopril", source="pharmacy_system", dosage="10mg", frequency="once daily"),
            MedicationEntry(drug_name="atorvastatin", source="pharmacy_system", dosage="40mg", frequency="at bedtime"),
        ],
    },
    "test-clean": {
        "medications": [
            MedicationEntry(drug_name="lisinopril", source="pharmacy_system", dosage="10mg", frequency="once daily"),
            MedicationEntry(drug_name="atorvastatin", source="pharmacy_system", dosage="20mg", frequency="at bedtime"),
            MedicationEntry(drug_name="metformin", source="pharmacy_system", dosage="500mg", frequency="twice daily"),
        ],
    },
    "test-moderate": {
        "medications": [
            MedicationEntry(drug_name="lisinopril", source="pharmacy_system", dosage="20mg", frequency="once daily"),
            MedicationEntry(drug_name="potassium", source="pharmacy_system", dosage="20mEq", frequency="once daily"),
            MedicationEntry(drug_name="omeprazole", source="pharmacy_system", dosage="20mg", frequency="once daily"),
        ],
    },
}


def normalize_medication(name: str) -> str:
    """Normalize a medication name to its generic form.

    Converts brand names to generics, lowercases, strips dosage info.
    """
    cleaned = name.lower().strip()

    # Remove common dosage patterns
    import re
    cleaned = re.sub(r"\d+\s*mg", "", cleaned).strip()
    cleaned = re.sub(r"\d+\s*mcg", "", cleaned).strip()
    cleaned = re.sub(r"\d+\s*ml", "", cleaned).strip()

    # Brand to generic lookup
    return BRAND_TO_GENERIC.get(cleaned, cleaned)


def query_pharmacy_system(
    patient_ehr_id: Optional[str],
    reported_medications: list[str],
) -> tuple[list[MedicationEntry], list[DrugInteraction], CheckStatus]:
    """Query the hospital pharmacy system for medication data and interactions.

    For MVP: Returns stubbed data based on patient_ehr_id.

    Args:
        patient_ehr_id: EHR patient ID (for pharmacy lookup).
        reported_medications: Patient-reported medications from triage.

    Returns:
        Tuple of (medication_list, interactions, check_status).
    """

    # --- MVP STUB IMPLEMENTATION ---

    # Simulate timeout for test patient
    if patient_ehr_id == "test-unavailable":
        time.sleep(config.PHARMACY_TIMEOUT + 1)  # Exceed timeout
        return [], [], CheckStatus.UNAVAILABLE

    # Get stub data if available
    medications: list[MedicationEntry] = []
    if patient_ehr_id and patient_ehr_id in STUB_PATIENTS:
        medications = STUB_PATIENTS[patient_ehr_id]["medications"]
        logger.info(f"Pharmacy stub: loaded {len(medications)} medications for {patient_ehr_id}")
    else:
        # No pharmacy data — use patient-reported only
        for med_name in reported_medications:
            normalized = normalize_medication(med_name)
            medications.append(MedicationEntry(
                drug_name=normalized,
                brand_name=med_name if med_name.lower() != normalized else None,
                source="patient_reported",
            ))

    # Check for interactions among the medication list
    med_names = [m.drug_name.lower() for m in medications]
    interactions: list[DrugInteraction] = []

    for known in KNOWN_INTERACTIONS:
        drug_a = known["drug_a"].lower()
        drug_b = known["drug_b"].lower()
        if drug_a in med_names and drug_b in med_names:
            interactions.append(DrugInteraction(
                drug_a=known["drug_a"],
                drug_b=known["drug_b"],
                severity=InteractionSeverity(known["severity"]),
                mechanism=known["mechanism"],
                clinical_effect=known["clinical_effect"],
                recommendation=known["recommendation"],
            ))

    status = CheckStatus.COMPLETE if patient_ehr_id else CheckStatus.PARTIAL
    return medications, interactions, status
