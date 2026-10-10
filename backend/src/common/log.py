"""Structured JSON logging for Lambda handlers.

Every line is a JSON object with level/logger/message plus caller-supplied
context. There is no redaction machinery: callers must never pass tokens,
presigned URLs or JWT claims as context.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

_CONFIGURED: set[str] = set()


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        ctx = getattr(record, "context", None)
        if isinstance(ctx, dict):
            payload.update(ctx)
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
    """Log one structured JSON line with safe context fields only."""
    logger.log(
        getattr(logging, level.upper(), logging.INFO),
        message,
        extra={"context": fields},
    )
