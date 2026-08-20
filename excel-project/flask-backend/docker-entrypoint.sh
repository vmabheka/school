#!/bin/sh
set -eu

printf '%s\n' 'Waiting for the production database...'
python - <<'PY'
import os
import time
from sqlalchemy import create_engine, text

url = os.environ['DATABASE_URL']
last_error = None
for attempt in range(60):
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        print('Database is ready.')
        break
    except Exception as exc:
        last_error = exc
        time.sleep(2)
else:
    raise SystemExit(f'Database did not become ready: {last_error}')
PY

printf '%s\n' 'Initializing/upgrading database schema...'
python - <<'PY'
from app import app, init_db

with app.app_context():
    init_db()
print('Database initialization complete.')
PY

exec "$@"
