"""Portal REST API handler.

Handles all REST endpoints for the Patient Portal:
- POST /triage/start — create new triage session + start Step Functions
- GET /triage/status/{sessionId} — get triage status
- GET /triage/history — patient's triage history
- GET /appointments — upcoming appointments
- POST /consent — grant consent
- DELETE /consent/{type} — revoke consent
- GET /profile — patient profile + consent status
"""

from __future__ import annotations

import json
import os
import uuid
import base64
from datetime import datetime, timezone
from typing import Any

import boto3

# Config from environment
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "triage-sessions")
PATIENTS_TABLE = os.environ.get("PATIENTS_TABLE", "triage-patients")
APPOINTMENTS_TABLE = os.environ.get("APPOINTMENTS_TABLE", "triage-appointments")
TRIAGE_PIPELINE_ARN = os.environ.get("TRIAGE_PIPELINE_ARN", "")
REGION = os.environ.get("AWS_REGION", "us-west-2")

dynamodb = boto3.resource("dynamodb")
sfn_client = boto3.client("stepfunctions")
sessions_table = dynamodb.Table(SESSIONS_TABLE)
patients_table = dynamodb.Table(PATIENTS_TABLE)
appointments_table = dynamodb.Table(APPOINTMENTS_TABLE)


def _extract_sub_from_jwt(token: str) -> str | None:
    """Extract 'sub' claim from JWT without verification (MVP)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)
        return claims.get("sub") or claims.get("username")
    except Exception:
        return None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Main Lambda handler — routes by HTTP method + path."""
    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    path_params = event.get("pathParameters") or {}

    # Extract patient_id from JWT claims (set by Cognito authorizer)
    # If no authorizer, try extracting from Authorization header directly
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    patient_id = claims.get("sub")

    if not patient_id:
        # Fallback: decode JWT from Authorization header
        auth_header = (event.get("headers") or {}).get("Authorization", "")
        if auth_header.startswith("Bearer "):
            patient_id = _extract_sub_from_jwt(auth_header[7:])

    if not patient_id:
        patient_id = "anonymous"

    try:
        # Route to handler
        if path == "/triage/start" and http_method == "POST":
            return _start_triage(patient_id, event)
        elif path.startswith("/triage/status/") and http_method == "GET":
            session_id = path_params.get("sessionId", path.split("/")[-1])
            return _get_triage_status(session_id)
        elif path == "/triage/history" and http_method == "GET":
            return _get_triage_history(patient_id)
        elif path == "/appointments" and http_method == "GET":
            return _get_appointments(patient_id)
        elif path == "/appointments/reschedule" and http_method == "POST":
            return _reschedule_appointment(patient_id, event)
        elif path == "/consent" and http_method == "POST":
            return _grant_consent(patient_id, event)
        elif path.startswith("/consent/") and http_method == "DELETE":
            consent_type = path_params.get("type", path.split("/")[-1])
            return _revoke_consent(patient_id, consent_type)
        elif path == "/profile" and http_method == "GET":
            return _get_profile(patient_id)
        # --- Admin / Nurse endpoints ---
        elif path == "/admin/sessions" and http_method == "GET":
            return _admin_get_sessions(event)
        elif path.startswith("/admin/sessions/") and http_method == "GET":
            # Check if it's /admin/sessions/{id}/appointments
            parts = path.split("/")
            if len(parts) == 5 and parts[4] == "appointments":
                session_id = parts[3]
                return _admin_get_session_appointments(session_id)
            else:
                session_id = path_params.get("sessionId", parts[3] if len(parts) > 3 else path.split("/")[-1])
                return _admin_get_session_detail(session_id)
        elif path == "/admin/override" and http_method == "POST":
            return _admin_override_urgency(patient_id, event)
        elif path == "/admin/audit" and http_method == "GET":
            return _admin_get_audit_log()
        elif path == "/admin/users" and http_method == "GET":
            return _admin_get_users()
        elif path == "/admin/roles" and http_method == "GET":
            return _admin_get_roles()
        elif path == "/admin/roles" and http_method == "POST":
            return _admin_create_role(event)
        elif path.startswith("/admin/roles/") and http_method == "DELETE":
            role_name = path.split("/")[-1]
            return _admin_delete_role(role_name)
        else:
            return _response(404, {"error": "Not found", "path": path})

    except Exception as e:
        print(f"Error handling {http_method} {path}: {e}")
        return _response(500, {"error": "Internal server error"})


