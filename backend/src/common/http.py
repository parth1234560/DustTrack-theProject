"""HTTP helpers for the API Lambda (API Gateway HTTP API, payload v2)."""

from __future__ import annotations

import base64
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from common.errors import ApiError

JSON_HEADERS: dict[str, str] = {"Content-Type": "application/json"}


def to_jsonable(value: Any) -> Any:
    """Convert DynamoDB-flavoured values (Decimal, dates) to JSON values."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    return value


def json_response(status: int, payload: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": dict(JSON_HEADERS),
        "body": json.dumps(to_jsonable(payload)),
    }


def error_response(
    code: str, message: str, status: int | None = None
) -> dict[str, Any]:
    err = ApiError(code, message, status)
    return json_response(err.status, err.to_body())


def parse_json_body(event: dict[str, Any]) -> dict[str, Any]:
    """Parse the request body; missing/empty body yields {}.

    Raises ApiError(INVALID_JSON) for malformed JSON or non-object bodies.
    """
    body = event.get("body")
    if body is None:
        return {}
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        if not body.strip():
            return {}
        text = body
        if event.get("isBase64Encoded"):
            try:
                text = base64.b64decode(body).decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise ApiError(
                    "INVALID_JSON", "Request body is not valid JSON"
                ) from exc
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ApiError("INVALID_JSON", "Request body is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ApiError("INVALID_JSON", "Request body must be a JSON object")
        return parsed
    raise ApiError("INVALID_JSON", "Request body must be a JSON object")


def encode_cursor(offset: int) -> str:
    """Encode an integer offset as an opaque base64url cursor."""
    raw = json.dumps({"o": offset}).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    """Decode a cursor back to an offset; None means the first page.

    Raises ApiError(INVALID_CURSOR) for any malformed cursor.
    """
    if cursor is None or cursor == "":
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        parsed = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        offset = parsed["o"] if isinstance(parsed, dict) else None
    except (ValueError, KeyError, UnicodeDecodeError):
        raise ApiError("INVALID_CURSOR", "Cursor is invalid") from None
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ApiError("INVALID_CURSOR", "Cursor is invalid")
    return offset
