"""Secrets Manager access with caching.

Secrets are cached at module level so Lambda warm starts reuse them
without re-fetching on every invocation.
"""

from __future__ import annotations

import json
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError


class SecretNotFoundError(Exception):
    """Raised when a secret cannot be retrieved."""

    pass


def _get_client():
    return boto3.client("secretsmanager")


@lru_cache(maxsize=8)
def get_secret(secret_arn: str) -> dict:
    """Retrieve and parse a secret from Secrets Manager.

    Cached for the lifetime of the Lambda execution environment (warm starts).

    Args:
        secret_arn: ARN or name of the secret.

    Returns:
        Parsed JSON dict of the secret value.

    Raises:
        SecretNotFoundError: If the secret doesn't exist or access is denied.
    """
    try:
        response = _get_client().get_secret_value(SecretId=secret_arn)
        return json.loads(response["SecretString"])
    except ClientError as e:
        raise SecretNotFoundError(
            f"Cannot retrieve secret '{secret_arn}': {e.response['Error']['Code']}"
        ) from e
