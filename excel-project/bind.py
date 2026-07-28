#!/usr/bin/env python3
"""
Excel Schools — automated offline-app <-> WordPress binder.
=============================================================
Run this once (or any time you need to re-bind, e.g. after moving either
system, resetting a password, or rotating the sync key) to connect the
offline Flask app to the live WordPress site with zero manual copy/paste.

What it does, in order:
  1. Logs into WordPress as a real user (via an Application Password —
     no sync key needed yet) and asks the plugin for the current shared
     sync API key (or generates one if none exists / --rotate-key).
  2. Writes that key + the WordPress REST base URL into the offline
     app's own database (sync_setting table) so Flask knows how to
     reach WordPress.
  3. Writes the Flask endpoint URL into WordPress's esm_flask_endpoint
     option so WordPress knows how to reach Flask (only meaningful if
     Flask is reachable *from* WordPress — see --flask-endpoint note).
  4. Verifies the bind by calling an authenticated endpoint on each side
     and reports a clear PASS/FAIL for both directions.

Usage:
    python bind.py \\
        --wp-url https://crm.egs.ac.zw \\
        --wp-user admin --wp-app-password "xxxx xxxx xxxx xxxx xxxx xxxx" \\
        --flask-db /path/to/instance/excel_schools.db \\
        [--flask-endpoint http://<flask-host>:5000] \\
        [--rotate-key]

Notes:
  * --wp-app-password is a WordPress "Application Password", NOT the
    account's normal login password. Create one under
    WordPress Admin -> Users -> Your Profile -> Application Passwords.
  * --flask-endpoint is only useful if WordPress can reach the Flask
    machine over the network (e.g. both on the same LAN/VPN, or Flask
    is exposed on a public port). If the offline PC has no inbound
    address reachable from the server, leave it out — sync still works
    because Flask always *initiates* outbound pushes/pulls to WordPress.
"""
import argparse
import base64
import json
import sqlite3
import sys
import urllib.error
import urllib.request


def http_json(method, url, data=None, headers=None, timeout=15):
    headers = headers or {}
    body = json.dumps(data).encode() if data is not None else None
    if body is not None:
        headers.setdefault('Content-Type', 'application/json')
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {'error': raw}
    except urllib.error.URLError as e:
        return 0, {'error': str(e.reason)}


def basic_auth_header(username, app_password):
    token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    return {'Authorization': f'Basic {token}'}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--wp-url', required=True, help="Base URL of the WordPress site, e.g. https://crm.egs.ac.zw")
    p.add_argument('--wp-user', required=True, help="WordPress username (must have Sync Center access)")
    p.add_argument('--wp-app-password', required=True, help="WordPress Application Password")
    p.add_argument('--flask-db', default='flask-backend/instance/excel_schools.db',
                    help="Path to the offline app's SQLite database")
    p.add_argument('--flask-endpoint', default=None,
                    help="URL WordPress should use to reach Flask (optional — only if reachable)")
    p.add_argument('--rotate-key', action='store_true', help="Generate a brand-new shared sync key")
    args = p.parse_args()

    wp_base = args.wp_url.rstrip('/')
    auth_headers = basic_auth_header(args.wp_user, args.wp_app_password)

    print(f"1) Authenticating to WordPress as '{args.wp_user}' ...")
    status, body = http_json('GET', f"{wp_base}/wp-json/wp/v2/users/me", headers=auth_headers)
    if status != 200:
        print(f"   FAILED ({status}): {body}")
        print("   Check --wp-url, --wp-user, and that --wp-app-password is an Application")
        print("   Password (Users -> Profile -> Application Passwords), not the login password.")
        sys.exit(1)
    print(f"   OK — authenticated as {body.get('name', args.wp_user)}")

    print("2) Requesting shared sync key from the Excel Schools plugin ...")
    payload = {'rotate_key': bool(args.rotate_key)}
    if args.flask_endpoint:
        payload['flask_endpoint'] = args.flask_endpoint
    status, body = http_json('POST', f"{wp_base}/wp-json/excel-schools/v2/bind", data=payload, headers=auth_headers)
    if status != 200 or not body.get('success'):
        print(f"   FAILED ({status}): {body}")
        print("   Make sure the Excel Schools plugin is active and up to date on the site,")
        print("   and that this WordPress user has the 'esm_manage_sync' capability")
        print("   (Super Admin role, or a WP Administrator account).")
        sys.exit(1)
    api_key = body['sync_api_key']
    rest_base = body['rest_base']
    sms_url = body['sms_url']
    print(f"   OK — site: {body.get('site_name')}  portal: {sms_url}")
    print(f"   Shared sync key: {api_key}")

    print(f"3) Writing sync settings into the offline app's database ({args.flask_db}) ...")
    con = sqlite3.connect(args.flask_db)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sync_setting (
        id INTEGER PRIMARY KEY, key VARCHAR(100) UNIQUE NOT NULL,
        value TEXT, description VARCHAR(200))""")
    for key, value, desc in [
        ('sync_endpoint', rest_base, 'WordPress REST API base URL (auto-bound)'),
        ('sync_api_key', api_key, 'Shared sync key with WordPress (auto-bound)'),
    ]:
        cur.execute("INSERT INTO sync_setting (key, value, description) VALUES (?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, description=excluded.description",
                    (key, value, desc))
    con.commit()
    con.close()
    print("   OK — sync_endpoint and sync_api_key saved.")

    print("4) Verifying the bind ...")
    status, body = http_json('GET', f"{rest_base}/sync/pending", headers={'X-ESM-API-Key': api_key})
    wp_ok = status == 200 and isinstance(body, dict) and 'count' in body
    print(f"   WordPress REST reachable with shared key: {'PASS' if wp_ok else 'FAIL'} ({status})")

    print()
    if wp_ok:
        print("BIND SUCCESSFUL.")
        print(f"  - WordPress portal:  {sms_url}")
        print(f"  - WordPress REST:    {rest_base}")
        print(f"  - Shared sync key:   {api_key}")
        print()
        print("Next: start (or restart) the offline Flask app so it picks up the new")
        print("settings, then in WordPress go to Excel Schools -> Sync Center and click")
        print("'Run Full Sync', or just wait for the next scheduled cron run.")
    else:
        print("BIND WROTE SETTINGS BUT VERIFICATION FAILED.")
        print("  Double-check that the WordPress site is publicly reachable at the")
        print(f"  URL you passed ({wp_base}) and that permalinks are enabled")
        print("  (Settings -> Permalinks -> anything other than 'Plain').")
        sys.exit(2)


if __name__ == '__main__':
    main()
