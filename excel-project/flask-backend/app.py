"""
Excel Group of Schools - School Management System
===================================================
A comprehensive web-based school management system that can be deployed
both online and offline with periodic synchronization.

Author: Valentine T Mabheka
Version: 2.1.0
"""

import os
import io
import json
import re
import uuid
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, session, send_file, make_response)
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import requests

# ─── App Configuration ────────────────────────────────────────────────
app = Flask(__name__)
_deployment_mode = os.environ.get('DEPLOYMENT_MODE', 'offline').strip().lower()
_is_production = _deployment_mode == 'online'
_secret_key = os.environ.get('SECRET_KEY', 'excel-schools-secret-key-2024')
_database_url = os.environ.get('DATABASE_URL', 'sqlite:///excel_schools.db')

if _is_production:
    if len(_secret_key) < 32 or _secret_key in {
        'excel-schools-secret-key-2024',
        'excel-schools-change-this-in-production',
        'change-this-to-a-long-random-string',
    }:
        raise RuntimeError('Production requires a unique SECRET_KEY of at least 32 characters.')
    if _database_url.startswith('sqlite:') and os.environ.get('ALLOW_SQLITE_PRODUCTION') != 'true':
        raise RuntimeError('Production requires PostgreSQL/MySQL; set ALLOW_SQLITE_PRODUCTION=true only for temporary testing.')

_engine_options = {
    'pool_pre_ping': True,
    'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '300')),
}
if _database_url.startswith('sqlite:'):
    # One WSGI process owns the central offline database while multiple LAN
    # clients submit requests concurrently. Extend lock waits and permit the
    # Waitress worker threads to share SQLAlchemy-managed connections.
    _engine_options['connect_args'] = {
        'timeout': int(os.environ.get('SQLITE_BUSY_TIMEOUT', '30')),
        'check_same_thread': False,
    }

app.config.update(
    SECRET_KEY=_secret_key,
    SQLALCHEMY_DATABASE_URI=_database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS=_engine_options,
    UPLOAD_FOLDER=os.environ.get(
        'UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    ),
    MAX_CONTENT_LENGTH=int(os.environ.get('MAX_UPLOAD_MB', '16')) * 1024 * 1024,
    SCHOOL_NAME=os.environ.get('SCHOOL_NAME', 'Excel Group of Schools'),
    SCHOOL_MOTTO=os.environ.get('SCHOOL_MOTTO', 'Excellence in Education'),
    SCHOOL_LOGO='images/logo.png',
    DEPLOYMENT_MODE=_deployment_mode,
    SYNC_ENDPOINT=os.environ.get('SYNC_ENDPOINT', ''),
    SYNC_API_KEY=os.environ.get('SYNC_API_KEY', ''),
    SESSION_COOKIE_SECURE=_is_production,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PREFERRED_URL_SCHEME='https' if _is_production else 'http',
    PERMANENT_SESSION_LIFETIME=timedelta(
        minutes=int(os.environ.get('SESSION_LIFETIME_MINUTES', '480'))
    ),
)

if os.environ.get('TRUST_PROXY', 'false').lower() == 'true':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

_cors_origins = [
    origin.strip() for origin in os.environ.get('CORS_ORIGINS', '').split(',')
    if origin.strip()
]
# Browser CORS is disabled unless explicit origins are configured. Server-to-
# server sync is unaffected because it does not require browser CORS headers.
if _cors_origins:
    CORS(app, resources={r"/api/*": {"origins": _cors_origins}})

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


@app.after_request
def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if _is_production:
        response.headers.setdefault(
            'Strict-Transport-Security', 'max-age=31536000; includeSubDomains'
        )
    return response


db = SQLAlchemy(app)

# App version (synced with WordPress plugin)
APP_VERSION = '2.1.0'
APP_VERSION_DATE = '2026-07-06'

# Initial super-admin credentials used only when provisioning a new database.
DEFAULT_ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'edusync')
DEFAULT_ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'edusync26')
if _is_production and (
    len(DEFAULT_ADMIN_PASSWORD) < 16 or DEFAULT_ADMIN_PASSWORD == 'edusync26'
):
    raise RuntimeError('Production requires a unique ADMIN_PASSWORD of at least 16 characters.')

# ─── Inject theme into every template ─────────────────────────────────
@app.context_processor
def inject_theme():
    try:
        theme = get_theme()
    except Exception:
        theme = dict(DEFAULT_THEME)
    role = session.get('user_role', '')
    return dict(
        theme=theme,
        school_name=theme.get('school_name', 'Excel Group of Schools'),
        user_role=role,
        role_label=ROLE_LABELS.get(role, role.title() if role else 'Guest'),
        role_nav_sections=ROLE_NAV_SECTIONS.get(role, []),
        role_nav_items=ROLE_NAV_ITEMS.get(role, []),
        # Expose capability flags & label dicts to all templates
        can_record_payments=role in ('accountant', 'bursar'),
        ROLE_LABELS=ROLE_LABELS,
    )

# ─── Models ────────────────────────────────────────────────────────────

# Association tables
student_parent = db.Table(
    'student_parent',
    db.Column('student_id', db.Integer, db.ForeignKey('student.id')),
    db.Column('parent_id', db.Integer, db.ForeignKey('parent.id'))
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='super_admin')  # super_admin, accountant, bursar, teacher, parent, student
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AcademicYear(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "2024-2025"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, default=False)
    terms = db.relationship('Term', backref='academic_year', lazy=True)


class Term(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "Term 1"
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_year.id'))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, default=False)


class Class(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "Grade 1A"
    level = db.Column(db.String(20))  # e.g., "Grade 1", "Form 1"
    stream = db.Column(db.String(30))  # e.g., "A", "Blue"
    teacher_id = db.Column(db.Integer, db.ForeignKey('staff.id'))
    capacity = db.Column(db.Integer, default=40)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_year.id'))
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), unique=True)
    students = db.relationship('Student', backref='class_', lazy=True)


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True)
    description = db.Column(db.Text)
    is_compulsory = db.Column(db.Boolean, default=True)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admission_number = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    other_names = db.Column(db.String(50))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))  # Male, Female
    national_id = db.Column(db.String(20))
    photo = db.Column(db.String(200))
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    admission_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(20), default='Active')  # Active, Inactive, Graduated, Transferred
    previous_school = db.Column(db.String(200))
    medical_info = db.Column(db.Text)
    address = db.Column(db.String(300))
    city = db.Column(db.String(100))
    province = db.Column(db.String(100))
    country = db.Column(db.String(100), default='Zimbabwe')
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    # Scholarship fields
    fee_classification = db.Column(db.String(30), default='Regular')  # Regular, Staff Scholarship, Academic Scholarship, Sports Scholarship, Bursary, Orphan
    scholarship_type = db.Column(db.String(20), default='None')  # None, Full, Partial
    scholarship_percentage = db.Column(db.Float, default=0)  # 0-100 discount percentage
    scholarship_sponsor = db.Column(db.String(200))  # who funds the scholarship
    scholarship_staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'))  # linked staff for staff scholarship
    scholarship_notes = db.Column(db.Text)
    is_new_learner = db.Column(db.Boolean, default=True)
    billed_once_off_levies = db.Column(db.Boolean, default=False)
    entry_mode = db.Column(db.String(20), default='Day')  # Day or Stay In (boarding)
    # Relations
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    parents = db.relationship('Parent', secondary=student_parent, backref='students')
    exam_results = db.relationship('ExamResult', backref='student', lazy=True)
    fee_payments = db.relationship('FeePayment', backref='student', lazy=True)
    invoices = db.relationship('Invoice', backref='student', lazy=True)
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def effective_fee_multiplier(self):
        """Return the multiplier (0 to 1) for how much fee this student pays."""
        if self.fee_classification == 'Orphan' or self.scholarship_type == 'Full':
            return 0.0
        elif self.scholarship_type == 'Partial':
            return 1.0 - (self.scholarship_percentage / 100.0)
        return 1.0

    @property
    def scholarship_label(self):
        if self.fee_classification == 'Regular':
            return 'Regular'
        label = self.fee_classification
        if self.scholarship_type == 'Full':
            label += ' (Full)'
        elif self.scholarship_type == 'Partial':
            label += f' ({self.scholarship_percentage:.0f}% off)'
        return label


class Parent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    relationship = db.Column(db.String(20))  # Father, Mother, Guardian
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(300))
    occupation = db.Column(db.String(100))
    national_id = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_number = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    other_names = db.Column(db.String(50))
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    national_id = db.Column(db.String(20))
    photo = db.Column(db.String(200))
    qualification = db.Column(db.String(200))
    specialization = db.Column(db.String(200))
    department = db.Column(db.String(100))
    position = db.Column(db.String(100))  # Teacher, Head, Clerk, etc.
    employment_date = db.Column(db.Date, default=date.today)
    salary = db.Column(db.Float)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(300))
    status = db.Column(db.String(20), default='Active')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    classes = db.relationship('Class', backref='teacher', lazy=True)
    subject_assignments = db.relationship('StaffSubject', backref='staff', lazy=True)
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StaffSubject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'), nullable=False)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_year.id'))
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), unique=True)
    subject = db.relationship('Subject', backref='staff_assignments')
    class_ = db.relationship('Class', backref='subject_assignments')
    academic_year = db.relationship('AcademicYear', backref='staff_subject_assignments')
    __table_args__ = (
        db.UniqueConstraint(
            'staff_id', 'subject_id', 'class_id', 'academic_year_id',
            name='uq_staff_subject_class_year',
        ),
    )


class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "Mid-Term Exam"
    term_id = db.Column(db.Integer, db.ForeignKey('term.id'))
    exam_type = db.Column(db.String(50))  # Mid-Term, End-of-Term, Assignment, Quiz, Mock
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_year.id'))
    results = db.relationship('ExamResult', backref='exam', lazy=True)
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class ExamResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))
    marks_obtained = db.Column(db.Float)
    marks_total = db.Column(db.Float, default=100)
    grade = db.Column(db.String(5))
    remarks = db.Column(db.String(200))
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class FeeStructure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    level_id = db.Column(db.Integer, db.ForeignKey('fee_level.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_year.id'))
    term_id = db.Column(db.Integer, db.ForeignKey('term.id'))
    tuition = db.Column(db.Float, default=0)
    development_levy = db.Column(db.Float, default=0)
    registration_fee = db.Column(db.Float, default=10)
    textbook_levy = db.Column(db.Float, default=0)
    boarding = db.Column(db.Float, default=0)
    stay_in_fee = db.Column(db.Float, default=0)  # boarding learners only; 0 = automatic by level
    transport = db.Column(db.Float, default=0)
    lunch = db.Column(db.Float, default=0)
    library = db.Column(db.Float, default=0)
    technology = db.Column(db.Float, default=0)
    sports = db.Column(db.Float, default=0)
    other = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    level = db.relationship('FeeLevel', backref='fee_structures')
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class FeePayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    receipt_number = db.Column(db.String(20), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.Date, default=date.today)
    payment_method = db.Column(db.String(30))  # Cash, EcoCash, Bank Transfer, Swipe
    term_id = db.Column(db.Integer, db.ForeignKey('term.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_year.id'))
    description = db.Column(db.String(200))
    received_by = db.Column(db.Integer, db.ForeignKey('staff.id'))
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(30), unique=True, nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_year.id'))
    term_id = db.Column(db.Integer, db.ForeignKey('term.id'))
    issue_date = db.Column(db.Date, default=date.today)
    due_date = db.Column(db.Date)
    subtotal = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Unpaid')  # Unpaid, Partially Paid, Paid, Cancelled
    notes = db.Column(db.Text)
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')
    term = db.relationship('Term', backref='invoices', lazy=True)
    academic_year = db.relationship('AcademicYear', backref='invoices', lazy=True)


class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    description = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, default=0.0)


class Hostel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))  # Male, Female
    capacity = db.Column(db.Integer)
    warden_id = db.Column(db.Integer, db.ForeignKey('staff.id'))
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostel.id'))
    room_number = db.Column(db.String(20), nullable=False)
    capacity = db.Column(db.Integer, default=4)
    current_occupancy = db.Column(db.Integer, default=0)
    hostel = db.relationship('Hostel', backref='rooms')


class RoomAllocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))
    date_allocated = db.Column(db.Date, default=date.today)
    date_vacated = db.Column(db.Date)
    status = db.Column(db.String(20), default='Active')
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class TimetableSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class.id'))
    day_of_week = db.Column(db.String(10), nullable=False)  # Monday-Sunday
    period = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'))
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'))
    room = db.Column(db.String(50))
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # General, Academic, Events, Urgent
    target_audience = db.Column(db.String(50))  # All, Students, Staff, Parents
    posted_by = db.Column(db.Integer, db.ForeignKey('staff.id'))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    date_sent = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class SyncLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    action = db.Column(db.String(20))  # CREATE, UPDATE, DELETE
    sync_status = db.Column(db.String(20), default='pending')  # pending, synced, failed
    sync_timestamp = db.Column(db.DateTime)
    data_snapshot = db.Column(db.Text)  # JSON snapshot of the record
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SchoolSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))


class AppearanceSetting(db.Model):
    """Stores all customizable appearance / theme settings."""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))


class FeeLevel(db.Model):
    """Fee levels: ECD, Junior, O Level, A Level — each with a set fee amount per term."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)          # ECD, Junior, O Level, A Level
    code = db.Column(db.String(20), unique=True, nullable=False)  # ECD, JNR, OLV, ALV
    description = db.Column(db.Text)
    tuition = db.Column(db.Float, default=0)
    development_levy = db.Column(db.Float, default=0)
    registration_fee = db.Column(db.Float, default=10)
    textbook_levy = db.Column(db.Float, default=0)
    boarding = db.Column(db.Float, default=0)
    stay_in_fee = db.Column(db.Float, default=0)  # boarding learners only; 0 = automatic by level
    transport = db.Column(db.Float, default=0)
    lunch = db.Column(db.Float, default=0)
    library = db.Column(db.Float, default=0)
    technology = db.Column(db.Float, default=0)
    sports = db.Column(db.Float, default=0)
    other = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    sync_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))


class SyncSetting(db.Model):
    """Persisted sync configuration — survives app restarts."""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))

    @staticmethod
    def get(key, default=''):
        s = SyncSetting.query.filter_by(key=key).first()
        return s.value if s and s.value else default

    @staticmethod
    def set(key, value, description=''):
        s = SyncSetting.query.filter_by(key=key).first()
        if s:
            s.value = str(value)
            if description:
                s.description = description
        else:
            db.session.add(SyncSetting(key=key, value=str(value), description=description))
        db.session.commit()


# ─── Access Point Monitor (Background Thread) ────────────────────────

import threading
import socket
import time as _time


class AccessPointMonitor:
    """
    Background thread that monitors internet connectivity via the school's
    network access point.  When connectivity is detected the monitor
    automatically triggers a sync if auto-sync is enabled.

    Integration modes:
      • HTTP ping  — tries to reach the WordPress sync endpoint
      • DNS check  — resolves a well-known hostname (fallback)
      • Socket     — raw TCP connect to a public server (fallback)
      • NetworkManager D-Bus — Linux-only, detects WiFi/AP state changes
    """

    def __init__(self, flask_app):
        self.app = flask_app
        self._thread = None
        self._stop_event = threading.Event()
        self.last_check = None
        self.is_online = False
        self.last_error = ''
        self.check_count = 0
        self.auto_sync_count = 0
        self.last_auto_sync = None
        self._last_sync_time = None  # prevent sync-storm (min 60s between auto-syncs)

    # ── public API ────────────────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name='AccessPointMonitor')
        self._thread.start()
        app.logger.info('[AccessPointMonitor] Started background connectivity monitor')

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        app.logger.info('[AccessPointMonitor] Stopped')

    def status(self):
        """Return a dict describing current monitor state (safe for JSON)."""
        return {
            'running': self._thread is not None and self._thread.is_alive(),
            'is_online': self.is_online,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'last_error': self.last_error,
            'check_count': self.check_count,
            'auto_sync_count': self.auto_sync_count,
            'last_auto_sync': self.last_auto_sync.isoformat() if self.last_auto_sync else None,
        }

    # ── internal ──────────────────────────────────────────────────

    def _run(self):
        while not self._stop_event.is_set():
            try:
                with self.app.app_context():
                    self._check_and_sync()
            except Exception as e:
                app.logger.warning(f'[AccessPointMonitor] Error in check loop: {e}')
            # Wait interval (default 30 s, configurable via SyncSetting)
            interval = 30
            try:
                with self.app.app_context():
                    interval = int(SyncSetting.get('auto_sync_interval', '30'))
            except Exception:
                pass
            interval = max(10, min(interval, 600))  # clamp 10-600s
            self._stop_event.wait(interval)

    def _check_and_sync(self):
        """Detect internet & auto-sync when online."""
        auto_enabled = SyncSetting.get('auto_sync_enabled', 'false') == 'true'
        endpoint = SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', '')
        api_key = SyncSetting.get('sync_api_key', '') or app.config.get('SYNC_API_KEY', '')

        self.is_online = False
        self.last_check = datetime.utcnow()

        # Strategy 1: HTTP ping the WordPress endpoint
        if endpoint:
            try:
                import requests as _req
                resp = _req.get(
                    f"{endpoint.rstrip('/')}/api/stats",
                    headers={'X-ESM-API-Key': api_key},
                    timeout=8,
                )
                if resp.status_code == 200:
                    self.is_online = True
                    self.last_error = ''
                else:
                    self.last_error = f'HTTP {resp.status_code}'
            except _req.exceptions.ConnectionError:
                self.last_error = 'Connection refused'
            except _req.exceptions.Timeout:
                self.last_error = 'Timeout'
            except Exception as e:
                self.last_error = str(e)[:100]

        # Strategy 2: DNS resolution fallback
        if not self.is_online:
            try:
                socket.create_connection(('8.8.8.8', 53), timeout=5)
                self.is_online = True
                self.last_error = ''
            except OSError:
                if not self.last_error:
                    self.last_error = 'No internet (DNS check failed)'

        # Strategy 3: NetworkManager D-Bus (Linux only)
        if not self.is_online:
            try:
                self._check_networkmanager()
            except Exception:
                pass  # Non-Linux or NM not available — ignore

        self.check_count += 1

        # Auto-sync when online & enabled
        if self.is_online and auto_enabled and endpoint:
            # Prevent sync storms — at least 60s between auto-syncs
            now = datetime.utcnow()
            if self._last_sync_time and (now - self._last_sync_time).total_seconds() < 60:
                return
            self._last_sync_time = now
            try:
                self._do_auto_sync(endpoint, api_key)
            except Exception as e:
                app.logger.warning(f'[AccessPointMonitor] Auto-sync failed: {e}')

    def _check_networkmanager(self):
        """Use NetworkManager D-Bus to detect WiFi / access-point state (Linux)."""
        try:
            import dbus
            bus = dbus.SystemBus()
            nm = bus.get_object('org.freedesktop.NetworkManager', '/org/freedesktop/NetworkManager')
            props = dbus.Interface(nm, 'org.freedesktop.DBus.Properties')
            state = props.Get('org.freedesktop.NetworkManager', 'State')
            # NM_STATE_CONNECTED_GLOBAL = 70
            if int(state) >= 70:
                self.is_online = True
                self.last_error = ''
        except ImportError:
            pass  # dbus not installed
        except Exception:
            pass  # NM not running

    def _do_auto_sync(self, endpoint, api_key):
        """Push pending changes to WordPress, then pull from WordPress."""
        import requests as _req

        # --- PUSH ---
        pending_logs = SyncLog.query.filter_by(sync_status='pending').all()
        pushed = 0
        entity_tables = {
            'Student': Student, 'Staff': Staff, 'FeePayment': FeePayment,
            'ExamResult': ExamResult,
            'Notice': Notice, 'FeeLevel': FeeLevel, 'Class': Class,
            'Subject': Subject, 'FeeStructure': FeeStructure, 'StaffSubject': StaffSubject,
        }
        for log in pending_logs:
            try:
                data = json.loads(log.data_snapshot) if log.data_snapshot else {}
                if log.action in ('CREATE', 'UPDATE') and log.entity_type in entity_tables:
                    model = entity_tables[log.entity_type]
                    record = model.query.get(log.entity_id)
                    if record:
                        data = {}
                        for c in record.__table__.columns:
                            val = getattr(record, c.name)
                            if isinstance(val, (datetime, date)):
                                val = val.isoformat()
                            elif isinstance(val, timedelta):
                                val = str(val)
                            data[c.name] = val
                payload = {
                    'entity_type': log.entity_type,
                    'entity_id': log.entity_id,
                    'action': log.action,
                    'data': data,
                    'api_key': api_key,
                    'source': 'flask',
                    'timestamp': log.created_at.isoformat() if log.created_at else datetime.utcnow().isoformat(),
                }
                resp = _req.post(
                    f"{endpoint.rstrip('/')}/api/sync",
                    json=payload,
                    headers={'Content-Type': 'application/json', 'X-ESM-API-Key': api_key},
                    timeout=30,
                )
                if resp.status_code < 300:
                    log.sync_status = 'synced'
                    log.sync_timestamp = datetime.utcnow()
                    pushed += 1
                else:
                    log.sync_status = 'failed'
                    log.sync_timestamp = datetime.utcnow()
            except Exception:
                log.sync_status = 'failed'
                log.sync_timestamp = datetime.utcnow()
        db.session.commit()

        # --- PULL ---
        pulled = 0
        try:
            resp = _req.get(
                f"{endpoint.rstrip('/')}/api/sync/pending",
                headers={'X-ESM-API-Key': api_key},
                timeout=30,
            )
            if resp.status_code == 200:
                body = resp.json()
                items = body.get('pending', [])
                entity_models = {
                    'Student': Student, 'Staff': Staff, 'FeePayment': FeePayment,
                    'ExamResult': ExamResult,
                    'Notice': Notice, 'FeeLevel': FeeLevel, 'FeeStructure': FeeStructure,
                    'Class': Class, 'Subject': Subject, 'StaffSubject': StaffSubject,
                    'AcademicYear': AcademicYear, 'Term': Term,
                }
                synced_ids = []
                for item in items:
                    entity_type = item.get('entity_type', '')
                    action = item.get('action', '')
                    entity_data = item.get('data') or {}
                    sync_id_val = entity_data.get('sync_id', '')
                    incoming_ts = item.get('created_at', '')
                    model = entity_models.get(entity_type)
                    if not model:
                        continue
                    if action in ('CREATE', 'UPDATE'):
                        existing = None
                        if sync_id_val and hasattr(model, 'sync_id'):
                            existing = model.query.filter_by(sync_id=sync_id_val).first()
                        if existing:
                            should_update = True
                            if incoming_ts and hasattr(existing, 'updated_at') and existing.updated_at:
                                try:
                                    incoming_dt = datetime.fromisoformat(incoming_ts.replace('Z', '+00:00')).replace(tzinfo=None)
                                    if incoming_dt <= existing.updated_at:
                                        should_update = False
                                except (ValueError, AttributeError):
                                    pass
                            if should_update:
                                for k, v in entity_data.items():
                                    if hasattr(existing, k) and k not in ('id', 'created_at'):
                                        try:
                                            setattr(existing, k, v)
                                        except (ValueError, TypeError):
                                            pass
                                if hasattr(existing, 'updated_at'):
                                    existing.updated_at = datetime.utcnow()
                                pulled += 1
                        else:
                            try:
                                new_record = model()
                                for k, v in entity_data.items():
                                    if hasattr(new_record, k) and k != 'id':
                                        try:
                                            setattr(new_record, k, v)
                                        except (ValueError, TypeError):
                                            pass
                                if not getattr(new_record, 'sync_id', None) and sync_id_val:
                                    new_record.sync_id = sync_id_val
                                db.session.add(new_record)
                                pulled += 1
                            except Exception:
                                pass
                    elif action == 'DELETE':
                        eid = item.get('entity_id', 0)
                        if eid:
                            record = model.query.get(eid)
                            if record:
                                if hasattr(record, 'status'):
                                    record.status = 'Inactive'
                                else:
                                    db.session.delete(record)
                                pulled += 1
                    synced_ids.append(item.get('id'))
                if synced_ids:
                    try:
                        _req.post(
                            f"{endpoint.rstrip('/')}/api/sync/mark-synced",
                            json={'ids': synced_ids, 'api_key': api_key},
                            headers={'Content-Type': 'application/json', 'X-ESM-API-Key': api_key},
                            timeout=15,
                        )
                    except Exception:
                        pass
                db.session.commit()
        except Exception as e:
            app.logger.warning(f'[AccessPointMonitor] Pull failed: {e}')

        SyncSetting.set('last_sync_time', datetime.utcnow().isoformat(), 'Last successful sync timestamp')
        SyncSetting.set('last_sync_status', 'success', 'Last sync result status')
        SyncSetting.set('last_sync_pushed', str(pushed))
        SyncSetting.set('last_sync_pulled', str(pulled))

        self.auto_sync_count += 1
        self.last_auto_sync = datetime.utcnow()
        app.logger.info(f'[AccessPointMonitor] Auto-sync complete: pushed={pushed}, pulled={pulled}')


# Create the monitor instance (started after init_db)
ap_monitor = AccessPointMonitor(app)


# ─── Theme Helper ──────────────────────────────────────────────────────

# Default appearance values
# Brand colours derived from the official EGS crest (deep navy + gold/yellow).
DEFAULT_THEME = {
    'school_name': 'Excel Group of Schools',
    'school_motto': 'Wea Sono la Cremma Della Terra',
    'school_address': '',
    'school_phone': '',
    'school_email': '',
    # Deep navy blue — matches the EGS crest outer ring & shield
    'primary_color': '#1F2080',
    'primary_dark': '#13145A',
    'primary_light': '#3F4099',
    # Gold/yellow — matches the EGS crest highlight
    'secondary_color': '#FDEE00',
    'secondary_light': '#FFF266',
    # Accent (kept warm/orange so danger badges stay distinct from primary)
    'accent_color': '#E85D26',
    # Neutral surfaces
    'bg_color': '#F5F5F7',
    'card_color': '#FFFFFF',
    'text_color': '#14152E',
    'sidebar_style': 'gradient',  # gradient, solid, dark
    'font_family': 'Segoe UI, Tahoma, Geneva, Verdana, sans-serif',
    # Default logo (the official EGS crest)
    'logo_url': 'images/egs-logo.png',
    'favicon_url': '',
    'login_bg_image': '',
}


def get_theme():
    """Load all appearance settings; fall back to defaults."""
    settings = {}
    for row in AppearanceSetting.query.all():
        settings[row.key] = row.value
    # Merge with defaults
    theme = dict(DEFAULT_THEME)
    theme.update(settings)
    return theme


def set_theme(key, value):
    """Set a single appearance setting."""
    setting = AppearanceSetting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        setting = AppearanceSetting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()


# ─── Decorators ────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ─── Role Definitions & Privileges ─────────────────────────────────────

ROLE_LABELS = {
    'super_admin': 'Super Admin',
    'accountant': 'Accountant',
    'bursar': 'Bursar',
    'teacher': 'Teacher',
    'parent': 'Parent',
    'student': 'Student',
}

ROLE_DESCRIPTIONS = {
    'super_admin': 'Directors & Principals — Full system access',
    'accountant': 'Financial management — Fees, payments, reports',
    'bursar': 'Student admissions & financial oversight',
    'teacher': 'Academic access — Exams, class management',
    'parent': 'View child information — Fees, results, attendance',
    'student': 'Personal portal — Results, timetable, attendance',
}

ROLE_PRIVILEGES = {
    'super_admin': [
        'Full access to all modules',
        'User management & role assignment',
        'System settings & appearance',
        'Sync management',
        'Bulk import/export',
        'Fee level configuration',
        'Staff & student CRUD',
        'Financial reports & dashboards',
        'Communication management',
        'WhatsApp notifications',
    ],
    'accountant': [
        'Fee management — structures, payments, receipts',
        'Fee level configuration',
        'Financial reports',
        'Payment records & receipts (PDF)',
        'Fee balance checking',
        'Dashboard with financial stats',
        'Communication (view only)',
        'Reports — fees & financial',
    ],
    'bursar': [
        'Student admissions & registration',
        'Student CRUD (add, edit, view)',
        'Fee management — structures, payments, receipts',
        'Process fee payments & generate receipts',
        'Fee balance checking',
        'Scholarship classification',
        'Bulk student import',
        'Communication management',
        'Reports — students, fees',
        'Dashboard with student & financial stats',
        'Sync management — manual, automatic, import & export',
    ],
    'teacher': [
        'Exam & results entry',
        'Report card generation',
        'View student list (own class)',
        'Timetable view',
        'Library (issue/return)',
        'Communication (view notices)',
        'Reports — attendance, exam results',
    ],
    'parent': [
        'Parent portal — child overview',
        'View child attendance',
        'View child exam results',
        'View fee balance & payment history',
        'View notices & communication',
        'View child timetable',
    ],
    'student': [
        'Student portal — personal overview',
        'View own attendance',
        'View own exam results',
        'View own fee balance',
        'View own timetable',
        'View notices',
    ],
}

# Which nav sections each role can see
ROLE_NAV_SECTIONS = {
    'super_admin': ['main', 'people', 'academic', 'finance', 'resources', 'communication', 'analytics', 'system'],
    'accountant': ['main', 'finance', 'analytics', 'communication'],
    'bursar': ['main', 'people', 'finance', 'communication', 'analytics', 'system'],
    'teacher': ['main', 'people', 'academic', 'resources', 'communication', 'analytics'],
    'parent': ['main', 'communication'],
    'student': ['main', 'academic', 'communication'],
}

# Which specific nav items each role can access (route endpoint keywords)
ROLE_NAV_ITEMS = {
    'super_admin': ['dashboard', 'students_list', 'classes_list', 'staff_list', 'exams_list',
                    'timetable_view', 'fees_dashboard', 'invoices_list', 'debtors_list',
                    'fee_levels_list',
                    'hostel_dashboard', 'communication_dashboard',
                    'reports_dashboard', 'sync_dashboard', 'settings', 'appearance_settings',
                    'parent_portal', 'student_portal', 'user_management'],
    'accountant': ['dashboard', 'fees_dashboard', 'invoices_list', 'debtors_list',
                   'fee_levels_list', 'reports_dashboard',
                   'communication_dashboard', 'user_management'],
    'bursar': ['dashboard', 'students_list', 'classes_list', 'fees_dashboard', 'invoices_list',
               'debtors_list', 'communication_dashboard',
               'reports_dashboard', 'sync_dashboard'],
    'teacher': ['dashboard', 'students_list', 'exams_list',
                'timetable_view', 'communication_dashboard', 'reports_dashboard'],
    'parent': ['dashboard', 'parent_portal', 'communication_dashboard'],
    'student': ['dashboard', 'student_portal', 'communication_dashboard'],
}


def get_role_home_endpoint(role):
    """Return the default landing page endpoint for a given role."""
    return {
        'super_admin': 'dashboard',
        'accountant': 'fees_dashboard',
        'bursar': 'dashboard',
        'teacher': 'teacher_home',
        'parent': 'parent_portal',
        'student': 'student_portal',
    }.get(role, 'dashboard')


# ─── Teacher Access Control Helpers ─────────────────────────────────

def _staff_for_current_user():
    """Return the Staff record linked to the currently-logged-in user, or None."""
    if 'user_id' not in session:
        return None
    return Staff.query.filter_by(user_id=session['user_id']).first()


def get_teacher_class_ids(staff_id, ay_id=None):
    """Return every class explicitly assigned to this teacher.

    A teacher may access a class either as its form master (Class.teacher_id)
    or through a class+subject StaffSubject assignment. This is important for
    secondary teachers who commonly teach one subject across several streams.
    """
    if ay_id is None:
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        ay_id = current_year.id if current_year else None
    form_class_query = Class.query.filter_by(teacher_id=staff_id)
    if ay_id:
        form_class_query = form_class_query.filter(db.or_(
            Class.academic_year_id == ay_id,
            Class.academic_year_id.is_(None),
        ))
    class_ids = {c.id for c in form_class_query.all()}
    query = StaffSubject.query.filter_by(staff_id=staff_id)
    if ay_id:
        query = query.filter(db.or_(
            StaffSubject.academic_year_id == ay_id,
            StaffSubject.academic_year_id.is_(None),
        ))
    class_ids.update(ss.class_id for ss in query.all() if ss.class_id)
    return sorted(class_ids)


def get_teacher_subject_ids(staff_id, class_id=None, ay_id=None):
    """Return subjects explicitly assigned to a teacher, optionally per class."""
    query = StaffSubject.query.filter_by(staff_id=staff_id)
    if class_id:
        query = query.filter_by(class_id=class_id)
    if ay_id is None:
        current_year = AcademicYear.query.filter_by(is_current=True).first()
        ay_id = current_year.id if current_year else None
    if ay_id:
        query = query.filter(db.or_(
            StaffSubject.academic_year_id == ay_id,
            StaffSubject.academic_year_id.is_(None),
        ))
    return sorted({ss.subject_id for ss in query.all() if ss.subject_id})


def get_teacher_classes_with_subjects(staff_id, ay_id=None):
    """Return dict: {class_id: [subject_id, ...]} of (class, subject) pairs assigned.

    Combines:
      • Classes where the teacher is form master (Staff via Class.teacher_id)
      • Subjects assigned via StaffSubject (per academic year if given)
    """
    from collections import defaultdict
    result = defaultdict(set)
    form_class_query = Class.query.filter_by(teacher_id=staff_id)
    if ay_id:
        form_class_query = form_class_query.filter(db.or_(
            Class.academic_year_id == ay_id,
            Class.academic_year_id.is_(None),
        ))
    for c in form_class_query.all():
        # Primary form masters cover the standard primary learning areas.
        # Secondary form-master status is pastoral only; teaching access must
        # always come from explicit class+subject assignments.
        if is_primary_level(c.level):
            for subject in Subject.query.filter(Subject.name.in_(PRIMARY_LEARNING_AREAS)).all():
                result[c.id].add(subject.id)
        else:
            result[c.id]  # Keep the form class visible, with no implied subjects.
    # Also add explicit StaffSubject rows (class+subject combos)
    q = StaffSubject.query.filter_by(staff_id=staff_id)
    if ay_id:
        q = q.filter(db.or_(
            StaffSubject.academic_year_id == ay_id,
            StaffSubject.academic_year_id.is_(None),
        ))
    for ss in q.all():
        if ss.class_id and ss.subject_id:
            result[ss.class_id].add(ss.subject_id)
    return {cid: list(sids) for cid, sids in result.items()}


def teacher_can_access_class(staff_id, class_id):
    """Return True if this teacher has any assignment to the given class."""
    return class_id in get_teacher_class_ids(staff_id)


def teacher_can_access_subject(staff_id, subject_id, class_id=None):
    """Check an explicit subject assignment, optionally for one class."""
    return subject_id in get_teacher_subject_ids(staff_id, class_id=class_id)


def teacher_can_teach(staff_id, class_id, subject_id, ay_id=None):
    """Require the exact teacher+class+subject combination for mark entry."""
    return subject_id in get_teacher_classes_with_subjects(staff_id, ay_id).get(class_id, [])


def teacher_can_access_student(staff_id, student_id):
    """A teacher can access a student only if the student is in one of their classes."""
    s = Student.query.get(student_id)
    if not s or not s.class_id:
        return False
    return teacher_can_access_class(staff_id, s.class_id)


def teacher_query_filter(query, model, staff_id):
    """Apply teacher-access filtering to a SQLAlchemy query.

    `model` is the SQLAlchemy class. The function inspects common column
    names to figure out how to filter.
    """
    if not staff_id:
        return query
    class_ids = get_teacher_class_ids(staff_id)
    if hasattr(model, 'class_id'):
        return query.filter(model.class_id.in_(class_ids))
    if hasattr(model, 'student_id'):
        # Restrict via the student's class
        return query.join(Student, model.student_id == Student.id) \
                   .filter(Student.class_id.in_(class_ids))
    return query


def teacher_required(f):
    """Decorator: restrict access to users in the 'teacher' role only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_role' not in session or session['user_role'] != 'teacher':
            flash('This portal is for teachers only.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated



# ─── Helper Functions ──────────────────────────────────────────────────

def get_current_academic_year():
    return AcademicYear.query.filter_by(is_current=True).first()


def get_current_term():
    return Term.query.filter_by(is_current=True).first()


def compute_grade(marks, total=100):
    percentage = (marks / total) * 100 if total > 0 else 0
    if percentage >= 80:
        return 'A'
    elif percentage >= 70:
        return 'B'
    elif percentage >= 60:
        return 'C'
    elif percentage >= 50:
        return 'D'
    elif percentage >= 40:
        return 'E'
    else:
        return 'U'


def generate_receipt_number():
    today = date.today()
    prefix = f"REC{today.strftime('%Y%m')}"
    last_payment = FeePayment.query.filter(
        FeePayment.receipt_number.like(f"{prefix}%")
    ).order_by(FeePayment.id.desc()).first()
    if last_payment:
        last_num = int(last_payment.receipt_number[-4:])
        return f"{prefix}{last_num + 1:04d}"
    return f"{prefix}0001"


def generate_admission_number():
    today = date.today()
    prefix = f"EXC{today.strftime('%Y')}"
    last_student = Student.query.filter(
        Student.admission_number.like(f"{prefix}%")
    ).order_by(Student.id.desc()).first()
    if last_student:
        last_num = int(last_student.admission_number[-4:])
        return f"{prefix}{last_num + 1:04d}"
    return f"{prefix}0001"


def generate_employee_number():
    """Auto-generate an employee number like EMP0001, EMP0002, etc."""
    last_staff = Staff.query.order_by(Staff.id.desc()).first()
    if last_staff:
        try:
            last_num = int(last_staff.employee_number.replace('EMP', ''))
        except ValueError:
            last_num = 0
        return f"EMP{last_num + 1:04d}"
    return "EMP0001"


def generate_invoice_number():
    today = date.today()
    prefix = f"INV{today.strftime('%Y%m')}"
    last_invoice = Invoice.query.filter(
        Invoice.invoice_number.like(f"{prefix}%")
    ).order_by(Invoice.id.desc()).first()
    if last_invoice:
        last_num = int(last_invoice.invoice_number[-4:])
        return f"{prefix}{last_num + 1:04d}"
    return f"{prefix}0001"


# Stay In (boarding) fees billed every term to learners whose entry mode is
# "Stay In": $300 for primary and secondary (O Level), $260 for A Level.
# A fee level/structure can override this with its own stay_in_fee amount.
STAY_IN_FEE_PRIMARY_SECONDARY = 300.0
STAY_IN_FEE_A_LEVEL = 260.0


def normalize_entry_mode(value):
    """Map user input (Excel, forms) to the canonical entry modes Day / Stay In."""
    text = (value or '').strip().lower()
    if text in ('stay in', 'stay-in', 'stayin', 'boarding', 'boarder',
                'boarding student', 'resident', 'residential', 'hostel', 'hosteller'):
        return 'Stay In'
    return 'Day'


def get_stay_in_fee_default(student):
    """Automatic Stay In fee by level: $300 primary/secondary, $260 A Level."""
    if student.class_ and student.class_.level:
        m = re.search(r'Form\s*(\d+)', student.class_.level, re.IGNORECASE)
        if m and int(m.group(1)) >= 5:
            return STAY_IN_FEE_A_LEVEL
    return STAY_IN_FEE_PRIMARY_SECONDARY


def get_student_fee_structure(student, term=None, ay=None):
    if not term:
        term = get_current_term()
    if not ay:
        ay = get_current_academic_year()
    if not term or not ay:
        return None
    fs = None
    level = None
    if student.class_ and student.class_.level:
        level_name = student.class_.level
        fee_level_name = None
        if is_primary_level(level_name):
            if level_name.strip().lower().startswith('ecd'):
                fee_level_name = 'ECD'
            else:
                fee_level_name = 'Junior'
        else:
            m = re.search(r'Form\s*(\d+)', level_name, re.IGNORECASE)
            if m:
                f = int(m.group(1))
                if 1 <= f <= 4:
                    fee_level_name = 'O Level'
                elif f >= 5:
                    fee_level_name = 'A Level'
        level = FeeLevel.query.filter_by(name=fee_level_name).first() if fee_level_name else None
        if level:
            fs = FeeStructure.query.filter_by(
                level_id=level.id,
                academic_year_id=ay.id,
                term_id=term.id
            ).first()
    if not fs and student.class_id:
        fs = FeeStructure.query.filter_by(
            class_id=student.class_id,
            academic_year_id=ay.id,
            term_id=term.id
        ).first()
    return fs or level


def update_invoice_status(invoice):
    if not invoice:
        return
    total_paid = db.session.query(db.func.sum(FeePayment.amount)).filter(
        FeePayment.student_id == invoice.student_id,
        FeePayment.term_id == invoice.term_id,
        FeePayment.academic_year_id == invoice.academic_year_id
    ).scalar() or 0.0
    if invoice.total_amount <= 0 or total_paid >= invoice.total_amount:
        invoice.status = 'Paid'
    elif total_paid > 0:
        invoice.status = 'Partially Paid'
    else:
        invoice.status = 'Unpaid'


def update_invoice_statuses_for_student(student_id, term_id=None, academic_year_id=None):
    query = Invoice.query.filter_by(student_id=student_id)
    if term_id:
        query = query.filter_by(term_id=term_id)
    if academic_year_id:
        query = query.filter_by(academic_year_id=academic_year_id)
    invoices = query.all()
    for inv in invoices:
        update_invoice_status(inv)


def generate_student_invoice(student, term=None, academic_year=None):
    """Generate or refresh an invoice for a student for the given term/academic year."""
    if not term:
        term = get_current_term()
    if not academic_year:
        academic_year = get_current_academic_year()
    if not term or not academic_year:
        return None
    
    existing = Invoice.query.filter_by(
        student_id=student.id,
        term_id=term.id,
        academic_year_id=academic_year.id
    ).first()

    source = get_student_fee_structure(student, term, academic_year)
    if not source and not existing:
        return None

    items_data = []
    if source:
        tuition = getattr(source, 'tuition', 0.0) or 0.0
        dev_levy = getattr(source, 'development_levy', 0.0) or 0.0
        if tuition > 0: items_data.append(('Tuition Fee', tuition))
        if dev_levy > 0: items_data.append(('Development Levy', dev_levy))

        # Check once-off registration fee and textbook levy for new learners
        if getattr(student, 'is_new_learner', True) and not getattr(student, 'billed_once_off_levies', False):
            reg_fee = getattr(source, 'registration_fee', 10.0) or 10.0
            tb_levy = getattr(source, 'textbook_levy', 0.0) or 0.0
            if reg_fee > 0: items_data.append(('Registration Fee (Once-off)', reg_fee))
            if tb_levy > 0: items_data.append(('Textbook Levy (Once-off)', tb_levy))
            student.billed_once_off_levies = True

        # Stay In (boarding) learners are billed the Stay In fee every term.
        # Amount comes from the fee level/structure, or defaults automatically:
        # $300 primary & secondary, $260 A Level.
        if getattr(student, 'entry_mode', 'Day') == 'Stay In':
            stay_fee = float(getattr(source, 'stay_in_fee', 0.0) or 0.0)
            if stay_fee <= 0:
                stay_fee = get_stay_in_fee_default(student)
            if stay_fee > 0:
                items_data.append(('Stay In Fee (Boarding)', stay_fee))

        # Keep legacy optional fees if explicitly greater than 0
        if (getattr(student, 'entry_mode', 'Day') != 'Stay In'
                and getattr(source, 'boarding', 0.0) and source.boarding > 0):
            items_data.append(('Boarding Fee', source.boarding))
        if getattr(source, 'transport', 0.0) and source.transport > 0: items_data.append(('Transport Fee', source.transport))
        if getattr(source, 'lunch', 0.0) and source.lunch > 0: items_data.append(('Lunch & Meals', source.lunch))
        if getattr(source, 'library', 0.0) and source.library > 0: items_data.append(('Library Levy', source.library))
        if getattr(source, 'technology', 0.0) and source.technology > 0: items_data.append(('Technology Levy', source.technology))
        if getattr(source, 'sports', 0.0) and source.sports > 0: items_data.append(('Sports & Activities', source.sports))
        if getattr(source, 'other', 0.0) and source.other > 0: items_data.append(('Other Levies', source.other))
        if not items_data and getattr(source, 'total', 0.0) and source.total > 0:
            items_data.append(('General Term Fee', source.total))
    
    subtotal = sum(amt for desc, amt in items_data)
    multiplier = student.effective_fee_multiplier
    discount = subtotal * (1.0 - multiplier)
    total = subtotal - discount

    if existing:
        existing.subtotal = subtotal
        existing.discount_amount = discount
        existing.total_amount = total
        InvoiceItem.query.filter_by(invoice_id=existing.id).delete()
        for desc, amt in items_data:
            db.session.add(InvoiceItem(invoice_id=existing.id, description=desc, amount=amt))
        update_invoice_status(existing)
        return existing

    inv = Invoice(
        invoice_number=generate_invoice_number(),
        student_id=student.id,
        academic_year_id=academic_year.id,
        term_id=term.id,
        issue_date=date.today(),
        due_date=term.end_date if term and term.end_date else date.today(),
        subtotal=subtotal,
        discount_amount=discount,
        total_amount=total
    )
    db.session.add(inv)
    db.session.flush()
    for desc, amt in items_data:
        db.session.add(InvoiceItem(invoice_id=inv.id, description=desc, amount=amt))
    update_invoice_status(inv)
    return inv


def log_sync(entity_type, entity_id, action, data=None):
    """Log a change for offline-online synchronization."""
    log = SyncLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        data_snapshot=json.dumps(data) if data else None
    )
    db.session.add(log)
    db.session.commit()


