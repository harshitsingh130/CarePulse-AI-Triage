"""WebSocket $connect handler.

Extracts patient_id from JWT token, stores connection record
with session_id and patient_id. Also upserts the patient record.
"""

import os
import json
import base64
import boto3
from datetime import datetime, timezone

CONNECTIONS_TABLE = os.environ.get("CONNECTIONS_TABLE", "triage-connections")
PATIENTS_TABLE = os.environ.get("PATIENTS_TABLE", "triage-patients")
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "triage-sessions")

dynamodb = boto3.resource("dynamodb")
connections_table = dynamodb.Table(CONNECTIONS_TABLE)
patients_table = dynamodb.Table(PATIENTS_TABLE)
sessions_table = dynamodb.Table(SESSIONS_TABLE)


def extract_patient_id_from_jwt(token):
    """Extract the 'sub' (patient ID) from a JWT without full verification.
    For MVP — in production, validate signature with Cognito public keys.
    """
    try:
        # JWT is header.payload.signature — decode the payload
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # Add padding for base64
        payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)
        return claims.get("sub") or claims.get("username")
    except Exception as e:
        print(f"JWT decode error: {e}")
        return None


def upsert_patient(patient_id):
    """Create or update patient record on connection."""
    now = datetime.now(timezone.utc).isoformat()
    patients_table.update_item(
        Key={"patientId": patient_id},
        UpdateExpression="SET lastSeenAt = :now, updatedAt = :now",
        ExpressionAttributeValues={":now": now},
    )


def handler(event, context):
    """Handle WebSocket $connect event."""
    connection_id = event["requestContext"]["connectionId"]

    # Extract token and session_id from query string
    qs = event.get("queryStringParameters") or {}
    token = qs.get("token", "")
    session_id = qs.get("session_id", "")

    # Extract patient_id from JWT
    patient_id = extract_patient_id_from_jwt(token) if token else None
    if not patient_id:
        patient_id = "anonymous"

    print(f"WebSocket connect: conn={connection_id}, session={session_id}, patient={patient_id}")

    # Store connection mapping (with patient_id for downstream use)
    connections_table.put_item(Item={
        "connectionId": connection_id,
        "sessionId": session_id,
        "patientId": patient_id,
        "connectedAt": datetime.now(timezone.utc).isoformat(),
    })

    # Upsert patient record
    if patient_id and patient_id != "anonymous":
        try:
            upsert_patient(patient_id)
        except Exception as e:
            print(f"Patient upsert error: {e}")

    # Update session with patient_id if session exists
    if session_id and patient_id != "anonymous":
        try:
            sessions_table.update_item(
                Key={"sessionId": session_id},
                UpdateExpression="SET patientId = :pid, connectionId = :cid, updatedAt = :now",
                ExpressionAttributeValues={
                    ":pid": patient_id,
                    ":cid": connection_id,
                    ":now": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception as e:
            print(f"Session update error: {e}")

    return {"statusCode": 200, "body": "Connected"}
