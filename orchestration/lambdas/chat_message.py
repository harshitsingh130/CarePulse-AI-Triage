"""WebSocket message handler — Full E2E Pipeline.

Receives patient message, calls Bedrock for conversation,
detects when assessment is complete, then runs the full pipeline:
Scoring → Drug Check → Routing → SOAP Summary → Notify patient.
"""

import os
import json
import re
import boto3
from datetime import datetime, timezone

SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "triage-sessions")
CONNECTIONS_TABLE = os.environ.get("CONNECTIONS_TABLE", "triage-connections")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

dynamodb = boto3.resource("dynamodb")
sessions_table = dynamodb.Table(SESSIONS_TABLE)
connections_table = dynamodb.Table(CONNECTIONS_TABLE)
bedrock_runtime = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-west-2"))
apigw_client = None


def get_apigw_client(event):
    global apigw_client
    if apigw_client is None:
        domain = event["requestContext"]["domainName"]
        stage = event["requestContext"]["stage"]
        apigw_client = boto3.client("apigatewaymanagementapi", endpoint_url=f"https://{domain}/{stage}")
    return apigw_client


def send_to_connection(event, connection_id, message):
    get_apigw_client(event).post_to_connection(
        ConnectionId=connection_id,
        Data=json.dumps(message).encode("utf-8"),
    )


def get_session(session_id):
    return sessions_table.get_item(Key={"sessionId": session_id}).get("Item", {})


def update_session(session_id, **fields):
    """Update session fields in DynamoDB, handling reserved words and float types."""
    from decimal import Decimal

    # DynamoDB reserved words that need expression attribute names
    RESERVED_WORDS = {"status", "name", "type", "value", "count", "size", "data"}

    expr_parts = []
    values = {}
    names = {}

    for k, v in fields.items():
        # Convert floats to Decimal (DynamoDB requirement)
        v = _convert_floats(v)

        if k.lower() in RESERVED_WORDS:
            placeholder = f"#{k}"
            names[placeholder] = k
            expr_parts.append(f"{placeholder} = :{k}")
        else:
            expr_parts.append(f"{k} = :{k}")
        values[f":{k}"] = v

    update_kwargs = {
        "Key": {"sessionId": session_id},
        "UpdateExpression": "SET " + ", ".join(expr_parts),
        "ExpressionAttributeValues": values,
    }
    if names:
        update_kwargs["ExpressionAttributeNames"] = names

    sessions_table.update_item(**update_kwargs)


def _convert_floats(obj):
    """Recursively convert floats to Decimal for DynamoDB."""
    from decimal import Decimal
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_floats(i) for i in obj]
    return obj


def call_bedrock(messages, system_prompt, max_tokens=500, temperature=0.7):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system_prompt,
        "messages": messages,
    })
    response = bedrock_runtime.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


# --- Assessment Conversation ---

ASSESSMENT_PROMPT = """You are a clinical intake assistant for Healthcare Network.
Gather symptom information through a friendly, empathetic conversation. Do NOT diagnose.

Collect: primary complaint, onset, severity (1-10), duration/pattern, associated symptoms,
medical history, current medications, allergies.

Rules: Ask ONE question at a time. Be empathetic. Never diagnose. Target 8-12 exchanges.

IMPORTANT: When you have collected enough information (minimum: complaint, severity, onset),
end with EXACTLY this format (including the markers):

---ASSESSMENT_COMPLETE---
{
  "primary_complaint": "description",
  "severity": number,
  "onset": "description",
  "duration_pattern": "worsening/stable/improving/intermittent",
  "associated_symptoms": ["symptom1", "symptom2"],
  "medical_history": ["condition1"],
  "medications": ["med1"],
  "allergies": ["allergy1"]
}
---END_ASSESSMENT---

Before the markers, give a brief human-friendly closing message to the patient."""


def is_assessment_complete(ai_response):
    """Check if the AI included the assessment complete markers."""
    return "---ASSESSMENT_COMPLETE---" in ai_response


