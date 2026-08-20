#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
ENV_FILE=${ENV_FILE:-.env.production}
COMPOSE_FILE=${COMPOSE_FILE:-compose.production.yml}

if ! command -v docker >/dev/null 2>&1; then
    echo 'Docker is required but was not found.' >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo 'The Docker Compose plugin is required.' >&2
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    python3 generate-production-env.py --output "$ENV_FILE"
    echo "Edit $ENV_FILE, set SYNC_API_KEY and public domain values, then run this script again." >&2
    exit 2
fi

chmod 600 "$ENV_FILE"
if grep -Eq '(^|=)(REPLACE_|change-this|edusync26)' "$ENV_FILE"; then
    echo "$ENV_FILE still contains placeholder or unsafe values." >&2
    exit 1
fi
if ! grep -Eq '^DEPLOYMENT_MODE=online$' "$ENV_FILE"; then
    echo 'DEPLOYMENT_MODE must be online.' >&2
    exit 1
fi
if ! grep -Eq '^SYNC_ENDPOINT=https://.+/wp-json/excel-schools/v2/?$' "$ENV_FILE"; then
    echo 'SYNC_ENDPOINT must be the HTTPS WordPress REST namespace ending in /wp-json/excel-schools/v2.' >&2
    exit 1
fi
if ! grep -Eq '^SYNC_API_KEY=.{16,}$' "$ENV_FILE"; then
    echo 'SYNC_API_KEY must be set to the WordPress sync key.' >&2
    exit 1
fi

# Render first so missing/interpolation errors fail before changing services.
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/dev/null
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build --pull web
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans

APP_PORT=$(sed -n 's/^APP_PORT=//p' "$ENV_FILE" | tail -1)
APP_PORT=${APP_PORT:-8000}
echo "Waiting for application health on 127.0.0.1:$APP_PORT..."
attempt=0
while [ "$attempt" -lt 60 ]; do
    if python3 - "$APP_PORT" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

with urllib.request.urlopen(f'http://127.0.0.1:{sys.argv[1]}/healthz', timeout=3) as response:
    payload = json.load(response)
    if response.status != 200 or payload.get('status') != 'ok':
        raise SystemExit(1)
PY
    then
        echo 'Production deployment is healthy.'
        docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
        exit 0
    fi
    attempt=$((attempt + 1))
    sleep 2
done

echo 'Deployment did not become healthy. Recent web logs:' >&2
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --tail=100 web >&2
exit 1
