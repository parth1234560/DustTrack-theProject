"""DynamoDB access: the ONLY module that touches DynamoDB (lazy, Decimal-safe)."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from common import config

OnlyStatus = str | tuple[str, ...] | None


def to_dynamo(value: Any) -> Any:
    """Recursively convert floats to Decimal; reject NaN/inf.

    Booleans pass through as DynamoDB BOOL (callers validate numerics).
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("NaN/inf are not allowed in DynamoDB items")
        return Decimal(str(value))
    if isinstance(value, Decimal):
        return value
    if isinstance(value, dict):
        return {k: to_dynamo(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dynamo(v) for v in value]
    return value


def _table(name: str):
    return boto3.resource("dynamodb").Table(name)


def _get(table: str, key_name: str, key_value: str) -> dict[str, Any] | None:
    return _table(table).get_item(Key={key_name: key_value}).get("Item")


def _put(table: str, item: dict[str, Any]) -> None:
    _table(table).put_item(Item=to_dynamo(item))


def get_inspection(i: str) -> dict[str, Any] | None:
    return _get(config.INSPECTIONS_TABLE, "inspectionId", i)


def put_inspection(item: dict[str, Any]) -> None:
    _put(config.INSPECTIONS_TABLE, item)


def get_segment(i: str) -> dict[str, Any] | None:
    return _get(config.SEGMENTS_TABLE, "segmentId", i)


def put_segment(item: dict[str, Any]) -> None:
    _put(config.SEGMENTS_TABLE, item)


def put_cleaning_event(item: dict[str, Any]) -> None:
    _put(config.CLEANING_EVENTS_TABLE, item)


def list_segments() -> list[dict[str, Any]]:
    """Scan all segments (demo data is tiny; no indexes exist)."""
    table = _table(config.SEGMENTS_TABLE)
    items: list[dict[str, Any]] = []
    args: dict[str, Any] = {}
    while True:
        page = table.scan(**args)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            return items
        args["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def update_inspection(i: str, f: dict[str, Any], only: OnlyStatus = None) -> bool:
    """SET-update; with only, write solely from that status (else False)."""
    return _update(config.INSPECTIONS_TABLE, {"inspectionId": i}, f, only)


def update_segment(s: str, f: dict[str, Any]) -> bool:
    """SET-update a segment (publish guards the inspection, not the segment)."""
    return _update(config.SEGMENTS_TABLE, {"segmentId": s}, f)


def _update(
    t: str, key: dict[str, str], f: dict[str, Any], only: OnlyStatus = None
) -> bool:
    names = {f"#f{i}": k for i, k in enumerate(f)}
    values = {f":f{i}": to_dynamo(v) for i, v in enumerate(f.values())}
    expr = "SET " + ", ".join(f"#f{i} = :f{i}" for i in range(len(f)))
    request: dict[str, Any] = {
        "Key": key,
        "UpdateExpression": expr,
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
    }
    if only is not None:
        expected = (only,) if isinstance(only, str) else only
        holders = ", ".join(f":o{i}" for i in range(len(expected)))
        request["ConditionExpression"] = f"#st IN ({holders})"
        names["#st"] = "status"
        values.update({f":o{i}": s for i, s in enumerate(expected)})
    try:
        _table(t).update_item(**request)
        return True
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code != "ConditionalCheckFailedException":
            raise
        return False


def transition_to_processing(i: str, started_at: str) -> dict[str, Any] | None:
    """Move PENDING -> PROCESSING; fresh item (re-deliveries return as-is)."""
    fields = {"status": config.STATUS_PROCESSING, "processingStartedAt": started_at}
    update_inspection(i, fields, only=config.STATUS_PENDING)
    return get_inspection(i)


def mark_rejected(i: str, code: str, message: str, finished_at: str) -> bool:
    """Write REJECTED + code/message (only from PROCESSING)."""
    fields = {
        "status": config.STATUS_REJECTED,
        "rejectionCode": code,
        "rejectionMessage": message,
        "completedAt": finished_at,
    }
    return update_inspection(i, fields, only=config.STATUS_PROCESSING)


def mark_failed(i: str, failed_at: str) -> bool:
    """Write FAILED + INTERNAL_ERROR (only from PENDING/PROCESSING)."""
    fields = {
        "status": config.STATUS_FAILED,
        "failureCode": config.FAILURE_CODE,
        "completedAt": failed_at,
    }
    only = (config.STATUS_PENDING, config.STATUS_PROCESSING)
    return update_inspection(i, fields, only=only)


def complete_inspection(i: str, fields: dict[str, Any]) -> bool:
    """Write the COMPLETED outcome (only from PROCESSING; else a no-op)."""
    return update_inspection(i, fields, only=config.STATUS_PROCESSING)
