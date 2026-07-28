# Role-Based Access Control — Excel Group of Schools v2.0.0

**Author:** Valentine T Mabheka

---

## Role Definitions

### Super Admin (Directors, Principals)
- **Home Page:** Dashboard (`/`)
- **WordPress Portal Home:** `/sms/dashboard/`
- Full access to all modules
- User management & role assignment
- System settings & appearance customization
- Sync management
- Bulk import/export
- Fee level configuration
- Staff & student CRUD
- Financial reports & dashboards
- Communication management (WhatsApp + Email)
- Can access wp-admin for plugin settings

### Accountant
- **Home Page:** Fee Dashboard (`/fees`)
- **WordPress Portal Home:** `/sms/fees/`
- Fee management — structures, payments, receipts
- Fee level configuration
- Financial reports
- Payment records & receipts (PDF)
- Fee balance checking
- Dashboard with financial stats
- Communication (view + email)
- Reports — fees & financial

### Bursar (Also does Student Admissions)
- **Home Page:** Dashboard (`/`)
- **WordPress Portal Home:** `/sms/dashboard/`
- Student admissions & registration
- Student CRUD (add, edit, view)
- Fee management — structures, payments, receipts
- Fee balance checking
- Scholarship classification
- Bulk student import
- Communication management (WhatsApp + Email)
- Reports — students, fees
- Dashboard with student & financial stats

### Teacher
- **Home Page:** Dashboard (`/`)
- **WordPress Portal Home:** `/sms/dashboard/`
- Attendance marking & reports
- Exam & results entry
- Report card generation
- View student list
- Timetable view
- Library (issue/return)
- Communication (view notices + email + WhatsApp)
- Reports — attendance, exam results

### Parent
- **Home Page:** Parent Portal (`/parent-portal`)
- **WordPress Portal Home:** `/sms/parent-portal/`
- Parent portal — child overview
- View child attendance
- View child exam results
- View fee balance & payment history
- View notices & communication
- View child timetable
- Change password

### Student
- **Home Page:** Student Portal (`/student-portal`)
- **WordPress Portal Home:** `/sms/student-portal/`
- Student portal — personal overview
- View own attendance
- View own exam results
- View own fee balance
- View own timetable
- View notices
- Change password

---

## WordPress Capabilities

| Capability | Super Admin | Accountant | Bursar | Teacher | Parent | Student |
|-----------|:-----------:|:----------:|:------:|:-------:|:------:|:-------:|
| `esm_view_dashboard` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `esm_manage_students` | ✓ | | ✓ | ✓ | | |
| `esm_manage_staff` | ✓ | | | | | |
| `esm_manage_fees` | ✓ | ✓ | ✓ | | | |
| `esm_manage_attendance` | ✓ | | | ✓ | | |
| `esm_manage_exams` | ✓ | | | ✓ | | |
| `esm_manage_library` | ✓ | | | ✓ | | |
| `esm_manage_transport` | ✓ | | | | | |
| `esm_manage_hostel` | ✓ | | | | | |
| `esm_manage_timetable` | ✓ | | | ✓ | | |
| `esm_manage_communication` | ✓ | ✓ | ✓ | ✓ | | |
| `esm_manage_reports` | ✓ | ✓ | ✓ | ✓ | | |
| `esm_manage_settings` | ✓ | | | | | |
| `esm_manage_sync` | ✓ | | | | | |
| `esm_manage_users` | ✓ | | | | | |
| `esm_view_parent_portal` | ✓ | | | | ✓ | |
| `esm_view_student_portal` | ✓ | | | | | ✓ |

---

## Flask Route Protection

All routes use `@role_required()` decorator. Unauthorized access redirects to the user's dashboard.

### Super Admin Only
- `/users`, `/users/add`, `/users/<id>/edit`, `/users/<id>/delete`
- `/sync`, `/sync/export`, `/sync/import`, `/sync/push`
- `/appearance`, `/appearance/reset`
- `/settings`
- `/upload-logo`
- `/staff/add`, `/staff/<id>/edit`
- `/hostel/add`, `/hostel/allocate`
- `/transport/routes/add`, `/transport/vehicles/add`, `/transport/assign`
- `/library/books/add`
- `/fees/structures/add`
- `/fees/structures`
- `/fee-levels/add`, `/fee-levels/<id>/edit`, `/fee-levels/<id>/delete`

### Super Admin + Accountant
- `/fees` (dashboard)
- `/fees/pay`
- `/fees/payments`
- `/reports/fees`

### Super Admin + Bursar
- `/students/add`, `/students/<id>/edit`, `/students/<id>/delete`
- `/students/bulk-import`
- `/upload-student-photo/<id>`
- `/fee-levels`

### Super Admin + Accountant + Bursar
- `/fees/balance/<student_id>`

### Super Admin + Teacher
- `/attendance/mark`, `/attendance/report`, `/attendance/staff`
- `/exams/add`, `/exams/<id>/results`
- `/timetable/add`, `/timetable/view`, `/timetable/generate`
- `/library/issue`, `/library/return/<id>`

### All Roles
- `/` (dashboard) — content varies by role
- `/change-password`
- `/communication` (view notices/messages)
- `/login`, `/logout`

### Parent Only
- `/parent-portal`

### Student Only
- `/student-portal`

---

## WordPress Portal Access

### Portal Pages (`/sms/`)

| Page | Super Admin | Accountant | Bursar | Teacher | Parent | Student |
|------|:-----------:|:----------:|:------:|:-------:|:------:|:-------:|
| `/sms/dashboard/` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/sms/students/` | ✓ | | ✓ | ✓ | | |
| `/sms/staff/` | ✓ | | | | | |
| `/sms/fees/` | ✓ | ✓ | ✓ | | | |
| `/sms/fee-levels/` | ✓ | ✓ | | | | |
| `/sms/attendance/` | ✓ | | | ✓ | | |
| `/sms/exams/` | ✓ | | | ✓ | | |
| `/sms/library/` | ✓ | | | ✓ | | |
| `/sms/transport/` | ✓ | | | | | |
| `/sms/hostel/` | ✓ | | | | | |
| `/sms/timetable/` | ✓ | | | ✓ | | |
| `/sms/communication/` | ✓ | ✓ | ✓ | ✓ | | |
| `/sms/email/` | ✓ | ✓ | ✓ | ✓ | | |
| `/sms/reports/` | ✓ | ✓ | ✓ | ✓ | | |
| `/sms/parent-portal/` | ✓ | | | | ✓ | |
| `/sms/student-portal/` | ✓ | | | | | ✓ |
| `/sms/users/` | ✓ | | | | | |
| `/sms/change-password/` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

### wp-admin Access
- **Super Admin + WordPress Administrator:** Full wp-admin access
- **All other ESM roles:** Automatically redirected from wp-admin to `/sms/`
- AJAX requests are exempted from the redirect

---

## Role Badge Colors

| Role | Color | Hex |
|------|-------|-----|
| Super Admin | Red | #ef4444 |
| Accountant | Green | #10b981 |
| Bursar | Blue | #3b82f6 |
| Teacher | Amber | #f59e0b |
| Parent | Gold | #c8a951 |
| Student | Orange | #e85d26 |
