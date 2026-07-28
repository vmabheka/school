#!/usr/bin/env python3
"""
Migrate the real demo data from the offline Flask app's SQLite database
(deployment/flask-backend/instance/excel_schools.db) into the rebuilt
WordPress Excel Schools plugin's MySQL tables (wp_esm_*), preserving IDs
so foreign keys resolve, and including Invoices/InvoiceItems which the
previous plugin build had nowhere to store.
"""
import sqlite3
import pymysql
import sys

SQLITE_PATH = "/home/user/deployment/flask-backend/instance/excel_schools.db"
MYSQL_CFG = dict(host="localhost", user="egs_user", password="EgsStrongPass123!",
                  database="excel_schools_wp", charset="utf8mb4")
PFX = "wp_esm_"

sconn = sqlite3.connect(SQLITE_PATH)
sconn.row_factory = sqlite3.Row
scur = sconn.cursor()

mconn = pymysql.connect(**MYSQL_CFG)
mcur = mconn.cursor()


def clear(table):
    mcur.execute("SET FOREIGN_KEY_CHECKS=0")
    mcur.execute(f"TRUNCATE TABLE {PFX}{table}")
    mcur.execute("SET FOREIGN_KEY_CHECKS=1")


def fetch_all(table):
    scur.execute(f'SELECT * FROM "{table}"')
    cols = [d[0] for d in scur.description]
    return cols, scur.fetchall()


def insert_selected(table, sqlite_table, columns):
    """Copy `columns` (that exist in both DBs) row-for-row, preserving id."""
    scur.execute(f'SELECT * FROM "{sqlite_table}"')
    rows = scur.fetchall()
    count = 0
    for row in rows:
        d = dict(row)
        out = {c: d[c] for c in columns if c in d}
        cols_ = list(out.keys())
        sql = f"INSERT INTO {PFX}{table} ({','.join(cols_)}) VALUES ({','.join(['%s'] * len(cols_))})"
        try:
            mcur.execute(sql, [out[c] for c in cols_])
            count += 1
        except Exception as e:
            print(f"  ! insert failed on {table} id={d.get('id')}: {e}")
    return count


print("=== Clearing WordPress demo/seed data ===")
for t in ["invoice_items", "invoices", "fee_payments", "staff_subjects", "students", "staff",
          "fee_structures", "classes", "subjects", "fee_levels", "terms", "academic_years",
          "exam_results", "exams", "notices", "student_parent", "parents"]:
    try:
        clear(t)
    except Exception as e:
        print(f"  ! clear {t} failed: {e}")
mconn.commit()

print("=== Academic Years ===")
n = insert_selected("academic_years", "academic_year", ["id", "name", "start_date", "end_date", "is_current"])
mconn.commit(); print(f"  inserted {n}")

print("=== Terms ===")
n = insert_selected("terms", "term", ["id", "name", "academic_year_id", "start_date", "end_date", "is_current"])
mconn.commit(); print(f"  inserted {n}")

print("=== Classes ===")
n = insert_selected("classes", "class", ["id", "name", "level", "stream", "teacher_id", "capacity", "academic_year_id"])
mconn.commit(); print(f"  inserted {n}")

print("=== Subjects ===")
n = insert_selected("subjects", "subject", ["id", "name", "code", "description", "is_compulsory"])
mconn.commit(); print(f"  inserted {n}")

print("=== Fee Levels (column remap: library->library, other->other_fee) ===")
scur.execute('SELECT * FROM fee_level')
rows = scur.fetchall()
count = 0
for row in rows:
    d = dict(row)
    out = {
        "id": d["id"], "name": d["name"], "code": d["code"], "description": d["description"],
        "tuition": d["tuition"], "development_levy": d["development_levy"],
        "registration_fee": d["registration_fee"], "textbook_levy": d["textbook_levy"],
        "boarding": d["boarding"], "transport": d["transport"], "lunch": d["lunch"],
        "library": d["library"], "technology": d["technology"], "sports": d["sports"],
        "other": d["other"], "total": d["total"], "sync_id": d["sync_id"],
    }
    cols_ = list(out.keys())
    sql = f"INSERT INTO {PFX}fee_levels ({','.join(cols_)}) VALUES ({','.join(['%s'] * len(cols_))})"
    mcur.execute(sql, [out[c] for c in cols_])
    count += 1
