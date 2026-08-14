# Changelog

All notable changes to the **Excel Group of Schools** management system.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [2.7.1] — 2026-08-14

### Added (Flask app — WhatsApp parent registration)

- **Parents can now register via WhatsApp.** Text `REGISTER <child full name> <level>`
  (e.g. `REGISTER Tanaka Moyo Grade 6`) and the bot finds the learner by name
  and level. If several learners match, it lists them and asks the parent to
  pick the number.
- **Step-by-step collection of the parent's own details** — exactly the fields
  on the student registration form: first name, last name, relationship
  (Father/Mother/Guardian…), email, occupation, national ID and address, with
  input validation (valid email, valid relationship) and `SKIP` for optional
  fields. The phone number is taken automatically from the WhatsApp number.
- On completion the parent record is created and linked to the child; the
  session is cleared. An already-registered number registering another child
  simply links that child to the existing profile. `CANCEL` aborts a session,
  and stale sessions (24h) expire automatically.
- The HELP text and Communication Settings page document the new REGISTER
  command.

---

## [2.7.0] — 2026-08-14

### Added (Flask app)

#### Clean Database (password-protected)
- New **Danger Zone → Clean Database** on the Settings page. The wipe only
  runs after the super admin enters their account password and ticks the
  confirmation box — wrong password cancels the operation. Deletes all school
  data (students, parents, staff, classes, payments, invoices, exams,
  timetables, communication) while keeping user accounts, academic years,
  terms, subjects, fee levels, cost centres and settings.

#### Bursar payment edits require Super Admin approval
- Bursars/accountants can no longer be locked out of fixing a recorded
  payment — they submit a **change request** (new amount, date, method,
  description + reason) from the Payments list. The payment is untouched
  until a Super Admin approves it on the new **Payment Approvals** page
  (Finance → Payment Approvals). Approve applies the changes and recalculates
  the invoice; reject closes the request with a note. Full audit trail of
  decisions is kept.

#### Configurable communication systems
- New **Settings → Communication** page (super admin) to configure
  **WhatsApp (Meta Cloud API)** — base URL, access token, phone number ID,
  webhook verify token, enable toggle — and **Email (SMTP)** — host, port,
  user, password, from, TLS, enable toggle — plus automatic-receipt toggles
  for both channels, with **Test** buttons that send a real test message.
  Settings persist in the database (fall back to the existing environment
  variables). The page shows the WhatsApp webhook URL to paste into Meta.

#### WhatsApp parent records bot
- New public webhook `/api/whatsapp/webhook` (GET verification + POST
  message handling) that lets parents query their children's school records
  straight from WhatsApp. A parent's registered number is matched to their
  profile; commands: **BALANCE** (fee balance per child), **RESULTS** (latest
  exam results), **RECEIPTS** (recent payments), **RECORD** (school record
  summary), **HELP** (menu). Unknown numbers get a polite registration notice.

#### Automatic fee receipts on payment
- When a payment is recorded, the receipt is **automatically sent to the
  parent(s)** via WhatsApp and/or email according to the communication
  settings. A **Send to Parent** button on the receipt page re-sends a
  receipt manually at any time.

---

## [2.6.3] — 2026-08-12

### Fixed (Flask app)

- **"Add Class" no longer returns Internal Server Error.** The form crashed
  with `ValueError: invalid literal for int()` when the capacity field was
  blank or non-numeric. Capacity, academic year and teacher id are now parsed
  defensively (blank/garbage values fall back to safe defaults), the class
  name is validated, and any unexpected error rolls back and shows a friendly
  flash message instead of a 500. A friendly error page (with the actual
  detail) now replaces the bare "Internal Server Error" for any future 500,
  and 404s get a matching page.
