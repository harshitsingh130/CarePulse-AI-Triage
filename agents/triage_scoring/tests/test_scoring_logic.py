"""Unit tests + property-based tests for triage scoring logic."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from shared.models import (
    AllergyInfo,
    AssociatedSymptom,
    DurationPattern,
    MedicalHistory,
    MedicationList,
    OnsetInfo,
    PrimaryComplaint,
    SeverityInfo,
    StructuredSymptoms,
    UrgencyLevel,
)
from agents.triage_scoring.scoring_logic import (
    calibrate_confidence,
    check_history_modifiers,
    elevate_urgency,
    pre_classify,
)


def _make_symptoms(**overrides) -> StructuredSymptoms:
    """Factory for test StructuredSymptoms objects."""
    defaults = {
        "session_id": uuid4(),
        "patient_id": uuid4(),
        "assessment_complete": True,
        "completeness_score": 0.80,
        "red_flag_detected": False,
        "primary_complaint": PrimaryComplaint(text="headache", category="headache", confidence=0.9),
        "severity": SeverityInfo(score=5, source="explicit", confidence=0.9),
        "onset": OnsetInfo(description="2 days ago", days_ago_estimate=2, confidence=0.8),
        "duration_pattern": DurationPattern(type="stable", description="about the same", confidence=0.8),
        "associated_symptoms": [],
        "medical_history": MedicalHistory(conditions=[], source="patient_reported", confidence=0.8),
        "medications": MedicationList(current=[], source="patient_reported", confidence=0.8),
        "conversation_turns": 8,
        "assessed_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return StructuredSymptoms(**defaults)


class TestPreClassifier:
    """Test deterministic rule-based pre-classification."""

    def test_red_flag_triggers_emergency(self):
        symptoms = _make_symptoms(red_flag_detected=True, red_flag_category="cardiac")
        result = pre_classify(symptoms)
        assert result.triggered is True
        assert result.urgency_level == UrgencyLevel.EMERGENCY
        assert result.confidence >= 0.95

    def test_severity_10_triggers_emergency(self):
        symptoms = _make_symptoms(
            severity=SeverityInfo(score=10, source="explicit", confidence=0.95)
        )
        result = pre_classify(symptoms)
        assert result.triggered is True
        assert result.urgency_level == UrgencyLevel.EMERGENCY

    def test_severity_9_critical_category_triggers_emergency(self):
        symptoms = _make_symptoms(
            severity=SeverityInfo(score=9, source="explicit", confidence=0.9),
            primary_complaint=PrimaryComplaint(text="chest pain", category="chest_pain", confidence=0.9),
        )
        result = pre_classify(symptoms)
        assert result.triggered is True
        assert result.urgency_level == UrgencyLevel.EMERGENCY

    def test_low_severity_chronic_stable_triggers_routine(self):
        symptoms = _make_symptoms(
            severity=SeverityInfo(score=2, source="explicit", confidence=0.9),
            onset=OnsetInfo(description="2 weeks ago", days_ago_estimate=14, confidence=0.8),
            duration_pattern=DurationPattern(type="stable", description="same", confidence=0.8),
            associated_symptoms=[],
        )
        result = pre_classify(symptoms)
        assert result.triggered is True
        assert result.urgency_level == UrgencyLevel.ROUTINE

    def test_moderate_severity_not_triggered(self):
        symptoms = _make_symptoms(
            severity=SeverityInfo(score=6, source="explicit", confidence=0.9),
        )
        result = pre_classify(symptoms)
        assert result.triggered is False

    def test_severity_9_non_critical_category_not_triggered(self):
        symptoms = _make_symptoms(
            severity=SeverityInfo(score=9, source="explicit", confidence=0.9),
            primary_complaint=PrimaryComplaint(text="knee pain", category="musculoskeletal", confidence=0.9),
        )
        result = pre_classify(symptoms)
        assert result.triggered is False  # Needs LLM for non-critical category


class TestHistoryModifiers:
    """Test medical history + symptom combination detection."""

    def test_cardiac_history_chest_pain(self):
        symptoms = _make_symptoms(
            primary_complaint=PrimaryComplaint(text="chest pain", category="chest_pain", confidence=0.9),
            medical_history=MedicalHistory(conditions=["heart disease", "hypertension"], source="ehr", confidence=0.9),
        )
        modifiers = check_history_modifiers(symptoms)
        assert len(modifiers) >= 1
        assert any("Cardiac" in m for m in modifiers)

    def test_anticoagulant_bleeding(self):
        symptoms = _make_symptoms(
            primary_complaint=PrimaryComplaint(text="bleeding from cut", category="default", confidence=0.9),
            medications=MedicationList(current=["warfarin", "lisinopril"], source="ehr", confidence=0.9),
        )
        modifiers = check_history_modifiers(symptoms)
        assert len(modifiers) >= 1
        assert any("Anticoagulant" in m for m in modifiers)

    def test_no_modifiers_when_no_history(self):
        symptoms = _make_symptoms(
            medical_history=MedicalHistory(conditions=[], source="patient_reported", confidence=0.8),
        )
        modifiers = check_history_modifiers(symptoms)
        assert modifiers == []


class TestUrgencyElevation:
    """Test urgency level elevation."""

    def test_routine_to_standard(self):
        assert elevate_urgency(UrgencyLevel.ROUTINE) == UrgencyLevel.STANDARD

    def test_standard_to_urgent(self):
        assert elevate_urgency(UrgencyLevel.STANDARD) == UrgencyLevel.URGENT

    def test_urgent_to_emergency(self):
        assert elevate_urgency(UrgencyLevel.URGENT) == UrgencyLevel.EMERGENCY

    def test_emergency_stays_emergency(self):
        assert elevate_urgency(UrgencyLevel.EMERGENCY) == UrgencyLevel.EMERGENCY


class TestConfidenceCalibration:
    """Test confidence score adjustment logic."""

    def test_high_completeness_no_penalty(self):
        symptoms = _make_symptoms(completeness_score=0.85)
        final, adjustments = calibrate_confidence(0.80, symptoms)
        penalties = [a for a in adjustments if a.amount < 0]
        # Should not have completeness penalty
        assert not any("Completeness" in p.reason for p in penalties)

    def test_low_completeness_penalty(self):
        symptoms = _make_symptoms(completeness_score=0.45)
        final, adjustments = calibrate_confidence(0.80, symptoms)
        assert final < 0.80
        assert any("Completeness" in a.reason for a in adjustments)

    def test_confidence_bounds(self):
        # Even with huge penalties, confidence stays >= 0.1
        symptoms = _make_symptoms(completeness_score=0.30)
        final, _ = calibrate_confidence(0.20, symptoms)
        assert final >= 0.1

        # Even with huge boosts, confidence stays <= 0.99
        symptoms = _make_symptoms(
            completeness_score=0.95,
            red_flag_detected=True,
            medical_history=MedicalHistory(conditions=["test"], source="ehr", confidence=0.9),
        )
        final, _ = calibrate_confidence(0.95, symptoms)
        assert final <= 0.99

    def test_inferred_severity_penalty(self):
        symptoms = _make_symptoms(
            severity=SeverityInfo(score=6, source="inferred", confidence=0.7),
        )
        final, adjustments = calibrate_confidence(0.80, symptoms)
        assert any("inferred" in a.reason for a in adjustments)
        assert final < 0.80


class TestPBTProperties:
    """Property-based test candidates — testing invariants."""

    def test_red_flag_always_emergency(self):
        """Property: red_flag_detected == True → urgency is always EMERGENCY."""
        for severity in range(1, 11):
            symptoms = _make_symptoms(
                red_flag_detected=True,
                red_flag_category="cardiac",
                severity=SeverityInfo(score=severity, source="explicit", confidence=0.9),
            )
            result = pre_classify(symptoms)
            assert result.urgency_level == UrgencyLevel.EMERGENCY

    def test_severity_monotonicity(self):
        """Property: higher severity → urgency never decreases (for pre-classifier paths)."""
        # Test severity 10 is always >= severity 9
        s10 = _make_symptoms(severity=SeverityInfo(score=10, source="explicit", confidence=0.9))
        s9 = _make_symptoms(
            severity=SeverityInfo(score=9, source="explicit", confidence=0.9),
            primary_complaint=PrimaryComplaint(text="chest pain", category="chest_pain", confidence=0.9),
        )
        r10 = pre_classify(s10)
        r9 = pre_classify(s9)

        # Both should be Emergency for these inputs
        assert r10.urgency_level == UrgencyLevel.EMERGENCY
        assert r9.urgency_level == UrgencyLevel.EMERGENCY

    def test_modifier_ceiling(self):
        """Property: modifiers never elevate past EMERGENCY."""
        assert elevate_urgency(UrgencyLevel.EMERGENCY) == UrgencyLevel.EMERGENCY

    def test_confidence_bounds_property(self):
        """Property: confidence is always between 0.1 and 0.99."""
        for completeness in [0.1, 0.3, 0.5, 0.7, 0.9]:
            for base_conf in [0.1, 0.3, 0.5, 0.7, 0.9]:
                symptoms = _make_symptoms(completeness_score=completeness)
                final, _ = calibrate_confidence(base_conf, symptoms)
                assert 0.1 <= final <= 0.99
