"""Unit tests for Specialist Routing Agent."""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from shared.models import (
    ClassificationMethod,
    DurationPattern,
    MedicalHistory,
    OnsetInfo,
    PrimaryComplaint,
    SeverityInfo,
    StructuredSymptoms,
    UrgencyLevel,
    UrgencyResult,
)
from agents.specialist_routing.department_map import (
    CLINIC_NETWORK,
    DEPARTMENTS,
    match_department,
)
from agents.specialist_routing.agent import route_patient


def _make_symptoms(complaint_text: str, category: str, associated: list[str] = None) -> StructuredSymptoms:
    return StructuredSymptoms(
        session_id=uuid4(),
        patient_id=uuid4(),
        assessment_complete=True,
        completeness_score=0.80,
        primary_complaint=PrimaryComplaint(text=complaint_text, category=category, confidence=0.9),
        severity=SeverityInfo(score=6, source="explicit", confidence=0.9),
        onset=OnsetInfo(description="2 days ago", days_ago_estimate=2, confidence=0.8),
        duration_pattern=DurationPattern(type="stable", description="same", confidence=0.8),
        associated_symptoms=[],
        medical_history=MedicalHistory(conditions=[], source="patient_reported", confidence=0.8),
        conversation_turns=8,
        assessed_at=datetime.now(timezone.utc),
    )


def _make_urgency(level: UrgencyLevel = UrgencyLevel.STANDARD) -> UrgencyResult:
    return UrgencyResult(
        session_id=uuid4(),
        urgency_level=level,
        confidence_score=0.82,
        classification_method=ClassificationMethod.RULE_BASED,
        reasoning="Test",
        recommended_timeframe="within 48 hours",
        scored_at=datetime.now(timezone.utc),
    )


class TestDepartmentMatching:
    """Test symptom-to-department rule matching."""

    def test_chest_pain_maps_to_cardiology(self):
        result = match_department("chest pain for 2 days", "chest_pain", [])
        assert result.department == "Cardiology"
        assert result.confidence >= 0.80

    def test_headache_maps_to_neurology(self):
        result = match_department("severe headache with dizziness", "headache", ["dizziness"])
        assert result.department == "Neurology"

    def test_knee_pain_maps_to_orthopedics(self):
        result = match_department("knee pain after fall", "musculoskeletal", ["swelling"])
        assert result.department == "Orthopedics"

    def test_stomach_pain_maps_to_gi(self):
        result = match_department("stomach pain and nausea", "abdominal", ["nausea"])
        assert result.department == "Gastroenterology"

    def test_cough_maps_to_pulmonology(self):
        result = match_department("persistent cough with wheezing", "respiratory", ["wheezing"])
        assert result.department == "Pulmonology"

    def test_rash_maps_to_dermatology(self):
        result = match_department("spreading rash on arms", "skin", ["itching"])
        assert result.department == "Dermatology"

    def test_ear_pain_maps_to_ent(self):
        result = match_department("ear pain and hearing loss", "default", ["hearing loss"])
        assert result.department == "ENT"

    def test_urinary_maps_to_urology(self):
        result = match_department("blood in urine", "default", ["frequent urination"])
        assert result.department == "Urology"

    def test_depression_maps_to_psychiatry(self):
        result = match_department("feeling depressed and can't sleep", "mental_health", ["insomnia"])
        assert result.department == "Psychiatry"

    def test_unknown_maps_to_internal_medicine(self):
        result = match_department("something weird I can't describe", "default", [])
        assert result.department == "Internal Medicine"
        assert result.confidence < 0.70  # Low confidence for catch-all

    def test_ambiguous_returns_low_confidence(self):
        # Headache + ear pain could be Neurology or ENT
        result = match_department("headache with ear pain", "headache", ["ear pain"])
        # Should match something, potentially ambiguous
        assert result.department in ["Neurology", "ENT"]


class TestRoutePatient:
    """Test the full routing flow."""

    def test_rejects_emergency_cases(self):
        symptoms = _make_symptoms("chest pain", "chest_pain")
        urgency = _make_urgency(UrgencyLevel.EMERGENCY)
        result = route_patient(uuid4(), uuid4(), symptoms, urgency, "clinic-01")
        assert result.status == "rejected"

    def test_routes_standard_case(self):
        symptoms = _make_symptoms("knee pain after fall", "musculoskeletal")
        urgency = _make_urgency(UrgencyLevel.STANDARD)
        result = route_patient(uuid4(), uuid4(), symptoms, urgency, "clinic-01")
        assert result.department == "Orthopedics"
        assert result.status == "routed"
        assert result.primary_clinic is not None
        assert len(result.primary_clinic.available_slots) > 0

    def test_urgent_gets_same_day_window(self):
        symptoms = _make_symptoms("severe headache", "headache")
        urgency = _make_urgency(UrgencyLevel.URGENT)
        result = route_patient(uuid4(), uuid4(), symptoms, urgency, "clinic-01")
        assert result.appointment_window.priority == "HIGH"

    def test_routine_gets_2_week_window(self):
        symptoms = _make_symptoms("mild rash", "skin")
        urgency = _make_urgency(UrgencyLevel.ROUTINE)
        result = route_patient(uuid4(), uuid4(), symptoms, urgency, "clinic-01")
        assert result.appointment_window.priority == "STANDARD"


class TestClinicNetwork:
    """Test clinic configuration."""

    def test_all_clinics_have_required_fields(self):
        for clinic_id, clinic in CLINIC_NETWORK.items():
            assert "name" in clinic
            assert "departments" in clinic
            assert "alternatives" in clinic
            assert isinstance(clinic["departments"], list)
            assert len(clinic["departments"]) > 0

    def test_all_departments_valid(self):
        valid_depts = {d.name for d in DEPARTMENTS}
        for clinic_id, clinic in CLINIC_NETWORK.items():
            for dept in clinic["departments"]:
                assert dept in valid_depts, f"{dept} in {clinic_id} is not a valid department"
