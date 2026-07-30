#!/bin/sh
# Install the Gunicorn WSGI server and all application dependencies in a
# dedicated Python virtual environment. Safe to run again during upgrades.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT"
VENV_DIR=${VENV_DIR:-.venv}
PYTHON_BIN=${PYTHON_BIN:-python3}

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "$PYTHON_BIN is required but was not found." >&2
    exit 1
fi

if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
    echo "Python venv support is missing. On Debian/Ubuntu run: sudo apt install python3-venv" >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating Python virtual environment at $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_GUNICORN="$VENV_DIR/bin/gunicorn"

echo 'Upgrading packaging tools...'
"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel

echo 'Installing application dependencies and Gunicorn...'
"$VENV_PYTHON" -m pip install --upgrade -r requirements.txt

if [ ! -x "$VENV_GUNICORN" ]; then
    echo 'Gunicorn installation failed.' >&2
    exit 1
fi

"$VENV_GUNICORN" --version
"$VENV_PYTHON" -m py_compile app.py wsgi.py

cat <<EOF

Gunicorn WSGI server installed successfully.

Development/offline test command:
  $VENV_GUNICORN --config gunicorn.conf.py wsgi:app

Production command (load .env.production through your service/container):
  $VENV_GUNICORN --config gunicorn.conf.py wsgi:app

Do not expose Gunicorn directly to the internet. Place Nginx or another HTTPS
reverse proxy in front of it. See PRODUCTION.md for the complete setup.
EOF
