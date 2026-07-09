"""Unit tests for Drug Interaction Agent."""

import pytest
from uuid import uuid4

from shared.models import CheckStatus, InteractionSeverity
from agents.drug_interaction.pharmacy_client import (
    KNOWN_INTERACTIONS,
    normalize_medication,
    query_pharmacy_system,
)
from agents.drug_interaction.agent import check_interactions


class TestMedicationNormalization:
    """Test brand-to-generic name mapping."""

    def test_brand_to_generic(self):
        assert normalize_medication("Coumadin") == "warfarin"
        assert normalize_medication("Lipitor") == "atorvastatin"
        assert normalize_medication("Advil") == "ibuprofen"

    def test_case_insensitive(self):
        assert normalize_medication("COUMADIN") == "warfarin"
        assert normalize_medication("lipitor") == "atorvastatin"

    def test_generic_unchanged(self):
        assert normalize_medication("warfarin") == "warfarin"
        assert normalize_medication("metformin") == "metformin"

    def test_strips_dosage(self):
        assert normalize_medication("warfarin 5mg") == "warfarin"
        assert normalize_medication("lisinopril 10mg") == "lisinopril"

    def test_unknown_medication_passthrough(self):
        assert normalize_medication("somethingNew") == "somethingnew"


class TestPharmacySystemStub:
    """Test the stubbed pharmacy system interface."""

    def test_cardiac_patient_has_critical_interaction(self):
        meds, interactions, status = query_pharmacy_system("test-cardiac", [])
        assert status == CheckStatus.COMPLETE
        assert len(meds) == 4
        # warfarin + aspirin = critical interaction
        critical = [i for i in interactions if i.severity == InteractionSeverity.CRITICAL]
        assert len(critical) >= 1

    def test_clean_patient_no_interactions(self):
        meds, interactions, status = query_pharmacy_system("test-clean", [])
        assert status == CheckStatus.COMPLETE
        assert len(meds) == 3
        assert len(interactions) == 0

    def test_moderate_patient_has_moderate_interaction(self):
        meds, interactions, status = query_pharmacy_system("test-moderate", [])
        assert status == CheckStatus.COMPLETE
        moderate = [i for i in interactions if i.severity == InteractionSeverity.MODERATE]
        assert len(moderate) >= 1

    def test_unknown_patient_uses_reported_only(self):
        meds, interactions, status = query_pharmacy_system(None, ["warfarin", "ibuprofen"])
        assert status == CheckStatus.PARTIAL
        assert len(meds) == 2

    def test_no_ehr_id_patient_reported_interactions(self):
        meds, interactions, status = query_pharmacy_system(None, ["warfarin", "ibuprofen"])
        # Should find the warfarin+ibuprofen interaction
        critical = [i for i in interactions if i.severity == InteractionSeverity.CRITICAL]
        assert len(critical) >= 1


class TestInteractionAgent:
    """Test the main check_interactions function."""

    def test_single_medication_skips_check(self):
        result = check_interactions(
            session_id=uuid4(),
            patient_id=uuid4(),
            patient_ehr_id=None,
            reported_medications=["lisinopril"],
        )
        assert result.check_status == CheckStatus.COMPLETE
        assert len(result.interactions_found) == 0
        assert result.requires_physician_alert is False

    def test_empty_medications_no_error(self):
        result = check_interactions(
            session_id=uuid4(),
            patient_id=uuid4(),
            patient_ehr_id=None,
            reported_medications=[],
        )
        assert result.check_status == CheckStatus.COMPLETE
        assert result.critical_count == 0

    def test_critical_interaction_flags_alert(self):
        result = check_interactions(
            session_id=uuid4(),
            patient_id=uuid4(),
            patient_ehr_id="test-cardiac",
            reported_medications=[],
        )
        assert result.critical_count >= 1
        assert result.requires_physician_alert is True

    def test_no_interactions_clean_patient(self):
        result = check_interactions(
            session_id=uuid4(),
            patient_id=uuid4(),
            patient_ehr_id="test-clean",
            reported_medications=[],
        )
        assert result.critical_count == 0
        assert result.moderate_count == 0
        assert result.requires_physician_alert is False

    def test_merges_reported_with_pharmacy(self):
        result = check_interactions(
            session_id=uuid4(),
            patient_id=uuid4(),
            patient_ehr_id="test-clean",
            reported_medications=["vitamin D"],  # Not in pharmacy
        )
        # Should have pharmacy meds + reported
        med_names = [m.drug_name for m in result.medications_checked]
        assert "vitamin d" in med_names or "vitamin D" in [m.drug_name for m in result.medications_checked]
        assert len(result.medications_checked) >= 4  # 3 from pharmacy + 1 reported


class TestKnownInteractions:
    """Verify the known interactions database is well-formed."""

    def test_all_interactions_have_required_fields(self):
        for interaction in KNOWN_INTERACTIONS:
            assert "drug_a" in interaction
            assert "drug_b" in interaction
            assert "severity" in interaction
            assert "mechanism" in interaction
            assert "clinical_effect" in interaction
            assert "recommendation" in interaction
            assert interaction["severity"] in ("critical", "moderate", "informational")

    def test_no_self_interactions(self):
        for interaction in KNOWN_INTERACTIONS:
            assert interaction["drug_a"] != interaction["drug_b"]
