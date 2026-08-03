"""Windows executable entry point for the offline Excel Schools app.

This launcher runs the central LAN server: it listens on 0.0.0.0 so every
device on the same network can open the app and feed data into the one
database stored on this computer.

LAN connectivity is handled here, not just in the app:

  * The server always binds 0.0.0.0 (all network interfaces) in LAN mode.
  * When run as administrator it creates a PORT-BASED Windows Firewall allow
    rule. Port-based rules are required for PyInstaller one-file executables,
    because the actual listening process runs from a temporary folder and a
    rule scoped to the EXE path does not match it.
  * Every incoming request is printed to the console so the admin can see
    client devices connecting.
  * ``--diagnose`` prints network addresses, firewall rule state and network
    profile so connection problems can be fixed quickly.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

FIREWALL_RULE_NAME = 'Excel Schools LAN Server'
DEFAULT_PORT = 5000


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
    port = requested_port or int(os.environ.get('EXCEL_SCHOOLS_PORT', str(DEFAULT_PORT)))
    return data_dir, port


def lan_addresses() -> list[str]:
    """Return usable IPv4 addresses other devices can use on the LAN."""
    addresses: set[str] = set()
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
            if not address.startswith('127.') and not address.startswith('169.254.'):
                addresses.add(address)
    except OSError:
        pass
    # Fallback: ask the OS for every non-loopback IPv4 address.
    if os.name == 'nt':
        code, output = run_command([
            'powershell', '-NoProfile', '-Command',
            "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { "
            "$_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' "
            "-and $_.PrefixOrigin -ne 'WellKnown' } | "
            "ForEach-Object { $_.IPAddress }",
        ])
        if code == 0:
            for line in output.splitlines():
                line = line.strip()
                if line and not line.startswith('127.'):
                    addresses.add(line)
    return sorted(addresses)


def port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def run_command(args: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return result.returncode, (result.stdout or '') + (result.stderr or '')
    except Exception as exc:  # pragma: no cover - defensive
        return -1, str(exc)


def is_admin() -> bool:
    if os.name != 'nt':
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def configure_firewall(port: int, include_public: bool = False) -> tuple[bool, str]:
    """Open the Windows Firewall for the server port.

    Uses a PORT-BASED rule (no ``program=`` filter): the PyInstaller one-file
    EXE listens from a child process running in a temporary folder, so rules
    scoped to the EXE path never match and clients are silently blocked.
    """
    if os.name != 'nt':
        return False, 'Firewall configuration is only supported on Windows.'
    if not is_admin():
        return False, 'Not running as administrator; the firewall rule was not changed.'
    profiles = 'private,domain' + (',public' if include_public else '')
    run_command(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', f'name={FIREWALL_RULE_NAME}'])
    code, output = run_command([
        'netsh', 'advfirewall', 'firewall', 'add', 'rule',
        f'name={FIREWALL_RULE_NAME}',
        'dir=in', 'action=allow', 'protocol=TCP',
        f'localport={port}', f'profile={profiles}', 'enable=yes',
    ])
    if code == 0:
        return True, f'Windows Firewall is open for TCP port {port} on profiles: {profiles}.'
    return False, f'Could not create the firewall rule: {output.strip()}'


def connection_profiles() -> list[tuple[str, str]]:
    """Return (network name, category) pairs of active Windows networks."""
    if os.name != 'nt':
        return []
    code, output = run_command([
        'powershell', '-NoProfile', '-Command',
        "Get-NetConnectionProfile | Where-Object { $_.IPv4Connectivity -ne 'Disconnected' } | "
        "ForEach-Object { $_.Name + '|' + $_.NetworkCategory }",
    ])
    if code != 0:
        return []
    profiles = []
    for line in output.splitlines():
        if '|' in line:
            name, category = line.strip().split('|', 1)
            profiles.append((name, category))
    return profiles


def firewall_rule_state() -> str:
    if os.name != 'nt':
        return 'Not applicable (not Windows).'
    code, output = run_command([
        'netsh', 'advfirewall', 'firewall', 'show', 'rule', f'name={FIREWALL_RULE_NAME}',
    ])
    if code != 0:
        return f'No rule named "{FIREWALL_RULE_NAME}" exists yet.'
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return '\n'.join(lines) if lines else f'No rule named "{FIREWALL_RULE_NAME}" exists yet.'


def port_holders(port: int) -> str:
    """Find which process(es) are currently using the port."""
    code, output = run_command(['netstat', '-ano', '-p', 'TCP'])
    if code != 0:
        return 'Could not run netstat.'
    holders = []
    for line in output.splitlines():
        if f':{port}' in line and ('LISTENING' in line or 'ESTABLISHED' in line):
            holders.append(line.strip())
    return '\n'.join(holders) if holders else f'Nothing is listening on TCP port {port}.'


class AccessLogger:
    """WSGI middleware that prints one line per client request.

    The school network admin sees every device that connects, which makes it
    obvious when clients are (or are not) reaching the server.
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        started = time.time()

        def _start_response(status, headers, exc_info=None):
            try:
                remote = environ.get('REMOTE_ADDR', '-')
                method = environ.get('REQUEST_METHOD', '-')
                path = environ.get('PATH_INFO', '-')
                elapsed = int((time.time() - started) * 1000)
                print(
                    f'[{datetime.now().strftime("%H:%M:%S")}] {remote} '
                    f'{method} {path} -> {status} ({elapsed} ms)',
                    flush=True,
                )
            except Exception:
                pass
            return start_response(status, headers, exc_info)

        return self.wsgi_app(environ, _start_response)


