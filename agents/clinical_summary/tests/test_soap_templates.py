"""Unit tests for Clinical Summary Agent — template building and patient summary."""

import pytest
import json
from uuid import uuid4
from datetime import datetime, timezone

from shared.models import (
    CheckStatus,
    ClassificationMethod,
    ClinicAvailability,
    DurationPattern,
    GenerationMetadata,
    InteractionResult,
    InteractionSeverity,
    DrugInteraction,
    MedicalHistory,
    MedicationEntry,
    MedicationList,
    OnsetInfo,
    PatientSummary,
    PrimaryComplaint,
    RoutingDecision,
    SeverityInfo,
    SlotInfo,
    SOAPContent,
    SOAPFlags,
    SOAPNote,
    StructuredSymptoms,
    UrgencyLevel,
    UrgencyResult,
)
from agents.clinical_summary.soap_templates import (
    build_assessment_data,
    build_objective_data,
    build_plan_data,
    build_subjective_data,
)
from agents.clinical_summary.agent import generate_patient_summary


def _make_symptoms() -> dict:
    s = StructuredSymptoms(
        session_id=uuid4(),
        patient_id=uuid4(),
        assessment_complete=True,
        completeness_score=0.85,
        primary_complaint=PrimaryComplaint(text="severe headache for 3 days", category="headache", confidence=0.9),
        severity=SeverityInfo(score=7, source="explicit", confidence=0.9),
        onset=OnsetInfo(description="3 days ago", days_ago_estimate=3, confidence=0.8),
        duration_pattern=DurationPattern(type="worsening", description="getting worse each day", confidence=0.8),
        associated_symptoms=[],
        medical_history=MedicalHistory(conditions=["hypertension"], source="ehr", confidence=0.9),
        medications=MedicationList(current=["lisinopril", "atorvastatin"], source="ehr", confidence=0.9),
        conversation_turns=9,
        assessed_at=datetime.now(timezone.utc),
    )
    return json.loads(s.model_dump_json())


def _make_urgency() -> dict:
    u = UrgencyResult(
        session_id=uuid4(),
        urgency_level=UrgencyLevel.URGENT,
        confidence_score=0.82,
        classification_method=ClassificationMethod.LLM_REASONING,
        reasoning="Severity 7/10 worsening headache with hypertension history. Conservative bias → Urgent.",
        risk_factors=["hypertension", "worsening pattern"],
        recommended_timeframe="within 4 hours",
        modifiers_applied=["Cardiac history + headache"],
        requires_nurse_review=False,
        scored_at=datetime.now(timezone.utc),
    )
    return json.loads(u.model_dump_json())


def _make_interactions(with_critical: bool = False) -> dict:
    interactions = []
    if with_critical:
        interactions.append(DrugInteraction(
            drug_a="warfarin",
            drug_b="ibuprofen",
            severity=InteractionSeverity.CRITICAL,
            mechanism="NSAIDs + anticoagulant",
            clinical_effect="Increased bleeding risk",
            recommendation="Avoid combination",
        ))

    i = InteractionResult(
        session_id=uuid4(),
        patient_id=uuid4(),
        medications_checked=[
            MedicationEntry(drug_name="lisinopril", source="pharmacy_system", dosage="10mg"),
            MedicationEntry(drug_name="atorvastatin", source="pharmacy_system", dosage="20mg"),
        ],
        interactions_found=interactions,
        check_status=CheckStatus.COMPLETE,
        critical_count=1 if with_critical else 0,
        moderate_count=0,
        informational_count=0,
        requires_physician_alert=with_critical,
        checked_at=datetime.now(timezone.utc),
    )
    return json.loads(i.model_dump_json())


def _make_routing() -> dict:
    r = RoutingDecision(
        session_id=uuid4(),
        patient_id=uuid4(),
        department="Neurology",
        department_confidence=0.85,
        routing_method=ClassificationMethod.RULE_BASED,
        routing_reasoning="Headache maps to Neurology",
        primary_clinic=ClinicAvailability(
            clinic_id="clinic-01",
            clinic_name="Main Campus",
            available_slots=[
                SlotInfo(datetime=datetime(2026, 7, 9, 10, 30, tzinfo=timezone.utc), specialist_name="Dr. Smith", duration_minutes=30),
            ],
        ),
        alternatives=[],
        status="routed",
        routed_at=datetime.now(timezone.utc),
    )
    return json.loads(r.model_dump_json())


