#!/usr/bin/env python3
"""
remove-onceoff-levies.py
========================
Remove the once-off levies from uploaded students' invoices:

    1. Textbook Levy (Once-off)
    2. Registration Fee (Once-off)

The script also marks every affected learner as "once-off levies already
billed", so the system will NOT add these two fees again when their
invoice is refreshed or regenerated (including new terms).

Usage:
    python remove-onceoff-levies.py                 # apply the removal
    python remove-onceoff-levies.py --dry-run       # preview only, no changes
    python remove-onceoff-levies.py --yes           # apply without confirmation
    python remove-onceoff-levies.py --db <path>     # use a specific database

Which database does it use?
    The script finds the school database automatically, in this order:
      1. --db <path> or the EXCEL_SCHOOLS_DB environment variable
      2. the DATABASE_URL environment variable (if you run from a shell)
      3. %LOCALAPPDATA%\\ExcelSchools\\excel_schools.db   (Windows EXE mode)
      4. <this folder>\\instance\\excel_schools.db        (source mode)
      5. <this folder>\\excel_schools.db
    The chosen database is printed at the top of the output, so you can
    verify it is the one the running server uses.

On Windows you can also double-click  remove-onceoff-levies.bat.

The script is safe to run more than once: the second run finds nothing.
Stop the Excel Schools server first, run the script, then start the
server again.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def resolve_database(cli_db: str | None) -> str:
    """Decide which SQLite database to operate on (see docstring)."""
    explicit = cli_db or os.environ.get('EXCEL_SCHOOLS_DB') or os.environ.get('DATABASE_URL')
    if explicit:
        return explicit

    candidates: list[Path] = []
    # 1) Windows EXE mode: windows_launcher.py stores data under %LOCALAPPDATA%\ExcelSchools
    local = os.environ.get('LOCALAPPDATA')
    if local:
        candidates.append(Path(local) / 'ExcelSchools' / 'excel_schools.db')
    else:
        candidates.append(Path.home() / 'ExcelSchools' / 'excel_schools.db')
    # 2) Source mode: start.sh / START.bat with the default SQLAlchemy URL
    candidates.append(ROOT / 'instance' / 'excel_schools.db')
    candidates.append(ROOT / 'excel_schools.db')

    existing = [p for p in candidates if p.exists()]
    if len(existing) > 1:
        # Prefer the EXE data directory when it exists (deployed mode);
        # otherwise use the most recently modified database.
        if existing[0] in existing:
            return existing[0].as_posix()
        return max(existing, key=lambda p: p.stat().st_mtime).as_posix()
    if existing:
        return existing[0].as_posix()

    # Nothing exists yet: default to the source-mode database.
    (ROOT / 'instance').mkdir(exist_ok=True)
    return (ROOT / 'instance' / 'excel_schools.db').as_posix()


def main() -> int:
    dry_run = '--dry-run' in sys.argv
    auto_yes = '--yes' in sys.argv
    cli_db = None
    if '--db' in sys.argv:
        cli_db = sys.argv[sys.argv.index('--db') + 1]

    database = resolve_database(cli_db)
    # Point the app at the chosen database BEFORE importing it. Plain file
    # paths are converted to SQLAlchemy sqlite URLs.
    if '://' not in database:
        database = 'sqlite:///' + database
    os.environ['DATABASE_URL'] = database

    from app import app, db, Student, Invoice, InvoiceItem, update_invoice_status  # noqa: E402

    display_path = database[10:] if database.startswith('sqlite:///') else database
    db_path = Path(display_path)
    exists = db_path.exists()
    print('=' * 64)
    print(' Once-off levy removal')
    print('=' * 64)
    print(f' Database : {display_path}')
    if exists:
        size_kb = db_path.stat().st_size / 1024
        modified = __import__('datetime').datetime.fromtimestamp(
            db_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f' Status   : found ({size_kb:,.0f} KB, last modified {modified})')
    else:
        print(' Status   : NOT FOUND — the file does not exist yet.')
        print('            If this is not the school database, stop and run with:')
        print('            python remove-onceoff-levies.py --db <path to excel_schools.db>')
        print('            The Windows EXE stores it under %LOCALAPPDATA%\\ExcelSchools\\')
        return 1

    with app.app_context():
        # 1) Find every once-off levy line on any invoice.
        items = (
            InvoiceItem.query
            .filter(db.or_(
                InvoiceItem.description.ilike('%textbook%'),
                InvoiceItem.description.ilike('%registration%'),
            ))
            .order_by(InvoiceItem.id)
            .all()
        )

        if not items:
            print()
            print(' No Textbook Levy / Registration Fee items were found in THIS database.')
            print(' If you expected some, the server may use a different database file:')
            print('   - Windows EXE: %LOCALAPPDATA%\\ExcelSchools\\excel_schools.db')
            print('   - Source mode: <flask-backend>\\instance\\excel_schools.db')
            print(' Point the script at the right file with:  --db <path>')
            return 1

        by_invoice = {}
        for item in items:
            by_invoice.setdefault(item.invoice_id, []).append(item)

        invoices = Invoice.query.filter(Invoice.id.in_(list(by_invoice))).all()
        invoice_map = {inv.id: inv for inv in invoices}

        removed_count = 0
        removed_amount = 0.0
        student_ids = set()

        print(f' Found {len(items)} item(s) on {len(invoices)} invoice(s):')
        for item in items:
            inv = invoice_map.get(item.invoice_id)
            student = db.session.get(Student, inv.student_id) if inv else None
            name = (f'{student.first_name} {student.last_name}'
                    if student else f'student #{inv.student_id if inv else "?"}')
            print(f'   - {item.description:28s} ${item.amount:8.2f}  '
                  f'{name} ({inv.invoice_number if inv else "?"})')
            removed_count += 1
            removed_amount += item.amount or 0.0
            if inv:
                student_ids.add(inv.student_id)

        print('-' * 64)
        print(f' Items to remove : {removed_count}')
        print(f' Total value     : ${removed_amount:,.2f}')
        print(f' Students affected: {len(student_ids)}')

        if dry_run:
            print()
            print('DRY RUN — no changes were made.')
            return 0

        if not auto_yes:
            answer = input('\nApply this removal? [y/N]: ').strip().lower()
            if answer not in ('y', 'yes'):
                print('Cancelled — no changes were made.')
                return 0

        # 2) Delete the levy lines.
        for item in items:
            db.session.delete(item)

        # 3) Recalculate every affected invoice (subtotal, discount, total,
        #    status) and mark the learners so the fees are never billed again.
        for inv in invoices:
            remaining = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
            subtotal = sum(i.amount or 0.0 for i in remaining)
            student = db.session.get(Student, inv.student_id)
            multiplier = student.effective_fee_multiplier if student else 1.0
            discount = subtotal * (1.0 - multiplier)
            inv.subtotal = subtotal
            inv.discount_amount = discount
            inv.total_amount = subtotal - discount
            update_invoice_status(inv)
            if student:
                student.billed_once_off_levies = True
                student.updated_at = __import__('datetime').datetime.utcnow()

        db.session.commit()

        # 4) Verification: show what each affected invoice now contains.
        print()
        print(f' DONE — removed {removed_count} item(s) worth '
              f'${removed_amount:,.2f} from {len(invoices)} invoice(s) '
              f'covering {len(student_ids)} learner(s).')
        print()
        print(' Updated invoices:')
        for inv in invoices:
            student = db.session.get(Student, inv.student_id)
            name = (f'{student.first_name} {student.last_name}'
                    if student else f'student #{inv.student_id}')
            remaining = InvoiceItem.query.filter_by(invoice_id=inv.id).all()
            desc = ', '.join(f'{i.description} ${i.amount:.2f}' for i in remaining) or '(no items)'
            print(f'   {name} ({inv.invoice_number}): {desc} '
                  f'-> total ${inv.total_amount:,.2f} [{inv.status}]')
        print()
        print(' The learners are marked so Textbook Levy and Registration Fee')
        print(' will not be billed to them again.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
