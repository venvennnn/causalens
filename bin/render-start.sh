#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"

export FRONTEND_DIR="${FRONTEND_DIR:-$ROOT/frontend/out}"
export CORS_ORIGINS="${CORS_ORIGINS:-*}"
export BRIGHTDATA_TRANSPORT="${BRIGHTDATA_TRANSPORT:-http}"
export USE_CACHED_DEMO_ON_FAILURE="${USE_CACHED_DEMO_ON_FAILURE:-true}"

exec gunicorn \
  -k uvicorn.workers.UvicornWorker \
  app.main:app \
  --bind "0.0.0.0:${PORT:-8000}" \
  --timeout 120 \
  --graceful-timeout 30 \
  --workers 1 \
  --proxy-allow-from '*' \
  --forwarded-allow-ips '*'
