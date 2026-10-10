"""Golden-number tests for priority scoring."""

from __future__ import annotations

import pytest

from common import scoring

FULL = {
    "inspector_rating": 3,
    "days_since_cleaned": 10.0,
    "cadence_est_days": 8.0,
    "importance": 4,
    "weather_status": "OK",
    "rain_48h_mm": 0.0,
    "consecutive_dry_days": 7.0,
    "forecast_wind_kmh": 25.0,
    "debris": True,
}


def test_compute_components_golden():
    comp = scoring.compute_components(**FULL)
    assert comp["dust"] == pytest.approx(1.0)
    assert comp["overdue"] == pytest.approx(1.25 / 1.5)
    assert comp["importance"] == pytest.approx(0.8)
    assert comp["weather"] == pytest.approx(0.6 + 0.4 * (25.0 / 30.0))
    assert comp["debris"] == pytest.approx(1.0)


def test_priority_score_golden():
    comp = scoring.compute_components(**FULL)
    assert scoring.priority_score(comp) == 0.912
    assert scoring.priority_level(0.912) == "HIGH"


def test_priority_level_boundaries():
    assert scoring.priority_level(0.70) == "HIGH"
    assert scoring.priority_level(0.699) == "MEDIUM"
    assert scoring.priority_level(0.40) == "MEDIUM"
    assert scoring.priority_level(0.399) == "LOW"
    assert scoring.priority_level(0.0) == "LOW"


def test_dust_none_scores_zero():
    comp = scoring.compute_components(**{**FULL, "inspector_rating": None})
    assert comp["dust"] == 0.0


def test_overdue_never_cleaned_is_one():
    comp = scoring.compute_components(**{**FULL, "days_since_cleaned": None})
    assert comp["overdue"] == 1.0


def test_overdue_capped():
    comp = scoring.compute_components(**{**FULL, "days_since_cleaned": 100.0})
    assert comp["overdue"] == 1.0


def test_weather_rain_scores_zero():
    comp = scoring.compute_components(**{**FULL, "rain_48h_mm": 5.0})
    assert comp["weather"] == 0.0


def test_weather_fallback_scores_half():
    comp = scoring.compute_components(**{**FULL, "weather_status": "FALLBACK"})
    assert comp["weather"] == 0.5


def test_weather_unknown_metrics_fall_back():
    comp = scoring.compute_components(
        **{**FULL, "consecutive_dry_days": None, "forecast_wind_kmh": None}
    )
    assert comp["weather"] == 0.5


def test_debris_false():
    comp = scoring.compute_components(**{**FULL, "debris": False})
    assert comp["debris"] == 0.0


def test_cleaning_status_branches():
    kw = {"last_dust_level": 0, "days_since_cleaned": 2.0, "cadence_est_days": 8.0}
    assert scoring.cleaning_status(last_cleaned_at=None, **kw) == "NEEDS_CLEANING"
    assert (
        scoring.cleaning_status(
            last_cleaned_at="2026-10-01T00:00:00Z",
            last_dust_level=2,
            days_since_cleaned=2.0,
            cadence_est_days=8.0,
        )
        == "NEEDS_CLEANING"
    )
    assert (
        scoring.cleaning_status(
            last_cleaned_at="2026-10-01T00:00:00Z",
            last_dust_level=0,
            days_since_cleaned=9.0,
            cadence_est_days=8.0,
        )
        == "NEEDS_CLEANING"
    )
    assert (
        scoring.cleaning_status(last_cleaned_at="2026-10-08T00:00:00Z", **kw) == "CLEAN"
    )


def test_explanation_golden():
    comp = scoring.compute_components(**FULL)
    inputs = {
        "inspectorRating": 3,
        "daysSinceCleaned": 10.0,
        "cadenceEstDays": 8.0,
        "importance": 4,
        "weatherStatus": "OK",
        "rain48hMm": 0.0,
        "consecutiveDryDays": 7.0,
        "forecastWindKmh": 25.0,
    }
    assert scoring.build_explanation(comp, inputs) == (
        "Heavy deposits · 10 days since cleaning (est. cycle 8.0)"
    )


def test_explanation_phrases():
    base_inputs = {
        "inspectorRating": 0,
        "daysSinceCleaned": None,
        "cadenceEstDays": 8.0,
        "importance": 2,
        "weatherStatus": "FALLBACK",
        "rain48hMm": None,
        "consecutiveDryDays": None,
        "forecastWindKmh": None,
    }
    comp = {
        "dust": 0.0,
        "overdue": 1.0,
        "importance": 0.4,
        "weather": 0.5,
        "debris": 0.0,
    }
    # Weighted: overdue .25 wins, then importance .08.
    assert scoring.build_explanation(comp, base_inputs) == (
        "Never cleaned · Low-importance corridor"
    )
    no_inspection = dict(base_inputs, inspectorRating=None, daysSinceCleaned=1.0)
    comp2 = dict.fromkeys(["dust", "overdue", "importance", "weather", "debris"], 0.0)
    assert scoring.build_explanation(comp2, no_inspection) == (
        "No recent inspection · 1 days since cleaning (est. cycle 8.0)"
    )


def test_explanation_tie_break_order():
    # All weighted components equal (0) -> dust, overdue win by tie-break.
    comp = dict.fromkeys(["dust", "overdue", "importance", "weather", "debris"], 0.0)
    inputs = {
        "inspectorRating": 1,
        "daysSinceCleaned": 2.0,
        "cadenceEstDays": 8.0,
        "importance": 5,
        "weatherStatus": "OK",
        "rain48hMm": 0.0,
        "consecutiveDryDays": 0.0,
        "forecastWindKmh": 0.0,
    }
    assert scoring.build_explanation(comp, inputs) == (
        "Light deposits · 2 days since cleaning (est. cycle 8.0)"
    )


def test_score_segment_end_to_end():
    segment = {
        "segmentId": "SEG-001",
        "importance": 4,
        "cadenceEstDays": 8.0,
        "lastCleanedAt": "2026-09-29T10:30:00Z",
        "lastDustLevel": 3,
    }
    result = scoring.score_segment(
        segment,
        inspector_rating=3,
        weather={
            "rain48hMm": 0.0,
            "consecutiveDryDays": 7.0,
            "forecastWindKmh": 25.0,
        },
        debris=True,
        now="2026-10-09T10:30:00Z",
    )
    assert result.inputs["daysSinceCleaned"] == 10.0
    assert result.priority_score == 0.912
    assert result.priority_level == "HIGH"
    assert result.cleaning_status == "NEEDS_CLEANING"
    assert result.weights == {
        "dust": 0.35,
        "overdue": 0.25,
        "importance": 0.20,
        "weather": 0.10,
        "debris": 0.10,
    }
    assert "Heavy deposits" in result.explanation
