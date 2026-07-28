#!/bin/bash
# ================================================
# Excel Schools - One-Click Start Script
# ================================================

echo "=================================================="
echo "  Starting Excel Schools Flask Backend"
echo "=================================================="

cd "$(dirname "$0")"

echo ""
echo "→ Installing dependencies (if needed)..."
pip install -r requirements.txt Flask-CORS -q

echo ""
echo "→ Starting server..."
echo ""
echo "Server will be available at:"
echo "   http://127.0.0.1:5000"
echo "   http://127.0.0.1:5000/sync"
echo ""
echo "Press Ctrl+C to stop"
echo "=================================================="

python start_server.py
