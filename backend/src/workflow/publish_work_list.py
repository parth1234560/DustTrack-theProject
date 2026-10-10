from __future__ import annotations

from typing import Any

from common import clock, models, repo
from common.workflow_state import workflow_step


def _done(inspection_id: str, status: str, update: str) -> dict[str, Any]:
    return {
        "step": "publish_work_list",
        "inspectionId": inspection_id,
        "status": status,
        "segmentUpdate": update,
    }


@workflow_step("publish_work_list")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    validation = event.get("validation") or {}
    if validation.get("ignored"):
        return {"step": "publish_work_list", "skipped": True}
    inspection_id = str(validation["inspectionId"])
    inspection = repo.get_inspection(inspection_id)
    segment = repo.get_segment(str(validation["segmentId"]))
    cadence, score = event.get("cadence") or {}, event.get("segment_score") or {}
    par = event.get("parallel_results") or [{}, {}]
    analyse, fetch = par[0], par[1] if len(par) > 1 else {}
    breakdown = {k: score.get(k) for k in ("components", "weights", "inputs")}
    cadence_days = cadence.get("cadenceEstDays", segment.get("cadenceEstDays", 8.0))
    fields: dict[str, Any] = {
        "lastDustLevel": inspection["inspectorDustRating"],
        "lastInspectedAt": inspection["createdAt"],
        "cadenceEstDays": cadence_days,
        "priorityScore": score.get("priorityScore"),
        "priorityLevel": score.get("priorityLevel"),
        "priorityBreakdown": breakdown,
        "explanation": score.get("explanation"),
        "cleaningStatus": score.get("cleaningStatus"),
        "weatherSnapshot": fetch.get("weather"),
        "updatedAt": clock.utc_now_iso(),
    }
    if cadence.get("updated") and segment.get("lastCleanedAt"):
        fields["cadenceObservedForCleaningAt"] = segment["lastCleanedAt"]
    repo.update_segment(str(validation["segmentId"]), fields)
    completed = {
        "status": models.COMPLETED,
        "completedAt": clock.utc_now_iso(),
        "visionStatus": analyse.get("visionStatus", "SKIPPED"),
        "vision": analyse.get("vision"),
        "weatherStatus": fetch.get("weatherStatus", "FALLBACK"),
        "weather": fetch.get("weather"),
        "disagreement": score.get("disagreement", False),
        "priorityScore": score.get("priorityScore"),
        "priorityLevel": score.get("priorityLevel"),
    }
    if not repo.complete_inspection(inspection_id, completed):
        current = repo.get_inspection(inspection_id)
        return _done(inspection_id, str(current["status"]), "SKIPPED_STALE")
    return _done(inspection_id, models.COMPLETED, "APPLIED")
