# Excel Group of Schools - School Management System

A comprehensive web-based school management system designed for **Excel Group of Schools** that supports both **online** and **offline** deployment with periodic synchronization.

**Author:** Valentine T Mabheka
**Version:** 2.0.0

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

1. Build the Windows package with `build-windows-exe.bat`, or copy these two
   files from `dist` to the computer selected as the server:
   - `ExcelSchools-Offline.exe`
   - `setup-lan-server.bat`
2. Connect the server computer to the school router, preferably by Ethernet.
3. In Windows **Settings → Network & Internet → Properties**, set the network
   profile to **Private**.
4. Double-click `setup-lan-server.bat` and approve the administrator prompt.
   It creates a Private-network Windows Firewall rule for TCP port 5000,
   displays the server URLs, and starts the Waitress WSGI server.
5. Keep the black server window open. On each other device, open one of the
   displayed addresses, for example:

   ```text
   http://192.168.1.25:5000
   ```

6. Sign in with a separate user account appropriate to each staff member's
   role. Do **not** copy or run the EXE on client devices.

The central database, uploads, and a generated session secret are stored in:

```text
%LOCALAPPDATA%\ExcelSchools
```

Back up that directory regularly. Assign the server computer a DHCP reservation
(static LAN address) in the router so its URL does not change. Disable sleep on
the server computer during school hours. The firewall rule is Private-profile
only; do not expose port 5000 directly to the public internet.

To use another port before running the setup script:

```bat
set EXCEL_SCHOOLS_PORT=8080
setup-lan-server.bat
```

#### Python source setup (Linux/macOS/Windows)

```bash
# Listen on every LAN interface. Run this only on the server computer.
GUNICORN_BIND=0.0.0.0:5000 ./start.sh
```

Client devices then browse to `http://SERVER_IPV4:5000`. All writes pass through
the single WSGI process; client devices never open or copy the SQLite file.

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
