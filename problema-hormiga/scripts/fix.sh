#!/usr/bin/env bash

set -euo pipefail

echo "==> Ruff autofix"
uv run ruff check --fix .

echo
echo "==> Ruff format"
uv run ruff format .

echo
echo "Automatic fixes completed."
