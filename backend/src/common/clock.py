"""Injectable UTC clock.

All timestamps are ISO-8601 UTC with "Z" and second precision. Tests freeze
time with :func:`set_now` instead of patching datetime globally.
"""

from __future__ import annotations

from datetime import UTC, datetime

_override: datetime | None = None


def set_now(value: datetime | None) -> None:
    """Freeze (:class:`datetime`) or unfreeze (None) the clock. Test-only."""
    global _override
    _override = value


def now() -> datetime:
    """Current time as an aware UTC datetime."""
    if _override is not None:
        return _override
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Current time as ISO-8601 UTC with "Z", second precision."""
    return (
        now().astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, accepting both "Z" and "+00:00"."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def days_between_iso(earlier_iso: str, later_iso: str) -> float:
    """Fractional days from earlier to later (may be negative)."""
    delta = parse_iso(later_iso) - parse_iso(earlier_iso)
    return delta.total_seconds() / 86400.0
