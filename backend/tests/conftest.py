"""Pytest bootstrap: make backend/src importable and reset the clock."""

from __future__ import annotations

import os
import sys

import pytest

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from common import clock


@pytest.fixture(autouse=True)
def _reset_clock():
    clock.set_now(None)
    yield
    clock.set_now(None)
