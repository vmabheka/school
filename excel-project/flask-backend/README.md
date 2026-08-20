# MobiSchola — School Management System

A comprehensive web-based school management system that works **online or offline (LAN)** with periodic synchronization — and is fully brandable for any institution.

**MobiSchola v2.5.0 — By Edutechweb 0772577666 — Manage smarter—even offline.**

## Branding & Deployment Customisation

Every institution can rebrand the **site appearance** without code changes —
set values in **Appearance** (under Settings):

| Setting | Environment variable |
|---|---|
| School name | `SCHOOL_NAME` |
| School motto | `SCHOOL_MOTTO` |
| School address / phone / email | `SCHOOL_ADDRESS`, `SCHOOL_PHONE`, `SCHOOL_EMAIL` |
| School logo | uploaded in Appearance (used on all reports) |
| Currency symbol | `CURRENCY_SYMBOL` (default $) |
| Brand colours | `primary_color` etc. via Appearance |

**Software branding is fixed and cannot be changed from the UI.** The
"MobiSchola — By Edutechweb 0772577666 — Manage smarter—even offline." branding
is excluded from the Appearance page, the save form and the WordPress theme
sync. Only the deployment operator can override it with environment variables
(`SOFTWARE_NAME`, `SOFTWARE_BYLINE`, `SOFTWARE_TAGLINE`, `SOFTWARE_VERSION`)
at install time.

Appearance settings can be saved **even when the WordPress sync endpoint is
not configured** — the Push/Pull buttons simply appear once an endpoint is set
in Sync Center.

The **school logo is inherited by every report**: PDF receipts, PDF invoices,
report cards, debtors reports, on-screen receipts/invoices, and the thermal
print view all show the institution's logo and contact details.

## Payroll & payslips

- **Finance → Payroll** lists active staff with gross pay, PAYE, AIDS levy,
  net pay and bank details, with one-click payslip view and PDF download.
- A **payslip page** per employee shows the school header/logo, earnings,
  deductions (Pay As You Earn, AIDS Levy, other), net pay and the bank account
  the salary is deposited into, and prints cleanly.
- Super admins can edit the payslip details (gross salary, PAYE, AIDS levy,
  other deductions, bank name/account) directly on the payslip page.
- The bundled installation includes **Albert Makumbe (Teacher)** — gross
  US$500, PAYE US$60, AIDS Levy US$15 → **net US$425**, deposited into
  **ZB Bank account 451200282033405**.

## Printing receipts

Every payment receipt can be printed to **any printer, including an 80mm
thermal printer**:

- After recording a payment you land on the receipt page — click
  **Print Receipt (Thermal / Any Printer)**.
- The **Payments** page has a print button on every row.
- The thermal print view is formatted for 80mm roll paper and opens the
  standard print dialog, so you can pick the thermal printer, a laser or any
  other printer. PDF download is also available.

## Features

### Core Modules
1. **Student Management** - Enrollment, profiles, search, status tracking
2. **Staff Management** - Teacher and staff records, qualifications, departments
3. **Fee Management** - Fee structures, payments, receipts, balance tracking
4. **Attendance** - Student and staff attendance with daily marking
5. **Exams & Results** - Exam creation, result entry, report cards with grading
6. **Library** - Book inventory, issuing, returns, overdue tracking
7. **Transport** - Routes, vehicles, driver assignments, student allocation
8. **Hostel** - Hostels, rooms, bed allocations, warden assignments
9. **Timetable** - Class timetables, manual and auto-generation
10. **Communication** - Notices, internal messaging
11. **Reports** - Student, fee, attendance, and exam reports
12. **Sync Center** - Offline-to-online data synchronization

### Key Capabilities
- **Role-based Access Control** - Admin, Teacher, Staff, Student, Parent
- **Offline/Online Sync** - Export/Import JSON files or API-based push
- **Printable Reports** - Receipts, report cards, attendance sheets
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Zimbabwe-specific** - EcoCash, RTGS payment methods, local grading system

## Quick Start

### Prerequisites
- Python 3.8+
- pip

### Installation

```bash
# Navigate to the project directory
cd excel_school_mgmt

# Install dependencies
pip install -r requirements.txt

# Run the system (offline mode by default)
python run.py

# Or run in online mode
python run.py --online
```

### First Login
- **URL:** http://localhost:5000
- **Username:** edusync
- **Password:** edusync26

⚠️ **Change the default password immediately after first login!**

## Deployment

For a production server, use the hardened Docker/PostgreSQL/Gunicorn setup in
[`PRODUCTION.md`](PRODUCTION.md). It includes environment variables, persistent
volumes, health checks, Nginx HTTPS proxying, backups, and an operational
launch checklist.

