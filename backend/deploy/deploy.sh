#!/usr/bin/env bash
# Runs on the VPS after CI has rsynced the code into place.
set -euo pipefail

APP_DIR=/opt/clippit/backend
cd "$APP_DIR"

[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# Reads DATABASE_URL from the server's .env (never in the repo).
.venv/bin/alembic upgrade head

sudo systemctl restart clippit-api

for _ in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    echo "healthy"
    exit 0
  fi
  sleep 2
done

echo "Service did not become healthy; recent logs:" >&2
sudo journalctl -u clippit-api -n 60 --no-pager >&2
exit 1
