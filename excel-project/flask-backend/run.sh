#!/bin/sh
# Backwards-compatible launcher.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$ROOT/start.sh" "$@"
