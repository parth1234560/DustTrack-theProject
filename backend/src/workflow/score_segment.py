"""ScoreSegment: compute via scoring.score_segment. Writes nothing."""

from __future__ import annotations

from typing import Any

from common import log, repo, scoring
from common.workflow_state import workflow_step

logger = log.get_logger("score-segment")


def _disagreement(rating: Any, vision_rating: Any) -> bool:
    if rating is None or vision_rating is None:
        return False
    try:
        return abs(int(rating) - int(vision_rating)) >= 2
    except (TypeError, ValueError):
        return False


@workflow_step("score_segment")
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    validation = event.get("validation") or {}
    if validation.get("ignored"):
        return {"step": "score_segment", "skipped": True}
    inspection = repo.get_inspection(str(validation["inspectionId"]))
    segment = repo.get_segment(str(validation["segmentId"]))
    par = event.get("parallel_results") or [{}, {}]
    fetch = par[1] if len(par) > 1 and isinstance(par[1], dict) else {}
    analyse = par[0] if isinstance(par[0], dict) else {}
    weather = None
    if fetch.get("weatherStatus") == "OK" and isinstance(fetch.get("weather"), dict):
        weather = {"weatherStatus": "OK", **fetch["weather"]}
    rating = inspection["inspectorDustRating"]
    result = scoring.score_segment(
        segment,
        inspector_rating=rating,
        weather=weather,
        debris=bool(inspection.get("debrisReported")),
        now=str(inspection["createdAt"]),
    )
    vision = analyse.get("vision") or {}
    disagreement = _disagreement(rating, vision.get("dustLevel"))
    log.log_event(
        logger, "info", "segment scored", inspectionId=validation["inspectionId"]
    )
    return {
        "step": "score_segment",
        "priorityScore": result.priority_score,
        "priorityLevel": result.priority_level,
        "cleaningStatus": result.cleaning_status,
        "components": result.components,
        "weights": result.weights,
        "inputs": result.inputs,
        "explanation": result.explanation,
        "disagreement": disagreement,
    }
