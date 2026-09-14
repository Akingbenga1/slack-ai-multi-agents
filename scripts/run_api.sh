#!/usr/bin/env bash
# Dev API — reload only application code (not .venv / site-packages).
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run uvicorn api.app.main:app \
  --host 127.0.0.1 \
  --port "${PORT:-8000}" \
  --reload \
  --reload-dir api
