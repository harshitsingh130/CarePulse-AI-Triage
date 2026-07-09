"""Triage Scoring Agent — hybrid urgency classification.

Uses a rule-based pre-classifier for definitive cases and
LLM clinical reasoning for ambiguous cases. Applies history
modifiers and confidence calibration.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from shared.bedrock_client import BedrockError, BedrockTimeoutError, invoke_model_json
from shared.config import config
from shared.models import (
    ClassificationMethod,
    StructuredSymptoms,
    UrgencyLevel,
    UrgencyResult,
)
from shared.phi_redaction import get_logger

from .prompts import SCORING_SYSTEM_PROMPT, build_scoring_prompt
from .scoring_logic import (
    calibrate_confidence,
    check_history_modifiers,
    elevate_urgency,
    pre_classify,
)

logger = get_logger("triage-scoring", config.LOG_LEVEL)

# Fallback decision matrix when LLM is unavailable
FALLBACK_MATRIX: dict[tuple, UrgencyLevel] = {
    # (severity_range, pattern) → urgency
    # severity_range: "high" (7-10), "mid" (4-6), "low" (1-3)
    # pattern: "worsening", "stable", "improving", "unknown"
    ("high", "worsening"): UrgencyLevel.EMERGENCY,
    ("high", "stable"): UrgencyLevel.URGENT,
    ("high", "improving"): UrgencyLevel.URGENT,
    ("high", "unknown"): UrgencyLevel.URGENT,
    ("mid", "worsening"): UrgencyLevel.URGENT,
    ("mid", "stable"): UrgencyLevel.STANDARD,
    ("mid", "improving"): UrgencyLevel.STANDARD,
    ("mid", "unknown"): UrgencyLevel.STANDARD,
    ("low", "worsening"): UrgencyLevel.STANDARD,
    ("low", "stable"): UrgencyLevel.ROUTINE,
    ("low", "improving"): UrgencyLevel.ROUTINE,
    ("low", "unknown"): UrgencyLevel.ROUTINE,
}

TIMEFRAME_MAP = {
    UrgencyLevel.EMERGENCY: "immediate",
    UrgencyLevel.URGENT: "within 4 hours",
    UrgencyLevel.STANDARD: "within 48 hours",
    UrgencyLevel.ROUTINE: "within 2 weeks",
}


def _get_severity_range(score: int) -> str:
    if score >= 7:
        return "high"
    if score >= 4:
        return "mid"
    return "low"


def _get_pattern(symptoms: StructuredSymptoms) -> str:
    if symptoms.duration_pattern:
        return symptoms.duration_pattern.type
    return "unknown"


def score_urgency(symptoms: StructuredSymptoms) -> UrgencyResult:
    """Score patient urgency using hybrid approach.

    1. Rule-based pre-classifier (deterministic, fast)
    2. LLM clinical reasoning (nuanced cases)
    3. History modifier check (elevate if risky combination)
    4. Confidence calibration (adjust for data quality)

    Args:
        symptoms: Structured symptom data from assessment agent.

    Returns:
        UrgencyResult with classification, confidence, and reasoning.
    """
    session_id = symptoms.session_id

    # Step 1: Rule-based pre-classifier
    pre_result = pre_classify(symptoms)

    if pre_result.triggered:
        logger.info(
            "Pre-classifier triggered",
            extra={
                "session_id": str(session_id),
                "rule": pre_result.rule_fired,
                "urgency": pre_result.urgency_level.value,
            },
        )

        # Still apply history modifiers even for rule-based
        modifiers = check_history_modifiers(symptoms)
        final_level = pre_result.urgency_level
        if modifiers and final_level != UrgencyLevel.EMERGENCY:
            final_level = elevate_urgency(final_level)

        final_confidence, adjustments = calibrate_confidence(
            pre_result.confidence, symptoms
        )

        return UrgencyResult(
            session_id=session_id,
            urgency_level=final_level,
            confidence_score=final_confidence,
            classification_method=ClassificationMethod.RULE_BASED,
            reasoning=pre_result.reasoning,
            risk_factors=[],
            recommended_timeframe=TIMEFRAME_MAP[final_level],
            modifiers_applied=modifiers,
            data_quality_penalties=[adj.reason for adj in adjustments if adj.amount < 0],
            requires_nurse_review=final_confidence < config.NURSE_HANDOFF_THRESHOLD,
            scored_at=datetime.now(timezone.utc),
        )

    # Step 2: LLM clinical reasoning
    urgency_level, base_confidence, reasoning, risk_factors, timeframe = _invoke_llm_scoring(
        symptoms
    )

    # Step 3: History modifier check
    modifiers = check_history_modifiers(symptoms)
    if modifiers and urgency_level != UrgencyLevel.EMERGENCY:
        urgency_level = elevate_urgency(urgency_level)
        reasoning += f"\n\nHistory modifier applied: {', '.join(modifiers)}. Urgency elevated by one level."

    # Step 4: Confidence calibration
    final_confidence, adjustments = calibrate_confidence(base_confidence, symptoms)

    # Determine if nurse review needed
    requires_nurse = final_confidence < config.NURSE_HANDOFF_THRESHOLD
    if requires_nurse:
        logger.info(
            "Nurse review required",
            extra={"session_id": str(session_id), "confidence": final_confidence},
        )

    # Handle very low confidence
    if final_confidence < config.VERY_LOW_CONFIDENCE_THRESHOLD:
        urgency_level = UrgencyLevel.URGENT
        reasoning += "\n\nConfidence very low — defaulting to URGENT for safety."
        requires_nurse = True

    return UrgencyResult(
        session_id=session_id,
        urgency_level=urgency_level,
        confidence_score=final_confidence,
        classification_method=ClassificationMethod.LLM_REASONING,
        reasoning=reasoning,
        risk_factors=risk_factors,
        recommended_timeframe=timeframe or TIMEFRAME_MAP[urgency_level],
        modifiers_applied=modifiers,
        data_quality_penalties=[adj.reason for adj in adjustments if adj.amount < 0],
        requires_nurse_review=requires_nurse,
        scored_at=datetime.now(timezone.utc),
    )


def _invoke_llm_scoring(
    symptoms: StructuredSymptoms,
) -> tuple[UrgencyLevel, float, str, list[str], str]:
    """Invoke Bedrock for clinical reasoning.

    Returns: (urgency_level, confidence, reasoning, risk_factors, timeframe)
    Falls back to decision matrix if LLM fails.
    """
    symptoms_dict = json.loads(symptoms.model_dump_json())
    user_prompt = build_scoring_prompt(symptoms_dict)

    try:
        result = invoke_model_json(
            system_prompt=SCORING_SYSTEM_PROMPT,
            user_message=user_prompt,
            temperature=0.0,  # Deterministic
            max_tokens=1000,
        )

        urgency_str = result.get("urgency_level", "URGENT").upper()
        try:
            urgency_level = UrgencyLevel(urgency_str)
        except ValueError:
            urgency_level = UrgencyLevel.URGENT  # Conservative default

        confidence = float(result.get("confidence", 0.7))
        confidence = max(0.1, min(0.99, confidence))

        reasoning = result.get("reasoning", "LLM reasoning unavailable")
        risk_factors = result.get("risk_factors", [])
        timeframe = result.get("recommended_timeframe", "")

        logger.info(
            "LLM scoring complete",
            extra={
                "session_id": str(symptoms.session_id),
                "urgency": urgency_level.value,
                "confidence": confidence,
            },
        )

        return urgency_level, confidence, reasoning, risk_factors, timeframe

    except (BedrockTimeoutError, BedrockError, ValueError) as e:
        logger.warning(
            f"LLM scoring failed, using fallback matrix: {e}",
            extra={"session_id": str(symptoms.session_id)},
        )
        return _fallback_scoring(symptoms)


def _fallback_scoring(
    symptoms: StructuredSymptoms,
) -> tuple[UrgencyLevel, float, str, list[str], str]:
    """Fallback scoring using the decision matrix when LLM is unavailable."""
    severity_range = "mid"
    if symptoms.severity:
        severity_range = _get_severity_range(symptoms.severity.score)

    pattern = _get_pattern(symptoms)

    key = (severity_range, pattern)
    urgency_level = FALLBACK_MATRIX.get(key, UrgencyLevel.STANDARD)

    reasoning = (
        f"Fallback scoring (LLM unavailable). "
        f"Severity range: {severity_range}, pattern: {pattern}. "
        f"Matrix classification: {urgency_level.value}."
    )

    # Reduced confidence for fallback
    confidence = 0.60

    return urgency_level, confidence, reasoning, [], TIMEFRAME_MAP[urgency_level]
