"""Central configuration for the DustTrack backend.

Contract: every tunable lives here and nowhere else. Later parts must
import from here instead of introducing competing constants.

Environment variable *names* are final. Values are read at import time
into module constants. :func:`is_enforce_roles` re-reads the environment
on every call so tests can toggle ``ENFORCE_ROLES`` with ``monkeypatch``
without reloading this module.
"""

from __future__ import annotations

import os


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


# --- AWS resources -------------------------------------------------------
INSPECTIONS_TABLE: str = _str("INSPECTIONS_TABLE", "dusttrack-dev-inspections")
SEGMENTS_TABLE: str = _str("SEGMENTS_TABLE", "dusttrack-dev-segments")
CLEANING_EVENTS_TABLE: str = _str(
    "CLEANING_EVENTS_TABLE", "dusttrack-dev-cleaning-events"
)
PHOTO_BUCKET: str = _str("PHOTO_BUCKET", "")
AWS_REGION: str = _str("AWS_REGION", "ap-south-1")

UPLOAD_URL_EXPIRES: int = _int("UPLOAD_URL_EXPIRES", 900)
DOWNLOAD_URL_EXPIRES: int = _int("DOWNLOAD_URL_EXPIRES", 300)
MAX_IMAGE_BYTES: int = _int("MAX_IMAGE_BYTES", 10 * 1024 * 1024)
GPS_MAX_DISTANCE_M: float = _float("GPS_MAX_DISTANCE_M", 150.0)

VISION_PROVIDER: str = _str("VISION_PROVIDER", "none")
WEATHER_PROVIDER: str = _str("WEATHER_PROVIDER", "none")
BEDROCK_MODEL_ID: str = _str("BEDROCK_MODEL_ID", "")
ENFORCE_ROLES: str = _str("ENFORCE_ROLES", "true")
LOG_LEVEL: str = _str("LOG_LEVEL", "INFO")


def is_enforce_roles() -> bool:
    """Return True unless ENFORCE_ROLES is explicitly "false" (live read)."""
    return os.environ.get("ENFORCE_ROLES", ENFORCE_ROLES).strip().lower() != "false"


# --- Scoring -------------------------------------------------------------
WEIGHTS: dict[str, float] = {
    "dust": 0.35,
    "overdue": 0.25,
    "importance": 0.20,
    "weather": 0.10,
    "debris": 0.10,
}
# Tie-break order for the explanation template (largest weighted first).
COMPONENT_ORDER: tuple[str, ...] = (
    "dust",
    "overdue",
    "importance",
    "weather",
    "debris",
)

PRIORITY_HIGH_THRESHOLD: float = 0.70
PRIORITY_MEDIUM_THRESHOLD: float = 0.40

# Overdue is min(daysSinceCleaned / cadence, OVERDUE_CAP) / OVERDUE_CAP.
OVERDUE_CAP: float = 1.5

# Weather component tunables.
RAIN_THRESHOLD_MM: float = 2.0
DRY_DAY_NORMALIZER: float = 7.0
WIND_NORMALIZER_KMH: float = 30.0
WINDY_KMH: float = 20.0
DRY_SPELL_DAYS: float = 3.0
FALLBACK_WEATHER_COMPONENT: float = 0.5

# --- Cadence -------------------------------------------------------------
CADENCE_ALPHA: float = 0.3
CADENCE_DEFAULT_DAYS: float = 8.0
CADENCE_MIN_DAYS: float = 1.0
CADENCE_MAX_DAYS: float = 30.0
# An inspection only teaches the cadence estimate when rating >= this.
CADENCE_MIN_RATING: int = 2

# --- Inspections ---------------------------------------------------------
STATUS_PENDING: str = "PENDING"
STATUS_PROCESSING: str = "PROCESSING"
STATUS_COMPLETED: str = "COMPLETED"
STATUS_REJECTED: str = "REJECTED"
STATUS_FAILED: str = "FAILED"
TERMINAL_STATUSES: frozenset[str] = frozenset(
    {STATUS_COMPLETED, STATUS_REJECTED, STATUS_FAILED}
)

REJECTION_CODES: tuple[str, ...] = (
    "INVALID_IMAGE",
    "IMAGE_TOO_LARGE",
    "INVALID_GPS",
    "DUPLICATE_IMAGE",
    "OBJECT_MISSING",
    "SEGMENT_NOT_FOUND",
)
FAILURE_CODE: str = "INTERNAL_ERROR"

VALID_FILE_TYPES: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")
EXTENSION_FOR_MIME: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MIME_FOR_EXTENSION: dict[str, str] = {v: k for k, v in EXTENSION_FOR_MIME.items()}
PHOTO_KEY_PREFIX: str = "inspections"

VISION_FLAGS: tuple[str, ...] = (
    "debris_pile",
    "kerb_silt",
    "unpaved_shoulder",
    "construction_material",
)
# Flags that count as debris for the debris component.
DEBRIS_FLAGS: frozenset[str] = frozenset({"debris_pile", "construction_material"})

# --- API -----------------------------------------------------------------
LIMIT_DEFAULT: int = 50
LIMIT_MAX: int = 100
NOTES_MAX_LEN: int = 500
# POST .../cleaned rejects cleanedAt more than this far in the future.
CLEANED_FUTURE_SKEW_S: int = 300

INSPECTORS_GROUP: str = "inspectors"
SUPERVISORS_GROUP: str = "supervisors"