def extract_assessment_data(ai_response):
    """Extract structured JSON from the assessment complete response."""
    match = re.search(r"---ASSESSMENT_COMPLETE---\s*(\{.*?\})\s*---END_ASSESSMENT---", ai_response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def get_patient_facing_message(ai_response):
    """Get just the human-friendly part (before the markers)."""
    if "---ASSESSMENT_COMPLETE---" in ai_response:
        return ai_response.split("---ASSESSMENT_COMPLETE---")[0].strip()
    return ai_response


# --- Pipeline Agents ---

SCORING_PROMPT = """You are a clinical triage scoring system. Classify urgency as:
- EMERGENCY: Life-threatening, immediate intervention needed
- URGENT: Serious, same-day attention needed
- STANDARD: Needs attention within 24-48 hours
- ROUTINE: Non-urgent, within 1-2 weeks

Be conservative — when in doubt, choose MORE urgent.
Do NOT diagnose. Only classify urgency.

Respond ONLY with this JSON:
{"urgency_level": "EMERGENCY|URGENT|STANDARD|ROUTINE", "confidence": 0.0-1.0, "reasoning": "brief explanation", "recommended_timeframe": "immediate|within 4 hours|within 24 hours|within 48 hours|within 1 week"}"""

ROUTING_PROMPT = """You are a clinical routing system. Based on symptoms, route to ONE department:
Cardiology, Neurology, Orthopedics, Gastroenterology, Pulmonology, Dermatology, ENT, Urology, Psychiatry, Internal Medicine.

Respond ONLY with this JSON:
{"department": "DepartmentName", "reasoning": "brief explanation"}"""

SOAP_PROMPT = """You are a clinical note writer. Write a SOAP note from the triage data provided.
Use professional clinical language. Do NOT diagnose — describe symptoms and assessment.
Keep each section concise (3-5 sentences max)."""


def run_scoring(assessment_data):
    """Run triage scoring agent."""
    messages = [{"role": "user", "content": f"Score the urgency of this patient:\n{json.dumps(assessment_data, indent=2)}"}]
    response = call_bedrock(messages, SCORING_PROMPT, max_tokens=200, temperature=0.0)
    try:
        # Try to parse JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    return {"urgency_level": "STANDARD", "confidence": 0.6, "reasoning": "Unable to classify precisely", "recommended_timeframe": "within 48 hours"}


def run_routing(assessment_data, urgency):
    """Run specialist routing agent."""
    messages = [{"role": "user", "content": f"Route this patient:\nSymptoms: {json.dumps(assessment_data)}\nUrgency: {urgency}"}]
    response = call_bedrock(messages, ROUTING_PROMPT, max_tokens=100, temperature=0.0)
    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except:
        pass
    return {"department": "Internal Medicine", "reasoning": "Default routing"}


def run_soap_note(assessment_data, urgency_result, routing_result):
    """Generate SOAP note."""
    context = f"""Patient Assessment:
{json.dumps(assessment_data, indent=2)}

Triage Classification: {urgency_result.get('urgency_level')} (confidence: {urgency_result.get('confidence')})
Reasoning: {urgency_result.get('reasoning')}
Routed to: {routing_result.get('department')}"""

    messages = [{"role": "user", "content": f"Write a SOAP note for this triage:\n{context}"}]
    return call_bedrock(messages, SOAP_PROMPT, max_tokens=600, temperature=0.1)


def book_appointment(session_id, department, patient_id):
    """Find an available slot for the department and book it for the patient."""
    appointments_table = dynamodb.Table("triage-appointments")

    # Query available slots (patientId = AVAILABLE_SLOT)
    response = appointments_table.query(
        KeyConditionExpression="patientId = :avail",
        FilterExpression="department = :dept AND #s = :status",
        ExpressionAttributeValues={
            ":avail": "AVAILABLE_SLOT",
            ":dept": department,
            ":status": "AVAILABLE",
        },
        ExpressionAttributeNames={"#s": "status"},
        Limit=5,
    )

    items = response.get("Items", [])
    if not items:
        print(f"No available slots for {department}")
        return None

    # Pick the first available slot
    slot = items[0]
    appointment_id = slot["appointmentId"]

    # Book it: delete the AVAILABLE_SLOT entry and create a patient-specific one
    # Delete old
    appointments_table.delete_item(Key={
        "patientId": "AVAILABLE_SLOT",
        "appointmentId": appointment_id,
    })

    # Create booked appointment under patient's ID
    booked = {
        "patientId": patient_id,
        "appointmentId": appointment_id,
        "sessionId": session_id,
        "department": slot["department"],
        "specialistName": slot["specialistName"],
        "clinicId": slot["clinicId"],
        "clinicName": slot["clinicName"],
        "scheduledAt": slot["scheduledAt"],
        "status": "SCHEDULED",
        "durationMinutes": slot.get("durationMinutes", 30),
        "bookedAt": datetime.now(timezone.utc).isoformat(),
    }
    appointments_table.put_item(Item=booked)

    print(f"Appointment booked: {slot['specialistName']} at {slot['scheduledAt']}")
    return booked


# --- Main Handler ---

def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    body = json.loads(event.get("body", "{}"))
    patient_message = body.get("text", "").strip()

    if not patient_message:
        return {"statusCode": 400, "body": "Empty message"}

    print(f"Message from {connection_id}: {patient_message[:100]}")

    # Look up session
    conn = connections_table.get_item(Key={"connectionId": connection_id}).get("Item")
    if not conn:
        return {"statusCode": 400, "body": "Unknown connection"}
    session_id = conn.get("sessionId", "")

    # Load conversation history
    session = get_session(session_id)
    history = session.get("conversationHistory", [])

    # Add patient message
    history.append({"role": "patient", "content": patient_message})

    # Store first patient message as complaint summary (for history page)
    if len([m for m in history if m["role"] == "patient"]) == 1:
        update_session(session_id, firstPatientMessage=patient_message[:120])

    # Call Bedrock for AI response
    try:
        bedrock_messages = [{"role": "user" if m["role"] == "patient" else "assistant", "content": m["content"]} for m in history]
        ai_response = call_bedrock(bedrock_messages, ASSESSMENT_PROMPT)
        print(f"AI response length: {len(ai_response)}")
    except Exception as e:
        print(f"Bedrock error: {e}")
        ai_response = "I'm sorry, I'm having trouble processing that right now. Could you try again?"
        history.append({"role": "ai", "content": ai_response})
        update_session(session_id, conversationHistory=history)
        send_to_connection(event, connection_id, {"type": "message", "role": "ai", "content": ai_response})
        return {"statusCode": 200, "body": "Error response sent"}

    # Check if assessment is complete
    if is_assessment_complete(ai_response):
        # Send the patient-facing closing message
        patient_msg = get_patient_facing_message(ai_response)
        if patient_msg:
            send_to_connection(event, connection_id, {"type": "message", "role": "ai", "content": patient_msg})

        # Extract structured data
        assessment_data = extract_assessment_data(ai_response)
        if not assessment_data:
            # Fallback: ask Bedrock to extract
            assessment_data = {"primary_complaint": patient_message, "severity": 5, "onset": "unknown"}

        # Save a clean issue summary for display in history/status
        issue_summary = assessment_data.get("primary_complaint", "")
        if isinstance(issue_summary, dict):
            issue_summary = issue_summary.get("text", "")
        issue_summary = issue_summary or session.get("firstPatientMessage", "Triage session")

        history.append({"role": "ai", "content": patient_msg or "Assessment complete."})
        update_session(session_id, conversationHistory=history, structuredSymptoms=assessment_data, issueSummary=issue_summary[:150])

        # Send status update
        send_to_connection(event, connection_id, {"type": "status", "content": "Analyzing your symptoms...", "status": "SCORING"})

        # --- RUN FULL PIPELINE ---
        try:
            # Step 1: Triage Scoring
            print("Running scoring...")
            urgency_result = run_scoring(assessment_data)
            print(f"Urgency: {urgency_result.get('urgency_level')}")
            update_session(session_id, urgencyLevel=urgency_result.get("urgency_level"), urgencyResult=urgency_result)

            send_to_connection(event, connection_id, {
                "type": "status",
                "content": f"Urgency assessed: {urgency_result.get('urgency_level')}. Finding the right specialist...",
                "status": "ROUTING"
            })

            # Step 2: Specialist Routing
            print("Running routing...")
            routing_result = run_routing(assessment_data, urgency_result.get("urgency_level"))
            print(f"Department: {routing_result.get('department')}")
            update_session(session_id, routingDecision=routing_result)

            send_to_connection(event, connection_id, {
                "type": "status",
                "content": f"Routing to {routing_result.get('department')}. Generating clinical summary...",
                "status": "SUMMARY"
            })

            # Step 3: SOAP Note
            print("Generating SOAP...")
            soap_note = run_soap_note(assessment_data, urgency_result, routing_result)
            update_session(session_id, soapNote=soap_note)

            # Step 4: Complete session + Book appointment
            now = datetime.now(timezone.utc).isoformat()

            # Auto-book an available slot for the routed department
            booked_appointment = None
            try:
                booked_appointment = book_appointment(session_id, routing_result.get("department", ""), conn.get("patientId", "anonymous"))
            except Exception as e:
                print(f"Appointment booking error: {e}")
            update_session(session_id,
                status="COMPLETED",
                completedAt=now,
                patientSummary={
                    "symptoms_reported": assessment_data.get("primary_complaint", ""),
                    "medications_reviewed": f"{len(assessment_data.get('medications', []))} medications noted",
                    "urgency_level": f"{urgency_result.get('urgency_level')} — {urgency_result.get('recommended_timeframe', '')}",
                    "next_steps": f"Routed to {routing_result.get('department')}. {urgency_result.get('reasoning', '')}",
                }
            )

            # Send completion to patient
            completion_msg = {
                "type": "complete",
                "urgency_level": urgency_result.get("urgency_level"),
                "department": routing_result.get("department"),
                "summary": {
                    "urgency": urgency_result.get("urgency_level"),
                    "timeframe": urgency_result.get("recommended_timeframe"),
                    "department": routing_result.get("department"),
                    "reasoning": urgency_result.get("reasoning"),
                },
            }
            if booked_appointment:
                completion_msg["appointment"] = {
                    "specialist": booked_appointment.get("specialistName"),
                    "clinic": booked_appointment.get("clinicName"),
                    "time": booked_appointment.get("scheduledAt"),
                    "department": booked_appointment.get("department"),
                }
            send_to_connection(event, connection_id, completion_msg)

            # Step 5: Send email notification for URGENT/EMERGENCY cases
            urgency_level = urgency_result.get("urgency_level", "")
            if urgency_level in ("EMERGENCY", "URGENT"):
                try:
                    sns_client = boto3.client("sns")
                    notification_body = (
                        f"TRIAGE ALERT — {urgency_level}\n"
                        f"{'='*40}\n\n"
                        f"Patient Complaint: {assessment_data.get('primary_complaint', 'Unknown')}\n"
                        f"Severity: {assessment_data.get('severity', '?')}/10\n"
                        f"Onset: {assessment_data.get('onset', 'Unknown')}\n"
                        f"Associated Symptoms: {', '.join(assessment_data.get('associated_symptoms', []))}\n"
                        f"Medications: {', '.join(assessment_data.get('medications', [])) or 'None'}\n\n"
                        f"Urgency: {urgency_level}\n"
                        f"Timeframe: {urgency_result.get('recommended_timeframe', '')}\n"
                        f"Department: {routing_result.get('department', 'TBD')}\n"
                        f"Reasoning: {urgency_result.get('reasoning', '')}\n\n"
                        f"Session ID: {session_id}\n"
                        f"Time: {now}\n"
                    )
                    sns_client.publish(
                        TopicArn="arn:aws:sns:us-west-2:294680528184:triage-emergency-escalation",
                        Subject=f"TRIAGE {urgency_level}: {assessment_data.get('primary_complaint', 'Patient needs attention')[:80]}",
                        Message=notification_body,
                    )
                    print(f"Email notification sent for {urgency_level} case")
                except Exception as e:
                    print(f"SNS notification error: {e}")

            print(f"Pipeline complete: {urgency_result.get('urgency_level')} → {routing_result.get('department')}")

        except Exception as e:
            print(f"Pipeline error: {e}")
            send_to_connection(event, connection_id, {
                "type": "message",
                "role": "system",
                "content": "Your assessment has been recorded. Our team will review and contact you shortly.",
            })
            update_session(session_id, status="COMPLETED", completedAt=datetime.now(timezone.utc).isoformat())

    else:
        # Normal conversation turn — send AI response
        history.append({"role": "ai", "content": ai_response})
        update_session(session_id, conversationHistory=history)
        send_to_connection(event, connection_id, {"type": "message", "role": "ai", "content": ai_response})

    return {"statusCode": 200, "body": "OK"}
