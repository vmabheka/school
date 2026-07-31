"""Windows executable entry point for the offline Excel Schools app."""

from __future__ import annotations

import argparse
import os
import secrets
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


def configure_runtime(requested_port: int | None = None) -> tuple[Path, int]:
    data_dir = application_data_dir()
    upload_dir = data_dir / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    secret_file = data_dir / 'session-secret.txt'
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(64), encoding='utf-8')
    os.environ.setdefault('DEPLOYMENT_MODE', 'offline')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///' + (data_dir / 'excel_schools.db').as_posix())
    os.environ.setdefault('UPLOAD_FOLDER', str(upload_dir))
    os.environ.setdefault('SECRET_KEY', secret_file.read_text(encoding='utf-8').strip())
    port = requested_port or int(os.environ.get('EXCEL_SCHOOLS_PORT', '5000'))
    return data_dir, port


def lan_addresses() -> list[str]:
    """Return usable IPv4 addresses other devices can use on the LAN."""
    addresses = set()
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = result[4][0]
            if not address.startswith('127.') and not address.startswith('169.254.'):
                addresses.add(address)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            address = sock.getsockname()[0]
            if not address.startswith('127.'):
                addresses.add(address)
    except OSError:
        pass
    return sorted(addresses)


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
    parser = argparse.ArgumentParser(description='Excel Schools Offline Windows server')
    parser.add_argument('--verify-production-server', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--host', default=os.environ.get('EXCEL_SCHOOLS_HOST', '0.0.0.0'))
    parser.add_argument('--port', type=int, default=None)
    args = parser.parse_args()

    # Importing Waitress here is intentional: PyInstaller includes it in the
    # executable and the build script verifies this import in the frozen EXE.
    import waitress
    from waitress import serve

    if args.verify_production_server:
        version = getattr(waitress, '__version__', None)
        if not version:
            try:
                from importlib.metadata import version as package_version
                version = package_version('waitress')
            except Exception:
                version = 'bundled'
        print(f'PRODUCTION_WSGI_SERVER=Waitress {version}')
        print('PRODUCTION_WSGI_STATUS=embedded-and-ready')
        return 0

    data_dir, port = configure_runtime(args.port)
    host = args.host
    if not port_available(host, port):
        print(f'Port {port} is already in use. Close the other instance or set EXCEL_SCHOOLS_PORT.')
        input('Press Enter to close...')
        return 1

    # Imports happen after environment setup so SQLite and uploads are stored
    # outside PyInstaller's temporary extraction directory.
    from app import app, init_db

    with app.app_context():
        init_db()

    url = f'http://127.0.0.1:{port}'
    print('=' * 62)
    print(' Excel Schools Offline - Waitress Production WSGI Server')
    print(f' This computer: {url}')
    if host in ('0.0.0.0', '::'):
        addresses = lan_addresses()
        if addresses:
            print(' Other devices on the same network:')
            for address in addresses:
                print(f'   http://{address}:{port}')
        else:
            print(' LAN address was not detected. Run ipconfig to find the IPv4 address.')
    print(f' Data: {data_dir}')
    print(' Keep this window open. All devices feed data into this one database.')
    print(' Press Ctrl+C to stop the server.')
    print('=' * 62)
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    try:
        serve(app, host=host, port=port, threads=8, channel_timeout=120)
    except KeyboardInterrupt:
        print('\nExcel Schools stopped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
