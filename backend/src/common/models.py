"""Shared domain shapes and small builders (pure, no I/O).

Item-field contracts live here as builder functions so the API handler,
workflow steps and seed script construct identical shapes.
"""

from __future__ import annotations

import uuid
from typing import Any

from common import config

# Re-exported status vocabulary (canonical tunables live in config).
PENDING: str = config.STATUS_PENDING
PROCESSING: str = config.STATUS_PROCESSING
COMPLETED: str = config.STATUS_COMPLETED
REJECTED: str = config.STATUS_REJECTED
FAILED: str = config.STATUS_FAILED
TERMINAL_STATUSES: frozenset[str] = config.TERMINAL_STATUSES


def new_id() -> str:
    """A fresh UUID4 identifier (inspections, cleaning events)."""
    return str(uuid.uuid4())


def extension_for(file_type: str) -> str | None:
    """File extension for a MIME type, or None when unsupported."""
    return config.EXTENSION_FOR_MIME.get(file_type)


def photo_key(inspection_id: str, file_type: str) -> str:
    """S3 key for an inspection photo; raises ValueError for bad MIME."""
    ext = extension_for(file_type)
    if ext is None:
        raise ValueError(f"Unsupported fileType: {file_type}")
    return f"{config.PHOTO_KEY_PREFIX}/{inspection_id}/photo.{ext}"


def is_terminal(status: str) -> bool:
    """True for COMPLETED / REJECTED / FAILED (which never regress)."""
    return status in TERMINAL_STATUSES


def new_inspection(
    *,
    inspection_id: str,
    segment_id: str,
    inspector_id: str,
    photo_key: str,
    file_type: str,
    latitude: float,
    longitude: float,
    inspector_rating: int,
    created_at: str,
    notes: str | None = None,
    debris_reported: bool = False,
) -> dict[str, Any]:
    """Build a PENDING inspection item (floats converted on write by repo)."""
    item: dict[str, Any] = {
        "inspectionId": inspection_id,
        "segmentId": segment_id,
        "inspectorId": inspector_id,
        "status": PENDING,
        "createdAt": created_at,
        "photoKey": photo_key,
        "fileType": file_type,
        "latitude": latitude,
        "longitude": longitude,
        "inspectorDustRating": inspector_rating,
        "debrisReported": debris_reported,
    }
    if notes is not None:
        item["notes"] = notes
    return item


def new_cleaning_event(
    *,
    event_id: str,
    segment_id: str,
    cleaned_at: str,
    marked_by: str,
    method: str,
    squad_id: str | None = None,
    remarks: str | None = None,
) -> dict[str, Any]:
    """Build a cleaning-event item."""
    item: dict[str, Any] = {
        "eventId": event_id,
        "segmentId": segment_id,
        "cleanedAt": cleaned_at,
        "markedBy": marked_by,
        "method": method,
    }
    if squad_id is not None:
        item["squadId"] = squad_id
    if remarks is not None:
        item["remarks"] = remarks
    return item
