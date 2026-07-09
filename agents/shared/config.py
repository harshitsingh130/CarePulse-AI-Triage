"""Environment configuration for all agents.

Reads from environment variables set by CDK Lambda configuration.
Never hardcode values — everything comes from env or Secrets Manager.
"""

import os


class Config:
    """Application configuration loaded from environment variables."""

    # DynamoDB table names
    SESSIONS_TABLE: str = os.environ.get("SESSIONS_TABLE", "triage-sessions")
    PATIENTS_TABLE: str = os.environ.get("PATIENTS_TABLE", "triage-patients")
    CONVERSATIONS_TABLE: str = os.environ.get("CONVERSATIONS_TABLE", "triage-conversations")
    NOTIFICATIONS_TABLE: str = os.environ.get("NOTIFICATIONS_TABLE", "triage-notifications")
    AUDIT_TRAIL_TABLE: str = os.environ.get("AUDIT_TRAIL_TABLE", "triage-audit-trail")
    APPOINTMENTS_TABLE: str = os.environ.get("APPOINTMENTS_TABLE", "triage-appointments")

    # KMS
    PHI_KEY_ARN: str = os.environ.get("PHI_KEY_ARN", "")

    # Bedrock
    BEDROCK_MODEL_ID: str = os.environ.get(
        "BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514"
    )
    BEDROCK_REGION: str = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))

    # Step Functions
    TRIAGE_PIPELINE_ARN: str = os.environ.get("TRIAGE_PIPELINE_ARN", "")
    NURSE_HANDOFF_ARN: str = os.environ.get("NURSE_HANDOFF_ARN", "")

    # WebSocket API
    WEBSOCKET_API_ENDPOINT: str = os.environ.get("WEBSOCKET_API_ENDPOINT", "")

    # Secrets Manager
    PAGERDUTY_SECRET_ARN: str = os.environ.get("PAGERDUTY_SECRET_ARN", "")
    PHARMACY_SECRET_ARN: str = os.environ.get("PHARMACY_SECRET_ARN", "")

    # Logging
    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    # Timeouts (seconds)
    PHARMACY_TIMEOUT: int = int(os.environ.get("PHARMACY_TIMEOUT", "3"))
    SCHEDULING_TIMEOUT: int = int(os.environ.get("SCHEDULING_TIMEOUT", "2"))
    BEDROCK_TIMEOUT: int = int(os.environ.get("BEDROCK_TIMEOUT", "10"))

    # Confidence thresholds
    NURSE_HANDOFF_THRESHOLD: float = float(os.environ.get("NURSE_HANDOFF_THRESHOLD", "0.70"))
    VERY_LOW_CONFIDENCE_THRESHOLD: float = float(
        os.environ.get("VERY_LOW_CONFIDENCE_THRESHOLD", "0.50")
    )


config = Config()
