"""Cognito JWT claim helpers for the API Lambda.

The ``cognito:groups`` claim may arrive as a list, ``"[a b]"``, ``"a,b"``
or a single ``"a"`` string; :func:`get_groups` parses all four forms.
User identity always comes from the JWT ``sub``, never the request body.
"""

from __future__ import annotations

from typing import Any

from common.errors import ApiError

UNKNOWN_USER: str = "unknown"


def get_claims(event: dict[str, Any]) -> dict[str, Any]:
    """Extract JWT claims from a payload-v2 event ({} when absent)."""
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError, AttributeError):
        return {}
    return dict(claims) if isinstance(claims, dict) else {}


def get_user_id(event: dict[str, Any]) -> str:
    """Return the caller's JWT subject (never from the body)."""
    claims = get_claims(event)
    sub = claims.get("sub") or claims.get("username") or claims.get("cognito:username")
    return str(sub) if sub else UNKNOWN_USER


def _split_groups(text: str) -> list[str]:
    stripped = text.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    parts: list[str] = []
    for chunk in stripped.replace(",", " ").split():
        cleaned = chunk.strip().strip("\"'")
        if cleaned:
            parts.append(cleaned)
    return parts


def get_groups(event: dict[str, Any]) -> list[str]:
    """Parse the cognito:groups claim in all four wire formats."""
    raw = get_claims(event).get("cognito:groups", [])
    if isinstance(raw, str):
        return _split_groups(raw)
    if isinstance(raw, (list, tuple)):
        groups: list[str] = []
        for item in raw:
            text = str(item)
            if "," in text or "[" in text or " " in text.strip():
                groups.extend(_split_groups(text))
            elif text.strip():
                groups.append(text.strip())
        return groups
    return []


def require_role(event: dict[str, Any], *allowed: str) -> dict[str, Any]:
    """Require the caller to hold one of the allowed groups.

    Returns the claims on success. Raises ApiError(UNAUTHORIZED) without a
    subject, ApiError(FORBIDDEN) without a matching group.
    """
    claims = get_claims(event)
    if not claims.get("sub"):
        raise ApiError("UNAUTHORIZED", "Missing or invalid authentication", 401)
    groups = get_groups(event)
    if not any(g in allowed for g in groups):
        raise ApiError("FORBIDDEN", "User is not allowed to perform this action", 403)
    return claims