- **Offline app can now reach the WordPress portal (handshake/sync).** The
  WordPress plugin registers its REST routes under the `excel-schools/v2`
  namespace (`/wp-json/excel-schools/v2/stats`, `/sync`, `/sync/pending`,
  `/theme/import`, …) but the offline app was building URLs as
  `<endpoint>/api/stats` and `<endpoint>/api/sync` — a 404 on the WordPress
  side, so the connection check always reported "offline" and sync never
  worked. A new `_wp_rest_base()` helper now builds the correct namespace URL
  and accepts both stored styles: the bare site URL
  (`https://crm.egs.ac.zw`) or the full plugin namespace
  (`https://crm.egs.ac.zw/wp-json/excel-schools/v2`). Applied to the
  connection check, the access-point monitor, one-button sync (push / pull /
  mark-synced), manual push and theme push/pull. Verified end-to-end against
  a mock WordPress server: every request hits the correct
  `/wp-json/excel-schools/v2/...` path.

---

## [3.2.1] — 2026-08-12 (WordPress plugin)

### Fixed (WordPress portal — 404 "Access Denied" on /sms/)

- **In-place plugin updates now upgrade the database and rewrite rules.**
  WordPress does not run the activation hook during an update, so installing
  the new version over an existing one never created the new tables/columns
  (e.g. `esm_cost_centers`, `student.cost_center_id`) and never refreshed the
  `/sms/` rewrite rules — pages that touched the new tables threw SQL errors
  and the portal could 404. The `init`-time upgrade routine now calls
  `ESM_Database::create_tables()` + `seed_defaults()`, re-applies roles,
  re-registers the rewrite rules and flushes them whenever the plugin version
  changes. Plugin bumped to **3.2.1** so the routine runs on the current
  install.
- **`/sms/` routing no longer depends on the rewrite rules.** The portal
  router now falls back to parsing the `/sms/<page>/` path directly from the
  request URI, so the portal works even if permalinks are set to Plain or the
  rules are stale — instead of returning a WordPress 404.
- Guarded the cost-centre queries in the Debtors portal page and the Settings
  Cost Centres tab so a missing table can never take the page down.

---

## [2.6.2] — 2026-08-12

### Fixed (Flask app)

- **Appearance settings now save reliably.** The Appearance page had invalid
  HTML: a second `<form>` was nested inside the settings form, and per the
  HTML standard the nested form's closing tag also closed the outer form —
  so the "Save Appearance Settings" button ended up outside any form and
  clicking it did nothing in the browser. The page was restructured into one
  valid settings form (school branding, currency, colours, typography, save
  button) with the logo upload/remove controls moved into their own standalone
  card after it. Saving settings can no longer wipe the uploaded logo either —
  the save handler now only touches keys that are actually posted.
- **Sync settings save without JavaScript.** The Sync Center previously
  relied on a JS `fetch` for saving the endpoint / API key / auto-sync
  options. The cards are now inside a normal form that POSTs to a new
  `/sync/settings` route (with a no-JS fallback), so "Save Configuration"
  and "Save Settings" always persist, start/stop the background access-point
  monitor, and show a confirmation flash. The API endpoint
  (`/api/sync/auto-sync-settings`) is kept for compatibility.

---

## [2.6.1] — 2026-08-12

### Changed (Flask app)

- **Software branding is no longer customisable.** The Software Branding
  section (name, byline, tagline, version) was removed from the Appearance
  page. Those keys are now excluded from the appearance save form, the theme
  sync (push/pull), the theme export/import APIs and the WordPress sync — so
  site administrators can never change them, even with a crafted request.
  Any branding rows stored by older versions are wiped on startup, and the
  default seed no longer writes them. Only the deployment operator can
  override the fixed branding via environment variables at install time.
  The **currency symbol** remains a normal, editable site appearance setting
  (moved into the School Branding section).
- **Site appearance settings can be changed even when the WordPress sync
  endpoint is not configured.** Saving school name, motto, contact details,
  logo, colours and currency works fully offline; the Push / Pull buttons are
  hidden until an endpoint is configured in Sync Center, and the banner now
  explains that appearance is managed locally and remains fully changeable
  (instead of warning that sync buttons will fail).

---

## [2.6.0] — 2026-08-12

### Added (Flask app + WordPress portal)

