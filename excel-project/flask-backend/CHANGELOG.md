# Changelog

All notable changes to the **Excel Group of Schools** management system.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [2.3.0] — 2026-08-03

### Fixed (Flask app — LAN client access)

- **`windows_launcher.py`**: LAN mode now always binds `0.0.0.0`, prints every
  address client devices should open, and logs each incoming request (IP,
  method, path, status) so the admin can see clients connecting
- **Firewall fix**: `setup-lan-server.bat` now creates a **port-based** Windows
  Firewall allow rule (TCP port, Private + Domain profiles) instead of an
  EXE-path rule — the PyInstaller one-file EXE listens from a temporary child
  process folder, so path-scoped rules never matched and clients were blocked
- **Automatic firewall configuration**: when the EXE is started as
  Administrator it refreshes the port rule itself; otherwise it prints the
  one-time command to run
- **`--diagnose`** mode prints LAN addresses, active Windows network profiles
  (warns when Public), firewall rule state and port holders
- **New `test-client.bat`** (in `dist`): run on a failing client — ping, TCP
  port, and `/healthz` tests with step-by-step fix guidance
- **`START.bat`** prints the LAN URLs clients should use and points to
  `setup-lan-server.bat` for the firewall
- Legacy launchers (`server.py`, `launch.py`, `GO.py`, `run_flask.py`) now
  bind `0.0.0.0` instead of `127.0.0.1` so they also serve the network
- README: full "If client devices cannot connect" troubleshooting section
  (firewall, Private profile, AP isolation, antivirus, port tests)

### Added (earlier rounds, recorded here)

- **Central LAN server mode**: one computer hosts the offline server
  (`--lan`), all other devices feed data into it via the browser
- **Windows offline EXE** (`build-windows-exe.bat` → `dist\ExcelSchools-Offline.exe`)
  embedding the Waitress production WSGI server with `--verify-production-server`
  build-time verification
- **WSGI installers**: `install-wsgi-server.sh` + Gunicorn on Linux/macOS,
  Waitress in `START.bat` on Windows
- **Production deployment**: Docker/PostgreSQL/Gunicorn stack,
  `PRODUCTION.md`, hardened env validation, health checks, backups, Nginx
  reverse-proxy example
- **Debtor filters** (class, grade level, school, fee level) in Flask and
  WordPress portals
- **PDF downloads** for online reports and invoices
- **Teacher portal**: class + subject assignments per teacher (secondary),
  approved primary subjects (English, ChiShona, Mathematics, Social Science,
  PE and Arts, Science and Technology)
- **Complete offline export** for WordPress sync (all models) with manual JSON
  import; bursar sync privileges, class creation, and role-specific dashboards

---

## [2.1.0] — 2026-07-06

### Added (Flask app + WordPress plugin)

#### Debtors Report (sortable + exportable)
- **New route** `/fees/debtors` — sortable, filterable list of all students with outstanding fee balances
- **New route** `/fees/debtors/export` — exports to **CSV / Excel (.xlsx) / PDF** with filters preserved
- 8 sort options: balance (asc/desc), name (asc/desc), class, days overdue (asc/desc), admission #
- 5 filter controls: text search, class, fee level (ECD/Junior/O Level/A Level), scholarship category, minimum balance
- 6 summary stat cards: total debtors, total outstanding, severely overdue (>30d), recently overdue (≤30d), collected so far, scholarship discounts
- Color-coded table rows (red >30d overdue, amber ≤30d, green on-time)
- WordPress equivalent: **Debtors** submenu under Excel Schools → full admin page with the same features (CSV export built-in)
- Sidebar nav link added to base.html; WordPress menu item registered

#### Payment recording (security + UX)
- **Role restriction**: Super admins can NO LONGER record payments. Only `accountant` and `bursar` have access to `/fees/pay`
- **Student search bar with search button**: The payment form now has a dedicated search input + button + reset button + Enter-key shortcut
- Multi-row scrolling `<select>` (size="10") so multiple search matches are visible
- Live match-count status: "Found 3 of 45 students matching 'moyo'"
- Pre-fills balance info when arriving from debtors page (?student_id=N)
- "Fill outstanding balance" one-click button after balance lookup

