"""FetchWeather: MVP stub, always FALLBACK (neutral 0.5). Never raises."""

from __future__ import annotations

from typing import Any

from common import log, providers, repo
from common.workflow_state import workflow_step

logger = log.get_logger("fetch-weather")


def _fallback() -> dict[str, Any]:
    return {"step": "fetch_weather", "weatherStatus": "FALLBACK", "weather": None}


@workflow_step("fetch_weather")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        validation = event.get("validation") or {}
        if validation.get("ignored") or not validation.get("valid"):
            return _fallback()
        inspection = repo.get_inspection(str(validation["inspectionId"]))
        if inspection is None:
            return _fallback()
        weather = providers.get_weather(
            latitude=float(inspection["latitude"]),
            longitude=float(inspection["longitude"]),
        )
        return {"step": "fetch_weather", "weatherStatus": "OK", "weather": weather}
    except Exception as exc:  # noqa: BLE001 - never raises by contract
        log.log_event(logger, "warning", "weather fallback", error=str(exc))
        return _fallback()