mconn.commit()
print(f"  inserted {count}")

print("=== Fee Structures (column remap) ===")
scur.execute('SELECT * FROM fee_structure')
rows = scur.fetchall()
count = 0
for row in rows:
    d = dict(row)
    out = {
        "id": d["id"], "name": d["name"], "class_id": d["class_id"], "level_id": d["level_id"],
        "academic_year_id": d["academic_year_id"], "term_id": d["term_id"],
        "tuition": d["tuition"], "development_levy": d["development_levy"],
        "registration_fee": d["registration_fee"], "textbook_levy": d["textbook_levy"],
        "boarding": d["boarding"], "transport": d["transport"], "lunch": d["lunch"],
        "library": d["library"], "technology": d["technology"], "sports": d["sports"],
        "other": d["other"], "total": d["total"], "sync_id": d["sync_id"],
    }
    cols_ = list(out.keys())
    sql = f"INSERT INTO {PFX}fee_structures ({','.join(cols_)}) VALUES ({','.join(['%s'] * len(cols_))})"
    try:
        mcur.execute(sql, [out[c] for c in cols_])
        count += 1
    except Exception as e:
        print(f"  ! fee_structure {d.get('id')}: {e}")
mconn.commit()
print(f"  inserted {count}")

print("=== Students ===")
n = insert_selected("students", "student", [
    "id", "admission_number", "first_name", "last_name", "other_names", "date_of_birth",
    "gender", "national_id", "photo", "class_id", "admission_date", "status",
    "previous_school", "medical_info", "address", "city", "province", "country",
    "phone", "email", "fee_classification", "scholarship_type", "scholarship_percentage",
    "scholarship_sponsor", "scholarship_staff_id", "scholarship_notes",
    "is_new_learner", "billed_once_off_levies", "user_id", "sync_id",
    "created_at", "updated_at",
])
mconn.commit(); print(f"  inserted {n}")

print("=== Staff ===")
n = insert_selected("staff", "staff", [
    "id", "employee_number", "first_name", "last_name", "other_names", "date_of_birth",
    "gender", "national_id", "photo", "qualification", "specialization", "department",
    "position", "employment_date", "salary", "phone", "email", "address", "status",
    "user_id", "sync_id", "created_at", "updated_at",
])
mconn.commit(); print(f"  inserted {n}")

print("=== Staff Subjects ===")
n = insert_selected("staff_subjects", "staff_subject", ["id", "staff_id", "subject_id", "class_id", "academic_year_id"])
mconn.commit(); print(f"  inserted {n}")

print("=== Fee Payments ===")
n = insert_selected("fee_payments", "fee_payment", [
    "id", "student_id", "receipt_number", "amount", "payment_date", "payment_method",
    "term_id", "academic_year_id", "description", "received_by", "sync_id", "created_at",
])
mconn.commit(); print(f"  inserted {n}")

print("=== Invoices (previously had no WordPress table at all) ===")
n = insert_selected("invoices", "invoice", [
    "id", "invoice_number", "student_id", "academic_year_id", "term_id", "issue_date",
    "due_date", "subtotal", "discount_amount", "total_amount", "status", "notes",
    "sync_id", "created_at",
])
mconn.commit(); print(f"  inserted {n}")

print("=== Invoice Items ===")
n = insert_selected("invoice_items", "invoice_item", ["id", "invoice_id", "description", "amount"])
mconn.commit(); print(f"  inserted {n}")

print("=== Done ===")
mcur.close(); mconn.close(); sconn.close()