### One Offline Server for the School Network

Use **one computer only** as the central server. Every desktop, laptop, tablet,
or phone connected to the same router opens the system in a browser and feeds
data into the database on that server computer.

#### Windows EXE setup

1. Build the Windows package with `build-windows-exe.bat`, or copy these three
   files from `dist` to the computer selected as the server:
   - `MobiSchola.exe` — the server itself
   - `setup-lan-server.bat` — opens the firewall and starts the server
   - `test-client.bat` — connection test to run on any device that cannot connect
2. Connect the server computer to the school router, preferably by Ethernet.
3. In Windows **Settings → Network & Internet → Properties**, set the network
   profile to **Private** (Public networks block sharing by default).
4. Double-click `setup-lan-server.bat` and approve the administrator prompt.
   It creates a **port-based** Windows Firewall allow rule for TCP port 5000 on
   the Private and Domain profiles (a port rule is used on purpose: the EXE
   listens from a temporary folder, so a rule scoped to the EXE file path never
   matches), prints every server URL, copies them to the clipboard, and starts
   the Waitress WSGI server. It also offers to rename the computer to
   **MOBISCHOLA-SERVER** and creates a **MobiSchola Portal** shortcut on the
   desktop pointing at the permanent address.
5. **The server runs independently of a browser** — no browser opens on the
   server machine (the EXE runs headless by default; use `--open-browser`
   only if you want it). The console window shows the **PERMANENT SERVER
   ADDRESS** and every client request.
6. **Permanent address**: the server prints a name-based address that never
   changes even when the IP does — `http://MOBISCHOLA-SERVER:5000` (or
   `http://<computername>:5000` if you kept the name). The same address is
   written to `server-address.txt` in the data folder and to the desktop
   shortcut. Assign a DHCP reservation too so the IP stays fixed.
7. On each other device, open the permanent address (or one of the IP
   addresses shown), for example:

   ```text
   http://MOBISCHOLA-SERVER:5000
   ```

8. Sign in with a separate user account appropriate to each staff member's
   role. Do **not** copy or run the EXE on client devices — they only need a
   browser (a phone works too).

The central database, uploads, and a generated session secret are stored in:

```text
%LOCALAPPDATA%\ExcelSchools
```

Back up that directory regularly. Assign the server computer a DHCP reservation
(static LAN address) in the router so its URL does not change. Disable sleep on
the server computer during school hours. The firewall rule covers Private and
Domain networks only; do not expose port 5000 directly to the public internet.

To use another port before running the setup script:

```bat
set EXCEL_SCHOOLS_PORT=8080
setup-lan-server.bat
```

### Remove Textbook Levy & Registration Fee from uploaded learners

If learners already billed in a previous import carry the once-off
**Textbook Levy** and **Registration Fee** lines, run the cleanup script on
the server computer (stop the server first):

```bash
python remove-onceoff-levies.py          # preview with: --dry-run
```

On Windows, double-click `remove-onceoff-levies.bat`. The script removes the
two fees, recalculates the invoices, and marks the learners so the fees are
never billed to them again.

The script **finds the school database automatically**: it checks the Windows
EXE data folder (`%LOCALAPPDATA%\ExcelSchools\excel_schools.db`) first, then
the source-mode `instance/excel_schools.db`, and prints which database it is
using so you can verify it is the right one. If it reports "No items found"
in the wrong database, point it at the right file with:

```bash
python remove-onceoff-levies.py --db "C:\Users\...\AppData\Local\ExcelSchools\excel_schools.db"
```

To also allow connections while the network profile is **Public** (only if you
accept the risk on a trusted network):

```bat
set EXCEL_SCHOOLS_ALLOW_PUBLIC_PROFILE=1
setup-lan-server.bat
```

#### If client devices cannot connect

Run these checks in order:

1. **On the server**, keep the server window open and look at the addresses it
   printed. The clients must open one of the `http://<IP>:5000` addresses —
   not `127.0.0.1` (that only works on the server computer itself).
2. **On the server**, confirm the server window prints incoming requests. If
   nothing appears when a client tries to connect, the network/firewall is
   blocking the traffic (go to step 3–5). If requests appear, the app is fine
   and the problem is on the client side (steps 6–7).
3. **Firewall**: on the server run `setup-lan-server.bat` as **Administrator**
   once. It recreates the port-based allow rule. Check antivirus firewalls
   (Avast, Kaspersky, McAfee, Bitdefender…) for extra blocking rules.
4. **Network profile**: the server's network must be **Private**. Run
   `MobiSchola.exe --diagnose` on the server to see every network
   profile, the firewall rule state, and the port status in one place.
