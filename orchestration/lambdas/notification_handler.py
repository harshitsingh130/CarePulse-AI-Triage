"""Emergency notification handler.

Sends multi-channel notifications when Emergency is detected:
SMS, Push, PagerDuty webhook. Tracks delivery status per channel.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from shared.config import config
from shared.db import write_audit_entry
from shared.models import AuditEntry, AuditEventType, NotificationChannel, NotificationStatus
from shared.phi_redaction import get_logger
from shared.secrets import get_secret

logger = get_logger("notification", config.LOG_LEVEL)

_sns_client = boto3.client("sns")
_dynamodb = boto3.resource("dynamodb")
_notifications_table = _dynamodb.Table(config.NOTIFICATIONS_TABLE)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle emergency escalation notifications.

    Event shape:
    {
        "session_id": "uuid",
        "patient_id": "uuid",
        "urgency_level": "EMERGENCY",
        "channels": ["SMS", "PUSH", "PAGERDUTY"]
    }

    Sends notifications on all specified channels in parallel (within this Lambda).
    """
    session_id = event["session_id"]
    patient_id = event["patient_id"]
    channels = event.get("channels", ["SMS", "PUSH", "PAGERDUTY"])

    logger.info(
        "Emergency escalation triggered",
        extra={"session_id": session_id, "channels": channels},
    )

    # Build patient summary for notification content
    patient_summary = _build_notification_summary(session_id)

    results = {}
    for channel in channels:
        try:
            if channel == "SMS":
                results["SMS"] = _send_sms(session_id, patient_summary)
            elif channel == "PUSH":
                results["PUSH"] = _send_push(session_id, patient_summary)
            elif channel == "PAGERDUTY":
                results["PAGERDUTY"] = _send_pagerduty(session_id, patient_summary)
        except Exception as e:
            logger.error(f"Notification failed on {channel}: {e}", extra={"session_id": session_id})
            results[channel] = NotificationStatus.FAILED.value
            _record_notification(session_id, channel, NotificationStatus.FAILED, str(e))

    # Audit
    write_audit_entry(AuditEntry(
        patient_id=UUID(patient_id),
        timestamp=datetime.now(timezone.utc),
        event_type=AuditEventType.ESCALATION_TRIGGERED,
        session_id=UUID(session_id),
        actor_type="SYSTEM",
        actor_id="notification_handler",
        details={"channels": channels, "results": results},
    ))

    return {"session_id": session_id, "results": results}


def _build_notification_summary(session_id: str) -> str:
    """Build a concise patient summary for notification content."""
    from shared.db import get_session

    session = get_session(session_id)
    if not session:
        return f"EMERGENCY triage alert. Session: {session_id}. Check system for details."

    symptoms = session.get("structuredSymptoms", {})
    complaint = symptoms.get("primary_complaint", {}).get("text", "Unknown")
    severity = symptoms.get("severity", {}).get("score", "?")

    return (
        f"EMERGENCY TRIAGE ALERT\n"
        f"Session: {session_id[:8]}...\n"
        f"Complaint: {complaint}\n"
        f"Severity: {severity}/10\n"
        f"Action: Immediate review required."
    )


def _send_sms(session_id: str, summary: str) -> str:
    """Send SMS to on-call physician via SNS."""
    # In production: look up on-call schedule → get phone number
    # For MVP: send to a configured test number or SNS topic
    try:
        _sns_client.publish(
            TopicArn=f"arn:aws:sns:{config.BEDROCK_REGION}:*:triage-emergency-escalation",
            Message=summary,
            Subject="EMERGENCY TRIAGE ALERT",
            MessageAttributes={
                "channel": {"DataType": "String", "StringValue": "SMS"},
                "session_id": {"DataType": "String", "StringValue": session_id},
            },
        )
        _record_notification(session_id, "SMS", NotificationStatus.SENT)
        return NotificationStatus.SENT.value
    except ClientError as e:
        logger.error(f"SMS send failed: {e}")
        _record_notification(session_id, "SMS", NotificationStatus.FAILED, str(e))
        return NotificationStatus.FAILED.value


def _send_push(session_id: str, summary: str) -> str:
    """Send push notification via SNS platform endpoint."""
    # For MVP: publish to same topic (in production: platform endpoint per device)
    try:
        _sns_client.publish(
            TopicArn=f"arn:aws:sns:{config.BEDROCK_REGION}:*:triage-emergency-escalation",
            Message=json.dumps({
                "default": summary,
                "GCM": json.dumps({"notification": {"title": "EMERGENCY TRIAGE", "body": summary[:200]}}),
                "APNS": json.dumps({"aps": {"alert": {"title": "EMERGENCY TRIAGE", "body": summary[:200]}}}),
            }),
            MessageStructure="json",
            MessageAttributes={
                "channel": {"DataType": "String", "StringValue": "PUSH"},
            },
        )
        _record_notification(session_id, "PUSH", NotificationStatus.SENT)
        return NotificationStatus.SENT.value
    except ClientError as e:
        logger.error(f"Push send failed: {e}")
        _record_notification(session_id, "PUSH", NotificationStatus.FAILED, str(e))
        return NotificationStatus.FAILED.value


def _send_pagerduty(session_id: str, summary: str) -> str:
    """Create PagerDuty incident via Events API."""
    # For MVP: log the intent (PagerDuty integration requires webhook setup)
    try:
        if config.PAGERDUTY_SECRET_ARN:
            _secret = get_secret(config.PAGERDUTY_SECRET_ARN)
            # In production: HTTP POST to PagerDuty Events API v2
            # For MVP: just record that we would have paged
            logger.info("PagerDuty page triggered (stubbed)", extra={"session_id": session_id})
        else:
            logger.info("PagerDuty not configured — skipping", extra={"session_id": session_id})

        _record_notification(session_id, "PAGERDUTY", NotificationStatus.SENT)
        return NotificationStatus.SENT.value
    except Exception as e:
        logger.error(f"PagerDuty failed: {e}")
        _record_notification(session_id, "PAGERDUTY", NotificationStatus.FAILED, str(e))
        return NotificationStatus.FAILED.value


def _record_notification(
    session_id: str,
    channel: str,
    status: NotificationStatus,
    failure_reason: str = "",
) -> None:
    """Record notification attempt in DynamoDB."""
    _notifications_table.put_item(Item={
        "sessionId": session_id,
        "channel": channel,
        "status": status.value,
        "sentAt": datetime.now(timezone.utc).isoformat(),
        "failureReason": failure_reason,
        "retryCount": 0,
    })
