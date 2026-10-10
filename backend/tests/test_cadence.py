"""Tests for every cadence update / no-update branch."""

from __future__ import annotations

from common import cadence

INSPECTED = "2026-10-09T10:30:00Z"
CLEANED_10_DAYS_AGO = "2026-09-29T10:30:00Z"


def _update(**overrides):
    kw = {
        "current": 8.0,
        "last_cleaned_at": CLEANED_10_DAYS_AGO,
        "inspected_at": INSPECTED,
        "inspector_rating": 3,
        "observed_marker": None,
    }
    kw.update(overrides)
    return cadence.update_cadence(**kw)


def test_update_golden():
    # new = 0.7*8 + 0.3*10 = 8.6
    result = _update()
    assert result.updated is True
    assert result.cadence_est_days == 8.6
    assert result.previous_cadence_est_days == 8.0
    assert result.observed_days == 10.0
    assert result.reason == "updated"


def test_update_clamped_high():
    result = _update(current=30.0, last_cleaned_at="2026-06-01T00:00:00Z")
    assert result.cadence_est_days == 30.0
    assert result.updated is True


def test_update_clamped_low():
    result = _update(
        current=1.0,
        last_cleaned_at="2026-10-09T10:00:00Z",
        inspected_at="2026-10-09T10:30:00Z",
    )
    assert result.cadence_est_days == 1.0
    assert result.updated is True


def test_no_update_rating_below_threshold():
    result = _update(inspector_rating=1)
    assert result.updated is False
    assert result.cadence_est_days == 8.0
    assert result.observed_days is None
    assert result.reason == "rating_below_threshold"


def test_no_update_never_cleaned():
    result = _update(last_cleaned_at=None)
    assert result.updated is False
    assert result.reason == "no_previous_cleaning"


def test_no_update_cleaning_not_before_inspection():
    result = _update(last_cleaned_at=INSPECTED)
    assert result.updated is False
    assert result.reason == "cleaning_not_before_inspection"
    future = _update(last_cleaned_at="2026-10-10T00:00:00Z")
    assert future.updated is False
    assert future.reason == "cleaning_not_before_inspection"


def test_no_update_already_observed():
    result = _update(observed_marker=CLEANED_10_DAYS_AGO)
    assert result.updated is False
    assert result.reason == "already_observed"
    assert result.observed_days == 10.0
    assert result.cadence_est_days == 8.0


def test_update_when_marker_differs():
    result = _update(observed_marker="2026-09-01T00:00:00Z")
    assert result.updated is True
    assert result.reason == "updated"
