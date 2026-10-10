"""Cleaning-cadence estimation: pure exponentially weighted average.

``new = (1 - alpha) * old + alpha * observed`` with alpha 0.3, starting at
8.0 days, clamped to [1, 30]. Each cleaning cycle teaches the estimate
exactly once: an inspection updates the estimate only when the rating is
>= 2, a previous cleaning exists strictly before the inspection, and the
idempotency marker differs from that cleaning's timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass

from common import clock, config


@dataclass(frozen=True)
class CadenceResult:
    cadence_est_days: float
    previous_cadence_est_days: float
    updated: bool
    observed_days: float | None
    reason: str


def update_cadence(
    *,
    current: float,
    last_cleaned_at: str | None,
    inspected_at: str,
    inspector_rating: int,
    observed_marker: str | None,
) -> CadenceResult:
    """Compute (not store) the new cadence estimate.

    ``observed_marker`` is the segment's ``cadenceObservedForCleaningAt``;
    equality with ``last_cleaned_at`` means this cycle already taught the
    estimate. Reasons: "updated", "rating_below_threshold",
    "no_previous_cleaning", "cleaning_not_before_inspection",
    "already_observed".
    """
    if inspector_rating < config.CADENCE_MIN_RATING:
        return CadenceResult(current, current, False, None, "rating_below_threshold")
    if not last_cleaned_at:
        return CadenceResult(current, current, False, None, "no_previous_cleaning")
    inspection_time = clock.parse_iso(inspected_at)
    cleaned_time = clock.parse_iso(last_cleaned_at)
    if cleaned_time >= inspection_time:
        return CadenceResult(
            current, current, False, None, "cleaning_not_before_inspection"
        )
    observed = round((inspection_time - cleaned_time).total_seconds() / 86400.0, 3)
    if observed_marker is not None and observed_marker == last_cleaned_at:
        return CadenceResult(current, current, False, observed, "already_observed")
    updated = (1.0 - config.CADENCE_ALPHA) * current + config.CADENCE_ALPHA * observed
    updated = round(
        max(config.CADENCE_MIN_DAYS, min(config.CADENCE_MAX_DAYS, updated)), 2
    )
    return CadenceResult(updated, current, True, observed, "updated")
