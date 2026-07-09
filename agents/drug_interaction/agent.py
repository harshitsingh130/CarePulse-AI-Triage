"""Drug Interaction Agent — medication safety checking logic.

Assembles medication list from pharmacy system + patient-reported,
checks for interactions, classifies severity, and produces InteractionResult.
"""

from __future__ import annotations

import signal
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from shared.config import config
from shared.models import (
    CheckStatus,
    DrugInteraction,
    InteractionResult,
    InteractionSeverity,
    MedicationEntry,
)
from shared.phi_redaction import get_logger

from .pharmacy_client import normalize_medication, query_pharmacy_system

logger = get_logger("drug-interaction", config.LOG_LEVEL)


class PharmacyTimeoutError(Exception):
    """Raised when pharmacy system query exceeds timeout."""
    pass


def _timeout_handler(signum, frame):
    raise PharmacyTimeoutError("Pharmacy system query exceeded timeout")


def check_interactions(
    session_id: UUID,
    patient_id: UUID,
    patient_ehr_id: Optional[str],
    reported_medications: list[str],
) -> InteractionResult:
    """Check patient medications for dangerous drug-drug interactions.

    Args:
        session_id: Current triage session.
        patient_id: Patient identifier.
        patient_ehr_id: EHR patient ID for pharmacy lookup (may be None).
        reported_medications: Medications reported by patient during triage.

    Returns:
        InteractionResult with all findings.
    """

    # Normalize reported medications
    normalized_reported = [normalize_medication(m) for m in reported_medications]

    # Skip check if fewer than 2 medications total
    if len(normalized_reported) < 2 and not patient_ehr_id:
        logger.info(
            "Fewer than 2 medications — skipping interaction check",
            extra={"session_id": str(session_id)},
        )
        return InteractionResult(
            session_id=session_id,
            patient_id=patient_id,
            medications_checked=[
                MedicationEntry(drug_name=m, source="patient_reported")
                for m in normalized_reported
            ],
            interactions_found=[],
            check_status=CheckStatus.COMPLETE,
            critical_count=0,
            moderate_count=0,
            informational_count=0,
            requires_physician_alert=False,
            checked_at=datetime.now(timezone.utc),
        )

    # Query pharmacy system with timeout
    medications: list[MedicationEntry] = []
    interactions: list[DrugInteraction] = []
    check_status = CheckStatus.UNAVAILABLE

    try:
        # Set alarm for timeout (Unix only — Lambda runs on Linux)
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(config.PHARMACY_TIMEOUT)

        medications, interactions, check_status = query_pharmacy_system(
            patient_ehr_id=patient_ehr_id,
            reported_medications=normalized_reported,
        )

        # Cancel alarm
        signal.alarm(0)

    except PharmacyTimeoutError:
        logger.warning(
            "Pharmacy system timed out",
            extra={"session_id": str(session_id), "timeout": config.PHARMACY_TIMEOUT},
        )
        check_status = CheckStatus.UNAVAILABLE
        # Fall back to patient-reported only
        medications = [
            MedicationEntry(drug_name=m, source="patient_reported")
            for m in normalized_reported
        ]
    except Exception as e:
        logger.error(
            f"Pharmacy system error: {e}",
            extra={"session_id": str(session_id)},
        )
        check_status = CheckStatus.UNAVAILABLE
        medications = [
            MedicationEntry(drug_name=m, source="patient_reported")
            for m in normalized_reported
        ]
    finally:
        signal.alarm(0)  # Ensure alarm is cancelled

    # Merge patient-reported medications not already in pharmacy list
    pharmacy_names = {m.drug_name.lower() for m in medications}
    for med in normalized_reported:
        if med.lower() not in pharmacy_names:
            medications.append(MedicationEntry(
                drug_name=med,
                source="patient_reported",
            ))

    # Count by severity
    critical_count = sum(1 for i in interactions if i.severity == InteractionSeverity.CRITICAL)
    moderate_count = sum(1 for i in interactions if i.severity == InteractionSeverity.MODERATE)
    informational_count = sum(1 for i in interactions if i.severity == InteractionSeverity.INFORMATIONAL)

    result = InteractionResult(
        session_id=session_id,
        patient_id=patient_id,
        medications_checked=medications,
        interactions_found=interactions,
        check_status=check_status,
        critical_count=critical_count,
        moderate_count=moderate_count,
        informational_count=informational_count,
        requires_physician_alert=critical_count > 0,
        checked_at=datetime.now(timezone.utc),
    )

    logger.info(
        "Interaction check complete",
        extra={
            "session_id": str(session_id),
            "status": check_status.value,
            "medications_count": len(medications),
            "critical": critical_count,
            "moderate": moderate_count,
        },
    )

    return result