#### Auto-generated signature (anonymized)
- Stable signature ID like `SIG-CE06DBCB8318` (SHA-256 of receipt # + payment ID + created_at timestamp)
- Renders on receipt page (HTML) AND in the PDF receipt
- **Privacy-respecting display**: no full name shown, no "Auto-Generated Signature" label
- Shows only: **role** (Bursar/Accountant) + **position** + **@username** + **timestamp** + **signature ID**
- WordPress equivalent: same signature block in `generate_receipt_html()`

#### Branding & Color scheme
- **New official logo** deployed: `static/images/egs-logo.png` (the EGS crest — navy + gold)
- **New color scheme** derived from the logo:
  - Primary (deep navy): `#1F2080`
  - Primary dark: `#13145A`
  - Primary light: `#3F4099`
  - Secondary (gold): `#FDEE00`
  - Secondary light: `#FFF266`
  - Accent (orange): `#E85D26`
- Updated Flask `DEFAULT_THEME` and WordPress `ESM_Helpers::get_theme()` defaults
- Login page now displays the actual logo (with white background pill)
- Sidebar shows the logo automatically when `theme.logo_url` is set

#### Theme sync API (Flask ↔ WordPress)
- **Flask**: `GET /api/theme/export` returns theme as JSON
- **Flask**: `POST /api/theme/import` accepts theme JSON
- **Flask**: POST `/appearance/sync` → "Push to WordPress" button
- **Flask**: POST `/appearance/pull` → "Pull from WordPress" button
- **WordPress**: REST routes `/wp-json/excel-schools/v2/theme/{export,import}`
- **WordPress**: "Pull from Flask" / "Push to Flask" buttons on Settings → Appearance tab
- Theme constants synced via the same X-ESM-API-Key authentication as data sync

#### Dummy data seeder (demo / reset for learners)
- **9 streams × 4 fee levels = 36 classes** with names like "ECD Yellow", "Grade 5 Sciences", "Form 3 Arts"
- **40 students** (10 per level, all in the Yellow class)
- **36 teachers** with form master assignment + login accounts (`demo-e0001` … `demo-e0036`, password `demo123`)
- 40 invoices auto-generated, 30 payments with varied states (paid/half-paid/unpaid)
- Scholarship profile variety: Academic/Staff/Bursary/Sports/Orphan/Regular
- Idempotent: re-seeding never creates duplicates
- Demo data isolated: real records (admission numbers NOT starting with `DEMO-S`) are never touched
- Flask: `/settings/dummy-data/seed` & `/settings/dummy-data/clear` buttons on Settings page
- WordPress: same buttons on the **Debtors** admin page (admin role required)
- Login hint displayed: teachers use `demo0001` / `demo123`

### Changed
- **Flask**: 15 hard-coded `#1a5632` references in PDF generators replaced with `theme.primary_color` (now respects custom theme)
- **WordPress**: admin.css updated to new navy/gold color scheme
- **WordPress**: settings.php Appearance tab adds live color preview + Flask sync buttons
- **WordPress**: All "v2.0.0" footer references replaced with `<?php echo ESM_VERSION; ?>`

### Fixed
- **WordPress**: `class-portal.php` had a duplicate `}` causing **"Unmatched '}' on line 941"** parse error — fixed
- **WordPress**: `ESM_Helpers::get_theme()` now uses plugin's bundled `egs-logo.png` as default logo_url

### Security
- Super admin can no longer record payments (was a privilege separation concern)
- Theme sync endpoints protected by `SYNC_API_KEY` (same shared secret used for data sync)

### Technical
- Flask adds `APP_VERSION = '2.1.0'` constant and `APP_VERSION_DATE` metadata
- Flask startup banner now prints the live version
- WordPress plugin bumped: `ESM_VERSION` and `ESS_VERSION` both → `2.1.0`
- New `CHANGELOG.md` document added at the project root

---

## [2.2.0] — 2026-07-06 (plugin merge)

### Changed
- **Merged** `excel-schools-management` and `excel-schools-sync` into a **single unified WordPress plugin** at `wp-content/plugins/excel-schools/`
- Removed the need to install two separate plugins — one combined plugin now provides:
  - Full school management UI (Students, Staff, Fees, Exams, Library, Transport, Hostel, Timetable, Communication, Reports, Debtors, Teacher Portal)
  - Sync Center (Dashboard / Settings / Logs / Manual Sync)
  - Scheduled cron sync (ess_scheduled_sync, ess_health_check)
  - Real-time webhook receiver (ESS_Webhook_Handler)
  - Theme sync API (`/wp-json/excel-schools/v2/theme/{export,import}`)
  - All REST endpoints (`/wp-json/excel-schools/v2/...`)
- Backwards-compat aliases for legacy constants: `ESS_VERSION`, `ESS_PLUGIN_DIR`, `ESS_PLUGIN_URL`, `ESS_PLUGIN_FILE` are still defined (as aliases for the unified `ESM_*` constants) so old templates and code that referenced them continue to work
- Legacy plugin folders (`excel-schools-management/`, `excel-schools-sync/`) can be safely deleted after activating the unified plugin — **all data is preserved in WordPress custom tables** (`wp_esm_*`)
- New `readme.txt` for the unified plugin
- New `Plugin URI` and updated description

### Added
- `wp-content/plugins/excel-schools/sync/` subdirectory that holds sync-specific assets and templates, keeping the file layout organized
- `wp-content/plugins/excel-schools/excel-schools.php` — the unified plugin entry point that combines both old plugin entry points
- `wp-content/plugins/excel-schools/readme.txt` — WordPress-format readme

---

## [2.0.0] — 2026-06-28

### Added
- Initial release: complete school management system for Excel Group of Schools
- Student / Staff / Fees / Exams / Attendance / Library / Transport / Hostel / Timetable / Communication modules
- Offline-first design with SQLite + optional online PostgreSQL deployment
- WordPress plugin for online portal deployment
- Bidirectional sync between Flask (offline) and WordPress (online)
- WhatsApp Business API + SMTP email notifications
- Role-based access control (Super Admin, Accountant, Bursar, Teacher, Parent, Student)
- Multi-term fee management with scholarships, bursaries, and discounts
- PDF receipts, invoices, report cards
- Author: **Valentine T Mabheka**
