#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m compileall -q backend/app windows-agent/app
if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm install --no-audit --no-fund && npm run build)
else
  echo "npm not found; frontend build skipped"
fi
if command -v docker >/dev/null 2>&1; then
  docker compose config >/dev/null
else
  echo "docker not found; compose validation skipped"
fi
