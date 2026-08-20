#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
ENV_FILE=${ENV_FILE:-.env.production}
COMPOSE_FILE=${COMPOSE_FILE:-compose.production.yml}
BACKUP_DIR=${BACKUP_DIR:-./backups}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)

[ -f "$ENV_FILE" ] || { echo "$ENV_FILE does not exist." >&2; exit 1; }
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

DB_BACKUP="$BACKUP_DIR/database-$STAMP.sql.gz"
UPLOAD_BACKUP="$BACKUP_DIR/uploads-$STAMP.tar.gz"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip -9 > "$DB_BACKUP"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T web \
    tar czf - -C /app/static/uploads . > "$UPLOAD_BACKUP"

[ -s "$DB_BACKUP" ] || { echo 'Database backup is empty.' >&2; exit 1; }
[ -s "$UPLOAD_BACKUP" ] || { echo 'Upload backup is empty.' >&2; exit 1; }
sha256sum "$DB_BACKUP" "$UPLOAD_BACKUP" > "$BACKUP_DIR/checksums-$STAMP.sha256"
echo "Backups created in $BACKUP_DIR ($STAMP)."