def _start_triage(patient_id: str, event: dict) -> dict:
    """Create a new triage session and start the Step Functions pipeline."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Parse body for optional clinic_id
    body = json.loads(event.get("body", "{}") or "{}")
    clinic_id = body.get("clinic_id", "clinic-01")

    # Create session record
    sessions_table.put_item(Item={
        "sessionId": session_id,
        "patientId": patient_id,
        "status": "IN_PROGRESS",
        "clinicId": clinic_id,
        "startedAt": now,
        "updatedAt": now,
    })

    # Start Step Functions execution
    if TRIAGE_PIPELINE_ARN:
        try:
            sfn_client.start_execution(
                stateMachineArn=TRIAGE_PIPELINE_ARN,
                name=f"triage-{session_id[:8]}-{int(datetime.now().timestamp())}",
                input=json.dumps({
                    "session_id": session_id,
                    "patient_id": patient_id,
                    "patient_clinic_id": clinic_id,
                    "connection_id": None,  # WebSocket connected separately
                }),
            )
        except Exception as e:
            print(f"Failed to start Step Functions: {e}")
            # Session still created — can be resumed

    return _response(200, {
        "session_id": session_id,
        "status": "IN_PROGRESS",
        "message": "Triage session started",
    })


def _get_triage_status(session_id: str) -> dict:
    """Get current status of a triage session."""
    response = sessions_table.get_item(Key={"sessionId": session_id})
    item = response.get("Item")

    if not item:
        return _response(404, {"error": "Session not found"})

    # Extract routing decision safely
    routing = item.get("routingDecision", {})
    if isinstance(routing, str):
        try:
            routing = json.loads(routing)
        except:
            routing = {}

    # Extract urgency result
    urgency_result = item.get("urgencyResult", {})
    if isinstance(urgency_result, str):
        try:
            urgency_result = json.loads(urgency_result)
        except:
            urgency_result = {}

    # Extract structured symptoms for complaint
    symptoms = item.get("structuredSymptoms", {})
    if isinstance(symptoms, str):
        try:
            symptoms = json.loads(symptoms)
        except:
            symptoms = {}

    # Priority chain: issueSummary > structured primary_complaint > firstPatientMessage
    primary_complaint = item.get("issueSummary")
    if not primary_complaint:
        if isinstance(symptoms, dict):
            pc = symptoms.get("primary_complaint", "")
            if isinstance(pc, dict):
                primary_complaint = pc.get("text")
            elif isinstance(pc, str) and pc:
                primary_complaint = pc
    if not primary_complaint:
        primary_complaint = item.get("firstPatientMessage")

    # Build appointment from appointments table
    appointment = None
    try:
        appt_response = appointments_table.query(
            IndexName="sessionId-index",
            KeyConditionExpression="sessionId = :sid",
            ExpressionAttributeValues={":sid": session_id},
            Limit=1,
        )
        appt_items = appt_response.get("Items", [])
        if appt_items:
            a = appt_items[0]
            appointment = {
                "department": a.get("department"),
                "specialistName": a.get("specialistName"),
                "scheduledAt": a.get("scheduledAt"),
                "clinicName": a.get("clinicName"),
                "durationMinutes": a.get("durationMinutes", 30),
                "preparationNotes": a.get("preparationNotes"),
            }
    except Exception:
        # Index may not exist, try from routing decision
        pass

    return _response(200, {
        "session_id": item.get("sessionId"),
        "status": item.get("status"),
        "urgency_level": item.get("urgencyLevel"),
        "department": routing.get("department") if isinstance(routing, dict) else None,
        "routing_reasoning": routing.get("reasoning") if isinstance(routing, dict) else None,
        "urgency_reasoning": urgency_result.get("reasoning") if isinstance(urgency_result, dict) else None,
        "urgency_confidence": urgency_result.get("confidence") if isinstance(urgency_result, dict) else None,
        "recommended_timeframe": urgency_result.get("recommended_timeframe") if isinstance(urgency_result, dict) else None,
        "primary_complaint": primary_complaint,
        "patient_summary": item.get("patientSummary"),
        "appointment": appointment,
        "started_at": item.get("startedAt"),
        "completed_at": item.get("completedAt"),
    })


def _get_triage_history(patient_id: str) -> dict:
    """Get patient's triage session history."""
    response = sessions_table.query(
        IndexName="patientId-startedAt-index",
        KeyConditionExpression="patientId = :pid",
        ExpressionAttributeValues={":pid": patient_id},
        ScanIndexForward=False,  # Most recent first
        Limit=20,
    )

    items = response.get("Items", [])
    history = []
    for item in items:
        # Skip sessions with no human input
        has_input = item.get("issueSummary") or item.get("firstPatientMessage")
        if not has_input:
            # Check if conversationHistory has any patient messages
            conv = item.get("conversationHistory", [])
            has_input = any(m.get("role") == "patient" for m in conv) if isinstance(conv, list) else False
        if not has_input:
            continue

        # Handle structuredSymptoms being either a dict or string
        symptoms = item.get("structuredSymptoms", {})
        if isinstance(symptoms, str):
            try:
                symptoms = json.loads(symptoms)
            except:
                symptoms = {}

        # Priority: issueSummary > structured primary_complaint > firstPatientMessage
        primary = item.get("issueSummary")
        if not primary:
            if isinstance(symptoms, dict):
                pc = symptoms.get("primary_complaint", "")
                if isinstance(pc, dict):
                    primary = pc.get("text") or None
                elif isinstance(pc, str) and pc:
                    primary = pc
        if not primary:
            primary = item.get("firstPatientMessage") or None
        if not primary:
            primary = "Triage session"

        history.append({
            "session_id": item.get("sessionId"),
            "primary_complaint": primary,
            "urgency_level": item.get("urgencyLevel"),
            "status": item.get("status"),
            "department": item.get("routingDecision", {}).get("department") if isinstance(item.get("routingDecision"), dict) else None,
            "started_at": item.get("startedAt"),
            "completed_at": item.get("completedAt"),
        })

    return _response(200, history)


