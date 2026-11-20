#!/usr/bin/env bash

set -euo pipefail

echo "==> Ruff lint"
uv run ruff check .

echo
echo "==> Ruff format"
uv run ruff format --check .

echo
echo "==> mypy"
uv run mypy src/ant_pathfinding

echo
echo "==> pytest"
uv run pytest \
    --cov=ant_pathfinding \
    --cov-branch \
    --cov-report=term-missing

echo
echo "All quality checks passed."