def open_browser_when_ready(url: str) -> None:
    for _ in range(60):
        try:
            with socket.create_connection(('127.0.0.1', int(url.rsplit(':', 1)[1])), timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def run_diagnostics(port: int) -> None:
    print('=' * 62)
    print(' Excel Schools - LAN Diagnostics')
    print('=' * 62)

    print('\n[1/4] Addresses for client devices:')
    addresses = lan_addresses()
    if addresses:
        for address in addresses:
            print(f'   http://{address}:{port}')
    else:
        print('   No LAN IPv4 address detected. Run:  ipconfig')

    print('\n[2/4] Active Windows network profiles:')
    profiles = connection_profiles()
    if profiles:
        for name, category in profiles:
            marker = '  <-- WARNING: Public blocks clients by default' if category == 'Public' else ''
            print(f'   {name}  ({category}){marker}')
        if any(category == 'Public' for _, category in profiles):
            print('   Fix: Settings > Network & Internet > Wi-Fi/Ethernet > set to "Private",')
            print('   or rerun setup-lan-server.bat with EXCEL_SCHOOLS_ALLOW_PUBLIC_PROFILE=1.')
    else:
        print('   Could not read network profiles (or not Windows).')

    print('\n[3/4] Windows Firewall rule for the server:')
    print('   ' + firewall_rule_state().replace('\n', '\n   '))

    print('\n[4/4] Port state:')
    print('   ' + port_holders(port).replace('\n', '\n   '))

    print('\nQuick fixes for "clients cannot connect":')
    print('   1. On this computer run  setup-lan-server.bat  as Administrator (opens the firewall).')
    print('   2. Make sure this computer is on a Private network, not Public.')
    print('   3. Connect the server to the router by cable if clients are on Wi-Fi.')
    print('   4. Check the router: disable "AP isolation" / "client isolation".')
    print('   5. Check antivirus firewalls (Avast, Kaspersky, etc.) for extra blocks.')
    print('   6. From a client run:  test-client.bat <server IP>')
    print('=' * 62)


def main() -> int:
    parser = argparse.ArgumentParser(description='Excel Schools Offline Windows server')
    parser.add_argument('--verify-production-server', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--diagnose', action='store_true',
                        help='Print network/firewall diagnostics and exit.')
    parser.add_argument('--lan', action='store_true',
                        help='Force LAN server mode: listen on 0.0.0.0 and open the firewall when elevated.')
    parser.add_argument('--allow-public-firewall', action='store_true',
                        help='Also open the firewall for the Public network profile '
                             '(default: Private + Domain only).')
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

    if args.diagnose:
        run_diagnostics(port)
        return 0

    # LAN mode: always listen on every network interface.
    host = '0.0.0.0' if (args.lan or args.host in ('0.0.0.0', '::', '')) else args.host
    lan_mode = host == '0.0.0.0'

    if not port_available(host, port):
        print(f'ERROR: TCP port {port} is already in use.')
        print(port_holders(port))
        print('Close the other program, or choose another port with:')
        print('  set EXCEL_SCHOOLS_PORT=8080')
        input('Press Enter to close...')
        return 1

    if lan_mode:
        ok, message = configure_firewall(
            port, include_public=args.allow_public_firewall
            or os.environ.get('EXCEL_SCHOOLS_ALLOW_PUBLIC_PROFILE', '0').lower() == '1'
        )
        print(message)
        if not ok and is_admin() is False:
            print('To let client devices through the Windows Firewall, run once as administrator:')
            print('  setup-lan-server.bat')
        print()

    # Imports happen after environment setup so SQLite and uploads are stored
    # outside PyInstaller's temporary extraction directory.
    from app import app, init_db

    with app.app_context():
        init_db()

    url = f'http://127.0.0.1:{port}'
    print('=' * 62)
    print(' Excel Schools Offline - Waitress Production WSGI Server')
    print(f' This computer: {url}')
    if lan_mode:
        addresses = lan_addresses()
        if addresses:
            print(' Other devices on the same network:')
            for address in addresses:
                print(f'   http://{address}:{port}')
        else:
            print(' LAN address was not detected. Run ipconfig to find the IPv4 address.')
        print()
        print(' Cannot connect from another device? Run on this computer as Administrator:')
        print('   setup-lan-server.bat')
    print(f' Data: {data_dir}')
    print(' Keep this window open. All devices feed data into this one database.')
    print(' Every request from a client device is printed below.')
    print(' Press Ctrl+C to stop the server.')
    print('=' * 62)

    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()

    threads = int(os.environ.get('EXCEL_SCHOOLS_THREADS', '8'))
    app.wsgi_app = AccessLogger(app.wsgi_app)
    try:
        serve(app, host=host, port=port, threads=threads, channel_timeout=120)
    except KeyboardInterrupt:
        print('\nExcel Schools stopped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
