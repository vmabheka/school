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

### Offline Deployment (School Network/Local)
```bash
python run.py --host 0.0.0.0 --port 5000
```

The system runs on the local network. Access it from any connected device using the school's network IP address.

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
