#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

if ! command -v npm >/dev/null 2>&1; then
  NODE_VERSION="${NODE_VERSION:-22.14.0}"
  NODE_DIR="/tmp/node-v${NODE_VERSION}-linux-x64"
  if [ ! -x "$NODE_DIR/bin/npm" ]; then
    echo "npm not found; installing Node ${NODE_VERSION}"
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
      | tar -xJ -C /tmp
  fi
  export PATH="${NODE_DIR}/bin:${PATH}"
fi

node -v
npm -v
cd frontend
npm ci
NEXT_OUTPUT=export NEXT_PUBLIC_API_URL= NODE_ENV=production npm run build
