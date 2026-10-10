"""Moto-backed pipeline tests: happy path, rejection, never-raise, FAILED."""

from __future__ import annotations

import os
from typing import Any

import pytest

from common import geo, models, repo
from common.errors import InspectionRejected
from workflow import (
    analyse_image,
    fetch_weather,
    publish_work_list,
    score_segment,
    update_cadence,
    validate_input,
)

BUCKET = os.environ["PHOTO_BUCKET"]
CREATED = "2026-10-09T10:30:00Z"
CLEANED = "2026-09-29T10:30:00Z"
COORDS = [[77.20, 28.61], [77.21, 28.62]]
JPEG = b"\xff\xd8\xff-fake-jpeg-bytes"


def _segment() -> dict[str, Any]:
    return {
        "segmentId": "SEG-001",
        "roadName": "Karol Bagh Main",
        "corridorId": "C-1",
        "wardId": "WARD-05",
        "geometry": {"type": "LineString", "coordinates": COORDS},
        "lengthM": 1500.0,
        "importance": 4,
        "cadenceEstDays": 8.0,
        "lastCleanedAt": CLEANED,
        "lastDustLevel": 3,
        "lastInspectedAt": None,
        "cleaningStatus": "NEEDS_CLEANING",
        "priorityScore": 0.0,
        "priorityLevel": "LOW",
        "priorityBreakdown": {},
        "explanation": "",
        "weatherSnapshot": None,
        "isDemo": True,
        "updatedAt": CREATED,
    }


def _inspection(lat: float, lon: float) -> dict[str, Any]:
    key = models.photo_key("INS-1", "image/jpeg")
    return models.new_inspection(
        inspection_id="INS-1",
        segment_id="SEG-001",
        inspector_id="user-a",
        photo_key=key,
        file_type="image/jpeg",
        latitude=lat,
        longitude=lon,
        inspector_rating=3,
        created_at=CREATED,
    )


def _s3_event(key: str) -> dict[str, Any]:
    return {
        "detail": {
            "bucket": {"name": BUCKET},
            "object": {"key": key, "size": len(JPEG)},
        }
    }


def _setup(aws_resources, lat: float, lon: float) -> dict[str, Any]:
    repo.put_segment(_segment())
    repo.put_inspection(_inspection(lat, lon))
    aws_resources["s3"].put_object(
        Bucket=BUCKET,
        Key=models.photo_key("INS-1", "image/jpeg"),
        Body=JPEG,
        ContentType="image/jpeg",
    )
    return _s3_event(models.photo_key("INS-1", "image/jpeg"))


def _midpoint() -> tuple[float, float]:
    return geo.linestring_midpoint(COORDS)


def test_pipeline_happy_path(aws_resources):
    lat, lon = _midpoint()
    s3_event = _setup(aws_resources, lat, lon)
    validation = validate_input.handler(s3_event, None)
    assert validation["valid"] is True and validation["ignored"] is False
    state: dict[str, Any] = {"validation": validation}
    analyse = analyse_image.handler(state, None)
    weather = fetch_weather.handler(state, None)
    assert analyse["visionStatus"] == "SKIPPED"
    assert weather["weatherStatus"] == "FALLBACK"
    state["parallel_results"] = [analyse, weather]
    cadence = update_cadence.handler(state, None)
    assert cadence["updated"] is True and cadence["reason"] == "updated"
    state["cadence"] = cadence
    score = score_segment.handler(state, None)
    assert score["priorityLevel"] == "HIGH" and score["disagreement"] is False
    state["segment_score"] = score
    published = publish_work_list.handler(state, None)
    assert published == {
        "step": "publish_work_list",
        "inspectionId": "INS-1",
        "status": "COMPLETED",
        "segmentUpdate": "APPLIED",
    }
    inspection = repo.get_inspection("INS-1")
    assert inspection["status"] == "COMPLETED"
    assert float(inspection["priorityScore"]) == pytest.approx(
        float(score["priorityScore"])
    )
    segment = repo.get_segment("SEG-001")
    assert int(segment["lastDustLevel"]) == 3
    assert float(segment["cadenceEstDays"]) == pytest.approx(cadence["cadenceEstDays"])
    assert segment["cadenceObservedForCleaningAt"] == CLEANED
    assert "Heavy deposits" in segment["explanation"]
    # Re-delivery never regresses the terminal status.
    again = publish_work_list.handler(state, None)
    assert again["segmentUpdate"] == "SKIPPED_STALE" and again["status"] == "COMPLETED"


def test_rejection_invalid_gps(aws_resources):
    s3_event = _setup(aws_resources, 0.0, 0.0)
    with pytest.raises(InspectionRejected) as exc_info:
        validate_input.handler(s3_event, None)
    assert exc_info.value.rejection_code == "INVALID_GPS"
    inspection = repo.get_inspection("INS-1")
    assert inspection["status"] == "REJECTED"
    assert inspection["rejectionCode"] == "INVALID_GPS"


def test_branches_never_raise():
    assert analyse_image.handler({}, None)["visionStatus"] == "SKIPPED"
    assert fetch_weather.handler({}, None)["weatherStatus"] == "FALLBACK"


def test_unexpected_exception_marks_failed(aws_resources):
    repo.put_inspection(_inspection(*_midpoint()))
    state = {"validation": {"inspectionId": "INS-1", "segmentId": "SEG-999"}}
    with pytest.raises(AttributeError):
        score_segment.handler(state, None)
    assert repo.get_inspection("INS-1")["status"] == "FAILED"
