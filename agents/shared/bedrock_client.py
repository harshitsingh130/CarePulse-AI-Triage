"""Amazon Bedrock client with retry, timeout, and structured response parsing.

All agents use this client for LLM inference. Centralizes model configuration,
retry logic, and error handling.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from .config import config

_bedrock_config = BotoConfig(
    region_name=config.BEDROCK_REGION,
    read_timeout=config.BEDROCK_TIMEOUT,
    connect_timeout=5,
    retries={"max_attempts": 0},
)

_bedrock_runtime = None


def _get_bedrock():
    global _bedrock_runtime
    if _bedrock_runtime is None:
        _bedrock_runtime = boto3.client("bedrock-runtime", config=_bedrock_config)
    return _bedrock_runtime


class BedrockError(Exception):
    """Raised when Bedrock invocation fails after all retries."""

    pass


class BedrockThrottledError(BedrockError):
    """Raised when Bedrock throttles the request."""

    pass


class BedrockTimeoutError(BedrockError):
    """Raised when Bedrock call exceeds timeout."""

    pass


def invoke_model(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.0,
    max_tokens: int = 2000,
    model_id: Optional[str] = None,
    max_retries: int = 3,
) -> str:
    """Invoke Bedrock model with retry on throttling.

    Args:
        system_prompt: System instruction for the model.
        user_message: User/input message.
        temperature: Sampling temperature (0.0 = deterministic).
        max_tokens: Maximum response tokens.
        model_id: Override model ID (defaults to config).
        max_retries: Number of retry attempts on throttling.

    Returns:
        Model response text.

    Raises:
        BedrockThrottledError: If throttled after all retries.
        BedrockTimeoutError: If request times out.
        BedrockError: For other invocation failures.
    """
    target_model = model_id or config.BEDROCK_MODEL_ID

    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }
    )

    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = _get_bedrock().invoke_model(
                modelId=target_model,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ThrottlingException":
                last_error = e
                wait_time = (2**attempt) * 1  # 1s, 2s, 4s
                time.sleep(wait_time)
                continue
            elif error_code == "ModelTimeoutException":
                raise BedrockTimeoutError(f"Bedrock timed out after {config.BEDROCK_TIMEOUT}s") from e
            else:
                raise BedrockError(f"Bedrock invocation failed: {error_code}") from e

        except Exception as e:
            raise BedrockError(f"Unexpected error invoking Bedrock: {e}") from e

    raise BedrockThrottledError(
        f"Bedrock throttled after {max_retries} retries"
    ) from last_error


def invoke_model_json(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.0,
    max_tokens: int = 2000,
    model_id: Optional[str] = None,
) -> dict[str, Any]:
    """Invoke Bedrock and parse response as JSON.

    Expects the model to return valid JSON. Strips markdown code fences if present.

    Returns:
        Parsed JSON dict.

    Raises:
        ValueError: If response is not valid JSON.
        BedrockError: If invocation fails.
    """
    raw_response = invoke_model(
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=temperature,
        max_tokens=max_tokens,
        model_id=model_id,
    )

    # Strip markdown code fences if present
    text = raw_response.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Bedrock response is not valid JSON: {e}\nResponse: {text[:500]}") from e
