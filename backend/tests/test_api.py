"""API route tests: happy path per route, plus 403 and 404 cases."""

from __future__ import annotations

import json
from typing import Any

import pytest

from api import handler
from common import repo

SEG_A = {
    "segmentId": "SEG-001",
    "roadName": "Karol Bagh Main",
    "corridorId": "C-1",
    "wardId": "WARD-05",
    "geometry": {"type": "LineString", "coordinates": [[77.20, 28.61], [77.21, 28.62]]},
    "lengthM": 1500.0,
    "importance": 4,
    "cadenceEstDays": 8.0,
    "lastCleanedAt": "2026-09-29T10:30:00Z",
    "lastDustLevel": 3,
    "lastInspectedAt": "2026-10-09T10:30:00Z",
    "cleaningStatus": "NEEDS_CLEANING",
    "priorityScore": 0.9,
    "priorityLevel": "HIGH",
    "priorityBreakdown": {"components": {}, "weights": {}, "inputs": {}},
    "explanation": "Heavy deposits",
    "weatherSnapshot": None,
    "isDemo": True,
    "updatedAt": "2026-10-09T10:30:00Z",
}
SEG_CLEAN = {
    **SEG_A,
    "segmentId": "SEG-002",
    "cleaningStatus": "CLEAN",
    "priorityScore": 0.1,
    "priorityLevel": "LOW",
    "lastDustLevel": 0,
}
SEG_OTHER_WARD = {**SEG_A, "segmentId": "SEG-003", "wardId": "WARD-07"}


def api_event(
    method: str,
    path: str,
    sub: str = "user-a",
    groups: Any = ("inspectors",),
    body: Any = None,
    query: dict[str, str] | None = None,
) -> dict[str, Any]:
    if body is not None and not isinstance(body, str):
        body = json.dumps(body)
    return {
        "requestContext": {
            "http": {"method": method},
            "authorizer": {"jwt": {"claims": {"sub": sub, "cognito:groups": groups}}},
        },
        "rawPath": path,
        "body": body,
        "queryStringParameters": query,
    }


def call(method: str, path: str, **kw: Any) -> tuple[int, dict[str, Any]]:
    response = handler.lambda_handler(api_event(method, path, **kw), None)
    return response["statusCode"], json.loads(response["body"])


@pytest.fixture()
def seeded(aws_resources):
    repo.put_segment(dict(SEG_A))
    repo.put_segment(dict(SEG_CLEAN))
    repo.put_segment(dict(SEG_OTHER_WARD))
    return aws_resources


def _create(seeded, **body: Any) -> tuple[int, dict[str, Any]]:
    base = {
        "segmentId": "SEG-001",
        "latitude": 28.615,
        "longitude": 77.205,
        "dustRating": 2,
        "fileType": "image/jpeg",
    }
    return call("POST", "/v1/inspections", body={**base, **body})


def test_create_inspection_happy(seeded):
    status, payload = _create(seeded)
    assert status == 201
    assert payload["status"] == "PENDING"
    assert payload["upload"]["method"] == "PUT"
    assert payload["upload"]["contentType"] == "image/jpeg"
    assert payload["upload"]["expiresIn"] == 900
    assert payload["upload"]["url"].startswith("https://")


def test_create_validation_and_missing_segment(seeded):
    status, payload = _create(seeded, dustRating=9)
    assert status == 400 and payload["error"]["code"] == "VALIDATION_ERROR"
    status, payload = _create(seeded, segmentId="SEG-999")
    assert status == 404 and payload["error"]["code"] == "SEGMENT_NOT_FOUND"
    status, payload = _create(seeded, dustRating=True)
    assert status == 400  # booleans rejected where numbers are required


def test_get_inspection_own_supervisor_and_other_404(seeded):
    _, created = _create(seeded)
    inspection_id = created["inspectionId"]
    status, payload = call("GET", f"/v1/inspections/{inspection_id}")
    assert (
        status == 200 and payload["aiAnalysis"] is None and payload["imageUrl"] is None
    )
    status, _ = call(
        "GET", f"/v1/inspections/{inspection_id}", sub="boss", groups=("supervisors",)
    )
    assert status == 200
    status, payload = call("GET", f"/v1/inspections/{inspection_id}", sub="user-b")
    assert status == 404 and payload["error"]["code"] == "INSPECTION_NOT_FOUND"
    status, payload = call(
        "GET", "/v1/inspections/does-not-exist", sub="boss", groups=("supervisors",)
    )
    assert status == 404


