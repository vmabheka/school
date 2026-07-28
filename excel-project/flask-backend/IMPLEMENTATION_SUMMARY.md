# Excel Group of Schools — Implementation Summary
**Version 2.2.0 | Author: Valentine T Mabheka**

---

## ✅ All Features Verified & Effective (All Tests Passed)

### 1. Streamlined Core Modules (Updated in v2.2.0)
- **Removed Non-Core Modules**: Successfully removed Library, Transport, and Attendance marking modules along with their routes, models, dashboards, and sidebar navigation items to streamline school operations around core academic and financial administration.
- **Preserved & Verified User Functions**:
  - **Add Students**: Bursars and Super Admins have full access to `/students/add`, `/students/<id>/edit`, and `/students/bulk-import`.
  - **Exams & Record Marks**: Teachers and Super Admins have full access to `/exams/add` and `/exams/<id>/results` to create exams and enter student grades.

### 2. Automated Invoicing Engine & Once-Off Fee Billing
- **Instant Class-Based Billing**: Students are billed immediately upon being added to a class, edited into a class, or imported via bulk Excel upload.
- **Editable Default Fee Structure**:
  - **Recurring Term Fees**: Tuition Fee + Development Levy ($30 default for secondary Form 1–6; $0 default for primary ECD–Grade 7).
  - **Once-Off Levies**: Registration Fee ($10 default) + Textbook Levy ($56 default for ECD/Secondary Form 1–4; $126 default for Grade 1–7; $45 default for A Level). All defaults are fully adjustable per level.
- **Smart Group Classification**: Once-off levies (Registration & Textbook) apply strictly to genuinely new learners added *after* the initial batch Excel bulk import (`billed_once_off_levies` flag tracked per student).
- **Payment & Balance Tracking**: Every fee payment automatically updates the matching invoice status (`Unpaid` → `Partially Paid` → `Paid`) and outstanding balance in real time.

### 2. PDF Invoices (Single, Bulk ZIP & Combined Bulk PDF)
- `/fees/invoices`: Full invoice management center with filters by status, class, and search.
- **On-Demand Single PDF**: `/fees/invoices/<id>/pdf` generates styled official ReportLab PDF invoices.
- **Combined Bulk PDF**: `/fees/invoices/export-bulk-pdf` combines all filtered invoices into a single multi-page PDF document for continuous printing.
- **Bulk ZIP Archive**: `/fees/invoices/export-zip` downloads individual invoice PDF files packed in a ZIP archive.

### 3. Access Point Monitor (Background Thread)
- Daemon thread runs continuously while Flask app is running
- Detects internet via: HTTP ping → DNS check (8.8.8.8) → NetworkManager D-Bus (Linux)
- Automatically triggers full sync when internet detected
- Prevents sync storms (minimum 60s between auto-syncs)
- **Settings persist to database** — survive app restarts
- Auto-starts on `init_db()` if `auto_sync_enabled=true` in database
- API: `/api/sync/access-point-status` returns real-time monitor state

### 2. One-Button Sync with Internet Detection
- `/sync` dashboard: "Sync Now" button pushes + pulls in one click
- `/api/sync/check-internet` checks if WordPress endpoint is reachable
- Shows detailed results: pushed/failed/pulled/conflicts/skipped counts
- Bursar and Super Admin have access

### 3. Auto-Sync When Internet Detected
- Configurable interval (30s, 1min, 5min, 10min, 30min)
- UI shows countdown timer and sync status
- Background AP Monitor triggers sync independently of user activity
- Settings saved to `SyncSetting` table (not session) — survive restarts

### 4. Bursar Can Add Students AND Process Fee Payments
- `@role_required('super_admin', 'bursar')` on `/students/add`
- `@role_required('super_admin', 'accountant', 'bursar')` on `/fees/pay`
- Bursar also has: bulk import, sync center, attendance, reports

