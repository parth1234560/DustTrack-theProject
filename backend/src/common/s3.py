"""Minimal S3 access: head, small bounded read, presigned PUT/GET.

The client is created lazily (per call, never at import) so tests import
freely and moto can mock boto3.
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

_MISSING_CODES = {"404", "NoSuchKey", "NotFound", "NoSuchBucket"}
_S3_CONFIG = Config(signature_version="s3v4")  # SigV4 presigned URLs for ap-south-1


def _client():
    return boto3.client("s3", config=_S3_CONFIG)


def head_object(bucket: str, key: str) -> dict[str, Any] | None:
    """Head an object; None when it does not exist."""
    try:
        return _client().head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in _MISSING_CODES:
            return None
        raise


def read_object(bucket: str, key: str, max_bytes: int) -> bytes:
    """Read up to max_bytes + 1 (callers use the extra byte to detect overrun)."""
    response = _client().get_object(Bucket=bucket, Key=key)
    try:
        return response["Body"].read(max_bytes + 1)
    finally:
        response["Body"].close()


def presign_put(bucket: str, key: str, content_type: str, expires: int) -> str:
    """Presigned PUT URL (signs ContentType; the client must send it back)."""
    return _client().generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
    )


def presign_get(bucket: str, key: str, expires: int) -> str:
    """Short-lived presigned GET URL (never a public S3 URL)."""
    return _client().generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
