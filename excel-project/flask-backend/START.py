#!/usr/bin/env python3
"""
Excel Schools - Simple Startup Script
Run this file to start the Flask application.
"""

import os
import sys

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app import app, db

print("=" * 60)
print("Excel Group of Schools - Flask Backend")
print("Version 2.1.0")
print("=" * 60)

# Initialize database
with app.app_context():
    db.create_all()
    print("✓ Database ready")

print("✓ Server starting...")
print()
print("Open in browser:")
print("  → http://127.0.0.1:5000")
print("  → http://127.0.0.1:5000/sync")
print()
print("Press CTRL+C to stop")
print("=" * 60)
print()

app.run(host="127.0.0.1", port=5000, debug=True)