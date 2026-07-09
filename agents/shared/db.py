"""DynamoDB helpers for session management and audit trail.

Provides typed access to DynamoDB tables with automatic serialization
of Pydantic models and TTL calculation.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from .config import config
from .models import AuditEntry, AuditEventType, SessionStatus, TriageSession

_dynamodb = None
_sessions_table = None
_audit_table = None
_conversations_table = None


def _get_tables():
    global _dynamodb, _sessions_table, _audit_table, _conversations_table
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
        _sessions_table = _dynamodb.Table(config.SESSIONS_TABLE)
        _audit_table = _dynamodb.Table(config.AUDIT_TRAIL_TABLE)
        _conversations_table = _dynamodb.Table(config.CONVERSATIONS_TABLE)
    return _sessions_table, _audit_table, _conversations_table


def _serialize_value(value: Any) -> Any:
    """Convert Python types to DynamoDB-compatible values."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _ttl_days(days: int) -> int:
    """Calculate TTL epoch timestamp N days from now."""
    return int(time.time()) + (days * 86400)


def create_session(session: TriageSession) -> None:
    """Create a new triage session record."""
    item = json.loads(session.model_dump_json())
    item["ttl"] = _ttl_days(90)
    item = _serialize_value(item)
    _get_tables()[0].put_item(Item=item)


def get_session(session_id: str) -> Optional[dict]:
    """Get a session by ID. Returns raw DynamoDB item or None."""
    try:
        response = _get_tables()[0].get_item(Key={"sessionId": session_id})
        return response.get("Item")
    except ClientError:
        return None


def update_session_status(session_id: str, status: SessionStatus, **extra_fields) -> None:
    """Update session status and optional extra fields."""
    update_expr = "SET #status = :status, updatedAt = :now"
    expr_values: dict[str, Any] = {
        ":status": status.value,
        ":now": datetime.now(timezone.utc).isoformat(),
    }
    expr_names = {"#status": "status"}

    for key, value in extra_fields.items():
        update_expr += f", {key} = :{key}"
        expr_values[f":{key}"] = _serialize_value(value)

    _get_tables()[0].update_item(
        Key={"sessionId": session_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_values,
        ExpressionAttributeNames=expr_names,
    )


def update_session_field(session_id: str, field_name: str, value: Any) -> None:
    """Update a single field on a session record."""
    _get_tables()[0].update_item(
        Key={"sessionId": session_id},
        UpdateExpression=f"SET {field_name} = :val, updatedAt = :now",
        ExpressionAttributeValues={
            ":val": _serialize_value(value),
            ":now": datetime.now(timezone.utc).isoformat(),
        },
    )


def write_audit_entry(entry: AuditEntry) -> None:
    """Write an immutable audit trail entry. No TTL — retained permanently."""
    item = json.loads(entry.model_dump_json())
    item = _serialize_value(item)
    _get_tables()[1].put_item(Item=item)


def write_conversation_message(
    session_id: str,
    role: str,
    content: str,
    agent_name: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Append a message to the conversation history."""
    item = {
        "sessionId": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "content": content,
        "ttl": _ttl_days(90),
    }
    if agent_name:
        item["agentName"] = agent_name
    if metadata:
        item["metadata"] = metadata

    _get_tables()[2].put_item(Item=item)


def get_conversation(session_id: str) -> list[dict]:
    """Get all messages for a session, ordered by timestamp."""
    response = _get_tables()[2].query(
        KeyConditionExpression="sessionId = :sid",
        ExpressionAttributeValues={":sid": session_id},
        ScanIndexForward=True,
    )
    return response.get("Items", [])
