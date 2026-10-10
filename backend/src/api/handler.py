"""API Lambda: the six contract routes (single route table, JWT roles)."""

from __future__ import annotations

from typing import Any

from common import auth, clock, config, http, log, models, repo, s3, scoring
from common.errors import ApiError

logger = log.get_logger("api")

INSPECTORS = (config.INSPECTORS_GROUP, config.SUPERVISORS_GROUP)
SUPERVISORS = (config.SUPERVISORS_GROUP,)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        return _route(event)
    except ApiError as exc:
        return http.json_response(exc.status, exc.to_body())
    except Exception:  # noqa: BLE001 - 500 barrier, never leak internals
        log.log_event(logger, "error", "unhandled api error")
        return http.error_response("INTERNAL_ERROR", "Internal server error", 500)


def _route(event: dict[str, Any]) -> dict[str, Any]:
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    parts = [p for p in event.get("rawPath", "").split("/") if p]
    if len(parts) < 2 or parts[0] != "v1":
        return http.error_response("ROUTE_NOT_FOUND", "Route not found", 404)
    rest = parts[1:]
    if method == "POST" and rest == ["inspections"]:
        return _create_inspection(event)
    if method == "GET" and len(rest) == 2 and rest[0] == "inspections":
        return _get_inspection(event, rest[1])
    if method == "GET" and rest == ["worklist"]:
        return _worklist(event)
    if method == "GET" and rest == ["segments"]:
        return _list_segments(event)
    if method == "GET" and len(rest) == 2 and rest[0] == "segments":
        return _segment_detail(event, rest[1])
    if (method, rest[:1], rest[2:]) == ("POST", ["segments"], ["cleaned"]):
        return _mark_cleaned(event, rest[1])
    return http.error_response("ROUTE_NOT_FOUND", "Route not found", 404)


def _limit(query: dict[str, Any]) -> int:
    raw = query.get("limit")
    if raw is None:
        return config.LIMIT_DEFAULT
    try:
        return max(1, min(config.LIMIT_MAX, int(str(raw))))
    except (TypeError, ValueError):
        raise ApiError("VALIDATION_ERROR", "limit must be an integer") from None


def _number(body: dict[str, Any], name: str, lo: float, hi: float) -> float:
    value = body.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApiError("VALIDATION_ERROR", f"{name} must be a number")
    if not lo <= float(value) <= hi:
        raise ApiError("VALIDATION_ERROR", f"{name} is out of range")
    return float(value)


def _rating(body: dict[str, Any]) -> int:
    value = body.get("dustRating")
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 3:
        raise ApiError("VALIDATION_ERROR", "dustRating must be an integer from 0 to 3")
    return value


def _notes(body: dict[str, Any], name: str = "notes") -> str | None:
    value = body.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > config.NOTES_MAX_LEN:
        raise ApiError("VALIDATION_ERROR", f"{name} must be a string up to 500 chars")
    return value


def _create_inspection(event: dict[str, Any]) -> dict[str, Any]:
    auth.require_role(event, *INSPECTORS)
    body = http.parse_json_body(event)
    segment_id = body.get("segmentId")
    if not isinstance(segment_id, str) or not segment_id.strip():
        raise ApiError("VALIDATION_ERROR", "segmentId is required")
    segment_id = segment_id.strip()
    file_type = body.get("fileType")
    if file_type not in config.VALID_FILE_TYPES:
        raise ApiError("VALIDATION_ERROR", "fileType must be image/jpeg, png or webp")
    latitude = _number(body, "latitude", -90.0, 90.0)
    longitude = _number(body, "longitude", -180.0, 180.0)
    rating = _rating(body)
    notes = _notes(body)
    debris = body.get("debrisReported", False)
    if not isinstance(debris, bool):
        raise ApiError("VALIDATION_ERROR", "debrisReported must be a boolean")
    if repo.get_segment(segment_id) is None:
        raise ApiError("SEGMENT_NOT_FOUND", "Segment not found", 404)
    inspection_id = models.new_id()
    key = models.photo_key(inspection_id, str(file_type))
    repo.put_inspection(
        models.new_inspection(
            inspection_id=inspection_id,
            segment_id=segment_id,
            inspector_id=auth.get_user_id(event),
            photo_key=key,
            file_type=str(file_type),
            latitude=latitude,
            longitude=longitude,
            inspector_rating=rating,
            created_at=clock.utc_now_iso(),
            notes=notes,
            debris_reported=debris,
        )
    )
    url = s3.presign_put(
        config.PHOTO_BUCKET, key, str(file_type), config.UPLOAD_URL_EXPIRES
    )
    log.log_event(logger, "info", "inspection created", inspectionId=inspection_id)
    upload = {
        "url": url,
        "method": "PUT",
        "contentType": file_type,
        "expiresIn": config.UPLOAD_URL_EXPIRES,
    }
    return http.json_response(
        201, {"inspectionId": inspection_id, "status": "PENDING", "upload": upload}
    )


