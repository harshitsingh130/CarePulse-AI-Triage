"""Data contracts shared across all triage agents.

These Pydantic models define the exact JSON structure passed between agents.
Every agent imports from here — this is the single source of truth for
inter-agent communication contracts.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# --- Enumerations ---


class UrgencyLevel(str, Enum):
    EMERGENCY = "EMERGENCY"
    URGENT = "URGENT"
    STANDARD = "STANDARD"
    ROUTINE = "ROUTINE"


class SessionStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_NURSE = "AWAITING_NURSE"
    AWAITING_ROUTING = "AWAITING_ROUTING"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class ConversationRole(str, Enum):
    PATIENT = "PATIENT"
    AI_AGENT = "AI_AGENT"
    TRIAGE_NURSE = "TRIAGE_NURSE"
    SYSTEM = "SYSTEM"


class ClassificationMethod(str, Enum):
    RULE_BASED = "rule_based"
    LLM_REASONING = "llm_reasoning"
    HYBRID = "hybrid"


class InteractionSeverity(str, Enum):
    CRITICAL = "critical"
    MODERATE = "moderate"
    INFORMATIONAL = "informational"


class CheckStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class NotificationChannel(str, Enum):
    SMS = "SMS"
    PUSH = "PUSH"
    PAGERDUTY = "PAGERDUTY"
    LIVE_TRANSFER = "LIVE_TRANSFER"


class NotificationStatus(str, Enum):
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    OFFERED = "OFFERED"


class AuditEventType(str, Enum):
    TRIAGE_STARTED = "TRIAGE_STARTED"
    URGENCY_ASSIGNED = "URGENCY_ASSIGNED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    NURSE_OVERRIDE = "NURSE_OVERRIDE"
    ROUTING_DECIDED = "ROUTING_DECIDED"
    SOAP_GENERATED = "SOAP_GENERATED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    PHI_ACCESSED = "PHI_ACCESSED"
    DRUG_CHECK_PERFORMED = "DRUG_CHECK_PERFORMED"


# --- Symptom Assessment Agent Output (Unit 2) ---


class PrimaryComplaint(BaseModel):
    text: str = Field(..., description="Patient's description in their own words")
    category: str = Field(..., description="Mapped complaint category")
    confidence: float = Field(..., ge=0.0, le=1.0)


class OnsetInfo(BaseModel):
    description: str = Field(..., description="When symptoms started")
    days_ago_estimate: Optional[int] = Field(None, ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)


class SeverityInfo(BaseModel):
    score: int = Field(..., ge=1, le=10)
    source: str = Field(..., description="'explicit' or 'inferred'")
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("score")
    @classmethod
    def validate_severity_range(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("Severity must be between 1 and 10")
        return v


class DurationPattern(BaseModel):
    type: str = Field(..., description="constant|intermittent|worsening|improving|stable")
    description: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class AssociatedSymptom(BaseModel):
    symptom: str
    severity: Optional[int] = Field(None, ge=1, le=10)
    confidence: float = Field(..., ge=0.0, le=1.0)


class MedicalHistory(BaseModel):
    conditions: list[str] = Field(default_factory=list)
    source: str = Field(..., description="'ehr', 'patient_reported', or 'both'")
    confidence: float = Field(..., ge=0.0, le=1.0)


class MedicationList(BaseModel):
    current: list[str] = Field(default_factory=list)
    source: str = Field(..., description="'ehr', 'patient_reported', or 'both'")
    confidence: float = Field(..., ge=0.0, le=1.0)


class AllergyInfo(BaseModel):
    items: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class StructuredSymptoms(BaseModel):
    """Primary output of the Symptom Assessment Agent (Unit 2).
    Input to the Triage Scoring Agent (Unit 3).
    """

    session_id: UUID
    patient_id: UUID
    assessment_complete: bool = False
    completeness_score: float = Field(0.0, ge=0.0, le=1.0)
    red_flag_detected: bool = False
    red_flag_category: Optional[str] = None
    primary_complaint: Optional[PrimaryComplaint] = None
    onset: Optional[OnsetInfo] = None
    severity: Optional[SeverityInfo] = None
    duration_pattern: Optional[DurationPattern] = None
    associated_symptoms: list[AssociatedSymptom] = Field(default_factory=list)
    medical_history: Optional[MedicalHistory] = None
    medications: Optional[MedicationList] = None
    allergies: Optional[AllergyInfo] = None
    conversation_turns: int = 0
    fast_tracked: bool = False
    assessed_at: Optional[datetime] = None


# --- Triage Scoring Agent Output (Unit 3) ---


class UrgencyResult(BaseModel):
    """Primary output of the Triage Scoring Agent (Unit 3).
    Consumed by Supervisor, Clinical Summary, and Portal.
    """

    session_id: UUID
    urgency_level: UrgencyLevel
    confidence_score: float = Field(..., ge=0.1, le=0.99)
    classification_method: ClassificationMethod
    reasoning: str
    risk_factors: list[str] = Field(default_factory=list)
    recommended_timeframe: str
    modifiers_applied: list[str] = Field(default_factory=list)
    data_quality_penalties: list[str] = Field(default_factory=list)
    requires_nurse_review: bool = False
    scored_at: datetime


# --- Drug Interaction Agent Output (Unit 4) ---


class DrugInteraction(BaseModel):
    drug_a: str
    drug_b: str
    severity: InteractionSeverity
    mechanism: str
    clinical_effect: str
    recommendation: str


class MedicationEntry(BaseModel):
    drug_name: str
    brand_name: Optional[str] = None
    source: str = Field(..., description="'pharmacy_system', 'patient_reported', or 'both'")
    dosage: Optional[str] = None
    frequency: Optional[str] = None


class InteractionResult(BaseModel):
    """Primary output of the Drug Interaction Agent (Unit 4)."""

    session_id: UUID
    patient_id: UUID
    medications_checked: list[MedicationEntry] = Field(default_factory=list)
    interactions_found: list[DrugInteraction] = Field(default_factory=list)
    check_status: CheckStatus
    critical_count: int = 0
    moderate_count: int = 0
    informational_count: int = 0
    requires_physician_alert: bool = False
    checked_at: datetime


# --- Specialist Routing Agent Output (Unit 5) ---


class SlotInfo(BaseModel):
    datetime: datetime
    specialist_name: str
    duration_minutes: int = 30


class ClinicAvailability(BaseModel):
    clinic_id: str
    clinic_name: str
    available_slots: list[SlotInfo] = Field(default_factory=list)
    reason: Optional[str] = None


class AppointmentWindow(BaseModel):
    start: datetime
    end: datetime
    priority: str = Field(..., description="HIGH, NORMAL, or STANDARD")


class RoutingDecision(BaseModel):
    """Primary output of the Specialist Routing Agent (Unit 5)."""

    session_id: UUID
    patient_id: UUID
    department: str
    department_confidence: float = Field(..., ge=0.0, le=1.0)
    routing_method: ClassificationMethod
    routing_reasoning: str
    specialist_name: Optional[str] = None
    primary_clinic: Optional[ClinicAvailability] = None
    alternatives: list[ClinicAvailability] = Field(default_factory=list)
    appointment_window: Optional[AppointmentWindow] = None
    status: str = Field(..., description="routed, no_availability, or ambiguous_department")
    mental_health_priority: bool = False
    routed_at: datetime


# --- Clinical Summary Agent Output (Unit 6) ---


class SOAPContent(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str


class SOAPFlags(BaseModel):
    critical_interaction: bool = False
    nurse_override: bool = False
    fast_tracked: bool = False
    ehr_push_status: str = "stubbed"
    incomplete_data: list[str] = Field(default_factory=list)


class GenerationMetadata(BaseModel):
    model_version: str
    generation_time_ms: int
    validation_passed: bool = True
    retry_count: int = 0
    fallback_used: bool = False


class SOAPNote(BaseModel):
    """Primary output of the Clinical Summary Agent (Unit 6)."""

    session_id: UUID
    patient_id: UUID
    generated_at: datetime
    soap_note: SOAPContent
    flags: SOAPFlags
    metadata: GenerationMetadata


# --- Supervisor Agent Entities (Unit 7) ---


class EscalationEvent(BaseModel):
    session_id: UUID
    patient_id: UUID
    urgency_level: UrgencyLevel
    patient_summary: str
    channels: list[NotificationChannel]
    on_call_physician_id: Optional[str] = None
    triggered_at: datetime


class NurseOverride(BaseModel):
    original_urgency: UrgencyLevel
    override_urgency: UrgencyLevel
    nurse_id: str
    reason: str
    overridden_at: datetime


class TriageSession(BaseModel):
    """Complete session state stored in DynamoDB."""

    session_id: UUID
    patient_id: UUID
    status: SessionStatus
    urgency_level: Optional[UrgencyLevel] = None
    confidence_score: Optional[float] = None
    clinic_id: str
    structured_symptoms: Optional[StructuredSymptoms] = None
    urgency_result: Optional[UrgencyResult] = None
    interaction_result: Optional[InteractionResult] = None
    routing_decision: Optional[RoutingDecision] = None
    soap_note: Optional[SOAPNote] = None
    nurse_override: Optional[NurseOverride] = None
    workflow_execution_arn: Optional[str] = None
    connection_id: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


# --- Audit Trail ---


class AuditEntry(BaseModel):
    patient_id: UUID
    timestamp: datetime
    event_type: AuditEventType
    session_id: Optional[UUID] = None
    actor_type: str = Field(..., description="AI_AGENT, PATIENT, NURSE, PHYSICIAN, SYSTEM")
    actor_id: str
    details: Dict = Field(default_factory=dict)
    reasoning: Optional[str] = None


# --- Patient Portal Entities ---


class PatientSummary(BaseModel):
    """Redacted version of SOAP note safe for patient viewing."""

    symptoms_reported: str
    medications_reviewed: str
    urgency_level: str
    next_steps: str


class ConsentGrant(BaseModel):
    consent_type: str = Field(..., description="dataProcessing, aiTriage, or dataSharing")
    granted_at: datetime
    version: str = "1.0"
