#!/usr/bin/env bash
# Backend checks: lint, format, tests. Non-zero exit on any failure.
# Uses PYTHON (default "python"), e.g. PYTHON=.venv/bin/python or
# PYTHON=.venv/Scripts/python.exe on Windows (venv activated or not).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
"$PY" -m ruff check src/ tests/ scripts/seed_segments.py
"$PY" -m ruff format --check src/ tests/ scripts/seed_segments.py
"$PY" -m pytest tests/ -q -p no:cacheprovider
