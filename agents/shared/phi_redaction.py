"""PHI redaction for logging.

Provides a logging formatter that automatically redacts PHI patterns
before log entries reach CloudWatch. Used as a Lambda Layer shared
across all agent functions.
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar


# PHI patterns to detect and redact
PHI_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("DOB_SLASH", re.compile(r"\b\d{2}/\d{2}/\d{4}\b")),
    ("DOB_DASH", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),  # ISO dates that could be DOB
    ("PHONE", re.compile(r"\b(?:\+1)?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("EMAIL", re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")),
    ("MRN", re.compile(r"\bMRN[\s:]*\d+\b", re.IGNORECASE)),
    ("PATIENT_ID_LIKE", re.compile(r"\bPID[\s:]*\d+\b", re.IGNORECASE)),
]

# Words that should NOT be redacted even if they match a pattern
# (e.g., ISO timestamps in log entries are dates but not DOBs)
ALLOWLIST_CONTEXTS = [
    "timestamp",
    "scored_at",
    "assessed_at",
    "generated_at",
    "started_at",
    "completed_at",
]


def redact_phi(text: str) -> str:
    """Remove PHI patterns from text, replacing with [REDACTED].

    Args:
        text: Raw log text that may contain PHI.

    Returns:
        Text with PHI patterns replaced by [REDACTED].
    """
    result = text
    for pattern_name, pattern in PHI_PATTERNS:
        result = pattern.sub(f"[REDACTED:{pattern_name}]", result)
    return result


class PHIRedactingFormatter(logging.Formatter):
    """Logging formatter that redacts PHI before output.

    Use this formatter on all handlers to ensure PHI never reaches CloudWatch.
    """

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact_phi(original)


def get_logger(service_name: str, level: str = "INFO") -> logging.Logger:
    """Get a configured logger with PHI redaction.

    Args:
        service_name: Name of the service (used as logger name).
        level: Log level (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Configured logger instance with PHI redaction.
    """
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid duplicate handlers on repeated calls (Lambda warm starts)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = PHIRedactingFormatter(
            fmt='{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"service":"%(name)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
