#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Desktop, Rancher Desktop, or Colima first."
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  jwt_secret="$(openssl rand -hex 32)"
  admin_password="$(openssl rand -base64 24 | tr -d '\n' | tr '/+' 'Aa')"
  db_password="$(openssl rand -hex 24)"
  sed -i.bak "s|replace-with-a-long-random-secret|$jwt_secret|" .env
  sed -i.bak "s|replace-with-a-strong-password|$admin_password|" .env
  sed -i.bak "s|replace-with-a-long-random-db-password|$db_password|g" .env
  rm -f .env.bak
  echo
  echo "Generated local admin credentials:"
  echo "  Username: admin"
  echo "  Password: $admin_password"
  echo
  echo "Save this password in your password manager."
else
  echo ".env already exists; keeping current settings."
fi

docker compose up -d --build
echo
echo "RSAT Full Admin Center is available at http://localhost:8080"
