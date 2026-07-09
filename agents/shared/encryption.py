"""PHI field-level encryption using AWS KMS.

Provides encrypt/decrypt for individual PHI fields before DynamoDB storage.
Uses encryption context (session_id + field_name) to prevent ciphertext
from being moved between records.
"""

from __future__ import annotations

import base64
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .config import config

_kms_client = None


def _get_kms():
    global _kms_client
    if _kms_client is None:
        _kms_client = boto3.client("kms")
    return _kms_client


class EncryptionError(Exception):
    """Raised when encryption or decryption fails."""

    pass


def encrypt_field(plaintext: str, session_id: str, field_name: str) -> str:
    """Encrypt a PHI field value using KMS.

    Args:
        plaintext: The PHI value to encrypt.
        session_id: Session ID for encryption context binding.
        field_name: Field name for encryption context binding.

    Returns:
        Base64-encoded ciphertext string (safe for DynamoDB storage).

    Raises:
        EncryptionError: If KMS encryption fails.
    """
    if not config.PHI_KEY_ARN:
        # Development mode: skip encryption if no key configured
        return plaintext

    try:
        response = _get_kms().encrypt(
            KeyId=config.PHI_KEY_ARN,
            Plaintext=plaintext.encode("utf-8"),
            EncryptionContext={
                "session_id": session_id,
                "field_name": field_name,
            },
        )
        return base64.b64encode(response["CiphertextBlob"]).decode("utf-8")
    except ClientError as e:
        raise EncryptionError(f"Failed to encrypt field '{field_name}': {e}") from e


def decrypt_field(ciphertext: str, session_id: str, field_name: str) -> str:
    """Decrypt a PHI field value using KMS.

    Args:
        ciphertext: Base64-encoded ciphertext from DynamoDB.
        session_id: Session ID (must match encryption context).
        field_name: Field name (must match encryption context).

    Returns:
        Decrypted plaintext string.

    Raises:
        EncryptionError: If KMS decryption fails (wrong context, key, etc.).
    """
    if not config.PHI_KEY_ARN:
        # Development mode: data was stored as plaintext
        return ciphertext

    try:
        response = _get_kms().decrypt(
            CiphertextBlob=base64.b64decode(ciphertext),
            EncryptionContext={
                "session_id": session_id,
                "field_name": field_name,
            },
        )
        return response["Plaintext"].decode("utf-8")
    except ClientError as e:
        raise EncryptionError(f"Failed to decrypt field '{field_name}': {e}") from e


def encrypt_dict_fields(
    data: dict, session_id: str, fields_to_encrypt: list[str]
) -> dict:
    """Encrypt specific fields in a dictionary.

    Args:
        data: Dictionary containing fields to encrypt.
        session_id: Session ID for encryption context.
        fields_to_encrypt: List of field names to encrypt.

    Returns:
        New dictionary with specified fields encrypted.
    """
    result = data.copy()
    for field in fields_to_encrypt:
        if field in result and result[field] is not None:
            value = result[field]
            if isinstance(value, str):
                result[field] = encrypt_field(value, session_id, field)
    return result