#### Debtors report: cost centre filter + role-based totals
- **Cost centres (customisable)**: new Cost Centre entity seeded with
  **Primary, Secondary and Stay In**. Super admins can add, rename or delete
  centres on the new **Cost Centres** page (Settings → Finance → Cost Centres,
  also linked from the Debtors report and the student forms). Defaults are
  protected from deletion. The WordPress Settings page gains a matching Cost
  Centres tab.
- **Auto-assignment**: every learner is assigned a cost centre automatically —
  Stay In → Primary → Secondary — based on entry mode and class level, on add,
  edit, bulk import and class reassignment, and backfilled for existing
  installations on startup. The student add/edit forms allow an explicit
  override.
- **Debtors filters**: the Debtors report now filters by **Class** and
  **Cost Centre** (in addition to the existing grade/school/level filters),
  in both the offline app and the WordPress portal, with a Cost Centre column
  in the table.
- **Role-based totals**: the **Total Fees Collectible (target)**, Total
  Outstanding, Collected So Far and Scholarship Discounts are visible to the
  **Super Admin only**. The **Bursar** (and accountant) sees only the
  **percentage collected vs the target** — shown as a large card plus a
  collection progress bar; CSV/Excel/PDF exports replace money totals with the
  percentage for non-super-admin roles. Identical rules in the WordPress
  portal (administrators vs bursars).
- Cost centres and the student assignment are included in the offline↔online
  sync (new `cost_centers` entity; students carry `cost_center_id`).

---

## [2.5.0] — 2026-08-12

### Added (Flask app)

- **Fully customisable branding for any institution**: software name, byline,
  tagline, version, currency symbol and school contact details are now
  configurable on the **Appearance** page and via environment variables
  (`SOFTWARE_NAME`, `SOFTWARE_BYLINE`, `SOFTWARE_TAGLINE`,
  `SOFTWARE_VERSION`, `CURRENCY_SYMBOL`, `SCHOOL_ADDRESS`, `SCHOOL_PHONE`,
  `SCHOOL_EMAIL`, …). They appear on the login page, sidebar, receipts,
  invoices, reports, emails and Excel templates.
- **School logo inherited by all reports**: the uploaded logo is now embedded
  in the PDF receipt, PDF invoice, combined invoices, report card and debtors
  PDF (via a shared PDF header), and shown on the on-screen receipt, invoice
  and report-card pages — together with the school name, motto and contact
  line.
- **Thermal / any-printer receipt printing**: new print view
  (`/fees/receipt/<id>/print`) formatted for 80mm thermal roll paper with an
  auto print dialog; the receipt page and the Payments list link to it, and
  after recording a payment you land on the receipt with a one-click print
  button. Works with thermal printers and any regular printer.
- **Rebranded to MobiSchola**: software name/version updated from
  "Excel Group of Schools v2.0.0 — Valentine T Mabheka" to
  **MobiSchola v2.5.0 — By Edutechweb 0772577666 — Manage smarter—even
  offline.** across the Flask app, PDFs, Excel templates, launchers, and the
  WordPress portal (plugin 3.2.0).
- Fixed a pre-existing crash in the report-card PDF when an exam has no type.

---

## [2.4.2] — 2026-08-03

### Fixed (Flask app)

- **`remove-onceoff-levies.py` now targets the correct database.** The first
  version always opened the source-mode database (`instance/excel_schools.db`)
  and silently found nothing when the school data lived in the Windows EXE
  data folder (`%LOCALAPPDATA%\ExcelSchools\excel_schools.db`). The script now
  auto-detects the database: explicit `--db <path>` / `EXCEL_SCHOOLS_DB` /
  `DATABASE_URL` first, then the EXE data folder, then the source-mode
  database — and prints exactly which database it is using (with file size and
  modification time) at the top of the output. If it still finds nothing, it
  explains the possible database locations instead of just reporting an empty
  result. `--db <path>` is also available to force a specific file.

---

## [2.4.1] — 2026-08-03

### Added (Flask app)

