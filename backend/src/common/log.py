"""Structured JSON logging for Lambda handlers.

Every line is a JSON object with level/logger/message plus caller-supplied
context fields. Keys that look sensitive (tokens, presigned URLs, JWT
claims, secrets) are redacted automatically as a safety net -- callers must
still avoid passing them in the first place.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

_CONFIGURED: set[str] = set()

SENSITIVE_MARKERS: tuple[str, ...] = (
    "token",
    "authorization",
    "secret",
    "password",
    "cookie",
    "jwt",
    "claim",
    "presigned",
    "upload",
    "imageurl",
    "download",
)


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SENSITIVE_MARKERS)


def redact(fields: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of fields with sensitive values replaced."""
    return {k: ("[redacted]" if _is_sensitive(k) else v) for k, v in fields.items()}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        ctx = getattr(record, "context", None)
        if isinstance(ctx, dict):
            payload.update(redact(ctx))
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a JSON-formatted logger (idempotent per name)."""
    logger = logging.getLogger(name)
    if name not in _CONFIGURED:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED.add(name)
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, level, logging.INFO))
    return logger


def log_event(logger: logging.Logger, level: str, message: str, **fields: Any) -> None:
    """Log one structured JSON line; sensitive keys are redacted."""
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        message,
        extra={"context": redact(fields)},
    )