### 5. Bulk Staff & Student Upload (Both Offline & Online)
- **Student bulk import**: Excel (.xlsx/.xls), 21 columns, NO username/password
- **Staff bulk import**: Excel (.xlsx/.xls), 19 columns with role/username/password
- WordPress plugin has matching bulk import functionality
- Both templates include Instructions sheet

### 6. Staff-Only User Management
- `/users` shows only staff-linked user accounts + system accounts
- `/users/add` only offers staff roles: super_admin, accountant, bursar, teacher
- Students do NOT get user accounts — accessed via parent portal
- Parents do NOT get automatic user accounts — created by admin if needed
- `student_add` route does NOT create User records

### 7. Role Allocation During Bulk Upload
- Staff Excel `role` column: super_admin, accountant, bursar, teacher
- Position-based auto-mapping: Director→super_admin, Clerk→bursar, HOD→teacher, etc.
- Explicit `role` column overrides position mapping
- Username defaults to employee_number; password defaults to employee_number

### 8. Scholarship-Based Fee Classification (6 types)
| Classification | Types | Discount |
|---------------|-------|----------|
| Regular | None | 0% (mult=1.0) |
| Staff Scholarship | Full/Partial | Links to staff member |
| Academic Scholarship | Full/Partial | Merit-based |
| Sports Scholarship | Full/Partial | Talent-based |
| Bursary | Full/Partial | Need-based |
| Orphan | Full (auto) | 100% (mult=0.0) |

### 9. Auto-Generated Numbers
- Employee: `EMP0001`, `EMP0002`, etc.
- Student: `EXC20260001`, `EXC20260002`, etc.

### 10. 6-Role RBAC
| Role | Access Highlights |
|------|-------------------|
| Super Admin | Everything (users, settings, appearance, sync) |
| Accountant | Fees, payments, reports |
| Bursar | Students, fees, sync, bulk import |
| Teacher | Attendance, exams, student view |
| Parent | Parent portal (children's data) |
| Student | Student portal (own data via parent) |

---

## API Endpoints

| Endpoint | Method | Access | Description |
|----------|--------|--------|-------------|
| `/api/sync/check-internet` | GET | super_admin, bursar | Check WordPress connectivity |
| `/api/sync/one-button` | POST | super_admin, bursar | Push + pull sync |
| `/api/sync/auto-sync-settings` | POST | super_admin, bursar | Save auto-sync config |
| `/api/sync/status` | GET | super_admin, bursar | Sync status + AP monitor info |
| `/api/sync/access-point-status` | GET | super_admin, bursar | AP monitor details |
| `/api/sync` | POST | API key | Receive sync data |
| `/api/sync/pending` | GET | API key | Get pending items |
| `/api/sync/mark-synced` | POST | API key | Mark items synced |

---

## WordPress Plugins

### Excel Schools Management (`excel-schools-management/`)
- Custom portal at `/sms/` with branded login
- Role-based sidebar (bursar sees Sync nav)
- Sync portal page at `/sms/sync/`
- Staff-only user management at `/sms/users/`
- wp-admin blocking for non-admin ESM roles
- Bursar caps: `esm_manage_sync`, `esm_bulk_import`, `esm_manage_students`, `esm_manage_fees`

### Excel Schools Auto Sync (`excel-schools-sync/`)
- WP-Cron scheduled sync (configurable interval)
- One-button sync from wp-admin dashboard
- Timezone-aware conflict resolution (newest wins)
- Full import/export from/to Flask

---

## Default Login

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | super_admin |

---

## Test Results (46/46)

All features verified including: database models, 6-role RBAC, login, AP monitor start/stop/auto-start, sync settings persistence, sync dashboard, sync APIs, student add (no user account), scholarship fee classification, fee payment processing, bursar CAN/CANNOT access, staff-only user management, Excel templates, staff bulk import with role allocation, student bulk import (no user accounts), sync logging, fee levels, primary subjects, auto-generated numbers, WordPress plugin files, version & author.