- **`remove-onceoff-levies.py`** — one-off utility script that removes the
  **Textbook Levy (Once-off)** and **Registration Fee (Once-off)** lines from
  uploaded learners' invoices, recalculates each invoice (subtotal, discount,
  total and status — scholarship discounts included), and marks every affected
  learner as already billed so the system never adds these two fees again,
  even when invoices are regenerated for future terms. Supports
  `--dry-run` (preview), `--yes` (skip confirmation), and is safe to re-run
  (second run finds nothing). A double-clickable **`remove-onceoff-levies.bat`**
  wrapper is included for Windows.

---

## [2.4.0] — 2026-08-03

### Added (Flask app)

#### Entry Mode (Day / Stay In) and boarding billing
- New **Entry Mode** field on every learner: **Day** or **Stay In (Boarding)**.
  Available in the student add/edit forms, the student profile, and the
  students list (Mode column with a Stay In badge).
- **Stay In learners are automatically billed the Stay In fee every term**:
  $300 for primary and secondary (ECD/Junior/O Level) and $260 for A Level.
  The amount is configurable per fee level (new **Stay In Fee** column on the
  Fee Levels page, $300/$260 defaults seeded; 0 = automatic by level).
- Bulk import accepts an **`entry_mode`** column (`Day` / `Stay In`, with
  variants like boarding/day scholar normalised automatically). The Excel
  template, upload page guide and instructions sheet were updated.

#### Term 3 2026 billing
- The system now bills for **Term 3 2026**: Term 3 is created if missing and
  set as the current term (existing installations are moved forward once from
  Term 2; the change is a no-op afterwards).
- **The first bulk import does NOT bill book/textbook levy or registration
  fees.** Learners added by later imports are treated as new learners and are
  billed those once-off levies.

#### Bulk actions on the Students list
- **Bulk delete**: select learners with checkboxes (select-all included) and
  permanently remove them together with their invoices, invoice items, fee
  payments, exam results, hostel allocations and parent links.
- **Bulk reassign**: select learners and move them all to one class in a
  single action.
- **Quick reassign** on the student profile page moves one learner to another
  class without opening the full edit form.
- Pagination now preserves the scholarship filter.

---

## [2.3.2] — 2026-08-03

### Changed (Flask app — student upload)

- **Blank "Other Names" are now ignored everywhere**: the bulk import, the add
  student form, and the edit student form store `NULL` when the field is blank
  (or filled with placeholders like `-`, `N/A`, `None`), and the student list /
  profile / staff profile pages no longer render the literal word "None" in a
  name — a blank field simply shows the first and last name.
- **Classes are auto-created during student upload**: when a row's
  `class_name` does not exist yet, the class is created automatically with the
  correct level and stream detected from the name (`Grade 7A` → level "Grade
  7", stream "A"; `Form 3 Blue` → "Form 3"/"Blue"; `ECD A Yellow` →
  "ECD A"/"Yellow"). Primary classes also get the six approved learning areas
  auto-assigned, exactly like creating the class from the Classes page.
  **Only teacher allocation remains manual** — auto-created classes have no
  form teacher and the success message reminds the admin to assign teachers in
  Classes. Existing classes are reused and never duplicated.
- Upload page guide and downloadable Excel template updated to explain the new
  behaviour.

---

## [2.3.1] — 2026-08-03

### Fixed (Flask app)

- **"Internal Server Error" when clearing dummy data**: `_clear_dummy_data`
  deleted demo classes/staff through the ORM while `staff_subject` rows still
  referenced them. Those columns are `NOT NULL`, so SQLAlchemy's
  nullify-on-delete raised `IntegrityError: NOT NULL constraint failed:
  staff_subject.class_id` and the browser showed a 500. The clear routine now
  deletes `staff_subject` (and timetable slots) for demo classes/staff first,
  removes all student child rows (invoice items, invoices, payments, exam
  results, hostel allocations), unassigns demo teachers from every class, then
  deletes the demo parents — and rolls back with a friendly flash message if
  anything still fails, so the page can never 500 again. Re-seeding (which
  clears first) works too, and real data is untouched.

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