def _get_appointments(patient_id: str) -> dict:
    """Get patient's appointments."""
    response = appointments_table.query(
        KeyConditionExpression="patientId = :pid",
        ExpressionAttributeValues={":pid": patient_id},
    )

    items = response.get("Items", [])
    return _response(200, items)


def _reschedule_appointment(patient_id: str, event: dict) -> dict:
    """Reschedule an existing appointment to a new date/time."""
    body = json.loads(event.get("body", "{}") or "{}")
    appointment_id = body.get("appointmentId")
    new_datetime = body.get("newDateTime")

    if not appointment_id or not new_datetime:
        return _response(400, {"error": "appointmentId and newDateTime are required"})

    # Validate the new datetime format
    try:
        from datetime import datetime as dt
        parsed_dt = dt.fromisoformat(new_datetime.replace("Z", "+00:00"))
        # Ensure new time is in the future
        if parsed_dt <= datetime.now(timezone.utc):
            return _response(400, {"error": "New appointment time must be in the future"})
    except (ValueError, TypeError):
        return _response(400, {"error": "Invalid datetime format. Use ISO 8601 (e.g. 2026-07-15T10:00:00Z)"})

    # Verify the appointment belongs to this patient
    response = appointments_table.get_item(
        Key={"patientId": patient_id, "appointmentId": appointment_id}
    )
    item = response.get("Item")

    if not item:
        return _response(404, {"error": "Appointment not found"})

    if item.get("status") == "CANCELLED":
        return _response(400, {"error": "Cannot reschedule a cancelled appointment"})

    if item.get("status") == "COMPLETED":
        return _response(400, {"error": "Cannot reschedule a completed appointment"})

    now = datetime.now(timezone.utc).isoformat()
    original_time = item.get("scheduledAt", "")

    # Update the appointment with new time
    appointments_table.update_item(
        Key={"patientId": patient_id, "appointmentId": appointment_id},
        UpdateExpression="SET scheduledAt = :new_time, #s = :status, previousScheduledAt = :prev, rescheduledAt = :now, rescheduledBy = :by",
        ExpressionAttributeValues={
            ":new_time": new_datetime,
            ":status": "SCHEDULED",
            ":prev": original_time,
            ":now": now,
            ":by": "patient",
        },
        ExpressionAttributeNames={"#s": "status"},
    )

    return _response(200, {
        "message": "Appointment rescheduled successfully",
        "appointmentId": appointment_id,
        "previousTime": original_time,
        "newTime": new_datetime,
    })


