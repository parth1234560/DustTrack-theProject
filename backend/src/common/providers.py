"""Provider extension points (MVP stubs).

Later parts replace these bodies with the real Bedrock / Open-Meteo calls.
Signatures are final: analyse/fetch-weather handlers call exactly these.
"""

from __future__ import annotations

from typing import Any


class ProviderUnavailable(Exception):
    """Raised while a provider has no real implementation yet."""


def get_vision(*, bucket: str, key: str, content_type: str) -> dict[str, Any]:
    """Analyse a photo; raises ProviderUnavailable in the MVP."""
    raise ProviderUnavailable("vision provider not configured")


def get_weather(*, latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch weather for a point; raises ProviderUnavailable in the MVP."""
    raise ProviderUnavailable("weather provider not configured")
