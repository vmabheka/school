#!/usr/bin/env python3
"""
Excel Group of Schools - Management System
Startup Script
============================================

Usage:
    python run.py                  # Run in offline mode (default)
    python run.py --online         # Run in online mode
    python run.py --init-only      # Initialize database only
    python run.py --port 8080      # Run on custom port
"""

import argparse
import os
import sys

def main():
    parser = argparse.ArgumentParser(description='Excel Group of Schools Management System')
    parser.add_argument('--online', action='store_true', help='Run in online mode')
    parser.add_argument('--init-only', action='store_true', help='Initialize database only')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on (default: 5000)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    # Set environment
    if args.online:
        os.environ['DEPLOYMENT_MODE'] = 'online'
    
    from app import app, init_db

    # Initialize database
    with app.app_context():
        init_db()
    
    if args.init_only:
        print("Database initialized successfully.")
        return

    mode = app.config['DEPLOYMENT_MODE']
    
    print(f"\n{'='*60}")
    print(f"  Excel Group of Schools - Management System")
    print(f"  Version: 2.0.0")
    print(f"  Deployment Mode: {mode.upper()}")
    print(f"  Server: http://{args.host}:{args.port}")
    print(f"  Default Login: edusync / edusync26")
    print(f"{'='*60}\n")
    
    app.run(
        debug=args.debug,
        host=args.host,
        port=args.port
    )

if __name__ == '__main__':
    main()