def _grant_consent(patient_id: str, event: dict) -> dict:
    """Record consent grants."""
    body = json.loads(event.get("body", "{}") or "{}")
    consent_types = body.get("consent_types", [])
    now = datetime.now(timezone.utc).isoformat()

    consent_status = {}
    for ct in consent_types:
        consent_status[ct] = {"granted": True, "grantedAt": now, "version": "1.0"}

    patients_table.update_item(
        Key={"patientId": patient_id},
        UpdateExpression="SET consentStatus = :cs, updatedAt = :now",
        ExpressionAttributeValues={
            ":cs": consent_status,
            ":now": now,
        },
    )

    return _response(200, {"message": "Consent granted", "types": consent_types})


def _revoke_consent(patient_id: str, consent_type: str) -> dict:
    """Revoke a specific consent type."""
    now = datetime.now(timezone.utc).isoformat()

    patients_table.update_item(
        Key={"patientId": patient_id},
        UpdateExpression=f"REMOVE consentStatus.{consent_type} SET updatedAt = :now",
        ExpressionAttributeValues={":now": now},
    )

    return _response(200, {"message": f"Consent '{consent_type}' revoked"})


def _get_profile(patient_id: str) -> dict:
    """Get patient profile including consent status. Creates record if first visit."""
    response = patients_table.get_item(Key={"patientId": patient_id})
    item = response.get("Item")

    if not item:
        # First visit — create patient record
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "patientId": patient_id,
            "consentStatus": {},
            "createdAt": now,
            "updatedAt": now,
        }
        patients_table.put_item(Item=item)

    consent = item.get("consentStatus", {})
    has_consent = all(
        consent.get(ct, {}).get("granted", False)
        for ct in ["dataProcessing", "aiTriage", "dataSharing"]
    )

    return _response(200, {
        "patientId": patient_id,
        "consentStatus": consent,
        "hasConsent": has_consent,
    })


# -------------------------------------------------------
# ADMIN / NURSE ENDPOINTS
# -------------------------------------------------------

