#!/usr/bin/env bash
# Backend checks: lint, format, tests. Non-zero exit on any failure.
set -euo pipefail
cd "$(dirname "$0")/.."
VENV=".venv/bin"
"$VENV/ruff" check src/ tests/ scripts/seed_segments.py
"$VENV/ruff" format --check src/ tests/ scripts/seed_segments.py
"$VENV/pytest" tests/ -q -p no:cacheprovider
