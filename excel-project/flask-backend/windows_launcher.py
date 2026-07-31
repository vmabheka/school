"""Windows executable entry point for the offline Excel Schools app."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def application_data_dir() -> Path:
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home())
    path = base / 'ExcelSchools'
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_runtime() -> tuple[Path, int]:
    data_dir = application_data_dir()
    upload_dir = data_dir / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('DEPLOYMENT_MODE', 'offline')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///' + (data_dir / 'excel_schools.db').as_posix())
    os.environ.setdefault('UPLOAD_FOLDER', str(upload_dir))
    os.environ.setdefault('SECRET_KEY', 'offline-local-excel-schools-session-key')
    port = int(os.environ.get('EXCEL_SCHOOLS_PORT', '5000'))
    return data_dir, port


def port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def open_browser_when_ready(url: str) -> None:
    for _ in range(60):
        try:
            with socket.create_connection(('127.0.0.1', int(url.rsplit(':', 1)[1])), timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def main() -> int:
    data_dir, port = configure_runtime()
    host = os.environ.get('EXCEL_SCHOOLS_HOST', '0.0.0.0')
    if not port_available(host, port):
        print(f'Port {port} is already in use. Close the other instance or set EXCEL_SCHOOLS_PORT.')
        input('Press Enter to close...')
        return 1

    # Imports happen after environment setup so SQLite and uploads are stored
    # outside PyInstaller's temporary extraction directory.
    from app import app, init_db
    from waitress import serve

    with app.app_context():
        init_db()

    url = f'http://127.0.0.1:{port}'
    print('=' * 62)
    print(' Excel Schools Offline')
    print(f' Open: {url}')
    print(f' Data: {data_dir}')
    print(' Keep this window open. Press Ctrl+C to stop the server.')
    print('=' * 62)
    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    try:
        serve(app, host=host, port=port, threads=8, channel_timeout=120)
    except KeyboardInterrupt:
        print('\nExcel Schools stopped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