def _admin_get_sessions(event: dict) -> dict:
    """Get all triage sessions for the nurse queue. Returns recent sessions across all patients."""
    # Scan sessions table for recent sessions (last 50)
    response = sessions_table.scan(Limit=50)
    items = response.get("Items", [])

    # Sort by startedAt descending
    items.sort(key=lambda x: x.get("startedAt", ""), reverse=True)

    sessions = []
    for item in items:
        # Extract complaint
        complaint = item.get("issueSummary") or item.get("firstPatientMessage") or "No complaint recorded"

        # Extract urgency result for confidence
        urgency_result = item.get("urgencyResult", {})
        if isinstance(urgency_result, str):
            try:
                urgency_result = json.loads(urgency_result)
            except:
                urgency_result = {}

        sessions.append({
            "session_id": item.get("sessionId"),
            "patient_id": item.get("patientId", "anonymous"),
            "status": item.get("status"),
            "urgency_level": item.get("urgencyLevel"),
            "confidence": urgency_result.get("confidence") if isinstance(urgency_result, dict) else None,
            "primary_complaint": complaint,
            "department": item.get("routingDecision", {}).get("department") if isinstance(item.get("routingDecision"), dict) else None,
            "started_at": item.get("startedAt"),
            "completed_at": item.get("completedAt"),
            "has_override": bool(item.get("nurseOverride")),
        })

    return _response(200, sessions)


def _admin_get_session_detail(session_id: str) -> dict:
    """Get full session detail for nurse/physician review."""
    response = sessions_table.get_item(Key={"sessionId": session_id})
    item = response.get("Item")

    if not item:
        return _response(404, {"error": "Session not found"})

    # Parse complex fields
    symptoms = item.get("structuredSymptoms", {})
    if isinstance(symptoms, str):
        try:
            symptoms = json.loads(symptoms)
        except:
            symptoms = {}

    urgency_result = item.get("urgencyResult", {})
    if isinstance(urgency_result, str):
        try:
            urgency_result = json.loads(urgency_result)
        except:
            urgency_result = {}

    routing = item.get("routingDecision", {})
    if isinstance(routing, str):
        try:
            routing = json.loads(routing)
        except:
            routing = {}

    soap_note = item.get("soapNote", "")

    # Conversation history
    conversation = item.get("conversationHistory", [])

    return _response(200, {
        "session_id": item.get("sessionId"),
        "patient_id": item.get("patientId"),
        "status": item.get("status"),
        "urgency_level": item.get("urgencyLevel"),
        "started_at": item.get("startedAt"),
        "completed_at": item.get("completedAt"),
        "primary_complaint": item.get("issueSummary") or item.get("firstPatientMessage"),
        "structured_symptoms": symptoms,
        "urgency_result": urgency_result,
        "routing_decision": routing,
        "soap_note": soap_note,
        "patient_summary": item.get("patientSummary"),
        "conversation_history": conversation,
        "nurse_override": item.get("nurseOverride"),
    })


