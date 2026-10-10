"""Priority scoring: pure functions shared by workflow, API and rescoring.

``priority = 0.35*dust + 0.25*overdue + 0.20*importance + 0.10*weather
+ 0.10*debris`` with every component in [0, 1]. All tunables come from
:mod:`common.config`. No I/O; timestamps accepted as ISO strings or
aware datetimes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from common import clock, config

NEEDS_CLEANING: str = "NEEDS_CLEANING"
CLEAN: str = "CLEAN"

HIGH: str = "HIGH"
MEDIUM: str = "MEDIUM"
LOW: str = "LOW"

_DUST_PHRASES: dict[int, str] = {
    0: "Clean surface",
    1: "Light deposits",
    2: "Moderate deposits",
    3: "Heavy deposits",
}


@dataclass(frozen=True)
class ScoreResult:
    components: dict[str, float]
    weights: dict[str, float]
    inputs: dict[str, Any]
    priority_score: float
    priority_level: str
    cleaning_status: str
    explanation: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _dust_component(inspector_rating: int | None) -> float:
    if inspector_rating is None:
        return 0.0
    return _clamp01(float(max(0, min(3, inspector_rating))) / 3.0)


def _overdue_component(
    days_since_cleaned: float | None, cadence_est_days: float
) -> float:
    if days_since_cleaned is None:
        return 1.0  # never cleaned
    cadence = cadence_est_days if cadence_est_days > 0 else config.CADENCE_DEFAULT_DAYS
    return _clamp01(
        min(days_since_cleaned / cadence, config.OVERDUE_CAP) / config.OVERDUE_CAP
    )


def _importance_component(importance: int) -> float:
    return _clamp01(float(importance) / 5.0)


def _weather_component(
    weather_status: str,
    rain_48h_mm: float | None,
    consecutive_dry_days: float | None,
    forecast_wind_kmh: float | None,
) -> float:
    if weather_status != "OK":
        return config.FALLBACK_WEATHER_COMPONENT
    if rain_48h_mm is not None and rain_48h_mm >= config.RAIN_THRESHOLD_MM:
        return 0.0
    if consecutive_dry_days is None or forecast_wind_kmh is None:
        return config.FALLBACK_WEATHER_COMPONENT
    dry = _clamp01(consecutive_dry_days / config.DRY_DAY_NORMALIZER)
    wind = _clamp01(forecast_wind_kmh / config.WIND_NORMALIZER_KMH)
    return _clamp01(0.6 * dry + 0.4 * wind)


def compute_components(
    *,
    inspector_rating: int | None,
    days_since_cleaned: float | None,
    cadence_est_days: float,
    importance: int,
    weather_status: str,
    rain_48h_mm: float | None = None,
    consecutive_dry_days: float | None = None,
    forecast_wind_kmh: float | None = None,
    debris: bool = False,
) -> dict[str, float]:
    """Compute the five [0, 1] components (key order matches WEIGHTS)."""
    return {
        "dust": _dust_component(inspector_rating),
        "overdue": _overdue_component(days_since_cleaned, cadence_est_days),
        "importance": _importance_component(importance),
        "weather": _weather_component(
            weather_status, rain_48h_mm, consecutive_dry_days, forecast_wind_kmh
        ),
        "debris": 1.0 if debris else 0.0,
    }


def priority_score(components: dict[str, float]) -> float:
    """Weighted sum of components, rounded to 3 decimals."""
    total = sum(config.WEIGHTS[key] * components[key] for key in config.WEIGHTS)
    return round(total, 3)


def priority_level(score: float) -> str:
    """HIGH >= 0.70, MEDIUM >= 0.40, else LOW."""
    if score >= config.PRIORITY_HIGH_THRESHOLD:
        return HIGH
    if score >= config.PRIORITY_MEDIUM_THRESHOLD:
        return MEDIUM
    return LOW


def cleaning_status(
    *,
    last_cleaned_at: str | None,
    last_dust_level: int | None,
    days_since_cleaned: float | None,
    cadence_est_days: float,
) -> str:
    """Pure rule: NEEDS_CLEANING if never cleaned, dusty, or overdue."""
    if last_cleaned_at is None:
        return NEEDS_CLEANING
    if last_dust_level is not None and last_dust_level >= 1:
        return NEEDS_CLEANING
    if days_since_cleaned is not None and days_since_cleaned >= cadence_est_days:
        return NEEDS_CLEANING
    return CLEAN


def _dust_phrase(inspector_rating: int | None) -> str:
    if inspector_rating is None:
        return "No recent inspection"
    return _DUST_PHRASES[max(0, min(3, inspector_rating))]


def _overdue_phrase(days_since_cleaned: float | None, cadence_est_days: float) -> str:
    if days_since_cleaned is None:
        return "Never cleaned"
    days = max(0, round(days_since_cleaned))  # nearest whole day
    return f"{days} days since cleaning (est. cycle {cadence_est_days:.1f})"


def _importance_phrase(importance: int) -> str:
    if importance >= 4:
        return "High-importance corridor"
    if importance == 3:
        return "Medium-importance corridor"
    return "Low-importance corridor"


def _weather_phrase(
    weather_status: str,
    rain_48h_mm: float | None,
    consecutive_dry_days: float | None,
    forecast_wind_kmh: float | None,
) -> str:
    if weather_status != "OK":
        return "weather unavailable"
    if rain_48h_mm is not None and rain_48h_mm >= config.RAIN_THRESHOLD_MM:
        return "recent rain"
    if (
        (rain_48h_mm is None or rain_48h_mm < config.RAIN_THRESHOLD_MM)
        and forecast_wind_kmh is not None
        and forecast_wind_kmh >= config.WINDY_KMH
    ):
        return "dry and windy"
    if (
        consecutive_dry_days is not None
        and consecutive_dry_days >= config.DRY_SPELL_DAYS
    ):
        return "dry spell"
    return "mild conditions"


_PHRASES = ("dust", "overdue", "importance", "weather", "debris")


def build_explanation(components: dict[str, float], inputs: dict[str, Any]) -> str:
    """Template from the TWO largest *weighted* components, joined by " · ".

    Ties break in WEIGHTS order: dust, overdue, importance, weather, debris.
    ``inputs`` carries inspectorRating, daysSinceCleaned, cadenceEstDays,
    importance, weatherStatus, rain48hMm, consecutiveDryDays,
    forecastWindKmh (score_segment always builds this shape).
    """
    weighted = {k: components[k] * config.WEIGHTS[k] for k in config.WEIGHTS}
    order = {k: i for i, k in enumerate(config.COMPONENT_ORDER)}
    top_two = sorted(weighted, key=lambda k: (-weighted[k], order[k]))[:2]
    phrases: dict[str, str] = {
        "dust": _dust_phrase(inputs.get("inspectorRating")),
        "overdue": _overdue_phrase(
            inputs.get("daysSinceCleaned"), inputs.get("cadenceEstDays", 0.0)
        ),
        "importance": _importance_phrase(int(inputs.get("importance", 0))),
        "weather": _weather_phrase(
            inputs.get("weatherStatus", "FALLBACK"),
            inputs.get("rain48hMm"),
            inputs.get("consecutiveDryDays"),
            inputs.get("forecastWindKmh"),
        ),
        "debris": "debris flagged",
    }
    assert set(phrases) == set(_PHRASES)  # keep phrase map and weights in sync
    return " · ".join(phrases[k] for k in top_two)


def _as_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return clock.parse_iso(value)


def score_segment(
    segment: dict[str, Any],
    *,
    inspector_rating: int | None,
    weather: dict[str, Any] | None,
    debris: bool,
    now: datetime | str,
) -> ScoreResult:
    """Score a segment item; pure (no I/O).

    ``weather`` is None for FALLBACK/unknown, else a dict with optional
    ``weatherStatus`` (default "OK") plus ``rain48hMm``,
    ``consecutiveDryDays``, ``forecastWindKmh``. Raises ValueError on
    unparseable stored timestamps.
    """
    moment = _as_datetime(now)
    last_cleaned_at = segment.get("lastCleanedAt")
    cadence = float(segment.get("cadenceEstDays", config.CADENCE_DEFAULT_DAYS))
    importance = int(segment.get("importance", 3))
    last_dust = segment.get("lastDustLevel")

    days: float | None = None
    if last_cleaned_at is not None:
        days = round(
            (moment - clock.parse_iso(last_cleaned_at)).total_seconds() / 86400.0, 3
        )

    snapshot = weather or {}
    status = str(snapshot.get("weatherStatus", "OK" if weather else "FALLBACK"))
    components = compute_components(
        inspector_rating=inspector_rating,
        days_since_cleaned=days,
        cadence_est_days=cadence,
        importance=importance,
        weather_status=status,
        rain_48h_mm=snapshot.get("rain48hMm"),
        consecutive_dry_days=snapshot.get("consecutiveDryDays"),
        forecast_wind_kmh=snapshot.get("forecastWindKmh"),
        debris=debris,
    )
    inputs: dict[str, Any] = {
        "inspectorRating": inspector_rating,
        "daysSinceCleaned": days,
        "cadenceEstDays": cadence,
        "importance": importance,
        "weatherStatus": status,
        "rain48hMm": snapshot.get("rain48hMm"),
        "consecutiveDryDays": snapshot.get("consecutiveDryDays"),
        "forecastWindKmh": snapshot.get("forecastWindKmh"),
        "debris": debris,
        "lastDustLevel": last_dust,
        "neverCleaned": last_cleaned_at is None,
    }
    score = priority_score(components)
    return ScoreResult(
        components=components,
        weights=dict(config.WEIGHTS),
        inputs=inputs,
        priority_score=score,
        priority_level=priority_level(score),
        cleaning_status=cleaning_status(
            last_cleaned_at=last_cleaned_at,
            last_dust_level=last_dust,
            days_since_cleaned=days,
            cadence_est_days=cadence,
        ),
        explanation=build_explanation(components, inputs),
    )
