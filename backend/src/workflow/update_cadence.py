"""UpdateCadence: compute via cadence.py. Writes nothing."""

from __future__ import annotations

from typing import Any

from common import cadence, config, log, repo
from common.workflow_state import workflow_step

logger = log.get_logger("update-cadence")


@workflow_step("update_cadence")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    validation = event.get("validation") or {}
    if validation.get("ignored"):
        return {"step": "update_cadence", "skipped": True}
    inspection = repo.get_inspection(str(validation["inspectionId"]))
    segment = repo.get_segment(str(validation["segmentId"]))
    result = cadence.update_cadence(
        current=float(segment.get("cadenceEstDays", config.CADENCE_DEFAULT_DAYS)),
        last_cleaned_at=segment.get("lastCleanedAt"),
        inspected_at=str(inspection["createdAt"]),
        inspector_rating=int(inspection["inspectorDustRating"]),
        observed_marker=segment.get("cadenceObservedForCleaningAt"),
    )
    log.log_event(
        logger,
        "info",
        "cadence computed",
        inspectionId=validation["inspectionId"],
        updated=result.updated,
    )
    return {
        "step": "update_cadence",
        "cadenceEstDays": result.cadence_est_days,
        "previousCadenceEstDays": result.previous_cadence_est_days,
        "updated": result.updated,
        "observedDays": result.observed_days,
        "reason": result.reason,
    }