def _admin_override_urgency(actor_id: str, event: dict) -> dict:
    """Nurse overrides AI-assigned urgency level.
    Triggers downstream actions: email alert, appointment booking, audit trail.
    """
    body = json.loads(event.get("body", "{}") or "{}")
    session_id = body.get("session_id")
    new_urgency = body.get("urgency_level")
    reason = body.get("reason", "")

    if not session_id or not new_urgency:
        return _response(400, {"error": "session_id and urgency_level required"})

    if new_urgency not in ("EMERGENCY", "URGENT", "STANDARD", "ROUTINE"):
        return _response(400, {"error": "Invalid urgency_level"})

    # Get current session
    response = sessions_table.get_item(Key={"sessionId": session_id})
    item = response.get("Item")
    if not item:
        return _response(404, {"error": "Session not found"})

    original_urgency = item.get("urgencyLevel", "UNKNOWN")
    patient_id = item.get("patientId", "anonymous")
    complaint = item.get("issueSummary") or item.get("firstPatientMessage") or "Unknown"
    department = None
    if isinstance(item.get("routingDecision"), dict):
        department = item["routingDecision"].get("department")

    now = datetime.now(timezone.utc).isoformat()

    # Store override record
    override_record = {
        "original_urgency": original_urgency,
        "override_urgency": new_urgency,
        "actor_id": actor_id,
        "reason": reason,
        "overridden_at": now,
    }

    # Determine new status
    new_status = "ESCALATED" if new_urgency == "EMERGENCY" else item.get("status", "COMPLETED")

    # Update session with override + status
    sessions_table.update_item(
        Key={"sessionId": session_id},
        UpdateExpression="SET urgencyLevel = :new_urgency, nurseOverride = :override, #s = :status, updatedAt = :now",
        ExpressionAttributeValues={
            ":new_urgency": new_urgency,
            ":override": override_record,
            ":status": new_status,
            ":now": now,
        },
        ExpressionAttributeNames={"#s": "status"},
    )

    actions_taken = []

    # --- ACTION 1: Send SNS alert for EMERGENCY/URGENT ---
    if new_urgency in ("EMERGENCY", "URGENT"):
        try:
            sns_client = boto3.client("sns")
            notification_body = (
                f"NURSE OVERRIDE — {new_urgency}\n"
                f"{'='*40}\n\n"
                f"Original AI Assessment: {original_urgency}\n"
                f"Overridden to: {new_urgency}\n"
                f"Reason: {reason}\n"
                f"Override by: {actor_id}\n\n"
                f"Patient Complaint: {complaint}\n"
                f"Department: {department or 'Pending re-route'}\n"
                f"Session ID: {session_id}\n"
                f"Time: {now}\n"
            )
            sns_client.publish(
                TopicArn="arn:aws:sns:us-west-2:294680528184:triage-emergency-escalation",
                Subject=f"NURSE OVERRIDE {new_urgency}: {complaint[:60]}",
                Message=notification_body,
            )
            actions_taken.append("email_alert_sent")
        except Exception as e:
            print(f"SNS notification error on override: {e}")
            actions_taken.append("email_alert_failed")

    # --- ACTION 2: Book appointment if none exists ---
    try:
        appt_check = appointments_table.query(
            KeyConditionExpression="patientId = :pid",
            FilterExpression="sessionId = :sid",
            ExpressionAttributeValues={":pid": patient_id, ":sid": session_id},
            Limit=1,
        )
        existing_appts = appt_check.get("Items", [])

        if not existing_appts and department:
            # Book an appointment based on the routed department
            appt_id = str(uuid.uuid4())
            # Find available slot
            avail_response = appointments_table.query(
                KeyConditionExpression="patientId = :avail",
                FilterExpression="department = :dept AND #s = :status",
                ExpressionAttributeValues={
                    ":avail": "AVAILABLE_SLOT",
                    ":dept": department,
                    ":status": "AVAILABLE",
                },
                ExpressionAttributeNames={"#s": "status"},
                Limit=1,
            )
            avail_slots = avail_response.get("Items", [])

            if avail_slots:
                slot = avail_slots[0]
                # Delete available slot
                appointments_table.delete_item(Key={
                    "patientId": "AVAILABLE_SLOT",
                    "appointmentId": slot["appointmentId"],
                })
                # Book under patient
                appointments_table.put_item(Item={
                    "patientId": patient_id,
                    "appointmentId": slot["appointmentId"],
                    "sessionId": session_id,
                    "department": slot["department"],
                    "specialistName": slot.get("specialistName", ""),
                    "clinicId": slot.get("clinicId", ""),
                    "clinicName": slot.get("clinicName", ""),
                    "scheduledAt": slot.get("scheduledAt", ""),
                    "status": "SCHEDULED",
                    "durationMinutes": slot.get("durationMinutes", 30),
                    "bookedAt": now,
                    "bookedBy": f"nurse-override:{actor_id}",
                })
                actions_taken.append("appointment_booked")
            else:
                actions_taken.append("no_slots_available")
        elif existing_appts:
            actions_taken.append("appointment_already_exists")
        else:
            actions_taken.append("no_department_for_booking")
    except Exception as e:
        print(f"Appointment booking on override error: {e}")
        actions_taken.append(f"appointment_error")

    # --- ACTION 3: Write audit trail ---
    try:
        audit_table = dynamodb.Table("triage-audit-trail")
        audit_table.put_item(Item={
            "patientId": patient_id,
            "timestamp": now,
            "eventType": "NURSE_OVERRIDE",
            "sessionId": session_id,
            "actorType": "NURSE",
            "actorId": actor_id,
            "details": {
                "original_urgency": original_urgency,
                "new_urgency": new_urgency,
                "reason": reason,
                "actions_taken": actions_taken,
            },
        })
        actions_taken.append("audit_logged")
    except Exception as e:
        print(f"Audit trail write error: {e}")

    return _response(200, {
        "message": "Urgency overridden",
        "session_id": session_id,
        "original": original_urgency,
        "new": new_urgency,
        "reason": reason,
        "status": new_status,
        "actions_taken": actions_taken,
    })