def _ai_analysis(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("visionStatus") != "OK" or not isinstance(item.get("vision"), dict):
        return None
    vision = item["vision"]
    flags = vision.get("flags") or []
    return {
        "dustRating": vision.get("dustLevel"),
        "confidence": vision.get("confidence"),
        "debrisDetected": bool(flags),
        "flags": flags,
        "reason": vision.get("reason"),
    }


def _get_inspection(event: dict[str, Any], inspection_id: str) -> dict[str, Any]:
    auth.require_role(event, *INSPECTORS)
    item = repo.get_inspection(inspection_id)
    if item is None:
        raise ApiError("INSPECTION_NOT_FOUND", "Inspection not found", 404)
    own = item.get("inspectorId") == auth.get_user_id(event)
    if config.SUPERVISORS_GROUP not in auth.get_groups(event) and not own:
        raise ApiError("INSPECTION_NOT_FOUND", "Inspection not found", 404)
    status = str(item.get("status"))
    response: dict[str, Any] = {
        "inspectionId": item["inspectionId"],
        "segmentId": item.get("segmentId"),
        "status": status,
        "inspectorDustRating": item.get("inspectorDustRating"),
        "aiAnalysis": _ai_analysis(item),
        "imageUrl": None,
        "inspectedAt": item.get("createdAt"),
        "disagreement": item.get("disagreement"),
    }
    if status != "PENDING":
        response["imageUrl"] = s3.presign_get(
            config.PHOTO_BUCKET, str(item.get("photoKey")), config.DOWNLOAD_URL_EXPIRES
        )
    if status == "COMPLETED":
        response["result"] = {
            "priorityScore": item.get("priorityScore"),
            "priorityLevel": item.get("priorityLevel"),
            "explanation": item.get("explanation"),
        }
    if status == "REJECTED":
        response["rejectionCode"] = item.get("rejectionCode")
        response["rejectionMessage"] = item.get("rejectionMessage")
    if status == "FAILED":
        response["failureCode"] = item.get("failureCode")
    return http.json_response(200, response)


def _card(seg: dict[str, Any]) -> dict[str, Any]:
    cadence = seg.get("cadenceEstDays", config.CADENCE_DEFAULT_DAYS) or 0.0
    score = seg.get("priorityScore")
    return {
        "segmentId": seg.get("segmentId"),
        "roadName": seg.get("roadName"),
        "wardId": seg.get("wardId"),
        "corridorId": seg.get("corridorId"),
        "geometry": seg.get("geometry"),
        "cleaningCadenceDays": round(float(cadence), 1),
        "priorityScore": float(score) if score is not None else 0.0,
        "priorityLevel": seg.get("priorityLevel"),
        "cleaningStatus": seg.get("cleaningStatus"),
        "explanation": seg.get("explanation"),
        "dustRating": seg.get("lastDustLevel"),
        "importance": seg.get("importance"),
        "isDemo": bool(seg.get("isDemo", False)),
        "lastCleanedAt": seg.get("lastCleanedAt"),
        "lastInspectedAt": seg.get("lastInspectedAt"),
    }


def _pool(event: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None, int]:
    auth.require_role(event, *INSPECTORS)
    query = event.get("queryStringParameters") or {}
    ward = query.get("ward")
    items = [s for s in repo.list_segments() if ward is None or s.get("wardId") == ward]
    return items, ward, _limit(query)


def _list_segments(event: dict[str, Any]) -> dict[str, Any]:
    items, ward, limit = _pool(event)
    cards = [_card(s) for s in sorted(items, key=lambda s: str(s.get("segmentId")))]
    return http.json_response(
        200, {"wardId": ward, "items": cards[:limit], "nextCursor": None}
    )


def _segment_detail(event: dict[str, Any], segment_id: str) -> dict[str, Any]:
    auth.require_role(event, *INSPECTORS)
    seg = repo.get_segment(segment_id)
    if seg is None:
        raise ApiError("SEGMENT_NOT_FOUND", "Segment not found", 404)
    return http.json_response(
        200, {**_card(seg), "priorityBreakdown": seg.get("priorityBreakdown")}
    )


def _worklist(event: dict[str, Any]) -> dict[str, Any]:
    auth.require_role(event, *SUPERVISORS)
    query = event.get("queryStringParameters") or {}
    ward = query.get("ward")
    now = clock.utc_now_iso()
    ranked = sorted(
        (
            s
            for s in repo.list_segments()
            if s.get("cleaningStatus", "NEEDS_CLEANING") != "CLEAN"
            and (ward is None or s.get("wardId") == ward)
        ),
        key=lambda s: (-float(s.get("priorityScore") or 0.0), str(s.get("segmentId"))),
    )
    items = []
    for seg in ranked[: _limit(query)]:
        last = seg.get("lastCleanedAt")
        items.append(
            {
                "segmentId": seg.get("segmentId"),
                "roadName": seg.get("roadName"),
                "priorityScore": float(seg.get("priorityScore") or 0.0),
                "priorityLevel": seg.get("priorityLevel"),
                "dustRating": seg.get("lastDustLevel"),
                "lastCleanedAt": last,
                "explanation": seg.get("explanation"),
                "cleaningStatus": seg.get("cleaningStatus"),
                "cleaningCadenceDays": round(float(seg.get("cadenceEstDays", 8.0)), 1),
                "daysSinceCleaned": clock.days_between_iso(last, now) if last else None,
            }
        )
    return http.json_response(200, {"wardId": ward, "items": items, "nextCursor": None})


def _mark_cleaned(event: dict[str, Any], segment_id: str) -> dict[str, Any]:
    auth.require_role(event, *SUPERVISORS)
    seg = repo.get_segment(segment_id)
    if seg is None:
        raise ApiError("SEGMENT_NOT_FOUND", "Segment not found", 404)
    body = http.parse_json_body(event)
    if body.get("method") not in ("MANUAL", "MECHANICAL"):
        raise ApiError("VALIDATION_ERROR", "method must be MANUAL or MECHANICAL")
    raw_cleaned = body.get("cleanedAt") or clock.utc_now_iso()
    try:
        cleaned_time = clock.parse_iso(str(raw_cleaned))
    except ValueError:
        raise ApiError("VALIDATION_ERROR", "cleanedAt must be ISO-8601") from None
    if (cleaned_time - clock.now()).total_seconds() > config.CLEANED_FUTURE_SKEW_S:
        raise ApiError("VALIDATION_ERROR", "cleanedAt cannot be in the future")
    existing = seg.get("lastCleanedAt")
    latest = str(raw_cleaned)
    if existing is not None and clock.parse_iso(str(existing)) > cleaned_time:
        latest = str(existing)
    squad = body.get("squadId")
    if squad is not None and not isinstance(squad, str):
        raise ApiError("VALIDATION_ERROR", "squadId must be a string")
    remarks = _notes(body, "remarks")
    snapshot = seg.get("weatherSnapshot")
    weather = (
        {"weatherStatus": "OK", **snapshot} if isinstance(snapshot, dict) else None
    )
    try:
        result = scoring.score_segment(
            {
                "importance": seg.get("importance", 3),
                "cadenceEstDays": float(seg.get("cadenceEstDays", 8.0)),
                "lastCleanedAt": latest,
                "lastDustLevel": 0,
            },
            inspector_rating=None,
            weather=weather,
            debris=False,
            now=latest,
        )
    except ValueError:
        log.log_event(logger, "error", "rescore failed", segmentId=segment_id)
        raise ApiError("INTERNAL_ERROR", "Internal server error", 500) from None
    event_id = models.new_id()
    repo.put_cleaning_event(
        models.new_cleaning_event(
            event_id=event_id,
            segment_id=segment_id,
            cleaned_at=latest,
            marked_by=auth.get_user_id(event),
            method=str(body.get("method")),
            squad_id=squad,
            remarks=remarks,
        )
    )
    breakdown = {"components": result.components, "weights": result.weights}
    breakdown["inputs"] = result.inputs
    repo.update_segment(
        segment_id,
        {
            "lastCleanedAt": latest,
            "lastDustLevel": 0,
            "priorityScore": result.priority_score,
            "priorityLevel": result.priority_level,
            "priorityBreakdown": breakdown,
            "explanation": result.explanation,
            "cleaningStatus": result.cleaning_status,
            "updatedAt": clock.utc_now_iso(),
        },
    )
    log.log_event(logger, "info", "segment cleaned", segmentId=segment_id)
    return http.json_response(
        201,
        {"cleaningEventId": event_id, "segmentId": segment_id, "status": "RECORDED"},
    )
