"""Unit tests for the Symptom Assessment Agent."""

import pytest
from uuid import uuid4

from agents.symptom_assessment.agent import (
    ConversationPhase,
    ConversationState,
    check_red_flags,
    get_complaint_category,
    _extract_severity,
    _estimate_days_ago,
    _classify_duration,
    _extract_allergies,
    _is_explicit_number,
)


class TestRedFlagDetection:
    """Test emergency red flag pattern matching."""

    def test_cardiac_red_flag(self):
        assert check_red_flags("I have chest pain and I can't breathe") == "cardiac"

    def test_respiratory_red_flag(self):
        assert check_red_flags("I can't breathe, my throat is closing") == "respiratory"

    def test_neurological_red_flag(self):
        assert check_red_flags("This is the worst headache of my life") == "neurological"

    def test_mental_health_red_flag(self):
        assert check_red_flags("I want to kill myself") == "mental_health"

    def test_hemorrhage_red_flag(self):
        assert check_red_flags("The bleeding won't stop") == "hemorrhage"

    def test_no_red_flag(self):
        assert check_red_flags("I have a mild headache") is None

    def test_no_red_flag_general_complaint(self):
        assert check_red_flags("My knee hurts when I walk") is None


class TestSeverityExtraction:
    """Test severity score extraction from text."""

    def test_explicit_number(self):
        assert _extract_severity("It's about a 7") == 7

    def test_number_in_sentence(self):
        assert _extract_severity("I'd say 8 out of 10") == 8

    def test_natural_language_severe(self):
        assert _extract_severity("It's really bad") == 8

    def test_natural_language_mild(self):
        assert _extract_severity("It's mild, just a little annoying") == 3

    def test_natural_language_moderate(self):
        assert _extract_severity("It's moderate, uncomfortable") == 5

    def test_unbearable(self):
        assert _extract_severity("It's unbearable") == 10

    def test_barely_noticeable(self):
        assert _extract_severity("Barely noticeable") == 2


class TestOnsetEstimation:
    """Test days-ago estimation from onset descriptions."""

    def test_today(self):
        assert _estimate_days_ago("It started today") == 0

    def test_yesterday(self):
        assert _estimate_days_ago("Started yesterday") == 1

    def test_three_days(self):
        assert _estimate_days_ago("About 3 days ago") == 3

    def test_a_week(self):
        assert _estimate_days_ago("About a week ago") == 7

    def test_two_weeks(self):
        assert _estimate_days_ago("Two weeks ago") == 14

    def test_unknown(self):
        assert _estimate_days_ago("I'm not sure exactly when") is None


class TestDurationClassification:
    """Test duration pattern classification."""

    def test_worsening(self):
        assert _classify_duration("It's getting worse every day") == "worsening"

    def test_improving(self):
        assert _classify_duration("It's getting better slowly") == "improving"

    def test_intermittent(self):
        assert _classify_duration("It comes and goes") == "intermittent"

    def test_constant(self):
        assert _classify_duration("It's constant, all the time") == "constant"

    def test_stable(self):
        assert _classify_duration("About the same as before") == "stable"


class TestComplaintCategory:
    """Test primary complaint to category mapping."""

    def test_headache(self):
        assert get_complaint_category("I have a bad headache") == "headache"

    def test_chest_pain(self):
        assert get_complaint_category("Chest pain for 2 days") == "chest_pain"

    def test_stomach(self):
        assert get_complaint_category("My stomach really hurts") == "abdominal"

    def test_breathing(self):
        assert get_complaint_category("Having trouble breathing") == "respiratory"

    def test_unknown(self):
        assert get_complaint_category("Something weird is happening") == "default"


class TestAllergyExtraction:
    """Test allergy list extraction."""

    def test_no_allergies(self):
        assert _extract_allergies("No, none") == []

    def test_nkda(self):
        assert _extract_allergies("NKDA") == []

    def test_single_allergy(self):
        result = _extract_allergies("penicillin")
        assert "penicillin" in result

    def test_multiple_allergies(self):
        result = _extract_allergies("penicillin, sulfa, and ibuprofen")
        assert len(result) >= 2


class TestConversationState:
    """Test conversation state management."""

    def test_initial_state(self):
        state = ConversationState(
            session_id=uuid4(),
            patient_id=uuid4(),
        )
        assert state.phase == ConversationPhase.GREETING
        assert state.turn_count == 0
        assert state.completeness_score == 0.0
        assert not state.is_complete()

    def test_completeness_with_mandatory_fields(self):
        from shared.models import PrimaryComplaint, SeverityInfo, OnsetInfo

        state = ConversationState(session_id=uuid4(), patient_id=uuid4())
        state.symptoms.primary_complaint = PrimaryComplaint(
            text="headache", category="headache", confidence=0.9
        )
        state.symptoms.severity = SeverityInfo(score=5, source="explicit", confidence=0.9)
        state.symptoms.onset = OnsetInfo(description="2 days ago", days_ago_estimate=2, confidence=0.8)

        # Should be 0.25 + 0.20 + 0.15 = 0.60 (below 0.70 threshold)
        assert state.completeness_score == 0.60
        assert not state.is_complete()

    def test_fast_track_completion(self):
        from shared.models import PrimaryComplaint, SeverityInfo, OnsetInfo

        state = ConversationState(session_id=uuid4(), patient_id=uuid4())
        state.symptoms.primary_complaint = PrimaryComplaint(
            text="severe headache", category="headache", confidence=0.9
        )
        state.symptoms.severity = SeverityInfo(score=9, source="explicit", confidence=0.9)
        state.symptoms.onset = OnsetInfo(description="today", days_ago_estimate=0, confidence=0.8)

        # Fast track: severity >= 8, completeness 0.60 >= 0.60 threshold
        assert state.fast_track
        assert state.is_complete()
