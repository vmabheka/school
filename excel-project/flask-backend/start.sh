#!/bin/bash
# Excel Schools - Flask Backend Startup Script
# This script installs dependencies and starts the server

set -e

echo "=================================================="
echo "  Excel Group of Schools - Starting Flask Backend"
echo "=================================================="

cd "$(dirname "$0")"

echo ""
echo "[1/4] Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo ""
echo "[2/4] Installing Flask-CORS (for cross-origin handshake)..."
pip install Flask-CORS --quiet

echo ""
echo "[3/4] Initializing database..."
python -c "
from app import app, db, init_db
with app.app_context():
    init_db()
print('Database initialized successfully.')
"

echo ""
echo "[4/4] Starting Flask server..."
echo ""
echo "Server will be available at:"
echo "  → http://127.0.0.1:5000"
echo "  → http://127.0.0.1:5000/sync"
echo ""
echo "Default login: edusync / edusync26"
echo ""
echo "Press Ctrl+C to stop the server."
echo "=================================================="
echo ""

python run.py --host 0.0.0.0 --port 5000 --debug