5. **Router**: disable **AP isolation / client isolation** on the router, or
   connect the server by Ethernet cable. Guest Wi-Fi cannot reach the server.
6. **On the failing client**, copy `test-client.bat` from the server (or run
   these commands directly):

   ```bat
   ping 192.168.1.25
   powershell -Command "Test-NetConnection 192.168.1.25 -Port 5000"
   curl -i http://192.168.1.25:5000/healthz
   ```

   `test-client.bat 192.168.1.25` runs all three tests and prints the fix for
   each result.
7. **Wrong network**: make sure the client is on the same Wi-Fi name / same
   router as the server. Different Wi-Fi networks cannot see each other.

#### Python source setup (Linux/macOS/Windows)

```bash
# Listen on every LAN interface. Run this only on the server computer.
GUNICORN_BIND=0.0.0.0:5000 ./start.sh
```

On Linux/macOS the same firewall rules apply (`ufw allow 5000/tcp` or
`firewall-cmd --add-port=5000/tcp`). Client devices then browse to
`http://SERVER_IPV4:5000`. All writes pass through the single WSGI process;
client devices never open or copy the SQLite file.

### Online Deployment (School Website)

#### Option 1: Traditional Server
```bash
# Set environment variables
export DATABASE_URL=postgresql://user:pass@localhost/excel_schools
export SECRET_KEY=your-very-secure-random-key
export DEPLOYMENT_MODE=online
export SYNC_ENDPOINT=https://your-school-website.com/api
export SYNC_API_KEY=your-api-key

# Run with Gunicorn (production)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

#### Option 2: Docker
```bash
docker build -t excel-schools .
docker run -p 5000:5000 \
  -e DATABASE_URL=postgresql://user:pass@db:5432/excel_schools \
  -e SECRET_KEY=your-secret-key \
  -e DEPLOYMENT_MODE=online \
  excel-schools
```

### Primary School Subjects

The approved primary subjects for ECD A through Grade 7 are:
**English, ChiShona, Mathematics, Social Science, PE and Arts, and Science and Technology**.
Primary form teachers receive these six subjects for their assigned class.

### Teacher Class and Subject Assignments

1. Sign in as a Super Admin and open **Staff**.
2. Open a teacher's profile and use **Class & Subject Assignments**.
3. Add one assignment for each exact class/subject combination and academic year.
   For example, John Sibanda teaching English to Form 3 Yellow, Blue, Purple,
   and Red requires four assignment rows. Add a fifth row for Physical
   Education in Form 1.
4. Teachers are redirected to `/teacher` and can only see learners in their
   form-master or explicitly assigned classes. Secondary form-master status
   does not automatically grant access to every subject.

### Offline-Online Synchronization

**Method 1: Manual Export/Import (Recommended for periodic sync)**
1. On the offline system, go to **Sync Center → Export All Data (JSON)**
2. Download the complete school-data snapshot (academic setup, classes, people, finance, exams, accommodation, timetables, and communication)
3. Transfer the file to the online system (USB, email, etc.)
4. In WordPress, go to **Excel Schools → Sync Center & JSON Import**
5. Upload the JSON file; records are merged by stable sync ID/source ID, so the same export can safely be imported again

**Method 2: Automatic API Push (Requires internet on offline system)**
1. Configure `SYNC_ENDPOINT` and `SYNC_API_KEY` environment variables
2. Click **Push to Online** in the Sync Center

**Recommended Sync Schedule:**
- Daily: Export from offline, import to online
- Weekly: Full reconciliation and verification

## System Architecture

```
┌──────────────────┐         ┌──────────────────┐
│   OFFLINE MODE   │         │   ONLINE MODE    │
│  (School Server) │         │  (Web Hosting)   │
│                  │         │                  │
│  SQLite Database │◄───────►│  MySQL/PostgreSQL│
│  Local Network   │  Sync   │  Public Internet │
│                  │         │                  │
└──────────────────┘         └──────────────────┘
```

## Grading System

| Range | Grade |
|-------|-------|
| 80-100% | A |
| 70-79% | B |
| 60-69% | C |
| 50-59% | D |
| 40-49% | E |
| Below 40% | U |

## Payment Methods Supported
- Cash
- EcoCash
- Bank Transfer
- Swipe (POS)
- RTGS

## Technology Stack
- **Backend:** Python 3 + Flask
- **Database:** SQLite (offline) / PostgreSQL (online)
- **Frontend:** HTML5, CSS3, JavaScript (responsive)
- **ORM:** SQLAlchemy
- **Authentication:** Session-based with password hashing

## License
© 2024-2026 Excel Group of Schools. All rights reserved.
