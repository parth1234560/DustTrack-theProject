"""Step Functions plumbing: S3 event parsing and the step decorator."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.parse import unquote_plus

from common import clock, config, log, repo
from common.errors import InspectionRejected

logger = log.get_logger("workflow")


def parse_s3_event(event: dict[str, Any]) -> tuple[str, str, str] | None:
    """Parse a raw S3 Object Created event.

    Returns (bucket, key, inspectionId) with the key URL-decoded ("+" means
    space). None for keys outside inspections/{id}/photo.* or malformed
    events (those executions are ignored, not failed).
    """
    try:
        detail = event["detail"]
        bucket = detail["bucket"]["name"]
        key = unquote_plus(detail["object"]["key"])
    except (KeyError, TypeError, AttributeError):
        return None
    parts = key.split("/")
    if len(parts) != 3 or parts[0] != config.PHOTO_KEY_PREFIX:
        return None
    if not parts[1] or not parts[2].startswith("photo."):
        return None
    return (bucket, key, parts[1])


def find_inspection_id(event: dict[str, Any]) -> str | None:
    """Inspection id from accumulated state, else from the raw S3 event."""
    validation = event.get("validation")
    if isinstance(validation, dict) and validation.get("inspectionId"):
        return str(validation["inspectionId"])
    parsed = parse_s3_event(event)
    return parsed[2] if parsed else None


def workflow_step(name: str) -> Callable:
    """Log a step; on unexpected exceptions mark the inspection FAILED.

    Best effort: the mark is conditional (never regresses a terminal
    status) and its own failure is swallowed. InspectionRejected passes
    through untouched (validate already wrote REJECTED).
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(event: dict[str, Any], context: Any) -> Any:
            try:
                return fn(event, context)
            except InspectionRejected:
                raise
            except Exception:
                inspection_id = find_inspection_id(
                    event if isinstance(event, dict) else {}
                )
                if inspection_id:
                    try:
                        repo.mark_failed(inspection_id, clock.utc_now_iso())
                    except Exception as exc:  # noqa: BLE001 - best effort only
                        log.log_event(
                            logger, "warning", "mark_failed failed", error=str(exc)
                        )
                log.log_event(logger, "error", f"{name} failed")
                raise

        return wrapper

    return decorator
