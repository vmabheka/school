# Binding the offline app to WordPress (automated)

Previously, connecting the offline Flask app to the live WordPress site meant
manually copying a secret "sync API key" between two different admin panels
and typing matching URLs into both — easy to get wrong, with no clear error
when it failed. This is now a single command.

## How it works

1. `bind.py` logs into WordPress as a real user using a WordPress
   **Application Password** (not the account's login password).
2. It asks the Excel Schools plugin for the current shared sync key over a
   new authenticated `/wp-json/excel-schools/v2/bind` endpoint — generating
   one if none exists yet, or rotating it if you pass `--rotate-key`.
3. It writes that key straight into the offline app's own database
   (`sync_setting` table), so Flask doesn't need any manual `.env` editing.
4. It verifies the bind by calling WordPress's REST API with the new key and
   reports PASS/FAIL clearly, instead of failing silently later.

Because the offline app always *initiates* the sync calls to WordPress (push
pending changes, pull pending changes), this works even if the offline PC
has no address reachable from the internet — only WordPress needs to be
reachable from wherever the offline app runs.

## One-time setup

1. In WordPress admin, go to **Users → Your Profile → Application
   Passwords**, enter a name like `flask-sync`, and click **Add New
   Application Password**. Copy the generated password (it's shown once).
   * This requires the Excel Schools plugin to be active — it explicitly
     enables Application Passwords even on plain-HTTP sites, since
     WordPress core normally requires HTTPS for this feature.
2. Run the binder from the machine hosting the offline Flask app:

   ```bash
   python bind.py \
     --wp-url https://crm.egs.ac.zw \
     --wp-user admin \
     --wp-app-password "xxxx xxxx xxxx xxxx xxxx xxxx" \
     --flask-db instance/excel_schools.db
   ```

3. Restart the Flask app so it picks up the new `sync_setting` values.
4. In WordPress, go to **Excel Schools → Sync Center** and click
   **Test Connection** — it should report success immediately.

## Re-binding later

Run the same command again any time you:
- move either system to a new URL/host,
- suspect the shared key leaked and want to rotate it (`--rotate-key`),
- restore either database from a backup and the keys drifted apart.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `401 rest_not_logged_in` | Wrong app password, or pasted the login password instead | Re-copy from Users → Application Passwords |
| `esm_manage_sync` capability error | The WP account isn't a Super Admin / Administrator | Use an admin account, or assign the `Excel Schools: Super Admin` role |
| Bind succeeds but "Test Connection" still fails in WP | Flask wasn't restarted after binding | Restart the Flask process |
| Bind script can't reach `--wp-url` at all | Site not publicly reachable from the offline PC, or wrong URL | Confirm the URL loads in a browser from that machine first |
