"""Unit tests for orchestration decision logic."""

import pytest
import json
from unittest.mock import patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from orchestration.lambdas.decision_logic import (
    init_session_handler,
    complete_session_handler,
    process_nurse_decision_handler,
)


class TestInitSession:
    def test_creates_session(self):
        with patch("orchestration.lambdas.decision_logic.create_session") as mock_create, \
             patch("orchestration.lambdas.decision_logic.write_audit_entry"):
            event = {
                "session_id": str(uuid4()),
                "patient_id": str(uuid4()),
                "patient_clinic_id": "clinic-01",
                "connection_id": "conn-123",
            }
            result = init_session_handler(event, None)
            assert result["session_id"] == event["session_id"]
            assert result["patient_id"] == event["patient_id"]
            mock_create.assert_called_once()


class TestCompleteSession:
    def test_marks_session_completed(self):
        with patch("orchestration.lambdas.decision_logic.update_session_status") as mock_update, \
             patch("orchestration.lambdas.decision_logic._send_to_patient"):
            event = {
                "session_id": str(uuid4()),
                "patient_id": str(uuid4()),
                "connection_id": "conn-123",
                "urgency_level": "STANDARD",
                "department": "Neurology",
                "patient_summary": {"next_steps": "test"},
            }
            result = complete_session_handler(event, None)
            assert result["status"] == "completed"
            mock_update.assert_called_once()

    def test_handles_timeout(self):
        with patch("orchestration.lambdas.decision_logic.update_session_status") as mock_update:
            event = {
                "session_id": str(uuid4()),
                "patient_id": str(uuid4()),
                "timeout": True,
            }
            result = complete_session_handler(event, None)
            assert result["status"] == "paused"


class TestProcessNurseDecision:
    def test_processes_nurse_override(self):
        with patch("orchestration.lambdas.decision_logic.update_session_field"), \
             patch("orchestration.lambdas.decision_logic.update_session_status"), \
             patch("orchestration.lambdas.decision_logic.write_audit_entry"):
            event = {
                "session_id": str(uuid4()),
                "patient_id": str(uuid4()),
                "nurse_urgency": "URGENT",
                "nurse_id": "nurse-001",
                "nurse_reason": "Symptoms suggest higher urgency",
                "original_urgency": "STANDARD",
            }
            result = process_nurse_decision_handler(event, None)
            assert result["updated_urgency_result"]["urgency_level"] == "URGENT"
            assert result["updated_urgency_result"]["confidence_score"] == 0.90

    def test_handles_timeout_default(self):
        with patch("orchestration.lambdas.decision_logic.update_session_field"), \
             patch("orchestration.lambdas.decision_logic.update_session_status"), \
             patch("orchestration.lambdas.decision_logic.write_audit_entry"):
            event = {
                "session_id": str(uuid4()),
                "patient_id": str(uuid4()),
                "nurse_urgency": "URGENT",
                "nurse_id": "SYSTEM_TIMEOUT",
                "nurse_reason": "Timeout",
                "original_urgency": "STANDARD",
                "timeout": True,
            }
            result = process_nurse_decision_handler(event, None)
            assert result["updated_urgency_result"]["urgency_level"] == "URGENT"
            assert result["updated_urgency_result"]["confidence_score"] == 0.65
