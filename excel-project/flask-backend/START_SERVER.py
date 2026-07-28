#!/usr/bin/env python3
"""
Excel Schools Flask Backend - Robust Startup Script
Run this file directly to start the server.
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db

def main():
    print("=" * 65)
    print("  Excel Group of Schools - Flask Backend")
    print("  Version: 2.1.0")
    print("=" * 65)
    
    # Initialize database
    with app.app_context():
        db.create_all()
        print("✓ Database initialized successfully")
    
    print("✓ CORS enabled for cross-origin handshake")
    print("✓ Sync routes registered")
    print()
    print("Server URLs:")
    print("  • Main App:        http://127.0.0.1:5000")
    print("  • Sync Center:     http://127.0.0.1:5000/sync")
    print("  • Handshake API:   http://127.0.0.1:5000/api/sync/handshake")
    print()
    print("Default Login: admin / admin123")
    print("=" * 65)
    print()
    
    # Start the server
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )

if __name__ == '__main__':
    main()