def _admin_get_audit_log() -> dict:
    """Get recent audit trail entries for admin review."""
    audit_table = dynamodb.Table("triage-audit-trail")
    response = audit_table.scan(Limit=50)
    items = response.get("Items", [])
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    entries = []
    for item in items:
        entries.append({
            "patient_id": item.get("patientId", ""),
            "timestamp": item.get("timestamp", ""),
            "event_type": item.get("eventType", ""),
            "session_id": item.get("sessionId", ""),
            "actor_type": item.get("actorType", ""),
            "actor_id": item.get("actorId", ""),
            "details": item.get("details", {}),
        })

    return _response(200, entries)


def _admin_get_users() -> dict:
    """Get Cognito user pool users and their groups."""
    cognito_client = boto3.client("cognito-idp")
    user_pool_id = os.environ.get("USER_POOL_ID", "us-west-2_fT2kDGhLX")

    try:
        users_response = cognito_client.list_users(UserPoolId=user_pool_id, Limit=50)
        users = []
        for user in users_response.get("Users", []):
            # Get groups for each user
            groups_response = cognito_client.admin_list_groups_for_user(
                Username=user["Username"],
                UserPoolId=user_pool_id,
            )
            groups = [g["GroupName"] for g in groups_response.get("Groups", [])]

            # Extract attributes
            attrs = {a["Name"]: a["Value"] for a in user.get("Attributes", [])}

            users.append({
                "username": user["Username"],
                "email": attrs.get("email", ""),
                "status": user.get("UserStatus", ""),
                "enabled": user.get("Enabled", False),
                "groups": groups,
                "created_at": user.get("UserCreateDate", "").isoformat() if user.get("UserCreateDate") else None,
                "last_modified": user.get("UserLastModifiedDate", "").isoformat() if user.get("UserLastModifiedDate") else None,
            })

        return _response(200, users)
    except Exception as e:
        print(f"Error listing users: {e}")
        return _response(500, {"error": "Failed to list users"})


def _admin_get_session_appointments(session_id: str) -> dict:
    """Get appointments associated with a specific session (typically after nurse override)."""
    try:
        # First get the session to find the patient_id
        session_response = sessions_table.get_item(Key={"sessionId": session_id})
        session_item = session_response.get("Item")
        if not session_item:
            return _response(404, {"error": "Session not found"})

        patient_id = session_item.get("patientId", "anonymous")

        # Query appointments for this patient, filtered by session
        appt_response = appointments_table.query(
            KeyConditionExpression="patientId = :pid",
            FilterExpression="sessionId = :sid",
            ExpressionAttributeValues={":pid": patient_id, ":sid": session_id},
        )
        items = appt_response.get("Items", [])

        appointments = []
        for item in items:
            appointments.append({
                "appointmentId": item.get("appointmentId"),
                "patientId": item.get("patientId"),
                "sessionId": item.get("sessionId"),
                "department": item.get("department", ""),
                "specialistName": item.get("specialistName", ""),
                "clinicId": item.get("clinicId", ""),
                "clinicName": item.get("clinicName", ""),
                "scheduledAt": item.get("scheduledAt", ""),
                "status": item.get("status", ""),
                "durationMinutes": item.get("durationMinutes"),
                "bookedAt": item.get("bookedAt"),
                "bookedBy": item.get("bookedBy"),
            })

        return _response(200, appointments)
    except Exception as e:
        print(f"Error fetching session appointments: {e}")
        return _response(500, {"error": "Failed to fetch appointments"})