class TestSubjectiveData:
    def test_builds_all_fields(self):
        data = build_subjective_data(_make_symptoms())
        assert data["primary_complaint"] == "severe headache for 3 days"
        assert data["severity"] == "7"
        assert data["onset"] == "3 days ago"
        assert "hypertension" in data["medical_history"]
        assert "lisinopril" in data["medications"]

    def test_handles_missing_data(self):
        minimal = {"primary_complaint": {}, "severity": {}, "onset": {}}
        data = build_subjective_data(minimal)
        assert data["primary_complaint"] == "Not reported"
        assert data["severity"] == "?"


class TestObjectiveData:
    def test_builds_with_interactions(self):
        data = build_objective_data(_make_symptoms(), _make_interactions(with_critical=True))
        assert "warfarin" in data["interactions"]
        assert "CRITICAL" in data["interactions"]

    def test_builds_without_interactions(self):
        data = build_objective_data(_make_symptoms(), _make_interactions(with_critical=False))
        assert "No significant" in data["interactions"]


class TestAssessmentData:
    def test_includes_urgency(self):
        data = build_assessment_data(_make_urgency(), _make_interactions())
        assert data["urgency_level"] == "URGENT"
        assert "82%" in data["confidence"]

    def test_includes_critical_alerts(self):
        data = build_assessment_data(_make_urgency(), _make_interactions(with_critical=True))
        assert "warfarin" in data["critical_interactions"]


class TestPlanData:
    def test_includes_routing(self):
        data = build_plan_data(_make_routing(), _make_urgency())
        assert data["department"] == "Neurology"
        assert data["appointment_status"] == "routed"
        assert "Dr. Smith" in data["specialist"]


class TestPatientSummary:
    def test_generates_redacted_summary(self):
        soap = SOAPNote(
            session_id=uuid4(),
            patient_id=uuid4(),
            generated_at=datetime.now(timezone.utc),
            soap_note=SOAPContent(
                subjective="Patient presents with severe headache for 3 days, worsening.",
                objective="Medications verified. No critical interactions.",
                assessment="Urgent. Worsening headache with hypertension.",
                plan="Neurology appointment scheduled.",
            ),
            flags=SOAPFlags(critical_interaction=False),
            metadata=GenerationMetadata(model_version="test", generation_time_ms=100),
        )
        urgency = UrgencyResult(
            session_id=uuid4(),
            urgency_level=UrgencyLevel.URGENT,
            confidence_score=0.82,
            classification_method=ClassificationMethod.LLM_REASONING,
            reasoning="test",
            recommended_timeframe="within 4 hours",
            scored_at=datetime.now(timezone.utc),
        )
        routing = RoutingDecision(
            session_id=uuid4(),
            patient_id=uuid4(),
            department="Neurology",
            department_confidence=0.85,
            routing_method=ClassificationMethod.RULE_BASED,
            routing_reasoning="test",
            primary_clinic=ClinicAvailability(
                clinic_id="c1",
                clinic_name="Main",
                available_slots=[SlotInfo(datetime=datetime.now(timezone.utc), specialist_name="Dr. A")],
            ),
            status="routed",
            routed_at=datetime.now(timezone.utc),
        )

        summary = generate_patient_summary(soap, urgency, routing)
        assert isinstance(summary, PatientSummary)
        assert "Urgent" in summary.urgency_level
        assert "Neurology" in summary.next_steps
        # Should NOT contain clinical reasoning
        assert "hypertension" not in summary.urgency_level


class TestSOAPSerialization:
    """PBT candidate: serialization round-trip."""

    def test_soap_note_round_trip(self):
        soap = SOAPNote(
            session_id=uuid4(),
            patient_id=uuid4(),
            generated_at=datetime.now(timezone.utc),
            soap_note=SOAPContent(
                subjective="Test subjective with special chars: <>&\"'",
                objective="Test objective",
                assessment="Test assessment",
                plan="Test plan",
            ),
            flags=SOAPFlags(critical_interaction=True, incomplete_data=["onset"]),
            metadata=GenerationMetadata(model_version="test-v1", generation_time_ms=500),
        )

        # Serialize and deserialize
        json_str = soap.model_dump_json()
        restored = SOAPNote.model_validate_json(json_str)

        assert restored.session_id == soap.session_id
        assert restored.soap_note.subjective == soap.soap_note.subjective
        assert restored.flags.critical_interaction == soap.flags.critical_interaction
        assert restored.metadata.generation_time_ms == 500
