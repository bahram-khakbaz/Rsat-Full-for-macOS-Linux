#!/bin/bash
set -euo pipefail
umask 077
export PATH="${RSAT_LAUNCHER_TEST_BIN:-/opt/homebrew/bin:/usr/local/bin}:/usr/bin:/bin:/usr/sbin:/sbin"
repo=${1:?Missing RSAT project directory}
cd "$repo"
if [[ ! -f .env || ! -f docker-compose.yml ]]; then
  echo 'RSAT project or .env is missing. Keep the installed work folder in place.' >&2
  exit 1
fi
if ! command -v docker >/dev/null || ! command -v colima >/dev/null; then
  echo 'Docker CLI or Colima is missing. Restore the installed Homebrew dependencies.' >&2
  exit 1
fi
# Always use the original profile/project so the existing database is reused.
if ! docker --context colima info >/dev/null 2>&1; then
  echo 'Starting Docker with the existing Colima profile...'
  colima start default --activate=false
fi
ready=false
for ((attempt=0; attempt<120; attempt++)); do
  if docker --context colima info >/dev/null 2>&1; then ready=true; break; fi
  sleep 2
done
if [[ "$ready" != true ]]; then echo 'Docker did not become ready.' >&2; exit 1; fi
echo 'Starting RSAT and checking service health...'
docker --context colima compose --project-name rsat-full-for-macos-linux up -d --no-build --pull never --wait --wait-timeout 180
for ((attempt=0; attempt<30; attempt++)); do
  if curl --fail --silent --max-time 5 http://localhost:8080/api/health >/dev/null; then
    echo 'RSAT READY — http://localhost:8080'
    exit 0
  fi
  sleep 2
done
echo 'RSAT web endpoint did not become ready. Check RSAT-startup.log.' >&2
exit 1