def _admin_get_roles() -> dict:
    """List all Cognito groups (roles) in the user pool."""
    cognito_client = boto3.client("cognito-idp")
    user_pool_id = os.environ.get("USER_POOL_ID", "us-west-2_fT2kDGhLX")

    try:
        response = cognito_client.list_groups(UserPoolId=user_pool_id, Limit=60)
        groups = []
        for group in response.get("Groups", []):
            groups.append({
                "name": group.get("GroupName"),
                "description": group.get("Description", ""),
                "precedence": group.get("Precedence"),
                "created_at": group.get("CreationDate", "").isoformat() if group.get("CreationDate") else None,
                "last_modified": group.get("LastModifiedDate", "").isoformat() if group.get("LastModifiedDate") else None,
            })
        return _response(200, groups)
    except Exception as e:
        print(f"Error listing roles: {e}")
        return _response(500, {"error": "Failed to list roles"})


def _admin_create_role(event: dict) -> dict:
    """Create a new Cognito group (role)."""
    cognito_client = boto3.client("cognito-idp")
    user_pool_id = os.environ.get("USER_POOL_ID", "us-west-2_fT2kDGhLX")

    body = json.loads(event.get("body", "{}") or "{}")
    group_name = body.get("name", "").strip().lower()
    description = body.get("description", "").strip()

    if not group_name:
        return _response(400, {"error": "Role name is required"})

    # Validate group name (alphanumeric + hyphens, no spaces)
    import re
    if not re.match(r'^[a-z][a-z0-9\-]{1,127}$', group_name):
        return _response(400, {"error": "Role name must start with a letter, contain only lowercase letters, numbers, and hyphens, and be 2-128 characters"})

    try:
        cognito_client.create_group(
            GroupName=group_name,
            UserPoolId=user_pool_id,
            Description=description or f"Role: {group_name}",
        )
        return _response(201, {"message": f"Role '{group_name}' created successfully", "name": group_name})
    except cognito_client.exceptions.GroupExistsException:
        return _response(409, {"error": f"Role '{group_name}' already exists"})
    except Exception as e:
        print(f"Error creating role: {e}")
        return _response(500, {"error": "Failed to create role"})


def _admin_delete_role(role_name: str) -> dict:
    """Delete a Cognito group (role). Refuses to delete core system roles."""
    cognito_client = boto3.client("cognito-idp")
    user_pool_id = os.environ.get("USER_POOL_ID", "us-west-2_fT2kDGhLX")

    # Protect core roles from deletion
    protected_roles = {"admin", "nurse", "physician", "patient"}
    if role_name.lower() in protected_roles:
        return _response(403, {"error": f"Cannot delete protected system role '{role_name}'"})

    try:
        cognito_client.delete_group(
            GroupName=role_name,
            UserPoolId=user_pool_id,
        )
        return _response(200, {"message": f"Role '{role_name}' deleted successfully"})
    except cognito_client.exceptions.ResourceNotFoundException:
        return _response(404, {"error": f"Role '{role_name}' not found"})
    except Exception as e:
        print(f"Error deleting role: {e}")
        return _response(500, {"error": "Failed to delete role"})


def _response(status_code: int, body: Any) -> dict:
    """Build API Gateway proxy response with CORS headers."""
    from decimal import Decimal

    class DecimalEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, Decimal):
                return float(o)
            return super().default(o)

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "https://d12oqv6vi0inhw.cloudfront.net",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=str, cls=DecimalEncoder),
    }
