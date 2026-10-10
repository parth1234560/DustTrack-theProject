"""AnalyseImage: MVP stub, always SKIPPED. Never raises."""

from __future__ import annotations

from typing import Any

from common import log, providers, repo
from common.workflow_state import workflow_step

logger = log.get_logger("analyse-image")


def _skipped(reason: str) -> dict[str, Any]:
    return {
        "step": "analyse_image",
        "visionStatus": "SKIPPED",
        "vision": None,
        "skipReason": reason,
    }


@workflow_step("analyse_image")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        validation = event.get("validation") or {}
        if validation.get("ignored") or not validation.get("valid"):
            return _skipped("ignored")
        inspection = repo.get_inspection(str(validation["inspectionId"]))
        if inspection is None:
            return _skipped("inspection_missing")
        vision = providers.get_vision(
            bucket=str(validation["bucket"]),
            key=str(validation["photoKey"]),
            content_type=str(inspection["fileType"]),
        )
        return {"step": "analyse_image", "visionStatus": "OK", "vision": vision}
    except Exception as exc:  # noqa: BLE001 - never raises by contract
        log.log_event(logger, "warning", "vision skipped", error=str(exc))
        return _skipped("provider_unavailable")