def get_dashboard_stats():
    """Aggregate statistics for the dashboard."""
    stats = {
        'total_students': Student.query.filter_by(status='Active').count(),
        'total_staff': Staff.query.filter_by(status='Active').count(),
        'total_classes': Class.query.count(),
        'total_parents': Parent.query.count(),
        'male_students': Student.query.filter_by(gender='Male', status='Active').count(),
        'female_students': Student.query.filter_by(gender='Female', status='Active').count(),
        'fees_collected_today': db.session.query(db.func.sum(FeePayment.amount)).filter(
            FeePayment.payment_date == date.today()
        ).scalar() or 0,
        'fees_collected_month': db.session.query(db.func.sum(FeePayment.amount)).filter(
            db.func.strftime('%Y-%m', FeePayment.payment_date) == date.today().strftime('%Y-%m')
        ).scalar() or 0,
        'pending_sync': SyncLog.query.filter_by(sync_status='pending').count(),
    }
    return stats


# ─── Auth Routes ───────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.is_active:
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_role'] = user.role
            session['role_label'] = ROLE_LABELS.get(user.role, user.role.title())
            user.last_login = datetime.utcnow()
            db.session.commit()
            flash('Login successful!', 'success')
            home = get_role_home_endpoint(user.role)
            return redirect(url_for(home))
        flash('Invalid username or password.', 'danger')
    return render_template('auth/login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current = request.form.get('current_password')
        new = request.form.get('new_password')
        confirm = request.form.get('confirm_password')
        user = User.query.get(session['user_id'])
        if not user.check_password(current):
            flash('Current password is incorrect.', 'danger')
        elif new != confirm:
            flash('New passwords do not match.', 'danger')
        else:
            user.set_password(new)
            db.session.commit()
            flash('Password changed successfully.', 'success')
            return redirect(url_for('dashboard'))
    return render_template('auth/change_password.html')


# ─── Dashboard ─────────────────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    if session.get('user_role') == 'teacher':
        return redirect(url_for('teacher_home'))
    stats = get_dashboard_stats()
    recent_students = Student.query.filter_by(status='Active').order_by(
        Student.created_at.desc()).limit(5).all()
    recent_payments = FeePayment.query.order_by(
        FeePayment.created_at.desc()).limit(5).all()
    notices = Notice.query.filter_by(is_active=True).order_by(
        Notice.date_posted.desc()).limit(5).all()
    role = session.get('user_role', '')
    return render_template('dashboard/index.html',
                           stats=stats,
                           recent_students=recent_students,
                           recent_payments=recent_payments,
                           notices=notices,
                           user_role=role)


# ─── Student Management ────────────────────────────────────────────────

@app.route('/students')
@login_required
@role_required('super_admin', 'bursar', 'teacher')
def students_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    class_filter = request.args.get('class', '')
    status_filter = request.args.get('status', '')
    scholarship_filter = request.args.get('scholarship', '')
    query = Student.query
    # Teacher portal: restrict visible students to those in the teacher's classes
    if session.get('user_role') == 'teacher':
        staff = _staff_for_current_user()
        if staff:
            query = query.filter(Student.class_id.in_(get_teacher_class_ids(staff.id)))
    if search:
        query = query.filter(db.or_(
            Student.first_name.ilike(f'%{search}%'),
            Student.last_name.ilike(f'%{search}%'),
            Student.admission_number.ilike(f'%{search}%')
        ))
    if class_filter:
        query = query.filter_by(class_id=class_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if scholarship_filter:
        if scholarship_filter == 'Any Scholarship':
            query = query.filter(Student.fee_classification != 'Regular')
        else:
            query = query.filter_by(fee_classification=scholarship_filter)
    students = query.order_by(Student.last_name).paginate(
        page=page, per_page=20, error_out=False)
    if session.get('user_role') == 'teacher':
        staff = _staff_for_current_user()
        class_ids = get_teacher_class_ids(staff.id) if staff else []
        classes = Class.query.filter(Class.id.in_(class_ids)).order_by(Class.name).all() if class_ids else []
    else:
        classes = Class.query.order_by(Class.name).all()
    classifications = db.session.query(Student.fee_classification).distinct().all()
    return render_template('students/list.html',
                           students=students,
                           classes=classes,
                           classifications=[c[0] for c in classifications if c[0]],
                           search=search,
                           class_filter=class_filter,
                           status_filter=status_filter,
                           scholarship_filter=scholarship_filter)


@app.route('/students/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'bursar')
def student_add():
    if request.method == 'POST':
        admission_number = generate_admission_number()
        student = Student(
            admission_number=admission_number,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            other_names=_clean_optional_text(request.form.get('other_names')),
            entry_mode=normalize_entry_mode(request.form.get('entry_mode')),
            date_of_birth=datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date() if request.form.get('date_of_birth') else None,
            gender=request.form.get('gender'),
            national_id=request.form.get('national_id'),
            class_id=request.form.get('class_id') or None,
            admission_date=datetime.strptime(request.form.get('admission_date'), '%Y-%m-%d').date() if request.form.get('admission_date') else date.today(),
            previous_school=request.form.get('previous_school'),
            medical_info=request.form.get('medical_info'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            province=request.form.get('province'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            # Scholarship fields
            fee_classification=request.form.get('fee_classification', 'Regular'),
            scholarship_type=request.form.get('scholarship_type', 'None'),
            scholarship_percentage=float(request.form.get('scholarship_percentage', 0)),
            scholarship_sponsor=request.form.get('scholarship_sponsor'),
            scholarship_staff_id=request.form.get('scholarship_staff_id') if request.form.get('scholarship_staff_id') else None,
            scholarship_notes=request.form.get('scholarship_notes'),
        )

        # Handle photo upload
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
                    filename = secure_filename(f"student_{admission_number}_{uuid.uuid4().hex[:8]}.{ext}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    student.photo = f"uploads/{filename}"

        db.session.add(student)
        db.session.flush()
        generate_student_invoice(student)

        # NOTE: Students do NOT get user accounts.
        # They access the system via the Student Portal linked to their parent's account.
        # Only staff members receive user accounts with roles.

        # Add parent if provided
        parent_fname = request.form.get('parent_first_name')
        parent_lname = request.form.get('parent_last_name')
        if parent_fname and parent_lname:
            parent = Parent(
                first_name=parent_fname,
                last_name=parent_lname,
                relationship=request.form.get('parent_relationship'),
                phone=request.form.get('parent_phone'),
                email=request.form.get('parent_email'),
                occupation=request.form.get('parent_occupation'),
                address=request.form.get('parent_address'),
                national_id=request.form.get('parent_national_id'),
            )
            db.session.add(parent)
            db.session.flush()
            student.parents.append(parent)
            # NOTE: Parents do NOT get automatic user accounts.
            # Parent accounts are created only by admin via User Management when needed.

        db.session.commit()
        log_sync('Student', student.id, 'CREATE', {'admission_number': student.admission_number})
        flash(f'Student registered successfully. Admission Number: {admission_number}', 'success')
        return redirect(url_for('students_list'))

    # GET — provide data for dropdowns
    classes = Class.query.order_by(Class.name).all()
    staff_list = Staff.query.filter_by(status='Active').all()
    fee_levels = FeeLevel.query.order_by(FeeLevel.id).all()
    next_admission = generate_admission_number()

    # Build level → classes map for JS dropdown
    level_classes = {}
    for c in classes:
        lvl = c.level or 'Unassigned'
        if lvl not in level_classes:
            level_classes[lvl] = []
        level_classes[lvl].append({'id': c.id, 'name': c.name})

    # Serialize fee levels for JS
    fee_levels_json = [{'id': fl.id, 'name': fl.name, 'code': fl.code,
                        'total': fl.total, 'description': fl.description or ''}
                       for fl in fee_levels]

    return render_template('students/add.html',
                           classes=classes,
                           staff_list=staff_list,
                           fee_levels=fee_levels,
                           next_admission=next_admission,
                           today=date.today().isoformat(),
                           level_classes=json.dumps(level_classes),
                           fee_levels_json=json.dumps(fee_levels_json))


@app.route('/students/<int:id>')
@login_required
def student_view(id):
    student = Student.query.get_or_404(id)
    # Teacher portal: block access to students not in their classes
    if session.get('user_role') == 'teacher':
        staff = _staff_for_current_user()
        if not staff or not teacher_can_access_student(staff.id, id):
            flash('You do not have access to this student.', 'danger')
            return redirect(url_for('teacher_home'))
        assigned_subject_ids = get_teacher_subject_ids(staff.id, class_id=student.class_id)
        results = ExamResult.query.filter(
            ExamResult.student_id == id,
            ExamResult.subject_id.in_(assigned_subject_ids),
        ).all() if assigned_subject_ids else []
        payments = []
    else:
        results = ExamResult.query.filter_by(student_id=id).all()
        payments = FeePayment.query.filter_by(student_id=id).order_by(
            FeePayment.payment_date.desc()).all()
    return render_template('students/view.html',
                           student=student,
                           attendances=[],
                           results=results,
                           payments=payments,
                           classes=Class.query.order_by(Class.name).all())


@app.route('/students/<int:id>/reassign-class', methods=['POST'])
@login_required
@role_required('super_admin', 'bursar')
def student_reassign_class(id):
    """Quickly move one student to a different class (from the profile page)."""
    student = Student.query.get_or_404(id)
    new_class_id = request.form.get('class_id') or None
    if not new_class_id:
        flash('Please select a class to move the student to.', 'warning')
        return redirect(url_for('student_view', id=id))
    cls = Class.query.get(new_class_id)
    if cls is None:
        flash('The selected class no longer exists.', 'danger')
        return redirect(url_for('student_view', id=id))
    old_class_name = student.class_.name if student.class_ else 'No class'
    student.class_id = cls.id
    student.updated_at = datetime.utcnow()
    db.session.commit()
    log_sync('Student', student.id, 'UPDATE', {
        'admission_number': student.admission_number,
        'class_id': student.class_id,
        'class_name': cls.name,
    })
    flash(f'{student.first_name} {student.last_name} moved from '
          f'{old_class_name} to {cls.name}.', 'success')
    return redirect(url_for('student_view', id=id))


@app.route('/students/bulk-reassign-class', methods=['POST'])
@login_required
@role_required('super_admin', 'bursar')
def students_bulk_reassign_class():
    """Move several selected students to one class in a single action."""
    new_class_id = request.form.get('new_class_id') or None
    student_ids = request.form.getlist('student_ids')
    if not new_class_id:
        flash('Please select the destination class.', 'warning')
        return redirect(url_for('students_list'))
    cls = Class.query.get(new_class_id)
    if cls is None:
        flash('The selected class no longer exists.', 'danger')
        return redirect(url_for('students_list'))
    ids = []
    for value in student_ids:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    if not ids:
        flash('No students were selected.', 'warning')
        return redirect(url_for('students_list'))
    moved = 0
    for student in Student.query.filter(Student.id.in_(ids)).all():
        if student.class_id != cls.id:
            student.class_id = cls.id
            student.updated_at = datetime.utcnow()
            moved += 1
    db.session.commit()
    for student in Student.query.filter(Student.id.in_(ids)).all():
        log_sync('Student', student.id, 'UPDATE', {
            'admission_number': student.admission_number,
            'class_id': student.class_id,
            'class_name': cls.name,
        })
    flash(f'{moved} student(s) moved to {cls.name}.', 'success')
    back = request.form.get('back') or ''
    if back.startswith('/'):
        return redirect(back)
    return redirect(url_for('students_list'))


@app.route('/students/bulk-delete', methods=['POST'])
@login_required
@role_required('super_admin', 'bursar')
def students_bulk_delete():
    """Permanently remove the selected learners and all of their records."""
    ids = []
    for value in request.form.getlist('student_ids'):
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    if not ids:
        flash('No students were selected.', 'warning')
        return redirect(request.form.get('back') or url_for('students_list'))
    students = Student.query.filter(Student.id.in_(ids)).all()
    deleted = len(students)
    # Remove links and child rows before deleting the learners themselves.
    db.session.execute(
        student_parent.delete().where(student_parent.c.student_id.in_(ids)))
    invoice_ids = db.session.query(Invoice.id).filter(Invoice.student_id.in_(ids))
    InvoiceItem.query.filter(InvoiceItem.invoice_id.in_(invoice_ids)).delete(
        synchronize_session=False)
    Invoice.query.filter(Invoice.student_id.in_(ids)).delete(
        synchronize_session=False)
    FeePayment.query.filter(FeePayment.student_id.in_(ids)).delete(
        synchronize_session=False)
    ExamResult.query.filter(ExamResult.student_id.in_(ids)).delete(
        synchronize_session=False)
    RoomAllocation.query.filter(RoomAllocation.student_id.in_(ids)).delete(
        synchronize_session=False)
    for student in students:
        log_sync('Student', student.id, 'DELETE')
        db.session.delete(student)
    db.session.commit()
    flash(f'{deleted} student(s) permanently deleted.', 'success')
    back = request.form.get('back') or ''
    if back.startswith('/'):
        return redirect(back)
    return redirect(url_for('students_list'))


@app.route('/students/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'bursar')
def student_edit(id):
    student = Student.query.get_or_404(id)
    if request.method == 'POST':
        student.first_name = request.form.get('first_name', student.first_name)
        student.last_name = request.form.get('last_name', student.last_name)
        student.other_names = _clean_optional_text(request.form.get('other_names'))
        student.entry_mode = normalize_entry_mode(request.form.get('entry_mode'))
        student.date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date() if request.form.get('date_of_birth') else student.date_of_birth
        student.gender = request.form.get('gender', student.gender)
        student.national_id = request.form.get('national_id')
        student.class_id = request.form.get('class_id', student.class_id)
        student.status = request.form.get('status', student.status)
        # Scholarship fields
        student.fee_classification = request.form.get('fee_classification', 'Regular')
        student.scholarship_type = request.form.get('scholarship_type', 'None')
        student.scholarship_percentage = float(request.form.get('scholarship_percentage', 0))
        student.scholarship_sponsor = request.form.get('scholarship_sponsor')
        student.scholarship_staff_id = request.form.get('scholarship_staff_id') if request.form.get('scholarship_staff_id') else None
        student.scholarship_notes = request.form.get('scholarship_notes')
        student.medical_info = request.form.get('medical_info')
        student.address = request.form.get('address')
        student.city = request.form.get('city')
        student.province = request.form.get('province')
        student.phone = request.form.get('phone')
        student.email = request.form.get('email')
        student.updated_at = datetime.utcnow()

        # Handle photo upload
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
                    filename = secure_filename(f"student_{student.admission_number}_{uuid.uuid4().hex[:8]}.{ext}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    student.photo = f"uploads/{filename}"

        generate_student_invoice(student)
        db.session.commit()
        log_sync('Student', student.id, 'UPDATE')
        flash('Student updated successfully.', 'success')
        return redirect(url_for('student_view', id=id))
    classes = Class.query.order_by(Class.name).all()
    staff_list = Staff.query.filter_by(status='Active').all()
    fee_levels = FeeLevel.query.order_by(FeeLevel.id).all()
    # Build level → classes map for JS dropdown
    level_classes = {}
    for c in classes:
        lvl = c.level or 'Unassigned'
        if lvl not in level_classes:
            level_classes[lvl] = []
        level_classes[lvl].append({'id': c.id, 'name': c.name})
    # Serialize fee levels for JS
    fee_levels_json = [{'id': fl.id, 'name': fl.name, 'code': fl.code,
                        'total': fl.total, 'description': fl.description or ''}
                       for fl in fee_levels]
    return render_template('students/edit.html',
                           student=student,
                           classes=classes,
                           staff_list=staff_list,
                           fee_levels=fee_levels,
                           level_classes=json.dumps(level_classes),
                           fee_levels_json=json.dumps(fee_levels_json))


@app.route('/students/<int:id>/delete', methods=['POST'])
@login_required
@role_required('super_admin')
def student_delete(id):
    student = Student.query.get_or_404(id)
    student.status = 'Inactive'
    db.session.commit()
    log_sync('Student', student.id, 'DELETE')
    flash('Student deactivated successfully.', 'success')
    return redirect(url_for('students_list'))


# ─── Staff Management ──────────────────────────────────────────────────

@app.route('/staff')
@login_required
@role_required('super_admin')
def staff_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    dept_filter = request.args.get('department', '')
    query = Staff.query
    if search:
        query = query.filter(db.or_(
            Staff.first_name.ilike(f'%{search}%'),
            Staff.last_name.ilike(f'%{search}%'),
            Staff.employee_number.ilike(f'%{search}%')
        ))
    if dept_filter:
        query = query.filter_by(department=dept_filter)
    staff = query.order_by(Staff.last_name).paginate(
        page=page, per_page=20, error_out=False)
    departments = db.session.query(Staff.department).distinct().all()
    return render_template('staff/list.html',
                           staff=staff,
                           departments=[d[0] for d in departments if d[0]],
                           search=search,
                           dept_filter=dept_filter)


@app.route('/staff/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def staff_add():
    if request.method == 'POST':
        emp_number = generate_employee_number()
        staff = Staff(
            employee_number=emp_number,
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            other_names=request.form.get('other_names'),
            date_of_birth=datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date() if request.form.get('date_of_birth') else None,
            gender=request.form.get('gender'),
            national_id=request.form.get('national_id'),
            qualification=request.form.get('qualification'),
            specialization=request.form.get('specialization'),
            department=request.form.get('department'),
            position=request.form.get('position'),
            employment_date=datetime.strptime(request.form.get('employment_date'), '%Y-%m-%d').date() if request.form.get('employment_date') else date.today(),
            salary=request.form.get('salary', type=float),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            address=request.form.get('address'),
        )
        db.session.add(staff)
        # Create user account with proper role mapping
        position = request.form.get('position', 'Teacher')
        valid_roles = {
            'super_admin': 'super_admin', 'director': 'super_admin', 'principal': 'super_admin',
            'accountant': 'accountant', 'bursar': 'bursar', 'teacher': 'teacher',
            'head': 'super_admin', 'deputy head': 'super_admin', 'hod': 'teacher',
            'clerk': 'bursar', 'librarian': 'teacher', 'driver': 'bursar', 'warden': 'bursar',
        }
        assigned_role = valid_roles.get(position.lower(), 'teacher')
        user = User(username=emp_number, role=assigned_role)
        db.session.add(user)
        db.session.flush()
        staff.user_id = user.id
        db.session.commit()
        log_sync('Staff', staff.id, 'CREATE', {'employee_number': emp_number})
        flash(f'Staff member added successfully. Employee Number: {emp_number}', 'success')
        return redirect(url_for('staff_list'))
    next_emp = generate_employee_number()
    return render_template('staff/add.html', next_employee_number=next_emp)


@app.route('/staff/<int:id>')
@login_required
def staff_view(id):
    staff = Staff.query.get_or_404(id)
    assignments = StaffSubject.query.filter_by(staff_id=id).order_by(
        StaffSubject.class_id, StaffSubject.subject_id
    ).all()
    return render_template('staff/view.html',
                           staff=staff,
                           attendances=[],
                           subjects=assignments,
                           assignments=assignments,
                           classes=Class.query.order_by(Class.name).all(),
                           all_subjects=Subject.query.order_by(Subject.name).all(),
                           academic_years=AcademicYear.query.order_by(AcademicYear.start_date.desc()).all())


@app.route('/staff/<int:id>/assignments', methods=['POST'])
@login_required
@role_required('super_admin')
def staff_assignment_add(id):
    """Assign one subject in one class to a teacher for an academic year."""
    staff = Staff.query.get_or_404(id)
    linked_user = User.query.get(staff.user_id) if staff.user_id else None
    if (linked_user and linked_user.role != 'teacher') or (not linked_user and (staff.position or '').lower() not in ('teacher', 'hod')):
        flash('Class and subject assignments can only be added to teacher accounts.', 'danger')
        return redirect(url_for('staff_view', id=id))
    class_id = request.form.get('class_id', type=int)
    subject_id = request.form.get('subject_id', type=int)
    academic_year_id = request.form.get('academic_year_id', type=int) or None
    if not class_id or not subject_id:
        flash('Select both a class and a subject.', 'danger')
        return redirect(url_for('staff_view', id=id))
    Class.query.get_or_404(class_id)
    Subject.query.get_or_404(subject_id)
    duplicate = StaffSubject.query.filter_by(
        staff_id=id,
        class_id=class_id,
        subject_id=subject_id,
        academic_year_id=academic_year_id,
    ).first()
    if duplicate:
        flash('That class and subject assignment already exists.', 'warning')
        return redirect(url_for('staff_view', id=id))

    assignment = StaffSubject(
        staff_id=id,
        class_id=class_id,
        subject_id=subject_id,
        academic_year_id=academic_year_id,
    )
    db.session.add(assignment)
    db.session.commit()
    log_sync('StaffSubject', assignment.id, 'CREATE', {
        'id': assignment.id,
        'staff_id': assignment.staff_id,
        'class_id': assignment.class_id,
        'subject_id': assignment.subject_id,
        'academic_year_id': assignment.academic_year_id,
        'sync_id': assignment.sync_id,
    })
    flash(f'Assignment added for {staff.first_name} {staff.last_name}.', 'success')
    return redirect(url_for('staff_view', id=id))


@app.route('/staff/<int:id>/assignments/<int:assignment_id>/delete', methods=['POST'])
@login_required
@role_required('super_admin')
def staff_assignment_delete(id, assignment_id):
    assignment = StaffSubject.query.filter_by(id=assignment_id, staff_id=id).first_or_404()
    snapshot = {
        'id': assignment.id,
        'staff_id': assignment.staff_id,
        'class_id': assignment.class_id,
        'subject_id': assignment.subject_id,
        'academic_year_id': assignment.academic_year_id,
        'sync_id': assignment.sync_id,
    }
    db.session.delete(assignment)
    db.session.commit()
    log_sync('StaffSubject', assignment_id, 'DELETE', snapshot)
    flash('Teaching assignment removed.', 'success')
    return redirect(url_for('staff_view', id=id))


@app.route('/staff/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def staff_edit(id):
    staff = Staff.query.get_or_404(id)
    if request.method == 'POST':
        for field in ['first_name', 'last_name', 'other_names', 'gender', 'national_id',
                       'qualification', 'specialization', 'department', 'position',
                       'phone', 'email', 'address']:
            setattr(staff, field, request.form.get(field, getattr(staff, field)))
        if request.form.get('date_of_birth'):
            staff.date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date()
        if request.form.get('salary'):
            staff.salary = float(request.form.get('salary'))
        staff.status = request.form.get('status', staff.status)
        staff.updated_at = datetime.utcnow()
        db.session.commit()
        log_sync('Staff', staff.id, 'UPDATE')
        flash('Staff updated successfully.', 'success')
        return redirect(url_for('staff_view', id=id))
    return render_template('staff/edit.html', staff=staff)


# ─── Fee Management ────────────────────────────────────────────────────

@app.route('/fees')
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def fees_dashboard():
    term = get_current_term()
    ay = get_current_academic_year()
    total_expected = 0
    total_scholarships = 0
    net_expected = 0
    total_collected = 0
    structures = []
    scholarship_summary = []
    level_fee_summary = []
    if term and ay:
        structures = FeeStructure.query.filter_by(
            academic_year_id=ay.id, term_id=term.id).all()
        for s in structures:
            # Determine which students to count: by level if set, or by class
            if s.level_id:
                level = FeeLevel.query.get(s.level_id)
                if level:
                    # Smart class matching for this level
                    if level.name == 'ECD':
                        level_classes = Class.query.filter(Class.level.ilike('ECD%')).all()
                    elif level.name == 'Junior':
                        level_classes = Class.query.filter(
                            db.or_(Class.level.ilike('Grade %'), Class.level.ilike('Gr %'))
                        ).all()
                    elif level.name == 'O Level':
                        all_cls = Class.query.filter(Class.level.ilike('Form %')).all()
                        level_classes = [c for c in all_cls
                                        if re.search(r'Form\s*(\d+)', c.level or '', re.IGNORECASE)
                                        and 1 <= int(re.search(r'Form\s*(\d+)', c.level, re.IGNORECASE).group(1)) <= 4]
                    elif level.name == 'A Level':
                        all_cls = Class.query.filter(Class.level.ilike('Form %')).all()
                        level_classes = [c for c in all_cls
                                        if re.search(r'Form\s*(\d+)', c.level or '', re.IGNORECASE)
                                        and int(re.search(r'Form\s*(\d+)', c.level, re.IGNORECASE).group(1)) >= 5]
                    else:
                        level_classes = Class.query.filter_by(level=level.name).all()
                    class_ids = [c.id for c in level_classes]
                    students_in_class = Student.query.filter(
                        Student.class_id.in_(class_ids), Student.status == 'Active'
                    ).all() if class_ids else []
                else:
                    students_in_class = Student.query.filter_by(
                        class_id=s.class_id, status='Active').all()
            else:
                students_in_class = Student.query.filter_by(
                    class_id=s.class_id, status='Active').all()
            for stu in students_in_class:
                total_expected += s.total
                discount = s.total * (1.0 - stu.effective_fee_multiplier)
                total_scholarships += discount
                if stu.fee_classification != 'Regular' and discount > 0:
                    scholarship_summary.append({
                        'student': f"{stu.first_name} {stu.last_name}",
                        'adm': stu.admission_number,
                        'classification': stu.fee_classification,
                        'type': stu.scholarship_type,
                        'discount': discount,
                    })
        net_expected = total_expected - total_scholarships
        total_collected = db.session.query(db.func.sum(FeePayment.amount)).filter(
            FeePayment.term_id == term.id,
            FeePayment.academic_year_id == ay.id
        ).scalar() or 0

    invoiced_total = 0
    invoiced_discount = 0
    invoiced_net = 0
    invoices_list = []
    uninvoiced_count = 0
    term_payments = []
    if term and ay:
        invoices_list = Invoice.query.filter_by(term_id=term.id, academic_year_id=ay.id).all()
        invoiced_total = sum(inv.subtotal for inv in invoices_list)
        invoiced_discount = sum(inv.discount_amount for inv in invoices_list)
        invoiced_net = sum(inv.total_amount for inv in invoices_list)
        
        active_students = Student.query.filter_by(status='Active').all()
        invoiced_student_ids = {inv.student_id for inv in invoices_list}
        uninvoiced_count = len([s for s in active_students if s.id not in invoiced_student_ids])
        term_payments = FeePayment.query.filter_by(term_id=term.id, academic_year_id=ay.id).all()

    # Build level-based fee summary
    fee_levels = FeeLevel.query.order_by(FeeLevel.id).all()
    for fl in fee_levels:
        if fl.name == 'ECD':
            level_classes = Class.query.filter(Class.level.ilike('ECD%')).all()
        elif fl.name == 'Junior':
            level_classes = Class.query.filter(
                db.or_(Class.level.ilike('Grade %'), Class.level.ilike('Gr %'))
            ).all()
        elif fl.name == 'O Level':
            all_classes = Class.query.filter(Class.level.ilike('Form %')).all()
            level_classes = [c for c in all_classes
                            if re.search(r'Form\s*(\d+)', c.level or '', re.IGNORECASE)
                            and 1 <= int(re.search(r'Form\s*(\d+)', c.level, re.IGNORECASE).group(1)) <= 4]
        elif fl.name == 'A Level':
            all_classes = Class.query.filter(Class.level.ilike('Form %')).all()
            level_classes = [c for c in all_classes
                            if re.search(r'Form\s*(\d+)', c.level or '', re.IGNORECASE)
                            and int(re.search(r'Form\s*(\d+)', c.level, re.IGNORECASE).group(1)) >= 5]
        else:
            level_classes = Class.query.filter_by(level=fl.name).all()
        class_ids = [c.id for c in level_classes]
        student_count = Student.query.filter(
            Student.class_id.in_(class_ids), Student.status == 'Active'
        ).count() if class_ids else 0
        
        level_invoices = [inv for inv in invoices_list if inv.student and inv.student.class_id in class_ids]
        billed_amount = sum(inv.total_amount for inv in level_invoices)
        level_payments = [p for p in term_payments if p.student and p.student.class_id in class_ids]
        collected_amount = sum(p.amount for p in level_payments)

        level_structures = FeeStructure.query.filter_by(
            level_id=fl.id,
            academic_year_id=ay.id if ay else None,
            term_id=term.id if term else None
        ).all() if (ay and term) else []
        level_fee_summary.append({
            'level': fl,
            'student_count': student_count,
            'billed_amount': billed_amount,
            'collected_amount': collected_amount,
            'structures': level_structures,
        })

    return render_template('fees/dashboard.html',
                           structures=structures,
                           total_expected=total_expected,
                           total_scholarships=total_scholarships,
                           net_expected=net_expected,
                           total_collected=total_collected,
                           invoiced_net=invoiced_net,
                           uninvoiced_count=uninvoiced_count,
                           invoices_count=len(invoices_list),
                           scholarship_summary=scholarship_summary,
                           current_term=term,
                           current_ay=ay,
                           fee_levels=fee_levels,
                           level_fee_summary=level_fee_summary)


@app.route('/fees/structures')
@login_required
@role_required('super_admin', 'accountant')
def fee_structures():
    structures = FeeStructure.query.all()
    return render_template('fees/structures.html', structures=structures)


@app.route('/fees/structures/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'accountant')
def fee_structure_add():
    if request.method == 'POST':
        tuition = float(request.form.get('tuition', 0))
        boarding = float(request.form.get('boarding', 0))
        transport = float(request.form.get('transport', 0))
        lunch = float(request.form.get('lunch', 0))
        library = float(request.form.get('library', 0))
        technology = float(request.form.get('technology', 0))
        sports = float(request.form.get('sports', 0))
        other = float(request.form.get('other', 0))
        total = tuition + boarding + transport + lunch + library + technology + sports + other
        fs = FeeStructure(
            name=request.form.get('name'),
            class_id=request.form.get('class_id') or None,
            level_id=request.form.get('level_id') or None,
            academic_year_id=request.form.get('academic_year_id'),
            term_id=request.form.get('term_id'),
            tuition=tuition,
            boarding=boarding,
            transport=transport,
            lunch=lunch,
            library=library,
            technology=technology,
            sports=sports,
            other=other,
            total=total,
        )
        db.session.add(fs)
        db.session.commit()
        log_sync('FeeStructure', fs.id, 'CREATE')
        flash('Fee structure created successfully.', 'success')
        return redirect(url_for('fee_structures'))
    classes = Class.query.order_by(Class.name).all()
    academic_years = AcademicYear.query.all()
    terms = Term.query.all()
    fee_levels = FeeLevel.query.order_by(FeeLevel.id).all()
    return render_template('fees/structure_add.html',
                           classes=classes,
                           academic_years=academic_years,
                           terms=terms,
                           fee_levels=fee_levels)


@app.route('/fees/pay', methods=['GET', 'POST'])
@login_required
@role_required('accountant', 'bursar')  # Super admins oversee the system but do NOT record payments
def fee_pay():
    if request.method == 'POST':
        receipt = generate_receipt_number()
        payment = FeePayment(
            student_id=request.form.get('student_id'),
            receipt_number=receipt,
            amount=float(request.form.get('amount')),
            payment_date=datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date() if request.form.get('payment_date') else date.today(),
            payment_method=request.form.get('payment_method'),
            term_id=request.form.get('term_id'),
            academic_year_id=request.form.get('academic_year_id'),
            description=request.form.get('description'),
            received_by=session.get('user_id'),
        )
        db.session.add(payment)
        db.session.flush()
        update_invoice_statuses_for_student(payment.student_id, payment.term_id, payment.academic_year_id)
        db.session.commit()
        log_sync('FeePayment', payment.id, 'CREATE', {'receipt': receipt})
        flash(f'Payment recorded successfully. Receipt: {receipt}', 'success')
        return redirect(url_for('fee_receipt', id=payment.id))

    students = Student.query.filter_by(status='Active').order_by(Student.last_name).all()
    terms = Term.query.all()
    academic_years = AcademicYear.query.all()
    prefill_student_id = request.args.get('student_id', type=int)
    return render_template('fees/pay.html',
                           students=students,
                           terms=terms,
                           academic_years=academic_years,
                           prefill_student_id=prefill_student_id,
                           today=date.today().isoformat())


@app.route('/fees/receipt/<int:id>')
@login_required
def fee_receipt(id):
    payment = FeePayment.query.get_or_404(id)
    recorder = _resolve_recorder(payment.received_by)
    signature_id = _generate_signature_id(payment)
    return render_template('fees/receipt.html', payment=payment,
                           recorder=recorder, signature_id=signature_id)


@app.route('/fees/payments')
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def fee_payments():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    method_filter = request.args.get('method', '')
    query = FeePayment.query
    if search:
        query = query.join(Student).filter(db.or_(
            Student.first_name.ilike(f'%{search}%'),
            Student.last_name.ilike(f'%{search}%'),
            FeePayment.receipt_number.ilike(f'%{search}%')
        ))
    if method_filter:
        query = query.filter_by(payment_method=method_filter)
    payments = query.order_by(FeePayment.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    return render_template('fees/payments.html',
                           payments=payments,
                           search=search,
                           method_filter=method_filter)


@app.route('/fees/invoices')
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def invoices_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    class_filter = request.args.get('class_id', '', type=int)

    term = get_current_term()
    ay = get_current_academic_year()

    query = Invoice.query
    if search:
        query = query.join(Student).filter(db.or_(
            Student.first_name.ilike(f'%{search}%'),
            Student.last_name.ilike(f'%{search}%'),
            Student.admission_number.ilike(f'%{search}%'),
            Invoice.invoice_number.ilike(f'%{search}%')
        ))
    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    if class_filter:
        if not search: query = query.join(Student)
        query = query.filter(Student.class_id == class_filter)

    invoices = query.order_by(Invoice.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False)
    
    classes = Class.query.order_by(Class.name).all()
    
    active_students = Student.query.filter_by(status='Active').all()
    invoiced_student_ids = {inv.student_id for inv in Invoice.query.filter_by(term_id=term.id if term else None, academic_year_id=ay.id if ay else None).all()}
    uninvoiced_count = len([s for s in active_students if s.id not in invoiced_student_ids])

    return render_template('fees/invoices.html',
                           invoices=invoices,
                           search=search,
                           status_filter=status_filter,
                           class_filter=class_filter,
                           classes=classes,
                           uninvoiced_count=uninvoiced_count,
                           term=term,
                           ay=ay)


@app.route('/fees/invoices/batch-generate', methods=['POST'])
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def invoices_batch_generate():
    term = get_current_term()
    ay = get_current_academic_year()
    if not term or not ay:
        flash('No current academic year or term configured.', 'danger')
        return redirect(url_for('invoices_list'))

    active_students = Student.query.filter_by(status='Active').all()
    count = 0
    for stu in active_students:
        inv = generate_student_invoice(stu, term, ay)
        if inv:
            count += 1
    db.session.commit()
    flash(f'Successfully processed/generated invoices for {count} active students.', 'success')
    return redirect(url_for('invoices_list'))


@app.route('/fees/invoices/<int:id>')
@login_required
@role_required('super_admin', 'accountant', 'bursar', 'teacher')
def invoice_view(id):
    invoice = Invoice.query.get_or_404(id)
    update_invoice_status(invoice)
    db.session.commit()
    payments = FeePayment.query.filter_by(
        student_id=invoice.student_id,
        term_id=invoice.term_id,
        academic_year_id=invoice.academic_year_id
    ).order_by(FeePayment.payment_date.desc()).all()
    total_paid = sum(p.amount for p in payments)
    balance = max(0.0, invoice.total_amount - total_paid)
    return render_template('fees/invoice_view.html',
                           invoice=invoice,
                           payments=payments,
                           total_paid=total_paid,
                           balance=balance)


@app.route('/fees/invoices/<int:id>/pdf')
@login_required
def invoice_pdf(id):
    invoice = Invoice.query.get_or_404(id)
    update_invoice_status(invoice)
    db.session.commit()
    buf = _generate_invoice_pdf(invoice)
    return send_file(buf, as_attachment=True, download_name=f"invoice_{invoice.invoice_number}.pdf", mimetype='application/pdf')


@app.route('/fees/invoices/export-zip')
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def invoices_export_zip():
    import zipfile
    level_filter = request.args.get('level', '')
    term = get_current_term()
    ay = get_current_academic_year()

    query = Invoice.query
    if term and ay:
        query = query.filter_by(term_id=term.id, academic_year_id=ay.id)
    
    if level_filter:
        query = query.join(Student).join(Class)
        if level_filter == 'ECD':
            query = query.filter(Class.level.ilike('ECD%'))
        elif level_filter == 'Junior':
            query = query.filter(db.or_(Class.level.ilike('Grade %'), Class.level.ilike('Gr %')))
        elif level_filter == 'O Level':
            query = query.filter(Class.level.ilike('Form 1%') | Class.level.ilike('Form 2%') | Class.level.ilike('Form 3%') | Class.level.ilike('Form 4%'))
        elif level_filter == 'A Level':
            query = query.filter(Class.level.ilike('Form 5%') | Class.level.ilike('Form 6%'))

    invoices = query.all()
    if not invoices:
        flash('No invoices found to export for the selected filter.', 'warning')
        return redirect(url_for('invoices_list'))

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for inv in invoices:
            pdf_buf = _generate_invoice_pdf(inv)
            filename = f"Invoice_{inv.invoice_number}_{inv.student.admission_number}.pdf"
            zf.writestr(filename, pdf_buf.getvalue())
    zip_buf.seek(0)
    zip_name = f"Invoices_{level_filter or 'All'}_{term.name if term else 'Term'}.zip"
    return send_file(zip_buf, as_attachment=True, download_name=zip_name, mimetype='application/zip')


@app.route('/fees/invoices/export-bulk-pdf')
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def invoices_export_bulk_pdf():
    level_filter = request.args.get('level', '')
    term = get_current_term()
    ay = get_current_academic_year()

    query = Invoice.query
    if term and ay:
        query = query.filter_by(term_id=term.id, academic_year_id=ay.id)
    
    if level_filter:
        query = query.join(Student).join(Class)
        if level_filter == 'ECD':
            query = query.filter(Class.level.ilike('ECD%'))
        elif level_filter == 'Junior':
            query = query.filter(db.or_(Class.level.ilike('Grade %'), Class.level.ilike('Gr %')))
        elif level_filter == 'O Level':
            query = query.filter(Class.level.ilike('Form 1%') | Class.level.ilike('Form 2%') | Class.level.ilike('Form 3%') | Class.level.ilike('Form 4%'))
        elif level_filter == 'A Level':
            query = query.filter(Class.level.ilike('Form 5%') | Class.level.ilike('Form 6%'))

    invoices = query.all()
    if not invoices:
        flash('No invoices found to export for the selected filter.', 'warning')
        return redirect(url_for('invoices_list'))

    pdf_buf = _generate_combined_invoices_pdf(invoices)
    pdf_name = f"Bulk_Invoices_{level_filter or 'All'}_{term.name if term else 'Term'}.pdf"
    return send_file(pdf_buf, as_attachment=True, download_name=pdf_name, mimetype='application/pdf')


@app.route('/fees/invoices/generate/<int:student_id>', methods=['POST'])
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def invoice_generate_on_demand(student_id):
    student = Student.query.get_or_404(student_id)
    inv = generate_student_invoice(student)
    db.session.commit()
    if inv:
        flash(f'Invoice {inv.invoice_number} successfully generated/updated for {student.first_name} {student.last_name}.', 'success')
        return redirect(url_for('invoice_view', id=inv.id))
    else:
        flash('Could not generate invoice. Make sure student is assigned to a class or level with defined fees.', 'warning')
        return redirect(url_for('student_view', id=student_id))


@app.route('/fees/balance/<int:student_id>')
@login_required
def fee_balance(student_id):
    student = Student.query.get_or_404(student_id)
    term = get_current_term()
    ay = get_current_academic_year()
    total_paid = 0
    total_due = 0
    scholarship_amount = 0
    net_due = 0
    level_name = None
    fs = None
    if term and ay:
        # Try level-based fee structure first
        if student.class_ and student.class_.level:
            level_name = student.class_.level
            # Map class level to fee level name
            fee_level_name = None
            if is_primary_level(level_name):
                if level_name.strip().lower().startswith('ecd'):
                    fee_level_name = 'ECD'
                else:
                    fee_level_name = 'Junior'
            else:
                m = re.search(r'Form\s*(\d+)', level_name, re.IGNORECASE)
                if m:
                    f = int(m.group(1))
                    if 1 <= f <= 4:
                        fee_level_name = 'O Level'
                    elif f >= 5:
                        fee_level_name = 'A Level'
            level = FeeLevel.query.filter_by(name=fee_level_name).first() if fee_level_name else None
            if level:
                fs = FeeStructure.query.filter_by(
                    level_id=level.id,
                    academic_year_id=ay.id,
                    term_id=term.id
                ).first()
        # Fallback to class-based fee structure
        if not fs:
            fs = FeeStructure.query.filter_by(
                class_id=student.class_id,
                academic_year_id=ay.id,
                term_id=term.id
            ).first()
        total_due = fs.total if fs else 0
        # Apply scholarship discount
        multiplier = student.effective_fee_multiplier
        scholarship_amount = total_due * (1.0 - multiplier)
        net_due = total_due * multiplier
        total_paid = db.session.query(db.func.sum(FeePayment.amount)).filter(
            FeePayment.student_id == student_id,
            FeePayment.term_id == term.id,
            FeePayment.academic_year_id == ay.id
        ).scalar() or 0
    balance = net_due - total_paid
    return jsonify({
        'student': f"{student.first_name} {student.last_name}",
        'fee_classification': student.fee_classification,
        'scholarship_type': student.scholarship_type,
        'scholarship_percentage': student.scholarship_percentage,
        'scholarship_label': student.scholarship_label,
        'level': level_name,
        'total_due': total_due,
        'scholarship_amount': scholarship_amount,
        'net_due': net_due,
        'total_paid': total_paid,
        'balance': balance
    })


# ─── Debtors Report (Sortable & Exportable) ────────────────────────────

# Sorting options exposed in the UI
DEBTOR_SORT_OPTIONS = [
    ('balance_desc', 'Balance (High → Low)'),
    ('balance_asc',  'Balance (Low → High)'),
    ('name_asc',     'Name (A → Z)'),
    ('name_desc',    'Name (Z → A)'),
    ('class_asc',    'Class'),
    ('overdue_desc', 'Days Overdue (Most → Least)'),
    ('overdue_asc',  'Days Overdue (Least → Most)'),
    ('admission_asc','Admission Number'),
]


def _resolve_recorder(received_by_id):
    """Resolve the user who recorded a payment.

    The `received_by` column stores the recording User's ID.
    Returns a dict with display info, or None if unavailable.
    """
    if not received_by_id:
        return None
    # First try as a User (the actual recorder's account)
    user = User.query.get(received_by_id)
    if user:
        # Try to get the linked Staff record for the full name
        staff = Staff.query.filter_by(user_id=user.id).first()
        display_name = (f"{staff.first_name} {staff.last_name}".strip()
                        if staff else user.username)
        position = staff.position if staff and staff.position else user.role.replace('_', ' ').title()
        initials = ''
        if staff and staff.first_name:
            initials = (staff.first_name[0] + (staff.last_name[0] if staff.last_name else '')).upper()
        elif user.username:
            initials = user.username[0].upper()
        return {
            'user': user,
            'staff': staff,
            'display_name': display_name,
            'username': user.username,
            'role': user.role,
            'role_label': ROLE_LABELS.get(user.role, user.role.title()),
            'position': position,
            'initials': initials or '?',
        }
    # Fallback: maybe legacy data stored a Staff ID
    staff = Staff.query.get(received_by_id)
    if staff:
        return {
            'user': None,
            'staff': staff,
            'display_name': f"{staff.first_name} {staff.last_name}",
            'username': staff.employee_number or '',
            'role': 'staff',
            'role_label': staff.position or 'Staff',
            'position': staff.position or 'Staff',
            'initials': ((staff.first_name[0] if staff.first_name else '') +
                         (staff.last_name[0] if staff.last_name else '')).upper() or '?',
        }
    return None


def _generate_signature_id(payment):
    """Generate a stable, human-readable signature ID for a payment.

    Combines the receipt number, payment id and created_at timestamp
    into a short alphanumeric token. Same payment always produces the
    same ID, providing tamper-evident traceability.
    """
    import hashlib
    if not payment:
        return 'SIG-UNKNOWN'
    seed = f"{payment.receipt_number}|{payment.id}|{payment.created_at.isoformat() if payment.created_at else ''}"
    digest = hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12].upper()
    return f"SIG-{digest}"


def _build_debtor_row(student, term_id, ay_id):
    """Build a debtor data dict for one student in a given term/year.

    Returns None if the student has no invoice or has fully paid
    (i.e. is not a debtor).
    """
    if not student.class_id or not term_id or not ay_id:
        return None

    invoice = Invoice.query.filter_by(
        student_id=student.id,
        term_id=term_id,
        academic_year_id=ay_id,
    ).first()
    if not invoice:
        return None

    paid = db.session.query(db.func.sum(FeePayment.amount)).filter(
        FeePayment.student_id == student.id,
        FeePayment.term_id == term_id,
        FeePayment.academic_year_id == ay_id,
    ).scalar() or 0.0
    paid = float(paid)

    net_due = float(invoice.total_amount or 0.0)
    balance = max(0.0, net_due - paid)
    if balance <= 0.0:
        return None  # Not a debtor

    today = date.today()
    days_overdue = 0
    if invoice.due_date and invoice.due_date < today:
        days_overdue = (today - invoice.due_date).days

    last_payment = FeePayment.query.filter(
        FeePayment.student_id == student.id,
        FeePayment.term_id == term_id,
        FeePayment.academic_year_id == ay_id,
    ).order_by(FeePayment.payment_date.desc()).first()

    parent_name = ''
    parent_phone = ''
    parent_email = ''
    if student.parents:
        p = student.parents[0]
        parent_name = f"{p.first_name} {p.last_name}"
        parent_phone = p.phone or ''
        parent_email = p.email or ''

    class_obj = student.class_
    class_name = class_obj.name if class_obj else 'Unassigned'
    grade_level = class_obj.level if class_obj and class_obj.level else ''
    level_name = get_fee_level_name(grade_level) if grade_level else ''
    school_name = ('Primary' if is_primary_level(grade_level) else 'Secondary') if grade_level else ''

    return {
        'student': student,
        'class_name': class_name,
        'grade_level': grade_level,
        'level_name': level_name,
        'school_name': school_name,
        'invoice': invoice,
        'invoice_number': invoice.invoice_number,
        'issue_date': invoice.issue_date,
        'due_date': invoice.due_date,
        'total_due': float(invoice.subtotal or 0.0),
        'scholarship_amount': float(invoice.discount_amount or 0.0),
        'net_due': net_due,
        'paid': paid,
        'balance': balance,
        'status': invoice.status or 'Unpaid',
        'days_overdue': days_overdue,
        'last_payment_date': last_payment.payment_date if last_payment else None,
        'parent_name': parent_name,
        'parent_phone': parent_phone,
        'parent_email': parent_email,
    }


def _query_debtors(term, ay, filters):
    """Apply filters and return list of debtor row dicts.

    `filters` supports search, class_id, grade_level, school, fee level,
    scholarship, minimum balance, and sorting.
    """
    if not term or not ay:
        return []

    search = (filters.get('search') or '').strip()
    class_filter = filters.get('class_id') or None
    grade_level_filter = (filters.get('grade_level') or '').strip()
    school_filter = (filters.get('school') or '').strip().lower()
    level_filter = (filters.get('level') or '').strip()
    scholarship_filter = (filters.get('scholarship') or '').strip()
    min_balance = filters.get('min_balance')
    sort_by = filters.get('sort_by') or 'balance_desc'

    query = Student.query.filter(Student.status == 'Active')
    if search:
        query = query.filter(db.or_(
            Student.first_name.ilike(f'%{search}%'),
            Student.last_name.ilike(f'%{search}%'),
            Student.admission_number.ilike(f'%{search}%'),
        ))
    if class_filter:
        try:
            query = query.filter(Student.class_id == int(class_filter))
        except (TypeError, ValueError):
            pass

    if grade_level_filter or school_filter or level_filter:
        query = query.join(Class, Student.class_id == Class.id)
    if grade_level_filter:
        query = query.filter(Class.level == grade_level_filter)
    if school_filter == 'primary':
        query = query.filter(db.or_(
            Class.level.ilike('ECD%'),
            Class.level.ilike('Grade%'),
            Class.level.ilike('Gr %'),
            Class.level.ilike('Primary%'),
        ))
    elif school_filter == 'secondary':
        query = query.filter(db.or_(
            Class.level.ilike('Form%'),
            Class.level.ilike('Secondary%'),
        ))
    if level_filter:
        if level_filter == 'ECD':
            query = query.filter(Class.level.ilike('ECD%'))
        elif level_filter == 'Junior':
            query = query.filter(db.or_(
                Class.level.ilike('Grade%'),
                Class.level.ilike('Gr %'),
            ))
        elif level_filter == 'O Level':
            query = query.filter(Class.level.ilike('Form 1%')
                                 | Class.level.ilike('Form 2%')
                                 | Class.level.ilike('Form 3%')
                                 | Class.level.ilike('Form 4%'))
        elif level_filter == 'A Level':
            query = query.filter(Class.level.ilike('Form 5%')
                                 | Class.level.ilike('Form 6%'))
    if scholarship_filter == 'scholarship':
        query = query.filter(Student.fee_classification != 'Regular')
    elif scholarship_filter == 'regular':
        query = query.filter(Student.fee_classification == 'Regular')
    elif scholarship_filter:
        query = query.filter(Student.fee_classification == scholarship_filter)

    students = query.order_by(Student.last_name, Student.first_name).all()

    debtors = []
    for stu in students:
        row = _build_debtor_row(stu, term.id, ay.id)
        if row is None:
            continue
        if min_balance is not None:
            try:
                if row['balance'] < float(min_balance):
                    continue
            except (TypeError, ValueError):
                pass
        debtors.append(row)

    # Sort
    def key_name(r):
        return (r['student'].last_name.lower(), r['student'].first_name.lower())
    def key_name_rev(r):
        return (r['student'].last_name.lower(), r['student'].first_name.lower())
    sorters = {
        'balance_desc': lambda r: -r['balance'],
        'balance_asc':  lambda r: r['balance'],
        'name_asc':     key_name,
        'name_desc':    lambda r: tuple(-ord(c) for c in key_name(r)[0]) or key_name_rev(r),
        'class_asc':    lambda r: (r['class_name'].lower(), key_name(r)),
        'overdue_desc': lambda r: -r['days_overdue'],
        'overdue_asc':  lambda r: r['days_overdue'],
        'admission_asc':lambda r: r['student'].admission_number or '',
    }
    sorter = sorters.get(sort_by, sorters['balance_desc'])
    debtors.sort(key=sorter)

    return debtors


def _sort_url(sort_key, current_sort):
    """Generate a URL for toggling sort by `sort_key`."""
    # If user clicks same key, flip direction
    flip_map = {
        'balance_desc': 'balance_asc',
        'balance_asc':  'balance_desc',
        'name_asc':     'name_desc',
        'name_desc':    'name_asc',
        'class_asc':    'class_desc',
        'overdue_desc': 'overdue_asc',
        'overdue_asc':  'overdue_desc',
        'admission_asc':'admission_desc',
    }
    target = flip_map.get(current_sort) if current_sort == sort_key else sort_key
    args = request.args.copy()
    args['sort'] = target
    return url_for('debtors_list', **args)


@app.route('/fees/debtors')
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def debtors_list():
    """List all students with outstanding fee balances — sortable & exportable."""
    term = get_current_term()
    ay = get_current_academic_year()

    filters = {
        'search': request.args.get('search', ''),
        'class_id': request.args.get('class_id', ''),
        'grade_level': request.args.get('grade_level', ''),
        'school': request.args.get('school', ''),
        'level': request.args.get('level', ''),
        'scholarship': request.args.get('scholarship', ''),
        'min_balance': request.args.get('min_balance', ''),
        'sort_by': request.args.get('sort', 'balance_desc'),
    }

    debtors = _query_debtors(term, ay, filters)

    # Summary stats
    total_debtors = len(debtors)
    total_owed = sum(r['balance'] for r in debtors)
    total_net_due = sum(r['net_due'] for r in debtors)
    total_paid = sum(r['paid'] for r in debtors)
    total_scholarships = sum(r['scholarship_amount'] for r in debtors)
    severely_overdue = sum(1 for r in debtors if r['days_overdue'] > 30)
    moderately_overdue = sum(1 for r in debtors if 0 < r['days_overdue'] <= 30)

    classes = Class.query.order_by(Class.name).all()
    grade_levels = sorted({
        level for level, in db.session.query(Class.level).distinct().all() if level
    })
    classifications = sorted({c for c, in db.session.query(Student.fee_classification).distinct().all() if c})

    return render_template(
        'fees/debtors.html',
        debtors=debtors,
        total_debtors=total_debtors,
        total_owed=total_owed,
        total_net_due=total_net_due,
        total_paid=total_paid,
        total_scholarships=total_scholarships,
        severely_overdue=severely_overdue,
        moderately_overdue=moderately_overdue,
        term=term,
        ay=ay,
        classes=classes,
        grade_levels=grade_levels,
        classifications=classifications,
        search=filters['search'],
        class_filter=filters['class_id'],
        grade_level_filter=filters['grade_level'],
        school_filter=filters['school'],
        level_filter=filters['level'],
        scholarship_filter=filters['scholarship'],
        min_balance=filters['min_balance'],
        sort_by=filters['sort_by'],
        sort_options=DEBTOR_SORT_OPTIONS,
        current_endpoint='debtors_list',
    )


@app.route('/fees/debtors/export')
@login_required
@role_required('super_admin', 'accountant', 'bursar')
def debtors_export():
    """Export debtors list — supports CSV, Excel, and PDF formats."""
    import csv

    fmt = (request.args.get('format', 'csv') or 'csv').lower()
    if fmt not in ('csv', 'excel', 'pdf'):
        flash('Unsupported export format.', 'danger')
        return redirect(url_for('debtors_list'))

    term = get_current_term()
    ay = get_current_academic_year()
    filters = {
        'search': request.args.get('search', ''),
        'class_id': request.args.get('class_id', ''),
        'grade_level': request.args.get('grade_level', ''),
        'school': request.args.get('school', ''),
        'level': request.args.get('level', ''),
        'scholarship': request.args.get('scholarship', ''),
        'min_balance': request.args.get('min_balance', ''),
        'sort_by': request.args.get('sort', 'balance_desc'),
    }
    debtors = _query_debtors(term, ay, filters)

    if not debtors:
        flash('No debtors match the current filters — nothing to export.', 'warning')
        return redirect(url_for('debtors_list'))

    total_owed = sum(r['balance'] for r in debtors)
    total_net_due = sum(r['net_due'] for r in debtors)
    total_paid = sum(r['paid'] for r in debtors)
    term_label = f"{term.name}_{ay.name}" if term and ay else 'Current'
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M')
    base_name = f"Debtors_{term_label}_{timestamp}"

    # ── CSV ──
    if fmt == 'csv':
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            'Adm No', 'First Name', 'Last Name', 'Class', 'Grade / School / Fee Level',
            'Gender', 'Scholarship', 'Invoice No', 'Issue Date', 'Due Date',
            'Days Overdue', 'Subtotal', 'Discount', 'Net Due', 'Paid',
            'Balance Owed', 'Invoice Status', 'Parent Name', 'Parent Phone',
            'Parent Email', 'Last Payment Date',
        ])
        for r in debtors:
            stu = r['student']
            writer.writerow([
                stu.admission_number or '',
                stu.first_name or '',
                stu.last_name or '',
                r['class_name'],
                ' / '.join(v for v in (r['grade_level'], r['school_name'], r['level_name']) if v),
                stu.gender or '',
                stu.scholarship_label or 'Regular',
                r['invoice_number'] or '',
                r['issue_date'].isoformat() if r['issue_date'] else '',
                r['due_date'].isoformat() if r['due_date'] else '',
                r['days_overdue'],
                f"{r['total_due']:.2f}",
                f"{r['scholarship_amount']:.2f}",
                f"{r['net_due']:.2f}",
                f"{r['paid']:.2f}",
                f"{r['balance']:.2f}",
                r['status'],
                r['parent_name'],
                r['parent_phone'],
                r['parent_email'],
                r['last_payment_date'].isoformat() if r['last_payment_date'] else '',
            ])
        # Total row
        writer.writerow([])
        writer.writerow(['', '', '', '', '', '', '', '', '', '',
                         'TOTAL', '', '', f"{total_net_due:.2f}",
                         f"{total_paid:.2f}",
                         f"{total_owed:.2f}", '', '', '', '', ''])

        resp = make_response(buf.getvalue())
        resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
        resp.headers['Content-Disposition'] = f'attachment; filename="{base_name}.csv"'
        return resp

    # ── Excel (.xlsx) ──
    if fmt == 'excel':
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Debtors'

        # Title block
        theme = get_theme()
        school_name = theme.get('school_name', 'Excel Group of Schools')
        title_font = Font(name='Calibri', bold=True, size=14, color='FFFFFF')
        title_fill = PatternFill(start_color='1A5632', end_color='1A5632', fill_type='solid')
        header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
        header_fill = PatternFill(start_color='1A5632', end_color='1A5632', fill_type='solid')
        header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        total_font = Font(name='Calibri', bold=True, size=11, color='B91C1C')
        total_fill = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid')
        thin = Side(style='thin', color='9CA3AF')
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        # Title row
        title_text = f"{school_name} — Debtors Report"
        subtitle_text = (f"Term: {term.name if term else 'N/A'} | "
                         f"Academic Year: {ay.name if ay else 'N/A'} | "
                         f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC")
        ws.merge_cells('A1:T1')
        c = ws.cell(row=1, column=1, value=title_text)
        c.font = title_font
        c.fill = title_fill
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 26
        ws.merge_cells('A2:T2')
        c2 = ws.cell(row=2, column=1, value=subtitle_text)
        c2.font = Font(name='Calibri', italic=True, size=10, color='6B7280')
        c2.alignment = Alignment(horizontal='center', vertical='center')

        headers = [
            'Adm No', 'First Name', 'Last Name', 'Class', 'Grade / School / Fee Level',
            'Gender', 'Scholarship', 'Invoice No', 'Issue Date', 'Due Date',
            'Days Overdue', 'Subtotal ($)', 'Discount ($)', 'Net Due ($)',
            'Paid ($)', 'Balance Owed ($)', 'Invoice Status',
            'Parent Name', 'Parent Phone', 'Parent Email',
        ]
        header_row = 4
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = border
        ws.row_dimensions[header_row].height = 32

        red_fill = PatternFill(start_color='FEE2E2', end_color='FEE2E2', fill_type='solid')
        yellow_fill = PatternFill(start_color='FEF3C7', end_color='FEF3C7', fill_type='solid')

        row_idx = header_row + 1
        for r in debtors:
            stu = r['student']
            values = [
                stu.admission_number or '',
                stu.first_name or '',
                stu.last_name or '',
                r['class_name'],
                ' / '.join(v for v in (r['grade_level'], r['school_name'], r['level_name']) if v),
                stu.gender or '',
                stu.scholarship_label or 'Regular',
                r['invoice_number'] or '',
                r['issue_date'] if r['issue_date'] else '',
                r['due_date'] if r['due_date'] else '',
                r['days_overdue'],
                round(r['total_due'], 2),
                round(r['scholarship_amount'], 2),
                round(r['net_due'], 2),
                round(r['paid'], 2),
                round(r['balance'], 2),
                r['status'],
                r['parent_name'],
                r['parent_phone'],
                r['parent_email'],
            ]
            for col, v in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col, value=v)
                cell.border = border
                if isinstance(v, (int, float)) and col >= 12:
                    cell.number_format = '#,##0.00'
                if col == 11 and isinstance(v, int) and v > 30:
                    cell.fill = red_fill
                    cell.font = Font(bold=True, color='B91C1C')
                elif col == 11 and isinstance(v, int) and v > 0:
                    cell.fill = yellow_fill
            row_idx += 1

        # Totals row
        ws.cell(row=row_idx, column=1, value=f"TOTAL — {len(debtors)} debtors").font = total_font
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=11)
        total_cell_net = ws.cell(row=row_idx, column=14, value=round(total_net_due, 2))
        total_cell_paid = ws.cell(row=row_idx, column=15, value=round(sum(r['paid'] for r in debtors), 2))
        total_cell_bal = ws.cell(row=row_idx, column=16, value=round(total_owed, 2))
        for col in (14, 15, 16):
            cell = ws.cell(row=row_idx, column=col)
            cell.font = total_font
            cell.fill = total_fill
            cell.border = border
            cell.number_format = '#,##0.00'
            cell.alignment = Alignment(horizontal='right')

        # Column widths
        widths = [12, 14, 14, 14, 10, 9, 22, 18, 12, 12, 13, 12, 12, 12, 12, 14, 14, 16, 14, 22]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

        # Freeze header
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        resp = make_response(output.getvalue())
        resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        resp.headers['Content-Disposition'] = f'attachment; filename="{base_name}.xlsx"'
        return resp

    # ── PDF ──
    if fmt == 'pdf':
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle, PageBreak, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

        theme = get_theme()
        primary = HexColor(theme.get('primary_color', '#1F2080'))
        red = HexColor('#b91c1c')
        amber = HexColor('#a16207')
        green = HexColor('#15803d')
        grey = HexColor('#6b7280')
        bg = HexColor('#f9fafb')

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            leftMargin=15 * mm, rightMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('TitleD', parent=styles['Title'], fontSize=16,
                                     textColor=primary, alignment=TA_CENTER)
        sub_style = ParagraphStyle('SubD', parent=styles['Normal'], fontSize=10,
                                   textColor=grey, alignment=TA_CENTER)
        meta_style = ParagraphStyle('MetaD', parent=styles['Normal'], fontSize=10, textColor=grey)
        cell_style = ParagraphStyle('CellD', parent=styles['Normal'], fontSize=8)
        cell_right = ParagraphStyle('CellRD', parent=cell_style, alignment=TA_RIGHT)
        cell_center = ParagraphStyle('CellCD', parent=cell_style, alignment=TA_CENTER)
        cell_bold = ParagraphStyle('CellBD', parent=cell_style, fontName='Helvetica-Bold')
        header_style = ParagraphStyle('HeaderD', parent=styles['Normal'], fontSize=8,
                                      fontName='Helvetica-Bold', textColor=HexColor('#ffffff'),
                                      alignment=TA_CENTER)
        overdue_red = ParagraphStyle('ODRed', parent=cell_style, fontName='Helvetica-Bold',
                                      textColor=red)
        overdue_amber = ParagraphStyle('ODAmb', parent=cell_style, fontName='Helvetica-Bold',
                                       textColor=amber)

        story = []
        school_name = theme.get('school_name', 'Excel Group of Schools')
        story.append(Paragraph(school_name, title_style))
        story.append(Paragraph("Debtors Report", ParagraphStyle('DH', parent=styles['Normal'],
                                                                fontSize=12, alignment=TA_CENTER,
                                                                fontName='Helvetica-Bold',
                                                                textColor=primary)))
        meta = (f"Term: {term.name if term else 'N/A'} ({ay.name if ay else 'N/A'}) | "
                f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC | "
                f"Total Debtors: {len(debtors)} | Total Owed: ${total_owed:,.2f}")
        story.append(Paragraph(meta, sub_style))
        story.append(HRFlowable(width='100%', thickness=1, color=primary))
        story.append(Spacer(1, 4 * mm))

        # Build a compact but readable column set (landscape A4)
        pdf_headers = [
            'Adm #', 'Student Name', 'Class', 'Scholarship',
            'Invoice', 'Due Date', 'Days Overdue',
            'Net Due ($)', 'Paid ($)', 'Balance ($)',
            'Status', 'Parent Phone',
        ]
        pdf_widths = [20 * mm, 38 * mm, 24 * mm, 28 * mm,
                      26 * mm, 22 * mm, 16 * mm,
                      22 * mm, 20 * mm, 22 * mm,
                      22 * mm, 30 * mm]

        data = [[Paragraph(f'<b>{h}</b>', header_style) for h in pdf_headers]]
        for r in debtors:
            stu = r['student']
            due_txt = r['due_date'].strftime('%d %b %Y') if r['due_date'] else '-'
            if r['days_overdue'] > 30:
                od = Paragraph(str(r['days_overdue']), overdue_red)
            elif r['days_overdue'] > 0:
                od = Paragraph(str(r['days_overdue']), overdue_amber)
            else:
                od = Paragraph(str(r['days_overdue']), cell_center)
            data.append([
                Paragraph(stu.admission_number or '-', cell_style),
                Paragraph(f"{stu.first_name} {stu.last_name}", cell_style),
                Paragraph(r['class_name'], cell_style),
                Paragraph(stu.scholarship_label or 'Regular', cell_style),
                Paragraph(r['invoice_number'] or '-', cell_style),
                Paragraph(due_txt, cell_style),
                od,
                Paragraph(f"{r['net_due']:,.2f}", cell_right),
                Paragraph(f"{r['paid']:,.2f}", cell_right),
                Paragraph(f"<b>{r['balance']:,.2f}</b>", cell_right),
                Paragraph(r['status'], cell_center),
                Paragraph(r['parent_phone'] or '-', cell_style),
            ])

        # Totals row
        data.append([
            Paragraph('<b>TOTAL</b>', cell_bold), '', '', '', '', '', '',
            Paragraph(f"<b>{total_net_due:,.2f}</b>", ParagraphStyle('TR1', parent=cell_right, fontName='Helvetica-Bold')),
            Paragraph(f"<b>{sum(r['paid'] for r in debtors):,.2f}</b>", ParagraphStyle('TR2', parent=cell_right, fontName='Helvetica-Bold')),
            Paragraph(f"<b>{total_owed:,.2f}</b>", ParagraphStyle('TR3', parent=cell_right, fontName='Helvetica-Bold', textColor=red)),
            Paragraph(f"<b>{len(debtors)} debtors</b>", cell_bold), '',
        ])

        table = Table(data, colWidths=pdf_widths, repeatRows=1)
        ts = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.25, HexColor('#e5e7eb')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [HexColor('#ffffff'), bg]),
            ('BACKGROUND', (0, -1), (-1, -1), HexColor('#fef3c7')),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ])
        table.setStyle(ts)
        story.append(table)
        story.append(Spacer(1, 4 * mm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=HexColor('#d1d5db')))
        story.append(Paragraph(
            "Excel Group of Schools v2.0.0 — Debtors Report — Valentine T Mabheka",
            ParagraphStyle('FooterD', parent=styles['Normal'], fontSize=7,
                           textColor=grey, alignment=TA_CENTER),
        ))

        doc.build(story)
        buf.seek(0)

        resp = make_response(buf.getvalue())
        resp.headers['Content-Type'] = 'application/pdf'
        resp.headers['Content-Disposition'] = f'attachment; filename="{base_name}.pdf"'
        return resp


# ─── Exam & Results ────────────────────────────────────────────────────

@app.route('/exams')
@login_required
@role_required('super_admin', 'teacher')
def exams_list():
    exams = Exam.query.order_by(Exam.start_date.desc()).all()
    return render_template('exams/list.html', exams=exams)


@app.route('/exams/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'teacher')
def exam_add():
    if request.method == 'POST':
        exam = Exam(
            name=request.form.get('name'),
            term_id=request.form.get('term_id'),
            exam_type=request.form.get('exam_type'),
            start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else None,
            end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date() if request.form.get('end_date') else None,
            academic_year_id=request.form.get('academic_year_id'),
        )
        db.session.add(exam)
        db.session.commit()
        log_sync('Exam', exam.id, 'CREATE')
        flash('Exam created successfully.', 'success')
        return redirect(url_for('exams_list'))
    terms = Term.query.all()
    academic_years = AcademicYear.query.all()
    return render_template('exams/add.html', terms=terms, academic_years=academic_years)


@app.route('/exams/<int:exam_id>/results', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'teacher')
def exam_results(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        subject_id = request.form.get('subject_id')
        # Teacher portal: block entering marks for non-assigned subjects/classes
        if session.get('user_role') == 'teacher':
            staff = _staff_for_current_user()
            if staff:
                try:
                    selected_class_id = int(class_id or 0)
                    selected_subject_id = int(subject_id or 0)
                    ay = get_current_academic_year()
                    if not teacher_can_teach(
                        staff.id, selected_class_id, selected_subject_id,
                        ay.id if ay else None,
                    ):
                        flash('You are not assigned to teach that subject for that class.', 'danger')
                        return redirect(url_for('exam_results', exam_id=exam_id))
                except (TypeError, ValueError):
                    flash('Invalid class or subject selection.', 'danger')
                    return redirect(url_for('exam_results', exam_id=exam_id))
        students = Student.query.filter_by(class_id=class_id, status='Active').all()
        for student in students:
            marks = request.form.get(f'marks_{student.id}')
            if marks is not None and marks != '':
                marks_val = float(marks)
                total = float(request.form.get(f'total_{student.id}', 100))
                grade = compute_grade(marks_val, total)
                existing = ExamResult.query.filter_by(
                    student_id=student.id,
                    exam_id=exam_id,
                    subject_id=subject_id
                ).first()
                if existing:
                    existing.marks_obtained = marks_val
                    existing.marks_total = total
                    existing.grade = grade
                else:
                    result = ExamResult(
                        student_id=student.id,
                        exam_id=exam_id,
                        subject_id=subject_id,
                        marks_obtained=marks_val,
                        marks_total=total,
                        grade=grade,
                    )
                    db.session.add(result)
        db.session.commit()
        log_sync('ExamResult', 0, 'CREATE')
        flash('Results recorded successfully.', 'success')

    assignment_map = {}
    if session.get('user_role') == 'teacher':
        staff = _staff_for_current_user()
        ay = get_current_academic_year()
        assignment_map = get_teacher_classes_with_subjects(
            staff.id, ay.id if ay else None
        ) if staff else {}
        teachable_class_ids = [cid for cid, sids in assignment_map.items() if sids]
        classes = Class.query.filter(Class.id.in_(teachable_class_ids)).order_by(Class.name).all() if teachable_class_ids else []
        subject_ids = sorted({sid for sids in assignment_map.values() for sid in sids})
        subjects = Subject.query.filter(Subject.id.in_(subject_ids)).order_by(Subject.name).all() if subject_ids else []
        results = ExamResult.query.join(Student).filter(
            ExamResult.exam_id == exam_id,
            Student.class_id.in_(teachable_class_ids),
            ExamResult.subject_id.in_(subject_ids),
        ).all() if teachable_class_ids and subject_ids else []
    else:
        classes = Class.query.order_by(Class.name).all()
        subjects = Subject.query.order_by(Subject.name).all()
        results = ExamResult.query.filter_by(exam_id=exam_id).all()
    return render_template('exams/results.html',
                           exam=exam,
                           classes=classes,
                           subjects=subjects,
                           assignment_map=assignment_map,
                           results=results)


@app.route('/exams/<int:exam_id>/report-card/<int:student_id>')
@login_required
def report_card(exam_id, student_id):
    student = Student.query.get_or_404(student_id)
    if session.get('user_role') == 'teacher':
        staff = _staff_for_current_user()
        if not staff or not teacher_can_access_student(staff.id, student_id):
            flash('You do not have access to that learner.', 'danger')
            return redirect(url_for('teacher_home'))
    exam = Exam.query.get_or_404(exam_id)
    results_query = ExamResult.query.filter_by(exam_id=exam_id, student_id=student_id)
    if session.get('user_role') == 'teacher':
        subject_ids = get_teacher_subject_ids(staff.id, class_id=student.class_id)
        results_query = results_query.filter(ExamResult.subject_id.in_(subject_ids))
    results = results_query.all()
    total_marks = sum(r.marks_obtained for r in results)
    total_possible = sum(r.marks_total for r in results)
    average = (total_marks / total_possible * 100) if total_possible > 0 else 0
    return render_template('exams/report_card.html',
                           student=student,
                           exam=exam,
                           results=results,
                           total_marks=total_marks,
                           total_possible=total_possible,
                           average=average)


# ─── Hostel ────────────────────────────────────────────────────────────

@app.route('/hostel')
@login_required
@role_required('super_admin')
def hostel_dashboard():
    hostels = Hostel.query.all()
    total_rooms = Room.query.count()
    total_allocations = RoomAllocation.query.filter_by(status='Active').count()
    return render_template('hostel/dashboard.html',
                           hostels=hostels,
                           total_rooms=total_rooms,
                           total_allocations=total_allocations)


@app.route('/hostel/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def hostel_add():
    if request.method == 'POST':
        hostel = Hostel(
            name=request.form.get('name'),
            gender=request.form.get('gender'),
            capacity=int(request.form.get('capacity', 100)),
            warden_id=request.form.get('warden_id'),
        )
        db.session.add(hostel)
        db.session.commit()
        # Add rooms
        num_rooms = int(request.form.get('num_rooms', 0))
        room_capacity = int(request.form.get('room_capacity', 4))
        for i in range(1, num_rooms + 1):
            room = Room(
                hostel_id=hostel.id,
                room_number=f"R{i:03d}",
                capacity=room_capacity,
            )
            db.session.add(room)
        db.session.commit()
        log_sync('Hostel', hostel.id, 'CREATE')
        flash('Hostel and rooms added successfully.', 'success')
        return redirect(url_for('hostel_dashboard'))
    wardens = Staff.query.filter(Staff.position.ilike('%warden%')).all()
    return render_template('hostel/add.html', wardens=wardens)


@app.route('/hostel/allocate', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def hostel_allocate():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        room_id = request.form.get('room_id')
        room = Room.query.get_or_404(room_id)
        if room.current_occupancy >= room.capacity:
            flash('Room is full.', 'danger')
            return redirect(url_for('hostel_allocate'))
        allocation = RoomAllocation(
            student_id=student_id,
            room_id=room_id,
        )
        room.current_occupancy += 1
        db.session.add(allocation)
        db.session.commit()
        log_sync('RoomAllocation', allocation.id, 'CREATE')
        flash('Room allocated successfully.', 'success')
        return redirect(url_for('hostel_dashboard'))
    students = Student.query.filter_by(status='Active').all()
    rooms = Room.query.filter(Room.current_occupancy < Room.capacity).all()
    return render_template('hostel/allocate.html', students=students, rooms=rooms)


# ─── Timetable ─────────────────────────────────────────────────────────

@app.route('/timetable')
@login_required
@role_required('super_admin', 'teacher', 'student')
def timetable_view():
    class_id = request.args.get('class_id')
    timetable = []
    selected_class = None
    classes = Class.query.all()
    if class_id:
        selected_class = Class.query.get(class_id)
        timetable = TimetableSlot.query.filter_by(class_id=class_id).order_by(
            TimetableSlot.day_of_week, TimetableSlot.period).all()
    return render_template('timetable/view.html',
                           timetable=timetable,
                           classes=classes,
                           selected_class=selected_class,
                           class_id=class_id)


@app.route('/timetable/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'teacher')
def timetable_add():
    if request.method == 'POST':
        slot = TimetableSlot(
            class_id=request.form.get('class_id'),
            day_of_week=request.form.get('day_of_week'),
            period=int(request.form.get('period')),
            start_time=datetime.strptime(request.form.get('start_time'), '%H:%M').time(),
            end_time=datetime.strptime(request.form.get('end_time'), '%H:%M').time(),
            subject_id=request.form.get('subject_id'),
            staff_id=request.form.get('staff_id'),
            room=request.form.get('room'),
        )
        db.session.add(slot)
        db.session.commit()
        log_sync('TimetableSlot', slot.id, 'CREATE')
        flash('Timetable slot added.', 'success')
        return redirect(url_for('timetable_view', class_id=request.form.get('class_id')))
    classes = Class.query.all()
    subjects = Subject.query.all()
    staff = Staff.query.filter_by(status='Active').all()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    return render_template('timetable/add.html',
                           classes=classes,
                           subjects=subjects,
                           staff=staff,
                           days=days)


@app.route('/timetable/generate', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'teacher')
def timetable_generate():
    """Auto-generate a basic timetable for a class."""
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        periods_per_day = int(request.form.get('periods_per_day', 8))
        # Clear existing timetable for this class
        TimetableSlot.query.filter_by(class_id=class_id).delete()
        subjects = Subject.query.all()
        staff_list = Staff.query.filter_by(status='Active').all()
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        start_hour = 8
        for day in days:
            for period in range(1, periods_per_day + 1):
                subject = subjects[(period - 1) % len(subjects)] if subjects else None
                staff_member = staff_list[(period - 1) % len(staff_list)] if staff_list else None
                start_time = f"{start_hour + (period - 1):02d}:00"
                end_time = f"{start_hour + (period - 1):02d}:40"
                slot = TimetableSlot(
                    class_id=class_id,
                    day_of_week=day,
                    period=period,
                    start_time=datetime.strptime(start_time, '%H:%M').time(),
                    end_time=datetime.strptime(end_time, '%H:%M').time(),
                    subject_id=subject.id if subject else None,
                    staff_id=staff_member.id if staff_member else None,
                )
                db.session.add(slot)
        db.session.commit()
        flash('Timetable generated successfully.', 'success')
        return redirect(url_for('timetable_view', class_id=class_id))
    classes = Class.query.all()
    return render_template('timetable/generate.html', classes=classes)


# ─── Reports ───────────────────────────────────────────────────────────

@app.route('/reports')
@login_required
@role_required('super_admin', 'accountant', 'bursar', 'teacher')
def reports_dashboard():
    return render_template('reports/dashboard.html')


@app.route('/reports/students')
@login_required
def report_students():
    class_id = request.args.get('class_id')
    query = Student.query.filter_by(status='Active')
    if class_id:
        query = query.filter_by(class_id=class_id)
    students = query.order_by(Student.last_name).all()
    classes = Class.query.all()
    return render_template('reports/students.html', students=students, classes=classes, class_id=class_id)


@app.route('/reports/fees')
@login_required
def report_fees():
    term_id = request.args.get('term_id')
    class_id = request.args.get('class_id')
    query = FeePayment.query
    if term_id:
        query = query.filter_by(term_id=term_id)
    if class_id:
        query = query.join(Student).filter(Student.class_id == class_id)
    payments = query.order_by(FeePayment.payment_date.desc()).all()
    terms = Term.query.all()
    classes = Class.query.all()
    total = sum(p.amount for p in payments)
    return render_template('reports/fees.html',
                           payments=payments,
                           terms=terms,
                           classes=classes,
                           total=total,
                           term_id=term_id,
                           class_id=class_id)


@app.route('/reports/exam-results')
@login_required
def report_exam_results():
    exam_id = request.args.get('exam_id')
    class_id = request.args.get('class_id')
    results = ExamResult.query
    if exam_id:
        results = results.filter_by(exam_id=exam_id)
    if class_id:
        results = results.join(Student).filter(Student.class_id == class_id)
    results = results.all()
    exams = Exam.query.all()
    classes = Class.query.all()
    return render_template('reports/exam_results.html',
                           results=results,
                           exams=exams,
                           classes=classes,
                           exam_id=exam_id,
                           class_id=class_id)


# ─── Communication ─────────────────────────────────────────────────────

@app.route('/communication')
@login_required
@role_required('super_admin', 'accountant', 'bursar', 'teacher', 'parent', 'student')
def communication_dashboard():
    notices = Notice.query.filter_by(is_active=True).order_by(
        Notice.date_posted.desc()).limit(10).all()
    messages = Message.query.filter_by(
        recipient_id=session['user_id']).order_by(
        Message.date_sent.desc()).limit(10).all()
    return render_template('communication/dashboard.html',
                           notices=notices,
                           messages=messages)


@app.route('/communication/notices/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'bursar', 'teacher')
def notice_add():
    if request.method == 'POST':
        notice = Notice(
            title=request.form.get('title'),
            content=request.form.get('content'),
            category=request.form.get('category'),
            target_audience=request.form.get('target_audience'),
            posted_by=session.get('user_id'),
            expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d') if request.form.get('expiry_date') else None,
        )
        db.session.add(notice)
        db.session.commit()
        log_sync('Notice', notice.id, 'CREATE')
        flash('Notice posted successfully.', 'success')
        return redirect(url_for('communication_dashboard'))
    return render_template('communication/notice_add.html')


@app.route('/communication/messages/send', methods=['GET', 'POST'])
@login_required
def message_send():
    if request.method == 'POST':
        msg = Message(
            sender_id=session['user_id'],
            recipient_id=request.form.get('recipient_id'),
            subject=request.form.get('subject'),
            body=request.form.get('body'),
        )
        db.session.add(msg)
        db.session.commit()
        flash('Message sent successfully.', 'success')
        return redirect(url_for('communication_dashboard'))
    # Get list of recipients based on role
    users = User.query.filter(User.id != session['user_id'], User.is_active == True).all()
    return render_template('communication/message_send.html', users=users)


# ─── Sync System (Offline → Online) ───────────────────────────────────

# Full-data export order keeps parent records before rows that reference
# them. These names match the WordPress esm_* table suffixes exactly.
SYNC_EXPORT_MODELS = {
    'academic_years': AcademicYear,
    'terms': Term,
    'staff': Staff,
    'classes': Class,
    'subjects': Subject,
    'staff_subjects': StaffSubject,
    'parents': Parent,
    'students': Student,
    'exams': Exam,
    'exam_results': ExamResult,
    'fee_levels': FeeLevel,
    'fee_structures': FeeStructure,
    'fee_payments': FeePayment,
    'invoices': Invoice,
    'invoice_items': InvoiceItem,
    'hostels': Hostel,
    'rooms': Room,
    'room_allocations': RoomAllocation,
    'timetable_slots': TimetableSlot,
    'notices': Notice,
    'messages': Message,
    'school_settings': SchoolSetting,
}


def _sync_json_value(value):
    """Convert SQLAlchemy values to portable JSON values."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if hasattr(value, 'isoformat'):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    return value


def _serialize_sync_record(record):
    row = {
        column.name: _sync_json_value(getattr(record, column.name))
        for column in record.__table__.columns
    }
    # WordPress uses setting_key/setting_value for these mirrored columns.
    if isinstance(record, SchoolSetting):
        row['setting_key'] = row.pop('key', None)
        row['setting_value'] = row.pop('value', None)
    return row


def build_full_sync_export():
    """Return every portable school-data table in WordPress import format."""
    export_data = {
        entity: [_serialize_sync_record(record) for record in model.query.all()]
        for entity, model in SYNC_EXPORT_MODELS.items()
    }
    # student_parent is a many-to-many SQLAlchemy table rather than a model.
    links = db.session.execute(db.select(student_parent)).mappings().all()
    export_data['student_parent'] = [dict(row) for row in links]

    pending_events = []
    for log in SyncLog.query.filter_by(sync_status='pending').order_by(SyncLog.created_at).all():
        snapshot = None
        if log.data_snapshot:
            try:
                snapshot = json.loads(log.data_snapshot)
            except (TypeError, json.JSONDecodeError):
                snapshot = log.data_snapshot
        pending_events.append({
            'id': log.id,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'action': log.action,
            'data': snapshot,
            'timestamp': log.created_at.isoformat() if log.created_at else None,
        })

    return {
        'format': 'excel-schools-full-sync',
        'version': APP_VERSION,
        'source': 'offline-flask',
        'exported_at': datetime.utcnow().isoformat() + 'Z',
        'data': export_data,
        'counts': {entity: len(records) for entity, records in export_data.items()},
        'pending_events': pending_events,
    }


@app.route('/sync')
@login_required
@role_required('super_admin', 'bursar')
def sync_dashboard():
    pending = SyncLog.query.filter_by(sync_status='pending').count()
    synced = SyncLog.query.filter_by(sync_status='synced').count()
    failed = SyncLog.query.filter_by(sync_status='failed').count()
    recent_logs = SyncLog.query.order_by(SyncLog.created_at.desc()).limit(50).all()
    mode = app.config['DEPLOYMENT_MODE']
    # Use persisted settings (survive restarts) — fall back to app.config / session
    endpoint = SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', '')
    api_key = SyncSetting.get('sync_api_key', '') or app.config.get('SYNC_API_KEY', '')
    last_sync = SyncSetting.get('last_sync_time', '') or session.get('last_sync_time', '')
    last_sync_status = SyncSetting.get('last_sync_status', '') or session.get('last_sync_status', '')
    auto_sync_enabled = SyncSetting.get('auto_sync_enabled', 'false') == 'true'
    auto_sync_interval = int(SyncSetting.get('auto_sync_interval', '300'))
    ap_status = ap_monitor.status()
    return render_template('sync/dashboard.html',
                           pending=pending,
                           synced=synced,
                           failed=failed,
                           recent_logs=recent_logs,
                           mode=mode,
                           endpoint=endpoint,
                           api_key=api_key,
                           last_sync=last_sync,
                           last_sync_status=last_sync_status,
                           auto_sync_enabled=auto_sync_enabled,
                           auto_sync_interval=auto_sync_interval,
                           ap_status=ap_status)


@app.route('/sync/export')
@login_required
@role_required('super_admin', 'bursar')
def sync_export():
    """Download a complete school-data snapshot for WordPress manual import."""
    payload = build_full_sync_export()
    content = json.dumps(payload, indent=2, ensure_ascii=False).encode('utf-8')
    filename = f"sync_export_{date.today().isoformat()}.json"
    return send_file(
        io.BytesIO(content),
        as_attachment=True,
        download_name=filename,
        mimetype='application/json',
    )


@app.route('/sync/import', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'bursar')
def sync_import():
    """Import a manual JSON export, including classes, into the offline app."""
    if request.method == 'POST':
        file = request.files.get('sync_file')
        if not file or not file.filename.lower().endswith('.json'):
            flash('Please upload a valid JSON file.', 'danger')
            return render_template('sync/import.html')

        try:
            payload = json.loads(file.read().decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            flash('The uploaded file is not valid JSON.', 'danger')
            return render_template('sync/import.html')

        # Accept event exports and full exports grouped below data.classes.
        if isinstance(payload, dict) and isinstance(payload.get('data'), dict):
            entries = [
                {'entity_type': 'Class', 'action': 'UPDATE', 'data': row}
                for row in payload['data'].get('classes', [])
            ]
        elif isinstance(payload, list):
            entries = payload
        else:
            entries = []

        imported = skipped = failed = 0
        for entry in entries:
            if entry.get('entity_type') != 'Class':
                skipped += 1
                continue
            action = str(entry.get('action', 'UPDATE')).upper()
            class_data = entry.get('data') or {}
            if isinstance(class_data, str):
                try:
                    class_data = json.loads(class_data)
                except json.JSONDecodeError:
                    failed += 1
                    continue
            sync_id_val = class_data.get('sync_id') or entry.get('sync_id')
            try:
                existing = Class.query.filter_by(sync_id=sync_id_val).first() if sync_id_val else None
                if not existing and class_data.get('name'):
                    existing = Class.query.filter_by(
                        name=class_data['name'],
                        academic_year_id=class_data.get('academic_year_id'),
                    ).first()

                if action == 'DELETE':
                    if existing:
                        db.session.delete(existing)
                        imported += 1
                    else:
                        skipped += 1
                    continue

                if not class_data.get('name'):
                    skipped += 1
                    continue
                cls = existing or Class()
                for field in ('name', 'level', 'stream', 'teacher_id', 'capacity', 'academic_year_id'):
                    if field in class_data:
                        setattr(cls, field, class_data[field] or None)
                if sync_id_val:
                    cls.sync_id = sync_id_val
                if not existing:
                    db.session.add(cls)
                imported += 1
            except (TypeError, ValueError):
                failed += 1

        if failed:
            db.session.rollback()
            flash(f'Import failed validation for {failed} class record(s); no changes were saved.', 'danger')
        else:
            db.session.commit()
            flash(f'Import complete: {imported} class record(s) applied, {skipped} unrelated or duplicate record(s) skipped.', 'success')
        return redirect(url_for('sync_dashboard'))
    return render_template('sync/import.html')


@app.route('/sync/push')
@login_required
@role_required('super_admin', 'bursar')
def sync_push():
    """Push pending changes to online system via API."""
    endpoint = SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', '')
    if not endpoint:
        flash('Sync endpoint not configured. Use export/import method instead.', 'warning')
        return redirect(url_for('sync_dashboard'))

    pending_logs = SyncLog.query.filter_by(sync_status='pending').all()
    success_count = 0
    fail_count = 0
    for log in pending_logs:
        try:
            payload = {
                'entity_type': log.entity_type,
                'entity_id': log.entity_id,
                'action': log.action,
                'data': log.data_snapshot,
                'api_key': app.config['SYNC_API_KEY'],
            }
            resp = requests.post(f"{endpoint}/api/sync", json=payload, timeout=30)
            if resp.status_code == 200:
                log.sync_status = 'synced'
                log.sync_timestamp = datetime.utcnow()
                success_count += 1
            else:
                log.sync_status = 'failed'
                fail_count += 1
        except Exception as e:
            log.sync_status = 'failed'
            fail_count += 1
    db.session.commit()
    flash(f'Sync complete: {success_count} succeeded, {fail_count} failed.', 'info')
    return redirect(url_for('sync_dashboard'))


# ─── Settings ──────────────────────────────────────────────────────────

@app.route('/settings')
@login_required
@role_required('super_admin')
def settings():
    ay = get_current_academic_year()
    term = get_current_term()
    academic_years = AcademicYear.query.all()
    terms = Term.query.all()
    subjects = Subject.query.all()
    classes = Class.query.all()
    active_staff = Staff.query.filter_by(status='Active').all()
    demo_counts = _dummy_data_status()
    return render_template('dashboard/settings.html',
                           current_ay=ay,
                           current_term=term,
                           academic_years=academic_years,
                           terms=terms,
                           subjects=subjects,
                           classes=classes,
                           active_staff=active_staff,
                           demo_counts=demo_counts,
                           demo_streams=DEMO_STREAMS,
                           demo_levels=[(lvl[0], lvl[3]) for lvl in DEMO_LEVELS],
                           demo_teacher_password=DEMO_TEACHER_PASSWORD,
                           demo_student_prefix=DEMO_STUDENT_PREFIX)


# ─── Dummy Data Seeder (Yellow / Blue / Red / Purple / Green / Orange / Sciences / Arts / Commercials) ─

DEMO_STREAMS = ['Yellow', 'Blue', 'Red', 'Purple', 'Green', 'Orange',
                'Sciences', 'Arts', 'Commercials']

DEMO_LEVELS = [
    # (level_field, name_prefix, level_label, streams_for_this_level)
    # ECD A and ECD B have only Yellow + Blue streams per the user specification.
    ('ECD A',   'ECD',     'ECD',     ['Yellow', 'Blue']),
    ('ECD B',   'ECD',     'ECD',     ['Yellow', 'Blue']),
    ('Grade 5', 'Grade 5', 'Junior',  ['Yellow', 'Blue', 'Red', 'Purple', 'Green',
                                        'Orange', 'Sciences', 'Arts', 'Commercials']),
    ('Form 3',  'Form 3',  'O Level', ['Yellow', 'Blue', 'Red', 'Purple', 'Green',
                                        'Orange', 'Sciences', 'Arts', 'Commercials']),
    ('Form 5',  'Form 5',  'A Level', ['Yellow', 'Blue', 'Red', 'Purple', 'Green',
                                        'Orange', 'Sciences', 'Arts', 'Commercials']),
]

DEMO_STUDENT_PREFIX = 'DEMO-S'
DEMO_STAFF_PREFIX = 'DEMO-E'
DEMO_TEACHER_PASSWORD = 'demo123'

# Zimbabwean first/last name pools (Shona + Ndebele mixed)
_DEMO_FIRST_NAMES = [
    'Tendai', 'Chiedza', 'Kudzai', 'Rumbidzai', 'Tatenda', 'Fadzai', 'Tarisai',
    'Vimbai', 'Ngonidzashe', 'Patience', 'Sibusisiwe', 'Nolwazi', 'Ntando',
    'Sipho', 'Nomsa', 'Bongani', 'Thandiwe', 'Mandla', 'Nomthandazo', 'Sanelisiwe',
    'Tawanda', 'Munashe', 'Gamuchirai', 'Runako', 'Tinotenda', 'Anesu', 'Tanaka',
    'Ruvarashe', 'Tashinga', 'Bright', 'Shamiso', 'Paidamoyo', 'Chenai',
    'Mufaro', 'Kudakwashe', 'Tadiwa', 'Simbarashe', 'Farai', 'Trust',
]
_DEMO_LAST_NAMES = [
    'Moyo', 'Dube', 'Ncube', 'Sibanda', 'Mhaka', 'Chirume', 'Gumbo', 'Ndlovu',
    'Mpofu', 'Tshuma', 'Sithole', 'Nyathi', 'Banda', 'Jiri', 'Mhlanga',
    'Maphosa', 'Mlambo', 'Nkomo', 'Zhou', 'Mutasa', 'Chivasa', 'Muzondo', 'Hove',
    'Mavhunga', 'Mugoni', 'Chikwava', 'Musoni', 'Chidzonga', 'Marongedzwa',
]
_DEMO_TEACHER_FIRST = ['Grace', 'John', 'Mary', 'David', 'Sarah', 'Peter',
                       'Anna', 'Joseph', 'Ruth', 'Daniel', 'Esther', 'Samuel']
_DEMO_TEACHER_LAST = ['Chimuti', 'Sibanda', 'Moyo', 'Nkomo', 'Mukamuri', 'Ndlovu',
                      'Mpofu', 'Banda', 'Tshuma', 'Mhlanga', 'Chivasa', 'Hove']


def _seed_dummy_data(actor_user_id=None):
    """Create dummy data: ECD A + ECD B (2 streams each = 4 classes),
    + Grade 5 + Form 3 + Form 5 (9 streams each = 27 classes) = 31 classes total,
    10 students per level in the Yellow class, 31 teachers.

    Returns (success, message).
    """
    ay = get_current_academic_year()
    term = get_current_term()
    if not ay or not term:
        return False, 'No current academic year or term configured.'

    # Clear any existing demo data first (so re-seeding is idempotent)
    _clear_dummy_data(silent=True)

    created_classes = {}  # level_name -> { stream_name: Class }
    teachers_created = 0

    # 1) Create classes per level (each level has its own stream list) + one teacher per class
    teacher_counter = 0
    for level_field, name_prefix, _, level_streams in DEMO_LEVELS:
        created_classes[level_field] = {}
        for stream in level_streams:
            class_name = f"{name_prefix} {stream}"
            cls = Class(
                name=class_name,
                level=level_field,
                stream=stream,
                capacity=40,
                academic_year_id=ay.id,
            )
            db.session.add(cls)
            db.session.flush()
            created_classes[level_field][stream] = cls

            # Form master (teacher) for this class
            first = _DEMO_TEACHER_FIRST[teacher_counter % len(_DEMO_TEACHER_FIRST)]
            last = _DEMO_TEACHER_LAST[teacher_counter % len(_DEMO_TEACHER_LAST)]
            emp_num = f"{DEMO_STAFF_PREFIX}{teacher_counter + 1:04d}"
            username = emp_num.lower()
            if User.query.filter_by(username=username).first() is None:
                user = User(username=username, role='teacher', is_active=True)
                user.set_password(DEMO_TEACHER_PASSWORD)
                db.session.add(user)
                db.session.flush()
            else:
                user = User.query.filter_by(username=username).first()
            staff = Staff(
                employee_number=emp_num,
                first_name=first,
                last_name=last,
                position='Teacher',
                department='Academic',
                status='Active',
                user_id=user.id,
            )
            db.session.add(staff)
            db.session.flush()
            cls.teacher_id = staff.id

            # Auto-assign subjects for PRIMARY level teachers:
            # each primary teacher gets all 6 Heritage-Based Curriculum learning areas.
            # (Secondary teachers are unassigned by default — admins add StaffSubject rows.)
            if is_primary_level(cls.level):
                for subj_name in PRIMARY_LEARNING_AREAS:
                    subj = Subject.query.filter_by(name=subj_name).first()
                    if subj and not StaffSubject.query.filter_by(
                            staff_id=staff.id, subject_id=subj.id, class_id=cls.id).first():
                        db.session.add(StaffSubject(
                            staff_id=staff.id, subject_id=subj.id, class_id=cls.id,
                            academic_year_id=ay.id))
            teacher_counter += 1
            teachers_created += 1

    # 2) Add 10 students per level in the Yellow class with varied profiles
    students_created = 0
    student_counter = 0
    for level_field, name_prefix, _, level_streams in DEMO_LEVELS:
        yellow_class = created_classes[level_field]['Yellow']
        for i in range(10):
            adm = f"{DEMO_STUDENT_PREFIX}{student_counter + 1:04d}"
            first = _DEMO_FIRST_NAMES[student_counter % len(_DEMO_FIRST_NAMES)]
            last = _DEMO_LAST_NAMES[(student_counter + 3) % len(_DEMO_LAST_NAMES)]
            gender = 'Male' if (student_counter % 2 == 0) else 'Female'
            dob = date(2014 + (student_counter % 7), ((student_counter * 3) % 12) + 1,
                       ((student_counter * 5) % 27) + 1)

            # Cycle through scholarship classifications for visual variety
            cycle = student_counter % 7
            if cycle == 0:
                fc, st, sp = 'Academic Scholarship', 'Partial', 50.0
            elif cycle == 1:
                fc, st, sp = 'Staff Scholarship', 'Full', 100.0
            elif cycle == 2:
                fc, st, sp = 'Bursary', 'Partial', 75.0
            elif cycle == 3:
                fc, st, sp = 'Sports Scholarship', 'Partial', 25.0
            elif cycle == 4:
                fc, st, sp = 'Orphan', 'Full', 100.0
            else:
                fc, st, sp = 'Regular', 'None', 0.0

            student = Student(
                admission_number=adm,
                first_name=first,
                last_name=last,
                gender=gender,
                date_of_birth=dob,
                class_id=yellow_class.id,
                admission_date=date.today() - timedelta(days=90 + student_counter),
                status='Active',
                fee_classification=fc,
                scholarship_type=st,
                scholarship_percentage=sp,
                entry_mode='Stay In' if cycle in (1, 2, 5) else 'Day',
                city='Harare',
                province='Harare',
                country='Zimbabwe',
                phone=f'0772{1000000 + student_counter:07d}',
                email=f'{adm.lower()}@demo.excelgroup.edu.zw',
            )
            db.session.add(student)
            db.session.flush()
            generate_student_invoice(student, term, ay)
            db.session.flush()

            # Vary payment statuses: paid-in-full / half-paid / unpaid
            inv = Invoice.query.filter_by(student_id=student.id,
                                          term_id=term.id,
                                          academic_year_id=ay.id).first()
            payment_actor = actor_user_id or User.query.filter_by(role='super_admin').first().id
            if inv:
                if cycle in (0, 4):
                    # Fully paid (scholarships usually settled)
                    p = FeePayment(
                        student_id=student.id,
                        receipt_number=generate_receipt_number(),
                        amount=inv.total_amount,
                        payment_date=date.today() - timedelta(days=30 + i),
                        payment_method='Cash' if i % 2 == 0 else 'Bank Transfer',
                        term_id=term.id,
                        academic_year_id=ay.id,
                        description='Term fees',
                        received_by=payment_actor,
                    )
                    db.session.add(p)
                elif cycle in (1, 2, 3):
                    # Partially paid
                    p = FeePayment(
                        student_id=student.id,
                        receipt_number=generate_receipt_number(),
                        amount=inv.total_amount * 0.5,
                        payment_date=date.today() - timedelta(days=15 + i),
                        payment_method='EcoCash',
                        term_id=term.id,
                        academic_year_id=ay.id,
                        description='First installment',
                        received_by=payment_actor,
                    )
                    db.session.add(p)
                # else (5, 6): unpaid (debtor)

            students_created += 1
            student_counter += 1

    db.session.commit()
    total_classes = sum(len(streams) for _, _, _, streams in DEMO_LEVELS)
    return True, (f'Created {total_classes} classes, '
                  f'{teachers_created} teachers (login: demo<NNNN> / {DEMO_TEACHER_PASSWORD}), '
                  f'and {students_created} students (in Yellow classes).')


def _clear_dummy_data(silent=False):
    """Remove all demo data (records whose admission_number / employee_number starts with DEMO-).

    Returns (success, message).
    """
    try:
        # 1) Identify the demo records first (same class names the seeder uses).
        demo_students = Student.query.filter(
            Student.admission_number.like(f'{DEMO_STUDENT_PREFIX}%')).all()
        demo_student_ids = [s.id for s in demo_students]

        demo_class_names = []
        for _, prefix, _, level_streams in DEMO_LEVELS:
            for stream in level_streams:
                demo_class_names.append(f"{prefix} {stream}")
        demo_classes = Class.query.filter(Class.name.in_(demo_class_names)).all()
        demo_class_ids = [c.id for c in demo_classes]

        demo_staff = Staff.query.filter(
            Staff.employee_number.like(f'{DEMO_STAFF_PREFIX}%')).all()
        demo_staff_ids = [s.id for s in demo_staff]
        demo_user_ids = [s.user_id for s in demo_staff if s.user_id]

        # 2) Delete child rows BEFORE their parents. StaffSubject has NOT NULL
        #    foreign keys to staff and class, so deleting a demo class/staff
        #    through the ORM would try to NULL those FKs and raise an
        #    IntegrityError ("Internal Server Error" in the browser).
        if demo_staff_ids or demo_class_ids:
            StaffSubject.query.filter(
                db.or_(
                    StaffSubject.staff_id.in_(demo_staff_ids),
                    StaffSubject.class_id.in_(demo_class_ids),
                )
            ).delete(synchronize_session=False)
            TimetableSlot.query.filter(
                db.or_(
                    TimetableSlot.staff_id.in_(demo_staff_ids),
                    TimetableSlot.class_id.in_(demo_class_ids),
                )
            ).delete(synchronize_session=False)

        # 3) Student child rows (invoice items, invoices, payments, results,
        #    hostel allocations) for demo students.
        if demo_student_ids:
            InvoiceItem.query.filter(
                InvoiceItem.invoice_id.in_(
                    db.session.query(Invoice.id).filter(
                        Invoice.student_id.in_(demo_student_ids))
                )
            ).delete(synchronize_session=False)
            Invoice.query.filter(
                Invoice.student_id.in_(demo_student_ids)).delete(
                    synchronize_session=False)
            FeePayment.query.filter(
                FeePayment.student_id.in_(demo_student_ids)).delete(
                    synchronize_session=False)
            ExamResult.query.filter(
                ExamResult.student_id.in_(demo_student_ids)).delete(
                    synchronize_session=False)
            RoomAllocation.query.filter(
                RoomAllocation.student_id.in_(demo_student_ids)).delete(
                    synchronize_session=False)

        # 4) Unassign demo teachers from EVERY class (demo or not) so the
        #    staff rows can be removed cleanly.
        if demo_staff_ids:
            Class.query.filter(Class.teacher_id.in_(demo_staff_ids)).update(
                {Class.teacher_id: None}, synchronize_session=False)

        # 5) Delete the demo parents themselves, then linked user accounts.
        for s in demo_students:
            db.session.delete(s)
        for c in demo_classes:
            db.session.delete(c)
        for s in demo_staff:
            db.session.delete(s)
        if demo_user_ids:
            User.query.filter(User.id.in_(demo_user_ids)).delete(
                synchronize_session=False)

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        msg = f'Failed to clear demo data: {exc}'
        if not silent:
            return False, msg
        return False, msg

    counts = {
        'students': len(demo_students),
        'classes': len(demo_classes),
        'staff': len(demo_staff),
    }
    msg = (f'Cleared {counts["students"]} demo students, {counts["classes"]} '
           f'demo classes and {counts["staff"]} demo staff.')
    if not silent:
        return True, msg
    return True, msg


def _dummy_data_status():
    """Return counts of demo records currently in the database."""
    # Build list of all demo class names: for each level, combine its specific streams.
    demo_class_names = []
    for _, prefix, _, level_streams in DEMO_LEVELS:
        for stream in level_streams:
            demo_class_names.append(f"{prefix} {stream}")

    return {
        'students': Student.query.filter(
            Student.admission_number.like(f'{DEMO_STUDENT_PREFIX}%')).count(),
        'classes': Class.query.filter(Class.name.in_(demo_class_names)).count(),
        'staff': Staff.query.filter(
            Staff.employee_number.like(f'{DEMO_STAFF_PREFIX}%')).count(),
        'teachers': User.query.filter(
            User.username.like(f'{DEMO_STAFF_PREFIX.lower()}%')).count(),
    }


@app.route('/settings/dummy-data/seed', methods=['POST'])
@login_required
@role_required('super_admin')
def settings_dummy_data_seed():
    """(Re)seed the demo data — safe to call multiple times."""
    success, message = _seed_dummy_data(actor_user_id=session.get('user_id'))
    flash(('✓ ' if success else '✗ ') + message,
          'success' if success else 'danger')
    return redirect(url_for('settings'))


@app.route('/settings/dummy-data/clear', methods=['POST'])
@login_required
@role_required('super_admin')
def settings_dummy_data_clear():
    """Remove all demo data."""
    success, message = _clear_dummy_data()
    flash(('✓ ' if success else '✗ ') + message,
          'success' if success else 'danger')
    return redirect(url_for('settings'))


@app.route('/settings/academic-year/add', methods=['POST'])
@login_required
@role_required('super_admin')
def add_academic_year():
    ay = AcademicYear(
        name=request.form.get('name'),
        start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
        end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date(),
        is_current=request.form.get('is_current') == 'on',
    )
    if ay.is_current:
        AcademicYear.query.update({AcademicYear.is_current: False})
    db.session.add(ay)
    db.session.commit()
    flash('Academic year added.', 'success')
    return redirect(url_for('settings'))


@app.route('/settings/term/add', methods=['POST'])
@login_required
@role_required('super_admin')
def add_term():
    term = Term(
        name=request.form.get('name'),
        academic_year_id=request.form.get('academic_year_id'),
        start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date(),
        end_date=datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date(),
        is_current=request.form.get('is_current') == 'on',
    )
    if term.is_current:
        Term.query.update({Term.is_current: False})
    db.session.add(term)
    db.session.commit()
    flash('Term added.', 'success')
    return redirect(url_for('settings'))


@app.route('/settings/subject/add', methods=['POST'])
@login_required
@role_required('super_admin')
def add_subject():
    subject = Subject(
        name=request.form.get('name'),
        code=request.form.get('code'),
        description=request.form.get('description'),
        is_compulsory=request.form.get('is_compulsory') == 'on',
    )
    db.session.add(subject)
    db.session.commit()
    flash('Subject added.', 'success')
    return redirect(url_for('settings'))


@app.route('/classes')
@login_required
@role_required('super_admin', 'bursar')
def classes_list():
    """List classes and expose class creation to admins and bursars."""
    classes = Class.query.order_by(Class.level, Class.name).all()
    academic_years = AcademicYear.query.order_by(AcademicYear.start_date.desc()).all()
    teachers = Staff.query.filter_by(status='Active').order_by(Staff.last_name, Staff.first_name).all()
    return render_template(
        'classes/list.html',
        classes=classes,
        academic_years=academic_years,
        teachers=teachers,
    )


@app.route('/settings/class/add', methods=['POST'])
@login_required
@role_required('super_admin', 'bursar')
def add_class():
    level = request.form.get('level')
    stream = request.form.get('stream', '')
    name = request.form.get('name')
    if not name:
        # Auto-generate name from level + stream
        name = f"{level} {stream}" if stream else level
    academic_year_id = request.form.get('academic_year_id') or None
    duplicate = Class.query.filter_by(name=name, academic_year_id=academic_year_id).first()
    if duplicate:
        flash('A class with that name already exists for the selected academic year.', 'warning')
        return redirect(url_for('classes_list'))

    cls = Class(
        name=name,
        level=level,
        stream=stream,
        teacher_id=request.form.get('teacher_id') or None,
        capacity=max(1, int(request.form.get('capacity', 40))),
        academic_year_id=academic_year_id,
    )
    db.session.add(cls)
    db.session.flush()

    # Auto-assign primary subjects if this is a primary level class
    if is_primary_level(level):
        for subj_name in PRIMARY_SUBJECTS:
            subj = Subject.query.filter_by(name=subj_name).first()
            if not subj:
                # Auto-create the subject with its stable cross-system code.
                code = PRIMARY_SUBJECT_CODES[subj_name]
                subj = Subject(name=subj_name, code=code, is_compulsory=True)
                db.session.add(subj)
                db.session.flush()

    db.session.commit()
    log_sync('Class', cls.id, 'CREATE', {
        'name': cls.name,
        'level': cls.level,
        'stream': cls.stream,
        'teacher_id': cls.teacher_id,
        'capacity': cls.capacity,
        'academic_year_id': cls.academic_year_id,
        'sync_id': cls.sync_id,
    })
    flash('Class added.' + (' Primary subjects auto-assigned.' if is_primary_level(level) else ''), 'success')
    return redirect(url_for('classes_list'))


# ─── Teacher Portal (My Classes / Subjects) ──────────────────────────

@app.route('/teacher')
@login_required
def teacher_home():
    """Landing page for teachers — shows their assigned classes & subjects."""
    if session.get('user_role') != 'teacher':
        flash('This portal is for teachers only.', 'danger')
        return redirect(url_for('dashboard'))
    staff = _staff_for_current_user()
    if not staff:
        flash('Your teacher profile is not set up yet. Please contact the administrator.', 'warning')
        return redirect(url_for('dashboard'))

    ay = get_current_academic_year()
    term = get_current_term()
    class_ids = get_teacher_class_ids(staff.id, ay.id if ay else None)
    classes = Class.query.filter(Class.id.in_(class_ids)).order_by(Class.name).all() if class_ids else []
    # Per-class subject breakdown
    cs_map = get_teacher_classes_with_subjects(staff.id, ay.id if ay else None)
    subject_ids = sorted({sid for sids in cs_map.values() for sid in sids})
    subjects = Subject.query.filter(Subject.id.in_(subject_ids)).order_by(Subject.name).all() if subject_ids else []

    # Student counts per class
    student_counts = {}
    for c in classes:
        student_counts[c.id] = Student.query.filter_by(class_id=c.id, status='Active').count()

    subjects_by_id = {subject.id: subject for subject in subjects}
    return render_template('dashboard/teacher_portal.html',
                           staff=staff, classes=classes, subjects=subjects,
                           subjects_by_id=subjects_by_id,
                           cs_map=cs_map, student_counts=student_counts,
                           term=term, ay=ay)


@app.route('/teacher/class/<int:class_id>')
@login_required
def teacher_class_view(class_id):
    """View a single class — teachers only see classes they're assigned to."""
    if session.get('user_role') != 'teacher':
        flash('This portal is for teachers only.', 'danger')
        return redirect(url_for('dashboard'))
    staff = _staff_for_current_user()
    if not staff or not teacher_can_access_class(staff.id, class_id):
        flash('You do not have access to this class.', 'danger')
        return redirect(url_for('teacher_home'))
    cls = Class.query.get_or_404(class_id)
    students = Student.query.filter_by(class_id=class_id, status='Active') \
                            .order_by(Student.last_name, Student.first_name).all()
    ay = get_current_academic_year()
    subject_ids = get_teacher_classes_with_subjects(
        staff.id, ay.id if ay else None
    ).get(class_id, [])
    subjects = Subject.query.filter(Subject.id.in_(subject_ids)).order_by(Subject.name).all() if subject_ids else []
    return render_template('dashboard/teacher_class.html',
                           cls=cls, students=students, subjects=subjects, staff=staff)


@app.route('/teacher/subject/<int:subject_id>')
@login_required
def teacher_subject_view(subject_id):
    """View a single subject — teachers only see subjects they're assigned to."""
    if session.get('user_role') != 'teacher':
        flash('This portal is for teachers only.', 'danger')
        return redirect(url_for('dashboard'))
    staff = _staff_for_current_user()
    if not staff or not teacher_can_access_subject(staff.id, subject_id):
        flash('You do not have access to this subject.', 'danger')
        return redirect(url_for('teacher_home'))
    subject = Subject.query.get_or_404(subject_id)
    ay = get_current_academic_year()
    assignment_map = get_teacher_classes_with_subjects(staff.id, ay.id if ay else None)
    class_ids = [cid for cid, subject_ids in assignment_map.items() if subject_id in subject_ids]
    classes = Class.query.filter(Class.id.in_(class_ids)).order_by(Class.name).all() if class_ids else []
    students = Student.query.filter(Student.class_id.in_(class_ids),
                                     Student.status == 'Active').order_by(
                                         Student.last_name, Student.first_name
                                     ).all() if class_ids else []
    return render_template('dashboard/teacher_subject.html',
                           subject=subject, students=students, classes=classes, staff=staff)


# ─── Bulk Import ───────────────────────────────────────────────────────

def _clean_optional_text(value):
    """Return stripped text or None for blank/placeholder cells."""
    text = (value or '').strip()
    if text.lower() in ('-', 'n/a', 'na', 'none', 'nil', '—', '–'):
        return None
    return text or None


def _parse_class_name(class_name):
    """Best-effort split of a class name into (level, stream).

    Examples:
        'Grade 7A'        -> ('Grade 7', 'A')
        'Grade 5 Yellow'  -> ('Grade 5', 'Yellow')
        'Form 3 Blue'     -> ('Form 3', 'Blue')
        'ECD A Yellow'    -> ('ECD A', 'Yellow')
        'ECD Yellow'      -> ('ECD A', 'Yellow')
        'Unknown Class'   -> ('Unknown Class', '')   (nothing is lost)
    """
    name = (class_name or '').strip()
    if not name:
        return '', ''
    lower = name.lower()
    m = re.match(r'^(ecd)\s*([ab])?(?:\s+(.*))?$', lower)
    if m:
        level = 'ECD ' + m.group(2).upper() if m.group(2) else 'ECD A'
        return level, (m.group(3) or '').strip().title()
    for prefix, label in (('grade', 'Grade'), ('gr', 'Grade'), ('form', 'Form')):
        m = re.match(rf'^({prefix}\s*\d{{1,2}})\s*([a-z]?)(?:\s+(.*))?$', lower)
        if m:
            level = label + ' ' + m.group(1).split()[-1]
            stream = (m.group(3) or '').strip().title() or m.group(2).upper()
            return level, stream
    return name, ''


def _auto_create_class(class_name):
    """Create a class on the fly during bulk import (no teacher assigned).

    Teacher allocation is always done manually afterwards on the Classes
    page, so the created class starts without a form teacher.
    """
    level, stream = _parse_class_name(class_name)
    ay = get_current_academic_year()
    cls = Class(
        name=class_name.strip(),
        level=level or None,
        stream=stream or None,
        capacity=40,
        academic_year_id=ay.id if ay else None,
    )
    db.session.add(cls)
    db.session.flush()
    # Auto-assign the approved primary learning areas for primary classes,
    # exactly like creating the class from the Classes page.
    if level and is_primary_level(level):
        for subj_name in PRIMARY_SUBJECTS:
            subj = Subject.query.filter_by(name=subj_name).first()
            if not subj:
                subj = Subject(
                    name=subj_name,
                    code=PRIMARY_SUBJECT_CODES[subj_name],
                    is_compulsory=True,
                )
                db.session.add(subj)
                db.session.flush()
    log_sync('Class', cls.id, 'CREATE', {
        'name': cls.name,
        'level': cls.level,
        'stream': cls.stream,
        'teacher_id': None,
        'capacity': cls.capacity,
        'academic_year_id': cls.academic_year_id,
        'sync_id': cls.sync_id,
    })
    return cls


@app.route('/students/bulk-import', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'bursar')
def students_bulk_import():
    if request.method == 'POST':
        file = request.files.get('import_file')
        if not file:
            flash('Please select a file to upload.', 'danger')
            return redirect(url_for('students_bulk_import'))
        filename = file.filename.lower()
        if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
            flash('Please upload an Excel file (.xlsx or .xls).', 'danger')
            return redirect(url_for('students_bulk_import'))
        try:
            wb = openpyxl.load_workbook(file)
            ws = wb.active
            headers = [str(cell.value).strip().lower() if cell.value else '' for cell in ws[1]]
            created = 0
            classes_created = 0
            created_class_cache = {}
            errors = []
            is_first_import = (SyncSetting.get('initial_bulk_import_done') != 'true')
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    row_data = dict(zip(headers, [str(v).strip() if v else '' for v in row]))
                    # Skip empty rows
                    if not row_data.get('first_name') or not row_data.get('last_name'):
                        continue
                    adm = row_data.get('admission_number') or generate_admission_number()
                    if Student.query.filter_by(admission_number=adm).first():
                        errors.append(f"Row {row_idx}: Admission number {adm} already exists")
                        continue
                    # Resolve the class, creating it automatically when the
                    # name is not in the system yet (teacher allocated later).
                    class_id = None
                    class_name = (row_data.get('class_name') or '').strip()
                    if class_name:
                        cls = created_class_cache.get(class_name.lower())
                        if cls is None:
                            cls = Class.query.filter_by(name=class_name).first()
                        if cls is None:
                            cls = _auto_create_class(class_name)
                            created_class_cache[class_name.lower()] = cls
                            classes_created += 1
                        class_id = cls.id
                    dob = None
                    if row_data.get('date_of_birth'):
                        try:
                            dob = datetime.strptime(row_data.get('date_of_birth'), '%Y-%m-%d').date()
                        except ValueError:
                            pass
                    adm_date = date.today()
                    if row_data.get('admission_date'):
                        try:
                            adm_date = datetime.strptime(row_data.get('admission_date'), '%Y-%m-%d').date()
                        except ValueError:
                            pass
                    student = Student(
                        admission_number=adm,
                        first_name=row_data.get('first_name', '').strip(),
                        last_name=row_data.get('last_name', '').strip(),
                        other_names=_clean_optional_text(row_data.get('other_names')),
                        date_of_birth=dob,
                        gender=row_data.get('gender', '').strip() or None,
                        national_id=_clean_optional_text(row_data.get('national_id')),
                        class_id=class_id,
                        admission_date=adm_date,
                        previous_school=_clean_optional_text(row_data.get('previous_school')),
                        address=_clean_optional_text(row_data.get('address')),
                        city=_clean_optional_text(row_data.get('city')),
                        province=_clean_optional_text(row_data.get('province')),
                        phone=_clean_optional_text(row_data.get('phone')),
                        email=_clean_optional_text(row_data.get('email')),
                        fee_classification=row_data.get('fee_classification', 'Regular').strip() or 'Regular',
                        scholarship_type=row_data.get('scholarship_type', 'None').strip() or 'None',
                        scholarship_percentage=float(row_data.get('scholarship_percentage', 0) or 0),
                        scholarship_sponsor=_clean_optional_text(row_data.get('scholarship_sponsor')),
                        scholarship_notes=_clean_optional_text(row_data.get('scholarship_notes')),
                        is_new_learner=not is_first_import,
                        billed_once_off_levies=is_first_import,
                        entry_mode=normalize_entry_mode(row_data.get('entry_mode')),
                    )
                    if student.fee_classification == 'Staff Scholarship' and row_data.get('staff_employee_number'):
                        staff_member = Staff.query.filter_by(employee_number=row_data.get('staff_employee_number').strip()).first()
                        if staff_member:
                            student.scholarship_staff_id = staff_member.id
                    db.session.add(student)
                    db.session.flush()
                    generate_student_invoice(student)
                    # NOTE: Students do NOT get user accounts.
                    # They access the system via the Student Portal linked to their parent's account.
                    created += 1
                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")
            if created > 0 and is_first_import:
                SyncSetting.set('initial_bulk_import_done', 'true')
            db.session.commit()
            msg = f'Successfully imported {created} students.'
            if classes_created:
                msg += (f' {classes_created} new class'
                        f'{"es" if classes_created != 1 else ""} auto-created'
                        f' (assign teachers in Classes).')
            if errors:
                msg += f' {len(errors)} rows had errors.'
            flash(msg, 'success' if created > 0 else 'warning')
            for err in errors[:10]:
                flash(err, 'danger')
        except Exception as e:
            flash(f'Error processing Excel file: {str(e)}', 'danger')
        return redirect(url_for('students_bulk_import'))

    classes = Class.query.all()
    return render_template('students/bulk_import.html', classes=classes)


@app.route('/students/excel-template')
@login_required
@role_required('super_admin', 'bursar')
def students_excel_template():
    """Download an Excel template for bulk student import."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Students Import"

    # Header styling
    header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='1A5632', end_color='1A5632', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    headers = [
        'admission_number', 'first_name', 'last_name', 'other_names',
        'date_of_birth', 'gender', 'national_id', 'class_name', 'entry_mode',
        'admission_date', 'previous_school', 'address', 'city', 'province',
        'phone', 'email', 'fee_classification', 'scholarship_type',
        'scholarship_percentage', 'scholarship_sponsor', 'staff_employee_number',
        'scholarship_notes'
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # Example rows
    examples = [
        ['', 'Tendai', 'Moyo', '', '2010-05-15', 'Male', '12-345678A12',
         'Grade 7A', 'Day', '2026-01-12', 'Previous School', '12 Herbert Chitepo',
         'Harare', 'Harare', '0771234567', 'tendai@example.com',
         'Regular', 'None', 0, '', '', ''],
        ['', 'Chiedza', 'Dube', '', '2011-03-22', 'Female', '', 'Grade 6A',
         'Stay In', '2026-01-12', '', '', 'Bulawayo', '', '0772987654', '',
         'Staff Scholarship', 'Full', 100, '', 'EMP001',
         'Child of staff member'],
        ['', 'Kudzai', 'Ncube', '', '2010-08-10', 'Male', '', 'Grade 7A',
         'Day', '', '', '', '', '', '', '',
         'Academic Scholarship', 'Partial', 50, 'School Bursary Fund', '',
         'Top performer'],
    ]
    example_fill = PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid')
    for r, row_data in enumerate(examples, 2):
        for c, val in enumerate(row_data, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.fill = example_fill
            cell.border = thin_border

    # Instruction sheet
    ws2 = wb.create_sheet("Instructions")
    instructions = [
        ["EXCEL GROUP OF SCHOOLS — Student Bulk Import Template", ""],
        ["Author: Valentine T Mabheka | Version 2.0.0", ""],
        ["", ""],
        ["INSTRUCTIONS:", ""],
        ["1.", "Fill in the 'Students Import' sheet with your student data."],
        ["2.", "Leave 'admission_number' blank to auto-generate."],
        ["3.", 'date_of_birth and admission_date must be YYYY-MM-DD format.'],
        ["4.", "'class_name' — if the class does not exist yet it is created automatically; only the teacher allocation is done manually later (Classes page)."],
        ["4b.", "'entry_mode' — Day or Stay In. Stay In (boarding) learners are billed the Stay In fee automatically every term ($300 primary/secondary, $260 A Level)."],
        ["5.", "gender must be Male or Female."],
        ["", ""],
        ["FEE CLASSIFICATION OPTIONS:", ""],
        ["Regular", "Full fee paying student"],
        ["Staff Scholarship", "child of a staff member — set scholarship_type to Full or Partial"],
        ["Academic Scholarship", "based on academic merit"],
        ["Sports Scholarship", "based on sports talent"],
        ["Bursary", "financial need-based discount"],
        ["Orphan", "automatically set to Full scholarship (100% discount)"],
        ["", ""],
        ["SCHOLARSHIP TYPE OPTIONS:", ""],
        ["None", "no discount (default for Regular)"],
        ["Full", "100% fee discount"],
        ["Partial", "enter discount percentage in scholarship_percentage column (0-100)"],
        ["", ""],
        ["STAFF SCHOLARSHIP:", ""],
        ["", "Enter the staff member's employee_number in the staff_employee_number column"],
    ]
    inst_font = Font(name='Calibri', size=11)
    bold_font = Font(name='Calibri', size=11, bold=True)
    title_font = Font(name='Calibri', size=14, bold=True, color='1A5632')
    for r, (a, b) in enumerate(instructions, 1):
        cell_a = ws2.cell(row=r, column=1, value=a)
        cell_b = ws2.cell(row=r, column=2, value=b)
        if r == 1:
            cell_a.font = title_font
        elif r in (4, 10, 16, 21):
            cell_a.font = bold_font
        else:
            cell_a.font = inst_font
        cell_b.font = inst_font
    ws2.column_dimensions['A'].width = 28
    ws2.column_dimensions['B'].width = 70

    # Auto-size columns on data sheet
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = 'attachment; filename=students_import_template.xlsx'
    return resp


@app.route('/staff/bulk-import', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'bursar')
def staff_bulk_import():
    if request.method == 'POST':
        file = request.files.get('import_file')
        if not file:
            flash('Please select a file to upload.', 'danger')
            return redirect(url_for('staff_bulk_import'))
        filename = file.filename.lower()
        if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
            flash('Please upload an Excel file (.xlsx or .xls).', 'danger')
            return redirect(url_for('staff_bulk_import'))
        try:
            wb = openpyxl.load_workbook(file)
            ws = wb.active
            headers = [str(cell.value).strip().lower() if cell.value else '' for cell in ws[1]]
            created = 0
            users_created = 0
            errors = []

            # Valid roles that can be assigned during bulk upload
            valid_roles = {
                'super_admin': 'super_admin', 'director': 'super_admin', 'principal': 'super_admin',
                'accountant': 'accountant',
                'bursar': 'bursar',
                'teacher': 'teacher',
                'head': 'super_admin', 'deputy head': 'super_admin', 'hod': 'teacher',
                'clerk': 'bursar', 'librarian': 'teacher', 'driver': 'bursar', 'warden': 'bursar',
            }

            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    row_data = dict(zip(headers, [str(v).strip() if v else '' for v in row]))
                    if not row_data.get('first_name') or not row_data.get('last_name'):
                        continue
                    emp_num = row_data.get('employee_number', '').strip() or generate_employee_number()
                    if Staff.query.filter_by(employee_number=emp_num).first():
                        errors.append(f"Row {row_idx}: Employee number {emp_num} already exists")
                        continue
                    dob = None
                    if row_data.get('date_of_birth'):
                        try:
                            dob = datetime.strptime(row_data.get('date_of_birth'), '%Y-%m-%d').date()
                        except ValueError:
                            pass
                    emp_date = date.today()
                    if row_data.get('employment_date'):
                        try:
                            emp_date = datetime.strptime(row_data.get('employment_date'), '%Y-%m-%d').date()
                        except ValueError:
                            pass

                    # Determine role from 'role' column or fallback to position
                    role_input = row_data.get('role', '').strip().lower()
                    position = row_data.get('position', '').strip() or 'Teacher'
                    if role_input and role_input in ROLE_LABELS:
                        assigned_role = role_input
                    elif role_input and role_input in valid_roles:
                        assigned_role = valid_roles[role_input]
                    elif position.lower() in valid_roles:
                        assigned_role = valid_roles[position.lower()]
                    else:
                        assigned_role = 'teacher'  # Default role

                    staff = Staff(
                        employee_number=emp_num,
                        first_name=row_data.get('first_name', '').strip(),
                        last_name=row_data.get('last_name', '').strip(),
                        other_names=row_data.get('other_names', '').strip() or None,
                        date_of_birth=dob,
                        gender=row_data.get('gender', '').strip() or None,
                        national_id=row_data.get('national_id', '').strip() or None,
                        qualification=row_data.get('qualification', '').strip() or None,
                        specialization=row_data.get('specialization', '').strip() or None,
                        department=row_data.get('department', '').strip() or None,
                        position=position,
                        employment_date=emp_date,
                        salary=float(row_data.get('salary', 0) or 0) or None,
                        phone=row_data.get('phone', '').strip() or None,
                        email=row_data.get('email', '').strip() or None,
                        address=row_data.get('address', '').strip() or None,
                    )
                    db.session.add(staff)

                    # Create user account for staff with assigned role
                    username = row_data.get('username', '').strip() or emp_num.lower()
                    password = row_data.get('password', '').strip() or emp_num.lower()
                    if not User.query.filter_by(username=username).first():
                        user = User(username=username, role=assigned_role, is_active=True)
                        user.set_password(password)
                        db.session.add(user)
                        db.session.flush()
                        staff.user_id = user.id
                        users_created += 1

                    created += 1
                except Exception as e:
                    errors.append(f"Row {row_idx}: {str(e)}")
            db.session.commit()
            msg = f'Successfully imported {created} staff members. {users_created} user accounts created.'
            if errors:
                msg += f' {len(errors)} rows had errors.'
            flash(msg, 'success' if created > 0 else 'warning')
            for err in errors[:10]:
                flash(err, 'danger')
        except Exception as e:
            flash(f'Error processing Excel file: {str(e)}', 'danger')
        return redirect(url_for('staff_bulk_import'))

    return render_template('staff/bulk_import.html')


@app.route('/staff/excel-template')
@login_required
@role_required('super_admin')
def staff_excel_template():
    """Download an Excel template for bulk staff import."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Staff Import"

    header_font = Font(name='Calibri', bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='1A5632', end_color='1A5632', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    headers = [
        'employee_number', 'first_name', 'last_name', 'other_names',
        'date_of_birth', 'gender', 'national_id', 'qualification',
        'specialization', 'department', 'position', 'employment_date',
        'salary', 'phone', 'email', 'address', 'role', 'username', 'password'
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    examples = [
        ['', 'Grace', 'Chimuti', '', '1985-06-20', 'Female', '23-456789A23',
         'B.Ed', 'Mathematics', 'Sciences', 'Teacher', '2020-01-15',
         2500, '0772987654', 'grace@school.com', 'Harare', 'Teacher', '', ''],
        ['', 'John', 'Sibanda', '', '1980-11-05', 'Male', '',
         'Diploma', 'English', 'Languages', 'Teacher', '2018-09-01',
         2200, '0773123456', '', 'Bulawayo', 'teacher', '', ''],
        ['', 'Mary', 'Moyo', '', '1975-03-15', 'Female', '',
         'MBA', 'Finance', 'Administration', 'Bursar', '2015-06-01',
         3500, '0774455667', 'mary@school.com', 'Harare', 'bursar', 'marymoyo', ''],
        ['', 'David', 'Nkomo', '', '1970-08-22', 'Male', '',
         'PhD', '', 'Executive', 'Director', '2010-01-01',
         5000, '0775566778', 'david@school.com', 'Harare', 'super_admin', 'dnkomo', 'SecureP@ss1'],
    ]
    example_fill = PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid')
    for r, row_data in enumerate(examples, 2):
        for c, val in enumerate(row_data, 1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.fill = example_fill
            cell.border = thin_border

    # Instruction sheet
    ws2 = wb.create_sheet("Instructions")
    instructions = [
        ["EXCEL GROUP OF SCHOOLS — Staff Bulk Import Template", ""],
        ["Author: Valentine T Mabheka | Version 2.0.0", ""],
        ["", ""],
        ["INSTRUCTIONS:", ""],
        ["1.", "Fill in the 'Staff Import' sheet with staff data."],
        ["2.", "first_name and last_name are REQUIRED. Leave employee_number blank to auto-generate."],
        ["3.", 'date_of_birth and employment_date must be YYYY-MM-DD format.'],
        ["4.", "gender must be Male or Female."],
        ["5.", "position examples: Teacher, Head, Deputy Head, HOD, Clerk, Bursar, Librarian, Driver, Warden"],
        ["", ""],
        ["ROLE ALLOCATION:", ""],
        ["6.", "The 'role' column assigns the user's system role. Options:"],
        ["", "super_admin (Director/Principal) | accountant | bursar | teacher"],
        ["7.", "If 'role' is blank, the system maps 'position' to a role:"],
        ["", "Director/Head/Deputy Head → super_admin"],
        ["", "Accountant → accountant | Clerk/Bursar/Warden/Driver → bursar"],
        ["", "Teacher/Librarian/HOD → teacher"],
        ["8.", "username: defaults to employee_number if blank. Must be unique."],
        ["9.", "password: defaults to employee_number if blank. Set custom passwords for security."],
        ["", ""],
        ["", "NOTE: Only staff get user accounts. Students and parents get accounts separately."],
    ]
    title_font = Font(name='Calibri', size=14, bold=True, color='1A5632')
    bold_font = Font(name='Calibri', size=11, bold=True)
    inst_font = Font(name='Calibri', size=11)
    for r, (a, b) in enumerate(instructions, 1):
        ws2.cell(row=r, column=1, value=a).font = title_font if r == 1 else bold_font if a.endswith(':') else inst_font
        ws2.cell(row=r, column=2, value=b).font = inst_font
    ws2.column_dimensions['A'].width = 28
    ws2.column_dimensions['B'].width = 70

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    resp = make_response(output.getvalue())
    resp.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    resp.headers['Content-Disposition'] = 'attachment; filename=staff_import_template.xlsx'
    return resp


# ─── Appearance / Theme Customization ─────────────────────────────────

@app.route('/appearance', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def appearance_settings():
    if request.method == 'POST':
        # Save all posted theme fields
        for key in DEFAULT_THEME.keys():
            val = request.form.get(key, '').strip()
            if val:
                set_theme(key, val)
            else:
                # Remove empty custom settings to fall back to default
                setting = AppearanceSetting.query.filter_by(key=key).first()
                if setting:
                    db.session.delete(setting)
        db.session.commit()
        flash('Appearance settings updated. Refresh the page to see changes.', 'success')
        return redirect(url_for('appearance_settings'))

    theme = get_theme()
    sync_endpoint = SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', '')
    return render_template('dashboard/appearance.html', theme=theme,
                           default_theme=DEFAULT_THEME, sync_endpoint=sync_endpoint)


@app.route('/appearance/reset', methods=['POST'])
@login_required
@role_required('super_admin')
def appearance_reset():
    """Reset all appearance settings to defaults."""
    AppearanceSetting.query.delete()
    db.session.commit()
    flash('Appearance reset to defaults.', 'success')
    return redirect(url_for('appearance_settings'))


# ─── Theme Sync API (Flask ↔ WordPress) ────────────────────────────────

THEME_SYNC_KEYS = list(DEFAULT_THEME.keys())


@app.route('/api/theme/export', methods=['GET'])
def api_theme_export():
    """Return the active theme settings as JSON for the WordPress plugin to import.

    Protected by SYNC_API_KEY (shared with the WordPress install) — but also
    open if no key is configured (offline-only deployments).
    """
    api_key = request.headers.get('X-ESM-API-Key', '') or request.args.get('key', '')
    if app.config.get('SYNC_API_KEY') and api_key != app.config['SYNC_API_KEY']:
        return jsonify({'error': 'Invalid API key'}), 403
    theme = get_theme()
    return jsonify({
        'success': True,
        'theme': theme,
        'default_theme': DEFAULT_THEME,
        'version': '2.0.0',
        'updated_at': datetime.utcnow().isoformat(),
    })


@app.route('/api/theme/import', methods=['POST'])
def api_theme_import():
    """Accept a JSON payload of theme settings and persist them locally.

    Used both by WordPress (push theme to Flask) and by the Flask UI itself
    (the "Pull from WordPress" button).
    """
    api_key = request.headers.get('X-ESM-API-Key', '') or (request.json or {}).get('api_key', '')
    if app.config.get('SYNC_API_KEY') and api_key != app.config['SYNC_API_KEY']:
        return jsonify({'error': 'Invalid API key'}), 403
    payload = request.json or {}
    theme_in = payload.get('theme', {}) or {}
    applied = []
    skipped = []
    for key in THEME_SYNC_KEYS:
        if key in theme_in and theme_in[key] not in (None, ''):
            set_theme(key, str(theme_in[key]))
            applied.append(key)
        else:
            skipped.append(key)
    return jsonify({
        'success': True,
        'applied_keys': applied,
        'skipped_keys': skipped,
    })


@app.route('/appearance/sync', methods=['POST'])
@login_required
@role_required('super_admin')
def appearance_sync_to_wordpress():
    """Push current theme settings to the configured WordPress endpoint."""
    endpoint = (SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', '') or '').rstrip('/')
    api_key = SyncSetting.get('sync_api_key', '') or app.config.get('SYNC_API_KEY', '')
    if not endpoint:
        flash('No WordPress sync endpoint configured. Set it in Sync Center first.', 'warning')
        return redirect(url_for('appearance_settings'))
    try:
        # Build the theme payload (only keys whose values differ from defaults so we
        # don't accidentally wipe WordPress-side customisations).
        current = get_theme()
        payload = {'theme': current, 'api_key': api_key, 'source': 'flask'}
        resp = requests.post(
            f"{endpoint}/wp-json/excel-schools/v2/theme/import",
            json=payload,
            headers={'Content-Type': 'application/json', 'X-ESM-API-Key': api_key},
            timeout=15,
        )
        if resp.status_code < 300:
            applied = (resp.json() or {}).get('applied_keys', [])
            flash(f'Pushed {len(applied)} theme key(s) to WordPress successfully.', 'success')
        else:
            flash(f'WordPress rejected theme sync: HTTP {resp.status_code}.', 'danger')
    except requests.exceptions.ConnectionError:
        flash('Could not reach WordPress endpoint. Check Sync Center configuration.', 'danger')
    except Exception as e:
        flash(f'Theme sync failed: {e}', 'danger')
    return redirect(url_for('appearance_settings'))


@app.route('/appearance/pull', methods=['POST'])
@login_required
@role_required('super_admin')
def appearance_pull_from_wordpress():
    """Pull theme settings from the configured WordPress endpoint and apply them locally."""
    endpoint = (SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', '') or '').rstrip('/')
    api_key = SyncSetting.get('sync_api_key', '') or app.config.get('SYNC_API_KEY', '')
    if not endpoint:
        flash('No WordPress sync endpoint configured. Set it in Sync Center first.', 'warning')
        return redirect(url_for('appearance_settings'))
    try:
        resp = requests.get(
            f"{endpoint}/wp-json/excel-schools/v2/theme/export",
            headers={'X-ESM-API-Key': api_key},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json() or {}
            remote_theme = data.get('theme', {})
            applied = []
            for key in THEME_SYNC_KEYS:
                if key in remote_theme and remote_theme[key] not in (None, ''):
                    set_theme(key, str(remote_theme[key]))
                    applied.append(key)
            flash(f'Pulled {len(applied)} theme key(s) from WordPress successfully.', 'success')
        else:
            flash(f'WordPress returned HTTP {resp.status_code}.', 'danger')
    except requests.exceptions.ConnectionError:
        flash('Could not reach WordPress endpoint. Check Sync Center configuration.', 'danger')
    except Exception as e:
        flash(f'Theme pull failed: {e}', 'danger')
    return redirect(url_for('appearance_settings'))


# ─── Logo Upload ───────────────────────────────────────────────────────

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp'}


def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@app.route('/upload-logo', methods=['POST'])
@login_required
@role_required('super_admin')
def upload_logo():
    """Upload a school logo image file directly."""
    file = request.files.get('logo_file')
    if not file or file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('appearance_settings'))
    if not allowed_image_file(file.filename):
        flash('Invalid file type. Allowed: PNG, JPG, JPEG, GIF, SVG, WEBP.', 'danger')
        return redirect(url_for('appearance_settings'))
    filename = secure_filename(file.filename)
    # Prefix with timestamp to avoid collisions
    filename = f"logo_{int(datetime.now().timestamp())}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    # Store relative path as the logo_url setting
    logo_url = f"uploads/{filename}"
    set_theme('logo_url', logo_url)
    flash('Logo uploaded successfully.', 'success')
    return redirect(url_for('appearance_settings'))


# ─── Fee Level Management ──────────────────────────────────────────────

@app.route('/fee-levels')
@login_required
@role_required('super_admin', 'accountant')
def fee_levels_list():
    levels = FeeLevel.query.order_by(FeeLevel.id).all()
    return render_template('fees/levels.html', levels=levels)


@app.route('/fee-levels/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'accountant')
def fee_level_add():
    if request.method == 'POST':
        tuition = float(request.form.get('tuition', 0))
        dev_levy = float(request.form.get('development_levy', 0))
        reg_fee = float(request.form.get('registration_fee', 10))
        tb_levy = float(request.form.get('textbook_levy', 0))
        boarding = float(request.form.get('boarding', 0))
        stay_in_fee = float(request.form.get('stay_in_fee', 0) or 0)
        transport = float(request.form.get('transport', 0))
        lunch = float(request.form.get('lunch', 0))
        library = float(request.form.get('library', 0))
        technology = float(request.form.get('technology', 0))
        sports = float(request.form.get('sports', 0))
        other = float(request.form.get('other', 0))
        total = tuition + dev_levy + boarding + transport + lunch + library + technology + sports + other
        fl = FeeLevel(
            name=request.form.get('name'),
            code=request.form.get('code'),
            description=request.form.get('description'),
            tuition=tuition,
            development_levy=dev_levy,
            registration_fee=reg_fee,
            textbook_levy=tb_levy,
            boarding=boarding,
            stay_in_fee=stay_in_fee,
            transport=transport,
            lunch=lunch,
            library=library,
            technology=technology,
            sports=sports,
            other=other,
            total=total,
        )
        db.session.add(fl)
        db.session.commit()
        flash('Fee level created successfully.', 'success')
        return redirect(url_for('fee_levels_list'))
    return render_template('fees/level_add.html')


@app.route('/fee-levels/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'accountant')
def fee_level_edit(id):
    fl = FeeLevel.query.get_or_404(id)
    if request.method == 'POST':
        fl.name = request.form.get('name', fl.name)
        fl.code = request.form.get('code', fl.code)
        fl.description = request.form.get('description')
        fl.tuition = float(request.form.get('tuition', 0))
        fl.development_levy = float(request.form.get('development_levy', 0))
        fl.registration_fee = float(request.form.get('registration_fee', 10))
        fl.textbook_levy = float(request.form.get('textbook_levy', 0))
        fl.boarding = float(request.form.get('boarding', 0))
        fl.stay_in_fee = float(request.form.get('stay_in_fee', 0) or 0)
        fl.transport = float(request.form.get('transport', 0))
        fl.lunch = float(request.form.get('lunch', 0))
        fl.library = float(request.form.get('library', 0))
        fl.technology = float(request.form.get('technology', 0))
        fl.sports = float(request.form.get('sports', 0))
        fl.other = float(request.form.get('other', 0))
        fl.total = (fl.tuition + fl.development_levy + fl.boarding + fl.transport + fl.lunch +
                    fl.library + fl.technology + fl.sports + fl.other)
        db.session.commit()
        flash('Fee level updated.', 'success')
        return redirect(url_for('fee_levels_list'))
    return render_template('fees/level_edit.html', fee_level=fl)


@app.route('/fee-levels/<int:id>/delete', methods=['POST'])
@login_required
@role_required('super_admin')
def fee_level_delete(id):
    fl = FeeLevel.query.get_or_404(id)
    db.session.delete(fl)
    db.session.commit()
    flash('Fee level deleted.', 'success')
    return redirect(url_for('fee_levels_list'))


# ─── Auto-assign Primary Subjects ──────────────────────────────────────

# School-approved subjects for primary level (ECD A through Grade 7).
# Keep these exact names aligned with WordPress and teacher assignment rules.
PRIMARY_LEARNING_AREAS = [
    'English',
    'ChiShona',
    'Mathematics',
    'Social Science',
    'PE and Arts',
    'Science and Technology',
]
PRIMARY_SUBJECT_CODES = {
    'English': 'ENGP',
    'ChiShona': 'CHIS',
    'Mathematics': 'MATH',
    'Social Science': 'SOCS',
    'PE and Arts': 'PEA',
    'Science and Technology': 'SNT',
}
# Backwards-compatibility alias (kept for any existing template refs)
PRIMARY_SUBJECTS = PRIMARY_LEARNING_AREAS


def is_primary_level(level_name):
    """Return True if the level is Primary (ECD A to Grade 7)."""
    if not level_name:
        return False
    lvl = level_name.strip().lower()
    if lvl.startswith('ecd'):
        return True
    if lvl.startswith('grade') or lvl.startswith('gr'):
        # Extract grade number
        m = re.search(r'(\d+)', lvl)
        if m:
            grade_num = int(m.group(1))
            return 1 <= grade_num <= 7
    return False


def get_fee_level_name(level_name):
    """Map a class level string (e.g. 'Grade 3', 'Form 5') to a FeeLevel name (ECD, Junior, O Level, A Level)."""
    if not level_name:
        return None
    if is_primary_level(level_name):
        lvl = level_name.strip().lower()
        if lvl.startswith('ecd'):
            return 'ECD'
        return 'Junior'
    m = re.search(r'Form\s*(\d+)', level_name, re.IGNORECASE)
    if m:
        f = int(m.group(1))
        if 1 <= f <= 4:
            return 'O Level'
        if f >= 5:
            return 'A Level'
    return None


@app.route('/api/class-level-info/<int:class_id>')
@login_required
def api_class_level_info(class_id):
    """Return level info for a class, including whether it's primary."""
    cls = Class.query.get_or_404(class_id)
    level = cls.level or ''
    primary = is_primary_level(level)
    fee_level_name = get_fee_level_name(level)
    fee_level = FeeLevel.query.filter_by(name=fee_level_name).first() if fee_level_name else None
    return jsonify({
        'class_name': cls.name,
        'level': level,
        'is_primary': primary,
        'fee_level_id': fee_level.id if fee_level else None,
        'fee_level_name': fee_level.name if fee_level else None,
        'fee_level_total': fee_level.total if fee_level else 0,
    })


# ─── Student Photo Upload ─────────────────────────────────────────────

@app.route('/upload-student-photo/<int:id>', methods=['POST'])
@login_required
@role_required('super_admin', 'bursar')
def upload_student_photo(id):
    student = Student.query.get_or_404(id)
    if 'photo' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('student_edit', id=id))
    file = request.files['photo']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('student_edit', id=id))
    allowed_ext = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_ext:
        flash('Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP', 'danger')
        return redirect(url_for('student_edit', id=id))
    filename = secure_filename(f"student_{id}_{uuid.uuid4().hex[:8]}.{ext}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    student.photo = f"uploads/{filename}"
    db.session.commit()
    log_sync('Student', student.id, 'UPDATE', {'photo': student.photo})
    flash('Photo uploaded successfully.', 'success')
    return redirect(url_for('student_view', id=id))


# ─── PDF Report Generation ────────────────────────────────────────────

def _generate_receipt_pdf(payment):
    """Generate a PDF fee receipt."""
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    theme = get_theme()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A5, leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=14, textColor=HexColor(theme.get('primary_color', '#1F2080')))
    subtitle_style = ParagraphStyle('Sub2', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=HexColor('#6b7280'))
    label_style = ParagraphStyle('Label2', parent=styles['Normal'], fontSize=9, textColor=HexColor('#6b7280'))
    value_style = ParagraphStyle('Value2', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')

    story = []
    school_name = theme.get('school_name', 'Excel Group of Schools')
    story.append(Paragraph(school_name, title_style))
    story.append(Paragraph(theme.get('school_motto', ''), subtitle_style))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor(theme.get('primary_color', '#1F2080'))))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("OFFICIAL RECEIPT", ParagraphStyle('Center', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=HexColor(theme.get('primary_color', '#1F2080')))))
    story.append(Spacer(1, 4*mm))

    student = payment.student
    receipt_data = [
        [Paragraph('Receipt No:', label_style), Paragraph(payment.receipt_number, value_style)],
        [Paragraph('Date:', label_style), Paragraph(payment.payment_date.strftime('%d %B %Y') if payment.payment_date else '', value_style)],
        [Paragraph('Student:', label_style), Paragraph(f"{student.first_name} {student.last_name}", value_style)],
        [Paragraph('Adm No:', label_style), Paragraph(student.admission_number, value_style)],
        [Paragraph('Method:', label_style), Paragraph(payment.payment_method or 'Cash', value_style)],
    ]
    t = Table(receipt_data, colWidths=[35*mm, 55*mm])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    story.append(t)
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#d1d5db')))
    story.append(Spacer(1, 2*mm))

    # Amount section
    amount_data = [
        [Paragraph('Amount Paid:', ParagraphStyle('AmtLabel', parent=styles['Normal'], fontSize=12, fontName='Helvetica-Bold')),
         Paragraph(f"${payment.amount:,.2f}", ParagraphStyle('AmtValue', parent=styles['Normal'], fontSize=14, fontName='Helvetica-Bold', alignment=TA_RIGHT, textColor=HexColor(theme.get('primary_color', '#1F2080'))))],
    ]
    amt_table = Table(amount_data, colWidths=[50*mm, 40*mm])
    amt_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story.append(amt_table)
    story.append(Spacer(1, 4*mm))

    if payment.description:
        story.append(Paragraph(f"<i>{payment.description}</i>", ParagraphStyle('Desc', parent=styles['Normal'], fontSize=8, textColor=HexColor('#6b7280'))))

    # ─── Signature block (anonymized — no full name, no "auto-generated" label) ──
    recorder = _resolve_recorder(payment.received_by)
    signature_id = _generate_signature_id(payment)
    primary_color = HexColor(theme.get('primary_color', '#1F2080'))
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=primary_color))
    story.append(Spacer(1, 2*mm))

    if recorder:
        sig_role_style = ParagraphStyle('SigRole', parent=styles['Normal'],
                                        fontSize=9, alignment=TA_CENTER,
                                        textColor=HexColor('#374151'))
        sig_meta_style = ParagraphStyle('SigMeta', parent=styles['Normal'],
                                        fontSize=7, alignment=TA_CENTER,
                                        textColor=HexColor('#6b7280'))

        story.append(Paragraph(
            f"<b>{recorder['role_label']}</b> · {recorder['position']} · "
            f"<font face='Courier' color='#6b7280'>@{recorder['username']}</font>",
            sig_role_style,
        ))
        story.append(Spacer(1, 1*mm))
        ts_text = payment.created_at.strftime('%d %B %Y at %H:%M:%S UTC') if payment.created_at else '—'
        story.append(Paragraph(f"Recorded on: {ts_text}", sig_meta_style))
        story.append(Paragraph(f"Signature ID: {signature_id}", sig_meta_style))
    else:
        story.append(Paragraph(
            "<i>Recorder information unavailable (legacy payment).</i>",
            ParagraphStyle('SigNone', parent=styles['Normal'], fontSize=8,
                           alignment=TA_CENTER, textColor=HexColor('#9ca3af')),
        ))
        story.append(Paragraph(f"Signature ID: {signature_id}",
                               ParagraphStyle('SigID', parent=styles['Normal'],
                                              fontSize=7, alignment=TA_CENTER,
                                              textColor=HexColor('#9ca3af'))))

    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#d1d5db')))
    story.append(Paragraph("Thank you for your payment!", ParagraphStyle('Thanks', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=HexColor('#6b7280'))))
    story.append(Paragraph("Excel Group of Schools v2.0.0 — Valentine T Mabheka", ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER, textColor=HexColor('#9ca3af'))))

    doc.build(story)
    buf.seek(0)
    return buf


def _build_invoice_story(invoice, styles, theme):
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    title_style = ParagraphStyle('TitleInv', parent=styles['Title'], fontSize=16, textColor=HexColor(theme.get('primary_color', '#1F2080')))
    subtitle_style = ParagraphStyle('SubInv', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, textColor=HexColor('#6b7280'))
    label_style = ParagraphStyle('LabelInv', parent=styles['Normal'], fontSize=10, textColor=HexColor('#6b7280'))
    value_style = ParagraphStyle('ValueInv', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')
    header_style = ParagraphStyle('HeaderInv', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=HexColor('#ffffff'))
    item_desc_style = ParagraphStyle('ItemDescInv', parent=styles['Normal'], fontSize=10)
    item_amt_style = ParagraphStyle('ItemAmtInv', parent=styles['Normal'], fontSize=10, alignment=TA_RIGHT)

    story = []
    school_name = theme.get('school_name', 'Excel Group of Schools')
    story.append(Paragraph(school_name, title_style))
    story.append(Paragraph(theme.get('school_motto', ''), subtitle_style))
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=HexColor(theme.get('primary_color', '#1F2080'))))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("OFFICIAL STUDENT FEE INVOICE", ParagraphStyle('CenterInv', parent=styles['Normal'], fontSize=13, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=HexColor(theme.get('primary_color', '#1F2080')))))
    story.append(Spacer(1, 6*mm))

    student = invoice.student
    meta_data = [
        [Paragraph('Invoice No:', label_style), Paragraph(invoice.invoice_number, value_style),
         Paragraph('Issue Date:', label_style), Paragraph(invoice.issue_date.strftime('%d %B %Y') if invoice.issue_date else '', value_style)],
        [Paragraph('Student Name:', label_style), Paragraph(f"{student.first_name} {student.last_name}", value_style),
         Paragraph('Due Date:', label_style), Paragraph(invoice.due_date.strftime('%d %B %Y') if invoice.due_date else '', value_style)],
        [Paragraph('Admission No:', label_style), Paragraph(student.admission_number, value_style),
         Paragraph('Term / Year:', label_style), Paragraph(f"{invoice.term.name if invoice.term else ''} ({invoice.academic_year.name if invoice.academic_year else ''})", value_style)],
        [Paragraph('Class:', label_style), Paragraph(student.class_.name if student.class_ else 'Unassigned', value_style),
         Paragraph('Status:', label_style), Paragraph(invoice.status, value_style)]
    ]
    meta_table = Table(meta_data, colWidths=[30*mm, 55*mm, 28*mm, 55*mm])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4)
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 6*mm))

    items_header = [Paragraph('<b>Description</b>', header_style), Paragraph('<b>Amount ($)</b>', ParagraphStyle('RHead', parent=header_style, alignment=TA_RIGHT))]
    items_rows = [items_header]
    for item in invoice.items:
        items_rows.append([
            Paragraph(item.description, item_desc_style),
            Paragraph(f"${item.amount:,.2f}", item_amt_style)
        ])
    if len(items_rows) == 1:
        items_rows.append([Paragraph('General Term Fees', item_desc_style), Paragraph(f"${invoice.subtotal:,.2f}", item_amt_style)])

    items_table = Table(items_rows, colWidths=[120*mm, 48*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor(theme.get('primary_color', '#1F2080'))),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4*mm))

    total_paid = db.session.query(db.func.sum(FeePayment.amount)).filter(
        FeePayment.student_id == invoice.student_id,
        FeePayment.term_id == invoice.term_id,
        FeePayment.academic_year_id == invoice.academic_year_id
    ).scalar() or 0.0
    balance = max(0.0, invoice.total_amount - total_paid)

    summary_data = [
        [Paragraph('Subtotal:', label_style), Paragraph(f"${invoice.subtotal:,.2f}", value_style)],
    ]
    if invoice.discount_amount > 0:
        summary_data.append([Paragraph(f'Scholarship Discount ({student.fee_classification}):', label_style), Paragraph(f"-${invoice.discount_amount:,.2f}", ParagraphStyle('DiscVal', parent=value_style, textColor=HexColor('#dc2626')))])
    summary_data.extend([
        [Paragraph('<b>Net Invoice Total:</b>', ParagraphStyle('BLabel', parent=label_style, fontName='Helvetica-Bold', fontSize=11)),
         Paragraph(f"<b>${invoice.total_amount:,.2f}</b>", ParagraphStyle('BVal', parent=value_style, fontSize=12, alignment=TA_RIGHT, textColor=HexColor(theme.get('primary_color', '#1F2080'))))],
        [Paragraph('Amount Paid to Date:', label_style), Paragraph(f"${total_paid:,.2f}", value_style)],
        [Paragraph('<b>Current Balance Due:</b>', ParagraphStyle('BalLabel', parent=label_style, fontName='Helvetica-Bold', fontSize=11)),
         Paragraph(f"<b>${balance:,.2f}</b>", ParagraphStyle('BalVal', parent=value_style, fontSize=12, alignment=TA_RIGHT, textColor=HexColor('#b91c1c' if balance > 0 else '#15803d')))]
    ])
    summary_table = Table(summary_data, colWidths=[120*mm, 48*mm])
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEABOVE', (0, -3), (-1, -3), 1, HexColor(theme.get('primary_color', '#1F2080'))),
        ('LINEABOVE', (0, -1), (-1, -1), 1, HexColor('#d1d5db')),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10*mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#d1d5db')))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Please ensure payments are completed on or before the due date. Thank you!", ParagraphStyle('ThanksInv', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=HexColor('#6b7280'))))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("Excel Group of Schools v2.0.0 — Valentine T Mabheka", ParagraphStyle('FooterInv', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=HexColor('#9ca3af'))))
    return story


def _generate_invoice_pdf(invoice):
    """Generate a PDF student fee invoice."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.styles import getSampleStyleSheet

    theme = get_theme()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story = _build_invoice_story(invoice, styles, theme)
    doc.build(story)
    buf.seek(0)
    return buf


def _generate_combined_invoices_pdf(invoices):
    """Generate a combined multi-page PDF containing all specified invoices."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet

    theme = get_theme()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    story = []
    for idx, inv in enumerate(invoices):
        story.extend(_build_invoice_story(inv, styles, theme))
        if idx < len(invoices) - 1:
            story.append(PageBreak())
    doc.build(story)
    buf.seek(0)
    return buf


def _generate_report_card_pdf(student, exam, results):
    """Generate a PDF report card for a student."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    theme = get_theme()
    primary = HexColor(theme.get('primary_color', '#1F2080'))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title3', parent=styles['Title'], fontSize=16, textColor=primary)
    subtitle_style = ParagraphStyle('Sub3', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=HexColor('#6b7280'))
    header_style = ParagraphStyle('Header3', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=primary)

    story = []
    story.append(Paragraph(theme.get('school_name', 'Excel Group of Schools'), title_style))
    story.append(Paragraph(theme.get('school_motto', ''), subtitle_style))
    story.append(Spacer(1, 3*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=primary))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("STUDENT REPORT CARD", ParagraphStyle('Center2', parent=styles['Normal'], fontSize=13, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=primary)))
    story.append(Spacer(1, 5*mm))

    # Student info
    class_name = student.class_.name if student.class_ else 'N/A'
    level_name = student.class_.level if student.class_ else ''
    fl_name = get_fee_level_name(level_name) if level_name else ''
    info_data = [
        [Paragraph('Student:', header_style), Paragraph(f"{student.first_name} {student.last_name}", styles['Normal']),
         Paragraph('Adm No:', header_style), Paragraph(student.admission_number, styles['Normal'])],
        [Paragraph('Class:', header_style), Paragraph(class_name, styles['Normal']),
         Paragraph('Level:', header_style), Paragraph(fl_name or 'N/A', styles['Normal'])],
        [Paragraph('Exam:', header_style), Paragraph(exam.name if exam else 'N/A', styles['Normal']),
         Paragraph('Type:', header_style), Paragraph(exam.exam_type if exam else 'N/A', styles['Normal'])],
        [Paragraph('Gender:', header_style), Paragraph(student.gender or 'N/A', styles['Normal']),
         Paragraph('DOB:', header_style), Paragraph(student.date_of_birth.strftime('%d/%m/%Y') if student.date_of_birth else 'N/A', styles['Normal'])],
    ]
    info_table = Table(info_data, colWidths=[25*mm, 45*mm, 25*mm, 45*mm])
    info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
    story.append(info_table)
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#d1d5db')))
    story.append(Spacer(1, 3*mm))

    # Results table
    results_header = [
        Paragraph('<b>Subject</b>', header_style),
        Paragraph('<b>Marks</b>', header_style),
        Paragraph('<b>Total</b>', header_style),
        Paragraph('<b>%</b>', header_style),
        Paragraph('<b>Grade</b>', header_style),
        Paragraph('<b>Remarks</b>', header_style),
    ]
    results_data = [results_header]
    total_marks = 0
    total_possible = 0
    for r in results:
        pct = (r.marks_obtained / r.marks_total * 100) if r.marks_total > 0 else 0
        total_marks += r.marks_obtained
        total_possible += r.marks_total
        subject_name = Subject.query.get(r.subject_id).name if r.subject_id else 'Unknown'
        results_data.append([
            Paragraph(subject_name, styles['Normal']),
            Paragraph(str(r.marks_obtained), styles['Normal']),
            Paragraph(str(r.marks_total), styles['Normal']),
            Paragraph(f"{pct:.1f}%", styles['Normal']),
            Paragraph(r.grade or '-', ParagraphStyle('Grade', parent=styles['Normal'], fontName='Helvetica-Bold', textColor=HexColor('#1F2080') if r.grade in ('A', 'B') else HexColor('#ef4444') if r.grade in ('U', 'E') else HexColor('#1a1a2e'))),
            Paragraph(r.remarks or '', styles['Normal']),
        ])
    # Totals row
    overall_pct = (total_marks / total_possible * 100) if total_possible > 0 else 0
    overall_grade = compute_grade(total_marks, total_possible)
    results_data.append([
        Paragraph('<b>TOTAL</b>', ParagraphStyle('Total', parent=styles['Normal'], fontName='Helvetica-Bold')),
        Paragraph(f'<b>{total_marks}</b>', ParagraphStyle('Total2', parent=styles['Normal'], fontName='Helvetica-Bold')),
        Paragraph(f'<b>{total_possible}</b>', ParagraphStyle('Total3', parent=styles['Normal'], fontName='Helvetica-Bold')),
        Paragraph(f'<b>{overall_pct:.1f}%</b>', ParagraphStyle('Total4', parent=styles['Normal'], fontName='Helvetica-Bold', textColor=primary)),
        Paragraph(f'<b>{overall_grade}</b>', ParagraphStyle('Total5', parent=styles['Normal'], fontName='Helvetica-Bold', textColor=primary)),
        Paragraph('', styles['Normal']),
    ])

    results_table = Table(results_data, colWidths=[40*mm, 18*mm, 18*mm, 18*mm, 18*mm, 38*mm])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f0f2f5')),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, -1), (-1, -1), HexColor('#f0f2f5')),
    ]))
    story.append(results_table)
    story.append(Spacer(1, 8*mm))

    # Grading scale
    story.append(Paragraph("Grading Scale:", header_style))
    grade_data = [
        [Paragraph('A: 80-100%', styles['Normal']), Paragraph('B: 70-79%', styles['Normal']),
         Paragraph('C: 60-69%', styles['Normal']), Paragraph('D: 50-59%', styles['Normal']),
         Paragraph('E: 40-49%', styles['Normal']), Paragraph('U: 0-39%', styles['Normal'])],
    ]
    grade_table = Table(grade_data, colWidths=[28*mm] * 6)
    grade_table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, HexColor('#e5e7eb')),
                                      ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f9fafb')),
                                      ('FONTSIZE', (0, 0), (-1, -1), 8)]))
    story.append(grade_table)
    story.append(Spacer(1, 10*mm))

    # Signatures
    sig_data = [
        [Paragraph('Class Teacher', ParagraphStyle('Sig', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
         Paragraph('', styles['Normal']),
         Paragraph('Headmaster', ParagraphStyle('Sig2', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))],
        [Paragraph('____________________', ParagraphStyle('SigLine', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)),
         Paragraph('', styles['Normal']),
         Paragraph('____________________', ParagraphStyle('SigLine2', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER))],
    ]
    sig_table = Table(sig_data, colWidths=[55*mm, 30*mm, 55*mm])
    sig_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('TOPPADDING', (0, 0), (-1, -1), 15)]))
    story.append(sig_table)
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#d1d5db')))
    story.append(Paragraph("Excel Group of Schools v2.0.0 — Valentine T Mabheka", ParagraphStyle('Footer2', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER, textColor=HexColor('#9ca3af'))))

    doc.build(story)
    buf.seek(0)
    return buf


@app.route('/fees/receipt/<int:id>/pdf')
@login_required
def fee_receipt_pdf(id):
    """Download a PDF receipt for a fee payment."""
    payment = FeePayment.query.get_or_404(id)
    buf = _generate_receipt_pdf(payment)
    return send_file(buf, as_attachment=True, download_name=f"receipt_{payment.receipt_number}.pdf", mimetype='application/pdf')


@app.route('/exams/<int:exam_id>/student/<int:student_id>/report-card/pdf')
@login_required
def report_card_pdf(exam_id, student_id):
    """Download a PDF report card for a student's exam results."""
    exam = Exam.query.get_or_404(exam_id)
    student = Student.query.get_or_404(student_id)
    if session.get('user_role') == 'teacher':
        staff = _staff_for_current_user()
        if not staff or not teacher_can_access_student(staff.id, student_id):
            flash('You do not have access to that learner.', 'danger')
            return redirect(url_for('teacher_home'))
    results_query = ExamResult.query.filter_by(student_id=student_id, exam_id=exam_id)
    if session.get('user_role') == 'teacher':
        subject_ids = get_teacher_subject_ids(staff.id, class_id=student.class_id)
        results_query = results_query.filter(ExamResult.subject_id.in_(subject_ids))
    results = results_query.all()
    if not results:
        flash('No results found for this student in this exam.', 'warning')
        return redirect(url_for('report_card', exam_id=exam_id, student_id=student_id))
    buf = _generate_report_card_pdf(student, exam, results)
    return send_file(buf, as_attachment=True, download_name=f"report_card_{student.admission_number}_{exam.name}.pdf", mimetype='application/pdf')


# ─── WhatsApp/SMS Notifications ───────────────────────────────────────

def send_whatsapp_message(phone, message):
    """Send a WhatsApp message via the Business API. Returns True on success."""
    api_url = os.environ.get('WHATSAPP_API_URL', '')
    api_token = os.environ.get('WHATSAPP_API_TOKEN', '')
    phone_id = os.environ.get('WHATSAPP_PHONE_ID', '')

    if not api_url or not api_token:
        # Log for manual processing
        log_sync('WhatsApp', 0, 'SEND', {'phone': phone, 'message': message[:200]})
        return False

    try:
        url = f"{api_url.rstrip('/')}/{phone_id}/messages"
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone,
            'type': 'text',
            'text': {'body': message[:640]},
        }
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        return resp.status_code < 300
    except Exception:
        return False


def send_whatsapp_to_parents(student_ids, message):
    """Send WhatsApp message to parents of given students."""
    sent = 0
    for sid in student_ids:
        student = Student.query.get(sid)
        if student and student.parents:
            for parent in student.parents:
                if parent.phone:
                    phone = re.sub(r'[^0-9+]', '', parent.phone)
                    if len(phone) >= 10:
                        if send_whatsapp_message(phone, message):
                            sent += 1
    return sent


# ─── Email/SMTP Notifications ─────────────────────────────────────────

def send_email_notification(to_emails, subject, body, html_body=None):
    """Send email notifications via SMTP. Returns count of successfully sent emails.
    
    Environment variables:
      SMTP_HOST: SMTP server hostname (e.g. smtp.gmail.com)
      SMTP_PORT: SMTP server port (default 587)
      SMTP_USER: SMTP username
      SMTP_PASS: SMTP password
      SMTP_FROM: From email address (default: SMTP_USER)
      SMTP_USE_TLS: Use TLS (default True)
    """
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    smtp_from = os.environ.get('SMTP_FROM', smtp_user)
    smtp_tls = os.environ.get('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')

    if not smtp_host or not smtp_user or not smtp_pass:
        # SMTP not configured — log for manual processing
        log_sync('Email', 0, 'SEND', {
            'to': to_emails[:5],  # Limit snapshot
            'subject': subject[:200],
            'smtp_configured': False,
        })
        return 0

    sent = 0
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        for email_addr in to_emails:
            if not email_addr or '@' not in email_addr:
                continue
            try:
                msg = MIMEMultipart('alternative')
                msg['From'] = smtp_from
                msg['To'] = email_addr
                msg['Subject'] = f"[Excel Schools] {subject}"
                
                # Plain text version
                msg.attach(MIMEText(body, 'plain'))
                # HTML version if provided
                if html_body:
                    msg.attach(MIMEText(html_body, 'html'))

                if smtp_tls:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [email_addr], msg.as_string())
                server.quit()
                sent += 1
            except Exception as e:
                log_sync('Email', 0, 'SEND_FAIL', {'to': email_addr, 'error': str(e)[:200]})
                continue
    except ImportError:
        pass
    return sent


@app.route('/communication/email', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'bursar', 'teacher')
def email_send():
    """Send email notifications to parents, staff, or custom recipients."""
    if request.method == 'POST':
        target = request.form.get('target', 'all_parents')
        subject = request.form.get('subject', '')
        message = request.form.get('message', '')
        custom_emails = request.form.get('custom_emails', '')

        if not subject or not message:
            flash('Subject and message are required.', 'danger')
            return redirect(url_for('email_send'))

        emails = []
        if target == 'all_parents':
            parents = Parent.query.filter(Parent.email != '', Parent.email.isnot(None)).all()
            emails = [p.email for p in parents if p.email]
        elif target == 'all_staff':
            staff = Staff.query.filter_by(status='Active').filter(Staff.email != '', Staff.email.isnot(None)).all()
            emails = [s.email for s in staff if s.email]
        elif target == 'custom' and custom_emails:
            emails = [e.strip() for e in custom_emails.split(',') if '@' in e.strip()]
        elif target.startswith('class_'):
            class_id = int(target.replace('class_', ''))
            students = Student.query.filter_by(class_id=class_id, status='Active').all()
            for s in students:
                for p in s.parents:
                    if p.email:
                        emails.append(p.email)

        # Deduplicate
        emails = list(set(emails))
        sent = send_email_notification(
            to_emails=emails,
            subject=subject,
            body=message,
            html_body=f"<div style='font-family:Segoe UI,sans-serif;max-width:600px;margin:0 auto;'>"
                      f"<div style='background:#1F2080;color:#fff;padding:20px;text-align:center;border-radius:12px 12px 0 0'>"
                      f"<h2 style='margin:0'>Excel Group of Schools</h2>"
                      f"<p style='margin:4px 0 0;opacity:.8'>Excellence in Education</p></div>"
                      f"<div style='padding:20px;background:#fff;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px'>"
                      f"<h3>{subject}</h3><p style='line-height:1.6'>{message}</p></div>"
                      f"<p style='text-align:center;font-size:11px;color:#9ca3af;margin-top:12px'>"
                      f"Excel Group of Schools v2.0.0 — Valentine T Mabheka</p></div>"
        )

        flash(f'Email: {sent} of {len(emails)} recipient(s) reached.', 'success' if sent > 0 else 'warning')
        return redirect(url_for('email_send'))

    classes = Class.query.order_by(Class.name).all()
    smtp_configured = bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_USER') and os.environ.get('SMTP_PASS'))
    return render_template('communication/email.html', classes=classes, smtp_configured=smtp_configured)


@app.route('/communication/whatsapp', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'bursar', 'teacher')
def whatsapp_send():
    """Send WhatsApp/SMS notifications."""
    if request.method == 'POST':
        target = request.form.get('target', 'all_parents')
        message = request.form.get('message', '')
        custom_numbers = request.form.get('custom_numbers', '')

        if not message:
            flash('Please enter a message.', 'danger')
            return redirect(url_for('whatsapp_send'))

        sent = 0
        if target == 'all_parents':
            parents = Parent.query.filter(Parent.phone != '', Parent.phone.isnot(None)).all()
            for p in parents:
                phone = re.sub(r'[^0-9+]', '', p.phone)
                if len(phone) >= 10:
                    if send_whatsapp_message(phone, message):
                        sent += 1
        elif target == 'all_staff':
            staff = Staff.query.filter_by(status='Active').filter(Staff.phone != '', Staff.phone.isnot(None)).all()
            for s in staff:
                phone = re.sub(r'[^0-9+]', '', s.phone)
                if len(phone) >= 10:
                    if send_whatsapp_message(phone, message):
                        sent += 1
        elif target == 'custom' and custom_numbers:
            numbers = [n.strip() for n in custom_numbers.split(',') if n.strip()]
            for phone in numbers:
                phone = re.sub(r'[^0-9+]', '', phone)
                if len(phone) >= 10:
                    if send_whatsapp_message(phone, message):
                        sent += 1
        elif target.startswith('class_'):
            class_id = int(target.replace('class_', ''))
            students = Student.query.filter_by(class_id=class_id, status='Active').all()
            sent = send_whatsapp_to_parents([s.id for s in students], message)

        flash(f'WhatsApp/SMS: {sent} message(s) sent.', 'success')
        return redirect(url_for('whatsapp_send'))

    classes = Class.query.order_by(Class.name).all()
    whatsapp_configured = bool(os.environ.get('WHATSAPP_API_URL') and os.environ.get('WHATSAPP_API_TOKEN'))
    return render_template('communication/whatsapp.html', classes=classes, whatsapp_configured=whatsapp_configured)


# ─── Parent Portal ────────────────────────────────────────────────────

@app.route('/parent-portal')
@login_required
def parent_portal():
    """Limited-access portal for parents to view their child's info."""
    user = User.query.get(session['user_id'])
    if session.get('user_role') not in ('parent', 'super_admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    # Find parent by user_id
    parent = Parent.query.filter_by(user_id=user.id).first()
    if not parent:
        # If super_admin, try to find any parent for demo
        if session.get('user_role') == 'super_admin':
            parent = Parent.query.first()
        if not parent:
            flash('Parent profile not found. Please link a parent account.', 'danger')
            return redirect(url_for('dashboard'))

    children = parent.students
    children_data = []
    for child in children:
        child_info = {
            'student': child,
            'attendances': [],
            'results': ExamResult.query.filter_by(student_id=child.id).all(),
            'payments': FeePayment.query.filter_by(student_id=child.id).order_by(FeePayment.payment_date.desc()).all(),
            'balance': _get_student_fee_balance(child.id),
        }
        children_data.append(child_info)

    notices = Notice.query.filter_by(is_active=True).filter(
        db.or_(Notice.target_audience == 'All', Notice.target_audience == 'Parents')
    ).order_by(Notice.date_posted.desc()).limit(10).all()

    return render_template('dashboard/parent_portal.html',
                           parent=parent,
                           children_data=children_data,
                           notices=notices)


# ─── Student Portal ────────────────────────────────────────────────────

@app.route('/student-portal')
@login_required
def student_portal():
    """Limited-access portal for students to view their own info.
    
    Students access the system through a parent's linked account or
    a dedicated student user account. If a student has no user account,
    they access via the parent portal instead.
    """
    user = User.query.get(session['user_id'])
    if session.get('user_role') not in ('student', 'parent', 'super_admin'):
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    # Find student by user_id (for dedicated student accounts)
    student = Student.query.filter_by(user_id=user.id).first()
    
    # If parent, let them select a child to view as student portal
    if not student and session.get('user_role') == 'parent':
        parent = Parent.query.filter_by(user_id=user.id).first()
        if parent and parent.students:
            student = parent.students[0]  # Show first child's data
    
    # If super_admin, show first student for demo
    if not student and session.get('user_role') == 'super_admin':
        student = Student.query.filter_by(status='Active').first()
    
    if not student:
        flash('Student profile not found. Students access the system through their parent\'s account.', 'info')
        return redirect(url_for('dashboard'))

    attendances = []
    results = ExamResult.query.filter_by(student_id=student.id).all()
    payments = FeePayment.query.filter_by(student_id=student.id).order_by(FeePayment.payment_date.desc()).all()
    balance = _get_student_fee_balance(student.id)
    notices = Notice.query.filter_by(is_active=True).filter(
        db.or_(Notice.target_audience == 'All', Notice.target_audience == 'Students')
    ).order_by(Notice.date_posted.desc()).limit(10).all()

    # Timetable
    timetable_slots = []
    if student.class_id:
        timetable_slots = TimetableSlot.query.filter_by(class_id=student.class_id).order_by(
            TimetableSlot.day_of_week, TimetableSlot.period).all()

    return render_template('dashboard/student_portal.html',
                           student=student,
                           attendances=attendances,
                           results=results,
                           payments=payments,
                           balance=balance,
                           notices=notices,
                           timetable_slots=timetable_slots)


# ─── User Management ──────────────────────────────────────────────────

@app.route('/users')
@login_required
@role_required('super_admin')
def user_management():
    """Manage system users — staff only. Roles are allocated to staff members."""
    # Get only users linked to staff
    staff_users = db.session.query(User, Staff).join(Staff, User.id == Staff.user_id).order_by(User.role, User.username).all()
    # Also include users without a linked staff profile (like the initial admin)
    unlinked_users = User.query.filter(~User.id.in_([s.user_id for s in Staff.query.filter(Staff.user_id != None).all()])).order_by(User.role).all()
    return render_template('users/list.html', staff_users=staff_users, unlinked_users=unlinked_users,
                           role_labels=ROLE_LABELS, role_descriptions=ROLE_DESCRIPTIONS)


@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def user_add():
    """Add a new system user linked to a staff member."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        staff_id = request.form.get('staff_id', type=int)

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
        else:
            user = User(username=username, role=role, is_active=True)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            # Link to staff member
            if staff_id:
                staff = Staff.query.get(staff_id)
                if staff:
                    staff.user_id = user.id

            db.session.commit()
            flash(f'User "{username}" created with role {ROLE_LABELS.get(role, role)}.', 'success')
            return redirect(url_for('user_management'))

    # Only show staff without linked users
    staff_list = Staff.query.filter(Staff.user_id == None).order_by(Staff.last_name).all()
    return render_template('users/add.html', role_labels=ROLE_LABELS,
                           role_descriptions=ROLE_DESCRIPTIONS, staff_list=staff_list)


@app.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def user_edit(id):
    """Edit a system user's role and status."""
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        user.role = request.form.get('role', user.role)
        user.is_active = 'is_active' in request.form
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        db.session.commit()
        flash(f'User "{user.username}" updated.', 'success')
        return redirect(url_for('user_management'))

    return render_template('users/edit.html', user=user, role_labels=ROLE_LABELS,
                           role_descriptions=ROLE_DESCRIPTIONS)


@app.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@role_required('super_admin')
def user_delete(id):
    """Delete a system user."""
    user = User.query.get_or_404(id)
    if user.id == session['user_id']:
        flash('Cannot delete your own account.', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'User "{user.username}" deleted.', 'success')
    return redirect(url_for('user_management'))


def _get_student_fee_balance(student_id):
    """Calculate fee balance for a student."""
    student = Student.query.get(student_id)
    if not student:
        return {'total_due': 0, 'paid': 0, 'balance': 0}

    level = student.class_.level if student.class_ else ''
    fee_level_name = get_fee_level_name(level)
    fee_level = FeeLevel.query.filter_by(name=fee_level_name).first() if fee_level_name else None
    total_due = fee_level.total if fee_level else 0
    multiplier = student.effective_fee_multiplier
    net_due = total_due * multiplier
    scholarship_amount = total_due * (1 - multiplier)
    paid = db.session.query(db.func.sum(FeePayment.amount)).filter_by(student_id=student_id).scalar() or 0

    return {
        'total_due': total_due,
        'scholarship_amount': scholarship_amount,
        'net_due': net_due,
        'paid': paid,
        'balance': net_due - paid,
        'classification': student.scholarship_label,
    }


@app.route('/api/dashboard/charts')
@login_required
def api_dashboard_charts():
    """API endpoint providing chart data for the dashboard."""
    # Gender distribution
    male = Student.query.filter_by(gender='Male', status='Active').count()
    female = Student.query.filter_by(gender='Female', status='Active').count()

    # Students by level
    levels = {'ECD': 0, 'Junior': 0, 'O Level': 0, 'A Level': 0, 'Unassigned': 0}
    students = Student.query.filter_by(status='Active').all()
    for s in students:
        level = s.class_.level if s.class_ else ''
        fl_name = get_fee_level_name(level) if level else None
        key = fl_name if fl_name and fl_name in levels else 'Unassigned'
        levels[key] = levels.get(key, 0) + 1

    # Fee collection by month (last 6 months)
    monthly_fees = []
    for i in range(5, -1, -1):
        month_date = date.today().replace(day=1) - timedelta(days=i*30)
        month_str = month_date.strftime('%Y-%m')
        collected = db.session.query(db.func.sum(FeePayment.amount)).filter(
            db.func.strftime('%Y-%m', FeePayment.payment_date) == month_str
        ).scalar() or 0
        monthly_fees.append({'month': month_date.strftime('%b %Y'), 'amount': float(collected)})

    # Scholarship breakdown
    scholarship_data = {}
    for s in Student.query.filter_by(status='Active').all():
        fc = s.fee_classification or 'Regular'
        scholarship_data[fc] = scholarship_data.get(fc, 0) + 1

    return jsonify({
        'gender': {'male': male, 'female': female},
        'levels': levels,
        'monthly_fees': monthly_fees,
        'scholarships': scholarship_data,
    })


# ─── API Endpoints (for online sync) ──────────────────────────────────

@app.route('/api/sync', methods=['POST'])
def api_sync():
    """API endpoint to receive sync data from WordPress/online systems.
    Supports CREATE, UPDATE, DELETE actions with upsert by sync_id.
    Implements timestamp-based conflict resolution for concurrent edits."""
    api_key = request.json.get('api_key') or request.headers.get('X-ESM-API-Key', '')
    if api_key != app.config['SYNC_API_KEY']:
        return jsonify({'error': 'Invalid API key'}), 403

    entity_type = request.json.get('entity_type')
    action = request.json.get('action')
    data = request.json.get('data') or {}
    sync_id_val = request.json.get('sync_id', '')
    entity_id = request.json.get('entity_id', 0)
    incoming_timestamp = request.json.get('timestamp')  # ISO timestamp from source
    conflict_strategy = request.json.get('conflict_strategy', 'newest_wins')

    entity_models = {
        'Student': Student, 'Staff': Staff, 'FeePayment': FeePayment,
        'ExamResult': ExamResult,
        'Notice': Notice, 'FeeStructure': FeeStructure, 'FeeLevel': FeeLevel,
        'Class': Class, 'Subject': Subject, 'StaffSubject': StaffSubject,
        'AcademicYear': AcademicYear, 'Term': Term,
    }

    result = {'status': 'ok', 'sync_id': sync_id_val}

    if action in ('CREATE', 'UPDATE') and entity_type in entity_models:
        model = entity_models[entity_type]
        existing = None
        if sync_id_val and hasattr(model, 'sync_id'):
            existing = model.query.filter_by(sync_id=sync_id_val).first()

        if existing:
            # Conflict resolution: compare timestamps
            should_update = True
            if conflict_strategy == 'newest_wins' and incoming_timestamp:
                try:
                    incoming_dt = datetime.fromisoformat(incoming_timestamp.replace('Z', '+00:00')).replace(tzinfo=None)
                    existing_dt = existing.updated_at if hasattr(existing, 'updated_at') and existing.updated_at else existing.created_at if hasattr(existing, 'created_at') else datetime.min
                    if incoming_dt <= existing_dt:
                        should_update = False
                        result['action_taken'] = 'SKIP_OLDER'
                        result['reason'] = f'Incoming timestamp ({incoming_dt}) is not newer than existing ({existing_dt})'
                except (ValueError, AttributeError):
                    pass  # If timestamp parsing fails, proceed with update
            elif conflict_strategy == 'flask_wins':
                should_update = False
                result['action_taken'] = 'SKIP_FLASK_WINS'
            # 'wp_wins' falls through to update

            if should_update:
                for key, value in data.items():
                    if hasattr(existing, key) and key not in ('id', 'created_at'):
                        try: setattr(existing, key, value)
                        except: pass
                if hasattr(existing, 'updated_at'):
                    existing.updated_at = datetime.utcnow()
                result['action_taken'] = 'UPDATE'
                result['entity_id'] = existing.id
        else:
            try:
                new_record = model()
                for key, value in data.items():
                    if hasattr(new_record, key) and key != 'id':
                        try: setattr(new_record, key, value)
                        except: pass
                if hasattr(new_record, 'sync_id') and not new_record.sync_id and sync_id_val:
                    new_record.sync_id = sync_id_val
                db.session.add(new_record)
                db.session.flush()
                result['action_taken'] = 'CREATE'
                result['entity_id'] = new_record.id
            except Exception as e:
                db.session.rollback()
                result['error'] = str(e)

    elif action == 'DELETE' and entity_type in entity_models:
        model = entity_models[entity_type]
        if entity_id:
            record = model.query.get(entity_id)
            if record:
                if entity_type in ('Student', 'Staff') and hasattr(record, 'status'):
                    record.status = 'Inactive'
                else:
                    db.session.delete(record)
                result['action_taken'] = 'DELETE'

    log = SyncLog(
        entity_type=entity_type, entity_id=entity_id, action=action,
        sync_status='synced', sync_timestamp=datetime.utcnow(),
        data_snapshot=json.dumps(data) if data else None,
    )
    db.session.add(log)
    db.session.commit()
    return jsonify(result)


@app.route('/api/sync/pending', methods=['GET'])
def api_sync_pending():
    """Return all pending sync changes for WordPress to pull."""
    api_key = request.headers.get('X-ESM-API-Key', '')
    if api_key != app.config['SYNC_API_KEY']:
        return jsonify({'error': 'Invalid API key'}), 403
    logs = SyncLog.query.filter_by(sync_status='pending').order_by(SyncLog.created_at.asc()).limit(500).all()
    items = []
    for log in logs:
        items.append({
            'id': log.id, 'entity_type': log.entity_type,
            'entity_id': log.entity_id, 'action': log.action,
            'data': json.loads(log.data_snapshot) if log.data_snapshot else None,
            'created_at': log.created_at.isoformat() if log.created_at else None,
        })
    return jsonify({'pending': items, 'count': len(items)})


@app.route('/api/sync/mark-synced', methods=['POST'])
def api_sync_mark_synced():
    """Mark sync log entries as synced (called by WordPress after pulling)."""
    api_key = request.headers.get('X-ESM-API-Key', '') or request.json.get('api_key', '')
    if api_key != app.config['SYNC_API_KEY']:
        return jsonify({'error': 'Invalid API key'}), 403
    ids = request.json.get('ids', [])
    if ids:
        SyncLog.query.filter(SyncLog.id.in_(ids)).update(
            {'sync_status': 'synced', 'sync_timestamp': datetime.utcnow()}, synchronize_session=False
        )
        db.session.commit()
    return jsonify({'marked': len(ids)})


@app.route('/api/sync/webhook', methods=['POST'])
def api_sync_webhook():
    """Webhook endpoint for real-time push from WordPress."""
    api_key = request.headers.get('X-ESM-API-Key', '') or request.json.get('api_key', '')
    if api_key != app.config['SYNC_API_KEY']:
        return jsonify({'error': 'Invalid API key'}), 403
    data = request.json
    entity_type = data.get('entity_type', '')
    action = data.get('event', data.get('action', ''))
    entity_data = data.get('data', {})
    sync_id_val = entity_data.get('sync_id', '')
    entity_models = {
        'Student': Student, 'Staff': Staff, 'FeePayment': FeePayment,
        'FeeLevel': FeeLevel, 'Class': Class, 'Subject': Subject, 'StaffSubject': StaffSubject,
    }
    if entity_type in entity_models and action in ('CREATE', 'UPDATE'):
        model = entity_models[entity_type]
        existing = model.query.filter_by(sync_id=sync_id_val).first() if sync_id_val else None
        if existing:
            for k, v in entity_data.items():
                if hasattr(existing, k) and k not in ('id', 'created_at'):
                    try: setattr(existing, k, v)
                    except: pass
        else:
            new = model()
            for k, v in entity_data.items():
                if hasattr(new, k) and k != 'id':
                    try: setattr(new, k, v)
                    except: pass
            db.session.add(new)
    elif action == 'DELETE' and entity_type in entity_models:
        eid = data.get('entity_id', 0)
        record = entity_models[entity_type].query.get(eid)
        if record:
            if hasattr(record, 'status'): record.status = 'Inactive'
            else: db.session.delete(record)
    db.session.commit()
    return jsonify({'status': 'ok', 'webhook_processed': True})


@app.route('/api/export/<entity>', methods=['GET'])
def api_export_entity(entity):
    """Export all data for a given entity type (for full sync/import)."""
    api_key = request.headers.get('X-ESM-API-Key', '')
    if api_key != app.config['SYNC_API_KEY']:
        return jsonify({'error': 'Invalid API key'}), 403
    if entity == 'student_parent':
        records = db.session.execute(db.select(student_parent)).mappings().all()
        data = [dict(row) for row in records]
    else:
        model = SYNC_EXPORT_MODELS.get(entity)
        if not model:
            return jsonify({'error': f'Unknown entity: {entity}'}), 400
        data = [_serialize_sync_record(record) for record in model.query.all()]
    return jsonify({'entity': entity, 'data': data, 'count': len(data), 'version': APP_VERSION})


# ─── One-Button Sync & Auto-Sync APIs ────────────────────────────────

@app.route('/api/sync/check-internet')
@login_required
@role_required('super_admin', 'bursar')
def api_check_internet():
    """Check if the Flask app can reach the WordPress sync endpoint."""
    endpoint = SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', '')
    if not endpoint:
        return jsonify({'connected': False, 'error': 'No sync endpoint configured'})
    api_key = SyncSetting.get('sync_api_key', '') or app.config.get('SYNC_API_KEY', '')
    try:
        resp = requests.get(
            f"{endpoint.rstrip('/')}/api/stats",
            headers={'X-ESM-API-Key': api_key},
            timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            ap_monitor.is_online = True
            ap_monitor.last_error = ''
            return jsonify({
                'connected': True,
                'wordpress_version': data.get('version', 'unknown'),
                'online_students': data.get('total_students', 0),
                'online_staff': data.get('total_staff', 0),
            })
        ap_monitor.is_online = False
        ap_monitor.last_error = f'HTTP {resp.status_code}'
        return jsonify({'connected': False, 'error': f'HTTP {resp.status_code}'})
    except requests.exceptions.ConnectionError:
        ap_monitor.is_online = False
        ap_monitor.last_error = 'Connection refused'
        return jsonify({'connected': False, 'error': 'Connection refused — no internet or endpoint unreachable'})
    except requests.exceptions.Timeout:
        ap_monitor.is_online = False
        ap_monitor.last_error = 'Timeout'
        return jsonify({'connected': False, 'error': 'Connection timed out'})
    except Exception as e:
        ap_monitor.is_online = False
        ap_monitor.last_error = str(e)[:100]
        return jsonify({'connected': False, 'error': str(e)})


@app.route('/api/sync/one-button', methods=['POST'])
@login_required
@role_required('super_admin', 'bursar')
def api_one_button_sync():
    """One-button sync: push pending changes to WordPress, then pull from WordPress."""
    endpoint = SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', '')
    api_key = SyncSetting.get('sync_api_key', '') or app.config.get('SYNC_API_KEY', '')

    if not endpoint:
        return jsonify({'success': False, 'error': 'Sync endpoint not configured. Go to Sync Center to configure.'})

    result = {'push': {'pushed': 0, 'failed': 0, 'total': 0}, 'pull': {'pulled': 0, 'conflicts': 0, 'skipped': 0, 'total': 0}, 'success': True}

    # STEP 1: Push pending changes to WordPress
    pending_logs = SyncLog.query.filter_by(sync_status='pending').all()
    result['push']['total'] = len(pending_logs)
    for log in pending_logs:
        try:
            data = json.loads(log.data_snapshot) if log.data_snapshot else {}
            entity_tables = {
                'Student': Student, 'Staff': Staff, 'FeePayment': FeePayment,
                'ExamResult': ExamResult,
                'Notice': Notice, 'FeeLevel': FeeLevel, 'Class': Class,
                'Subject': Subject, 'FeeStructure': FeeStructure, 'StaffSubject': StaffSubject,
            }
            if log.action in ('CREATE', 'UPDATE') and log.entity_type in entity_tables:
                model = entity_tables[log.entity_type]
                record = model.query.get(log.entity_id)
                if record:
                    data = {}
                    for c in record.__table__.columns:
                        val = getattr(record, c.name)
                        if isinstance(val, (datetime, date)):
                            val = val.isoformat()
                        elif isinstance(val, timedelta):
                            val = str(val)
                        data[c.name] = val

            payload = {
                'entity_type': log.entity_type,
                'entity_id': log.entity_id,
                'action': log.action,
                'data': data,
                'api_key': api_key,
                'source': 'flask',
                'timestamp': log.created_at.isoformat() if log.created_at else datetime.utcnow().isoformat(),
            }
            resp = requests.post(
                f"{endpoint.rstrip('/')}/api/sync",
                json=payload,
                headers={'Content-Type': 'application/json', 'X-ESM-API-Key': api_key},
                timeout=30
            )
            if resp.status_code < 300:
                log.sync_status = 'synced'
                log.sync_timestamp = datetime.utcnow()
                result['push']['pushed'] += 1
            else:
                log.sync_status = 'failed'
                log.sync_timestamp = datetime.utcnow()
                result['push']['failed'] += 1
        except Exception:
            log.sync_status = 'failed'
            log.sync_timestamp = datetime.utcnow()
            result['push']['failed'] += 1
    db.session.commit()

    # STEP 2: Pull changes from WordPress
    try:
        resp = requests.get(
            f"{endpoint.rstrip('/')}/api/sync/pending",
            headers={'X-ESM-API-Key': api_key},
            timeout=30
        )
        if resp.status_code == 200:
            body = resp.json()
            items = body.get('pending', [])
            result['pull']['total'] = len(items)
            synced_ids = []

            entity_models = {
                'Student': Student, 'Staff': Staff, 'FeePayment': FeePayment,
                'ExamResult': ExamResult,
                'Notice': Notice, 'FeeLevel': FeeLevel, 'FeeStructure': FeeStructure,
                'Class': Class, 'Subject': Subject, 'StaffSubject': StaffSubject,
                'AcademicYear': AcademicYear, 'Term': Term,
            }

            for item in items:
                entity_type = item.get('entity_type', '')
                action = item.get('action', '')
                entity_data = item.get('data') or {}
                sync_id_val = entity_data.get('sync_id', '')
                incoming_ts = item.get('created_at', '')

                model = entity_models.get(entity_type)
                if not model:
                    continue

                if action in ('CREATE', 'UPDATE'):
                    existing = None
                    if sync_id_val and hasattr(model, 'sync_id'):
                        existing = model.query.filter_by(sync_id=sync_id_val).first()

                    if existing:
                        should_update = True
                        if incoming_ts and hasattr(existing, 'updated_at') and existing.updated_at:
                            try:
                                incoming_dt = datetime.fromisoformat(incoming_ts.replace('Z', '+00:00')).replace(tzinfo=None)
                                if incoming_dt <= existing.updated_at:
                                    should_update = False
                                    result['pull']['skipped'] += 1
                            except (ValueError, AttributeError):
                                pass
                        if should_update:
                            for k, v in entity_data.items():
                                if hasattr(existing, k) and k not in ('id', 'created_at'):
                                    try: setattr(existing, k, v)
                                    except (ValueError, TypeError): pass
                            if hasattr(existing, 'updated_at'):
                                existing.updated_at = datetime.utcnow()
                            result['pull']['pulled'] += 1
                    else:
                        try:
                            new_record = model()
                            for k, v in entity_data.items():
                                if hasattr(new_record, k) and k != 'id':
                                    try: setattr(new_record, k, v)
                                    except (ValueError, TypeError): pass
                            if not getattr(new_record, 'sync_id', None) and sync_id_val:
                                new_record.sync_id = sync_id_val
                            db.session.add(new_record)
                            result['pull']['pulled'] += 1
                        except Exception:
                            result['pull']['conflicts'] += 1

                elif action == 'DELETE':
                    eid = item.get('entity_id', 0)
                    if eid:
                        record = model.query.get(eid)
                        if record:
                            if hasattr(record, 'status'): record.status = 'Inactive'
                            else: db.session.delete(record)
                            result['pull']['pulled'] += 1

                synced_ids.append(item.get('id'))

            # Confirm pulled items on WordPress side
            if synced_ids:
                try:
                    requests.post(
                        f"{endpoint.rstrip('/')}/api/sync/mark-synced",
                        json={'ids': synced_ids, 'api_key': api_key},
                        headers={'Content-Type': 'application/json', 'X-ESM-API-Key': api_key},
                        timeout=15
                    )
                except Exception:
                    pass

            db.session.commit()
    except Exception as e:
        result['pull']['error'] = str(e)

    # Persist sync result to database (survives restarts)
    sync_status_val = 'success' if result['push']['failed'] == 0 and 'error' not in result.get('pull', {}) else 'partial'
    SyncSetting.set('last_sync_time', datetime.utcnow().isoformat(), 'Last sync timestamp')
    SyncSetting.set('last_sync_status', sync_status_val, 'Last sync result')
    SyncSetting.set('last_sync_pushed', str(result['push']['pushed']))
    SyncSetting.set('last_sync_pulled', str(result['pull']['pulled']))
    session['last_sync_time'] = datetime.utcnow().isoformat()
    session['last_sync_status'] = sync_status_val

    return jsonify(result)


@app.route('/api/sync/auto-sync-settings', methods=['POST'])
@login_required
@role_required('super_admin', 'bursar')
def api_auto_sync_settings():
    """Save auto-sync settings — persisted to database (survives restarts)."""
    enabled = request.json.get('enabled', False)
    interval = request.json.get('interval', 300)
    endpoint = request.json.get('endpoint', '')
    api_key = request.json.get('api_key', '')

    # Persist to database
    SyncSetting.set('auto_sync_enabled', 'true' if enabled else 'false', 'Auto-sync on/off')
    SyncSetting.set('auto_sync_interval', str(int(interval)), 'Auto-sync check interval (seconds)')

    if endpoint:
        SyncSetting.set('sync_endpoint', endpoint, 'WordPress sync endpoint URL')
        app.config['SYNC_ENDPOINT'] = endpoint
    if api_key:
        SyncSetting.set('sync_api_key', api_key, 'Sync API key')
        app.config['SYNC_API_KEY'] = api_key

    # Ensure the background monitor is running/stopped as needed
    if enabled and not ap_monitor.status()['running']:
        ap_monitor.start()
    elif not enabled and ap_monitor.status()['running']:
        ap_monitor.stop()

    return jsonify({'success': True, 'enabled': enabled, 'interval': interval})


@app.route('/api/sync/status')
@login_required
@role_required('super_admin', 'bursar')
def api_sync_status():
    """Get current sync status for the auto-sync monitor."""
    pending = SyncLog.query.filter_by(sync_status='pending').count()
    return jsonify({
        'pending': pending,
        'last_sync': SyncSetting.get('last_sync_time', '') or session.get('last_sync_time', ''),
        'last_status': SyncSetting.get('last_sync_status', '') or session.get('last_sync_status', ''),
        'auto_sync': SyncSetting.get('auto_sync_enabled', 'false') == 'true',
        'auto_interval': int(SyncSetting.get('auto_sync_interval', '300')),
        'endpoint': SyncSetting.get('sync_endpoint', '') or app.config.get('SYNC_ENDPOINT', ''),
        'ap_monitor': ap_monitor.status(),
    })


@app.route('/api/sync/access-point-status')
@login_required
@role_required('super_admin', 'bursar')
def api_access_point_status():
    """Return the access point monitor status — real-time connectivity info."""
    return jsonify(ap_monitor.status())


@app.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for dashboard statistics."""
    return jsonify(get_dashboard_stats())


@app.route('/healthz')
def healthz():
    """Unauthenticated liveness/readiness check for containers and proxies."""
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok', 'version': APP_VERSION}), 200
    except Exception:
        app.logger.exception('Database health check failed')
        return jsonify({'status': 'unhealthy'}), 503


# ─── Initialize Database ──────────────────────────────────────────────

def init_db():
    """Create database tables and seed initial data."""
    db.create_all()

    # Ensure SQLite schema has new columns if migrating from existing db
    with db.engine.connect() as conn:
        for table, col, col_type, def_val in [
            ('fee_level', 'development_levy', 'FLOAT', '0'),
            ('fee_level', 'registration_fee', 'FLOAT', '10'),
            ('fee_level', 'textbook_levy', 'FLOAT', '0'),
            ('fee_structure', 'development_levy', 'FLOAT', '0'),
            ('fee_structure', 'registration_fee', 'FLOAT', '10'),
            ('fee_structure', 'textbook_levy', 'FLOAT', '0'),
            ('student', 'is_new_learner', 'BOOLEAN', '1'),
            ('student', 'billed_once_off_levies', 'BOOLEAN', '0'),
            ('student', 'entry_mode', 'VARCHAR(20)', "'Day'"),
            ('fee_level', 'stay_in_fee', 'FLOAT', '0'),
            ('fee_structure', 'stay_in_fee', 'FLOAT', '0'),
            ('class', 'sync_id', 'VARCHAR(36)', 'NULL'),
            ('staff_subject', 'sync_id', 'VARCHAR(36)', 'NULL'),
        ]:
            try:
                conn.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type} DEFAULT {def_val}"))
                conn.commit()
            except Exception:
                pass

    # Stable IDs let classes created on either installation upsert instead of
    # duplicating during manual or automatic bidirectional sync.
    for cls in Class.query.filter(Class.sync_id.is_(None)).all():
        cls.sync_id = str(uuid.uuid4())
    for assignment in StaffSubject.query.filter(StaffSubject.sync_id.is_(None)).all():
        assignment.sync_id = str(uuid.uuid4())
    db.session.commit()

    # Provision the default super admin. Existing installations that still use
    # the previous bootstrap account are migrated once, without resetting the
    # password on every startup (which would break Change Password).
    admin = User.query.filter_by(username=DEFAULT_ADMIN_USERNAME).first()
    if admin is None:
        admin = User.query.filter_by(username='admin').first()
        if admin is None:
            admin = User(username=DEFAULT_ADMIN_USERNAME)
            db.session.add(admin)
        else:
            admin.username = DEFAULT_ADMIN_USERNAME
        admin.set_password(DEFAULT_ADMIN_PASSWORD)

    admin.role = 'super_admin'
    admin.is_active = True

    # Migrate old role names to new role names
    for old_role, new_role in [('admin', 'super_admin'), ('staff', 'bursar')]:
        users_to_migrate = User.query.filter_by(role=old_role).all()
        for u in users_to_migrate:
            u.role = new_role

    # Create default academic year
    if not AcademicYear.query.first():
        ay = AcademicYear(
            name='2026',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        db.session.add(ay)
        db.session.flush()

        # Default terms
        terms_data = [
            ('Term 1', date(2026, 1, 12), date(2026, 4, 2)),
            ('Term 2', date(2026, 5, 4), date(2026, 8, 7)),
            ('Term 3', date(2026, 9, 7), date(2026, 12, 4)),
        ]
        for name, start, end in terms_data:
            t = Term(
                name=name,
                academic_year_id=ay.id,
                start_date=start,
                end_date=end,
                is_current=(name == 'Term 3'),
            )
            db.session.add(t)

    # Billing starts at Term 3 2026: move existing installations forward to
    # Term 3 (creating it if the current year has no Term 3 yet). Once the
    # current term is Term 3 this is a no-op on later startups.
    billing_ay = AcademicYear.query.filter_by(is_current=True).first() or AcademicYear.query.first()
    if billing_ay:
        term3 = Term.query.filter_by(name='Term 3', academic_year_id=billing_ay.id).first()
        if term3 is None:
            term3 = Term(
                name='Term 3',
                academic_year_id=billing_ay.id,
                start_date=date(2026, 9, 7),
                end_date=date(2026, 12, 4),
                is_current=False,
            )
            db.session.add(term3)
            db.session.flush()
        current_term = Term.query.filter_by(academic_year_id=billing_ay.id, is_current=True).first()
        if current_term is None or current_term.name != 'Term 3':
            Term.query.update({Term.is_current: False})
            term3.is_current = True
        db.session.commit()

    # Ensure the approved primary subjects and standard secondary subjects
    # exist on both new and upgraded installations. Existing custom subjects
    # are retained because they may already be referenced by results.
    primary_subjects = [
        (name, PRIMARY_SUBJECT_CODES[name], True)
        for name in PRIMARY_LEARNING_AREAS
    ]
    secondary_subjects = [
        ('English Language', 'ELAN', True),
        ('Shona', 'SHON', True),
        ('Science', 'SCI2', True),
        ('History', 'HIST', True),
        ('Geography', 'GEO', True),
        ('Religious Studies', 'RS', True),
        ('Physical Education', 'PE', True),
        ('Art', 'ART', False),
        ('Music', 'MUS', False),
        ('Computer Studies', 'CS', False),
        ('Agriculture', 'AGR', False),
        ('Commerce', 'COM', False),
        ('French', 'FRE', False),
        ('Biology', 'BIO', True),
        ('Chemistry', 'CHEM', True),
        ('Physics', 'PHY', True),
        ('Combined Science', 'CSC', True),
        ('Principles of Accounts', 'POA', False),
        ('Business Studies', 'BUST', False),
        ('Economics', 'ECO', False),
        ('Literature in English', 'LIT', False),
        ('Additional Mathematics', 'AMTH', False),
    ]
    for name, code, compulsory in primary_subjects + secondary_subjects:
        subject = Subject.query.filter_by(code=code).first()
        if not subject:
            subject = Subject.query.filter_by(name=name).first()
        if not subject:
            db.session.add(Subject(name=name, code=code, is_compulsory=compulsory))
        elif name in PRIMARY_LEARNING_AREAS:
            # Normalize approved primary names/codes when upgrading.
            subject.name = name
            subject.code = code
            subject.is_compulsory = True

    # Create default fee levels
    if not FeeLevel.query.first():
        fee_levels_data = [
            # (name, code, desc, tuition, dev_levy, reg_fee, tb_levy, stay_in_fee)
            ('ECD', 'ECD', 'Early Childhood Development (ECD A & B)', 150.0, 0.0, 10.0, 56.0, 300.0),
            ('Junior', 'JNR', 'Junior School (Grade 1 to Grade 7)', 100.0, 0.0, 10.0, 126.0, 300.0),
            ('O Level', 'OLV', 'O Level (Form 1 to Form 4)', 100.0, 30.0, 10.0, 56.0, 300.0),
            ('A Level', 'ALV', 'A Level (Form 5 to Form 6)', 150.0, 30.0, 10.0, 45.0, 260.0),
        ]
        for name, code, desc, tuition, dev_levy, reg_fee, tb_levy, stay_fee in fee_levels_data:
            total = tuition + dev_levy
            fl = FeeLevel(
                name=name, code=code, description=desc,
                tuition=tuition, development_levy=dev_levy,
                registration_fee=reg_fee, textbook_levy=tb_levy,
                stay_in_fee=stay_fee, total=total,
            )
            db.session.add(fl)

    # Ensure default fee levels have correct amounts if updating existing db
    defaults_map = {
        # name: (tuition, dev_levy, reg_fee, tb_levy, stay_in_fee)
        'ECD': (150.0, 0.0, 10.0, 56.0, 300.0),
        'Junior': (100.0, 0.0, 10.0, 126.0, 300.0),
        'O Level': (100.0, 30.0, 10.0, 56.0, 300.0),
        'A Level': (150.0, 30.0, 10.0, 45.0, 260.0),
    }
    for name, (tuition, dev_levy, reg_fee, tb_levy, stay_fee) in defaults_map.items():
        fl = FeeLevel.query.filter_by(name=name).first()
        if fl and (fl.tuition != tuition or fl.development_levy != dev_levy or fl.registration_fee != reg_fee
                   or fl.textbook_levy != tb_levy or fl.stay_in_fee != stay_fee
                   or fl.total != tuition + dev_levy):
            fl.tuition = tuition
            fl.development_levy = dev_levy
            fl.registration_fee = reg_fee
            fl.textbook_levy = tb_levy
            fl.stay_in_fee = stay_fee
            fl.total = tuition + dev_levy

    db.session.commit()

    # Seed default appearance settings
    if not AppearanceSetting.query.first():
        for key, val in DEFAULT_THEME.items():
            if val:
                s = AppearanceSetting(key=key, value=val)
                db.session.add(s)
        db.session.commit()

    # Restore persisted sync settings into app.config
    persisted_endpoint = SyncSetting.get('sync_endpoint', '')
    persisted_api_key = SyncSetting.get('sync_api_key', '')
    if persisted_endpoint:
        app.config['SYNC_ENDPOINT'] = persisted_endpoint
    if persisted_api_key:
        app.config['SYNC_API_KEY'] = persisted_api_key

    # Start the Access Point Monitor if auto-sync was enabled
    if SyncSetting.get('auto_sync_enabled', 'false') == 'true':
        ap_monitor.start()
        app.logger.info('[init_db] Auto-sync was enabled — Access Point Monitor started')


# ─── Main ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        init_db()
    mode = app.config['DEPLOYMENT_MODE']
    print(f"\n{'='*60}")
    print(f"  Excel Group of Schools - Management System")
    print(f"  Version 2.0.0 | Author: Valentine T Mabheka")
    print(f"  Deployment Mode: {mode.upper()}")
    print(f"  Server: http://localhost:5000")
    print(f"  Admin Username: {DEFAULT_ADMIN_USERNAME}")
    print(f"  Access Point Monitor: {'ACTIVE' if ap_monitor.status()['running'] else 'STANDBY'}")
    print(f"{'='*60}\n")
    app.run(debug=True, host='0.0.0.0', port=5000)

# ─── CORS + Internet Handshake Helper ─────────────────────────────────
@app.route('/api/sync/handshake', methods=['GET', 'POST'])
def api_sync_handshake():
    """Endpoint used by online WordPress to verify Flask is reachable and ready."""
    return jsonify({
        'status': 'ok',
        'message': 'Flask offline sync endpoint is live',
        'version': APP_VERSION,
        'school_name': app.config.get('SCHOOL_NAME', 'Excel Group of Schools'),
        'school_motto': app.config.get('SCHOOL_MOTTO', ''),
        'timestamp': datetime.utcnow().isoformat()
    })
