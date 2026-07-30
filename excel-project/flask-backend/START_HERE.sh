#!/bin/sh
# One-click Linux/macOS entry point. The main launcher installs and uses
# Gunicorn rather than Flask's development server.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$ROOT/start.sh" "$@"
