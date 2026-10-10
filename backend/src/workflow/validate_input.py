"""ValidateInput: photo checks; REJECTED + raise on failure."""

from __future__ import annotations

from typing import Any

from common import clock, config, geo, log, repo, s3
from common.errors import InspectionRejected
from common.workflow_state import parse_s3_event, workflow_step

logger = log.get_logger("validate-input")


def _reject(inspection_id: str, code: str, message: str) -> None:
    repo.mark_rejected(inspection_id, code, message, clock.utc_now_iso())
    log.log_event(logger, "info", "rejected", inspectionId=inspection_id, code=code)
    raise InspectionRejected(code, message)


def _validation(
    inspection: dict[str, Any], bucket: str, key: str, size: Any
) -> dict[str, Any]:
    return {
        "step": "validate_input",
        "valid": True,
        "ignored": False,
        "inspectionId": inspection["inspectionId"],
        "segmentId": inspection["segmentId"],
        "photoKey": key,
        "bucket": bucket,
        "imageSizeBytes": size,
    }


@workflow_step("validate_input")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    parsed = parse_s3_event(event)
    if parsed is None:
        return {"step": "validate_input", "ignored": True}
    bucket, key, inspection_id = parsed
    inspection = repo.get_inspection(inspection_id)
    if inspection is None:
        raise InspectionRejected("OBJECT_MISSING", "Inspection record not found")
    inspection = repo.transition_to_processing(inspection_id, clock.utc_now_iso())
    head = s3.head_object(bucket, key)
    if head is None or key != inspection["photoKey"]:
        _reject(inspection_id, "OBJECT_MISSING", "Photo object not found")
    size = head.get("ContentLength", 0)
    if size <= 0 or head.get("ContentType") != inspection["fileType"]:
        _reject(inspection_id, "INVALID_IMAGE", "Photo is empty or not an image")
    if size > config.MAX_IMAGE_BYTES:
        _reject(inspection_id, "IMAGE_TOO_LARGE", "Photo exceeds the size limit")
    segment = repo.get_segment(str(inspection["segmentId"]))
    if segment is None:
        _reject(inspection_id, "SEGMENT_NOT_FOUND", "Segment does not exist")
    point = (float(inspection["latitude"]), float(inspection["longitude"]))
    dist = geo.distance_to_linestring_m(*point, segment["geometry"]["coordinates"])
    if dist > config.GPS_MAX_DISTANCE_M:
        _reject(inspection_id, "INVALID_GPS", "Photo is too far from the segment")
    return _validation(inspection, bucket, key, size)