def test_list_and_detail_segments(seeded):
    status, payload = call("GET", "/v1/segments", query={"ward": "WARD-05"})
    assert status == 200 and payload["wardId"] == "WARD-05"
    assert {i["segmentId"] for i in payload["items"]} == {"SEG-001", "SEG-002"}
    assert payload["nextCursor"] is None
    card = payload["items"][0]
    assert card["cleaningCadenceDays"] == 8.0 and "priorityLevel" in card
    status, payload = call("GET", "/v1/segments", query={"limit": "1"})
    assert len(payload["items"]) == 1
    status, payload = call("GET", "/v1/segments/SEG-001")
    assert status == 200 and payload["priorityBreakdown"] == {
        "components": {},
        "weights": {},
        "inputs": {},
    }
    status, payload = call("GET", "/v1/segments/SEG-999")
    assert status == 404 and payload["error"]["code"] == "SEGMENT_NOT_FOUND"


def test_worklist_supervisor_excludes_clean(seeded):
    status, payload = call(
        "GET",
        "/v1/worklist",
        sub="boss",
        groups=("supervisors",),
        query={"ward": "WARD-05"},
    )
    assert status == 200
    assert [i["segmentId"] for i in payload["items"]] == ["SEG-001"]
    item = payload["items"][0]
    assert item["daysSinceCleaned"] is not None and item["daysSinceCleaned"] > 0
    assert item["cleaningCadenceDays"] == 8.0


def test_worklist_forbidden_for_inspectors(seeded):
    status, payload = call("GET", "/v1/worklist")
    assert status == 403 and payload["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    "groups", [["supervisors"], "[supervisors]", "supervisors,boss", "supervisors"]
)
def test_group_claim_formats(seeded, groups):
    status, _ = call("GET", "/v1/worklist", sub="boss", groups=groups)
    assert status == 200


def test_cleaned_happy_and_worklist_exclusion(seeded):
    status, payload = call(
        "POST",
        "/v1/segments/SEG-001/cleaned",
        sub="boss",
        groups=("supervisors",),
        body={"method": "MANUAL", "squadId": "TEAM-02"},
    )
    assert status == 201 and payload["status"] == "RECORDED"
    status, detail = call("GET", "/v1/segments/SEG-001")
    assert detail["cleaningStatus"] == "CLEAN" and detail["dustRating"] == 0
    status, payload = call(
        "GET",
        "/v1/worklist",
        sub="boss",
        groups=("supervisors",),
        query={"ward": "WARD-05"},
    )
    assert payload["items"] == []
    status, payload = call(
        "POST",
        "/v1/segments/SEG-001/cleaned",
        sub="boss",
        groups=("supervisors",),
        body={"method": "ROBOT"},
    )
    assert status == 400
    status, payload = call(
        "POST",
        "/v1/segments/SEG-001/cleaned",
        sub="boss",
        groups=("supervisors",),
        body={"method": "MANUAL", "cleanedAt": "2099-01-01T00:00:00Z"},
    )
    assert status == 400 and payload["error"]["code"] == "VALIDATION_ERROR"
    status, payload = call(
        "POST",
        "/v1/segments/SEG-999/cleaned",
        sub="boss",
        groups=("supervisors",),
        body={"method": "MANUAL"},
    )
    assert status == 404 and payload["error"]["code"] == "SEGMENT_NOT_FOUND"


def test_route_not_found_and_invalid_json(seeded):
    status, payload = call("GET", "/v1/nope")
    assert status == 404 and payload["error"]["code"] == "ROUTE_NOT_FOUND"
    status, payload = call("POST", "/v1/inspections", body="{bad json")
    assert status == 400 and payload["error"]["code"] == "INVALID_JSON"
