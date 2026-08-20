#!/bin/sh
# MobiSchola launcher for Linux/macOS.
# Installs Gunicorn in .venv, initializes the database, then serves wsgi:app.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"

printf '%s\n' '=================================================='
printf '%s\n' '  MobiSchola - WSGI Startup'
printf '%s\n' '=================================================='

printf '\n[1/3] Installing/updating the Gunicorn WSGI server...\n'
./install-wsgi-server.sh

printf '\n[2/3] Initializing/upgrading the database...\n'
.venv/bin/python - <<'PY'
from app import app, init_db

with app.app_context():
    init_db()
print('Database initialized successfully.')
PY

# The shared Gunicorn configuration defaults to localhost:8000 for production.
# This convenience launcher retains the historical local-network port 5000.
GUNICORN_BIND=${GUNICORN_BIND:-0.0.0.0:5000}
export GUNICORN_BIND

printf '\n[3/3] Starting Gunicorn WSGI server at http://%s ...\n' "$GUNICORN_BIND"
printf '%s\n' 'Press Ctrl+C to stop the server.'
printf '%s\n' '=================================================='
exec .venv/bin/gunicorn --config gunicorn.conf.py wsgi:app
