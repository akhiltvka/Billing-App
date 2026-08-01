"""
cloud_license_server/app.py — Central Licensing API & Developer Web Portal
Deployable on Render.com with Supabase PostgreSQL (or SQLite local fallback for testing).
"""

import os
import sqlite3
import hmac
import hashlib
import zipfile
from io import BytesIO
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, request, render_template, redirect, url_for, session, send_file

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_SECRET_KEY", "mpi_cloud_admin_secret_key_2025_#99!")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@5000")

# Database connection string: PostgreSQL (Supabase) if DATABASE_URL set, else SQLite local file
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    """Returns tuple: (connection_object, is_postgres_bool)"""
    if DATABASE_URL:
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            return conn, True
        except Exception as e:
            print(f"[DB Notice] PostgreSQL connection attempt error: {e}. Falling back to SQLite.")

    db_file = os.path.join(os.path.dirname(__file__), "central_licenses.db")
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn, False

def init_db():
    try:
        conn, is_pg = get_db()
        if is_pg:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS outlets (
                    id SERIAL PRIMARY KEY,
                    machine_id VARCHAR(64) UNIQUE NOT NULL,
                    shop_name VARCHAR(255),
                    phone VARCHAR(32),
                    owner_name VARCHAR(255),
                    status VARCHAR(32) DEFAULT 'trial',
                    activated_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    grace_expires_at TIMESTAMP,
                    payment_status VARCHAR(32) DEFAULT 'UNPAID',
                    utr_number VARCHAR(64),
                    last_ping TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS outlet_registrations (
                    id           SERIAL PRIMARY KEY,
                    outlet_code  VARCHAR(4) UNIQUE NOT NULL,
                    machine_id   VARCHAR(64),
                    md_username  TEXT NOT NULL,
                    md_fullname  TEXT NOT NULL,
                    group_name   TEXT,
                    outlet_name  TEXT NOT NULL,
                    outlet_phone TEXT,
                    address      TEXT,
                    city         TEXT,
                    state        TEXT,
                    pincode      TEXT,
                    registered_at TIMESTAMP DEFAULT NOW(),
                    updated_at    TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS outlet_users (
                    id           SERIAL PRIMARY KEY,
                    machine_id   VARCHAR(64) NOT NULL,
                    username     VARCHAR(255) NOT NULL,
                    full_name    VARCHAR(255),
                    role         VARCHAR(64),
                    employee_id  VARCHAR(64),
                    active       INTEGER,
                    last_login   VARCHAR(64),
                    updated_at   TIMESTAMP DEFAULT NOW(),
                    UNIQUE(machine_id, username)
                );
            """)
            conn.commit()

            # Dynamic migrations to add missing columns to existing PostgreSQL tables
            try:
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'outlets'")
                existing_cols = [r['column_name'].lower() for r in cur.fetchall()]
                migrations = {
                    'grace_expires_at': "ALTER TABLE outlets ADD COLUMN grace_expires_at TIMESTAMP",
                    'payment_status': "ALTER TABLE outlets ADD COLUMN payment_status VARCHAR(32) DEFAULT 'UNPAID'",
                    'utr_number': "ALTER TABLE outlets ADD COLUMN utr_number VARCHAR(64)"
                }
                for col, sql_cmd in migrations.items():
                    if col not in existing_cols:
                        cur.execute(sql_cmd)
                        conn.commit()
            except Exception as me:
                conn.rollback()
                print(f"[Migration Warning] outlets columns: {me}")

            try:
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'outlet_registrations'")
                reg_cols = [r['column_name'].lower() for r in cur.fetchall()]
                if 'machine_id' not in reg_cols:
                    cur.execute("ALTER TABLE outlet_registrations ADD COLUMN machine_id VARCHAR(64)")
                    conn.commit()
            except Exception as me:
                conn.rollback()
                print(f"[Migration Warning] registrations columns: {me}")

            conn.close()
        else:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS outlets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id TEXT UNIQUE NOT NULL,
                    shop_name TEXT,
                    phone TEXT,
                    owner_name TEXT,
                    status TEXT DEFAULT 'trial',
                    activated_at TEXT,
                    expires_at TEXT,
                    grace_expires_at TEXT,
                    payment_status TEXT DEFAULT 'UNPAID',
                    utr_number TEXT,
                    last_ping TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS outlet_registrations (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    outlet_code  TEXT UNIQUE NOT NULL,
                    machine_id   TEXT,
                    md_username  TEXT NOT NULL,
                    md_fullname  TEXT NOT NULL,
                    group_name   TEXT,
                    outlet_name  TEXT NOT NULL,
                    outlet_phone TEXT,
                    address      TEXT,
                    city         TEXT,
                    state        TEXT,
                    pincode      TEXT,
                    registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS outlet_users (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id   TEXT NOT NULL,
                    username     TEXT NOT NULL,
                    full_name    TEXT,
                    role         TEXT,
                    employee_id  TEXT,
                    active       INTEGER,
                    last_login   TEXT,
                    updated_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(machine_id, username)
                );
            """)
            conn.commit()

            # Dynamic migrations to add missing columns to existing SQLite tables
            try:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(outlets)")
                existing_cols = [r[1].lower() for r in cursor.fetchall()]
                migrations = {
                    'grace_expires_at': "ALTER TABLE outlets ADD COLUMN grace_expires_at TEXT",
                    'payment_status': "ALTER TABLE outlets ADD COLUMN payment_status TEXT DEFAULT 'UNPAID'",
                    'utr_number': "ALTER TABLE outlets ADD COLUMN utr_number TEXT"
                }
                for col, sql_cmd in migrations.items():
                    if col not in existing_cols:
                        conn.execute(sql_cmd)
                        conn.commit()

                cursor.execute("PRAGMA table_info(outlet_registrations)")
                reg_cols = [r[1].lower() for r in cursor.fetchall()]
                if 'machine_id' not in reg_cols:
                    conn.execute("ALTER TABLE outlet_registrations ADD COLUMN machine_id TEXT")
                    conn.commit()
            except Exception as me:
                print(f"[Migration Warning] SQLite columns: {me}")

            conn.close()
    except Exception as e:
        print(f"[DB Init Error] {e}")

# ─── API Endpoints for Outlet Apps ──────────────────────────────────────────

@app.route('/api/v1/outlet/register', methods=['POST'])
def register_outlet():
    """
    Called when an MD registers a new outlet.
    Generates a unique 4-digit outlet code (e.g. KK01) and stores full outlet details.
    Returns the assigned outlet_code.
    """
    try:
        init_db()
        d = request.get_json() or {}
        machine_id   = (d.get('machine_id')   or '').strip().upper()
        md_username  = (d.get('md_username')  or '').strip()
        md_fullname  = (d.get('md_fullname')  or '').strip()
        group_name   = (d.get('group_name')   or '').strip()
        outlet_name  = (d.get('outlet_name')  or '').strip()
        outlet_phone = (d.get('outlet_phone') or '').strip()
        address      = (d.get('address')      or '').strip()
        city         = (d.get('city')         or '').strip()
        state        = (d.get('state')        or '').strip()
        pincode      = (d.get('pincode')      or '').strip()

        if not md_username or not outlet_name:
            return jsonify({'status': 'error', 'message': 'md_username and outlet_name are required'}), 400

        # Generate 2-letter prefix from outlet name
        prefix = ''.join(c for c in outlet_name.upper() if c.isalpha())[:2]
        if len(prefix) < 2:
            prefix = (prefix + 'XX')[:2]

        conn, is_pg = get_db()

        # Check if this machine_id already has a registered outlet_code → return it
        if machine_id and is_pg:
            cur = conn.cursor()
            cur.execute("SELECT outlet_code FROM outlet_registrations WHERE machine_id = %s", (machine_id,))
            existing = cur.fetchone()
        elif machine_id:
            existing = conn.execute("SELECT outlet_code FROM outlet_registrations WHERE machine_id = ?", (machine_id,)).fetchone()
        else:
            existing = None

        if existing:
            outlet_code = existing['outlet_code']
            conn.close()
            return jsonify({'status': 'ok', 'outlet_code': outlet_code, 'message': f'Outlet already registered as {outlet_code}'})

        # Count existing outlets with this prefix to determine serial
        if is_pg:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM outlet_registrations WHERE outlet_code LIKE %s", (f'{prefix}%',))
            row = cur.fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM outlet_registrations WHERE outlet_code LIKE ?", (f'{prefix}%',)).fetchone()

        serial = (row['cnt'] if row else 0) + 1
        outlet_code = f"{prefix}{serial:02d}"

        # Ensure uniqueness (collision safety)
        for attempt in range(50):
            if is_pg:
                cur.execute("SELECT 1 FROM outlet_registrations WHERE outlet_code = %s", (outlet_code,))
                exists = cur.fetchone()
            else:
                exists = conn.execute("SELECT 1 FROM outlet_registrations WHERE outlet_code = ?", (outlet_code,)).fetchone()
            if not exists:
                break
            serial += 1
            outlet_code = f"{prefix}{serial:02d}"

        # Insert the outlet registration
        now_str = str(datetime.now())[:19]
        if is_pg:
            cur.execute("""
                INSERT INTO outlet_registrations
                    (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                     outlet_phone, address, city, state, pincode, registered_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
            """, (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                  outlet_phone, address, city, state, pincode))
        else:
            conn.execute("""
                INSERT INTO outlet_registrations
                    (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                     outlet_phone, address, city, state, pincode, registered_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                  outlet_phone, address, city, state, pincode, now_str, now_str))

        conn.commit()
        conn.close()

        print(f"[OUTLET REGISTERED] {outlet_code} | {outlet_name} | MD: {md_username} | Machine: {machine_id}")
        return jsonify({'status': 'ok', 'outlet_code': outlet_code,
                        'message': f"Outlet '{outlet_name}' registered as {outlet_code}"}), 201

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/v1/outlet/md-outlets', methods=['GET'])
def get_md_outlets():
    """Returns all outlet codes registered under a given MD username."""
    try:
        init_db()
        md_username = request.args.get('md_username', '').strip()
        if not md_username:
            return jsonify({'status': 'error', 'message': 'md_username required'}), 400

        conn, is_pg = get_db()
        if is_pg:
            cur = conn.cursor()
            cur.execute(
                "SELECT outlet_code, outlet_name, city, machine_id FROM outlet_registrations WHERE md_username = %s ORDER BY registered_at",
                (md_username,)
            )
            rows = cur.fetchall()
        else:
            rows = conn.execute(
                "SELECT outlet_code, outlet_name, city, machine_id FROM outlet_registrations WHERE md_username = ? ORDER BY registered_at",
                (md_username,)
            ).fetchall()

        conn.close()
        outlets = [dict(r) for r in rows]
        return jsonify({'status': 'ok', 'outlets': outlets, 'count': len(outlets)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/v1/outlet/ping', methods=['POST'])
def outlet_ping():
    try:
        init_db()
        d = request.get_json() or {}
        machine_id = (d.get('machine_id') or '').strip().upper()
        if not machine_id:
            return jsonify({'status': 'error', 'message': 'Machine ID required'}), 400

        shop_name = d.get('shop_name', 'Unknown Shop')
        phone = d.get('phone', '')
        now_str = str(datetime.now())[:19]

        conn, is_pg = get_db()
        cur = conn.cursor() if is_pg else None

        # Auto-heal / rebuild registration details if missing on cloud DB
        outlet_code = (d.get('outlet_code') or '').strip().upper()
        if outlet_code:
            md_username = (d.get('md_username') or '').strip()
            md_fullname = (d.get('md_fullname') or '').strip()
            group_name = (d.get('group_name') or '').strip()
            addr = (d.get('address') or '').strip()
            city = (d.get('city') or '').strip()
            state = (d.get('state') or '').strip()
            pincode = (d.get('pincode') or '').strip()

            if is_pg:
                cur.execute("SELECT id FROM outlet_registrations WHERE machine_id = %s", (machine_id,))
                reg_exists = cur.fetchone()
                if not reg_exists:
                    cur.execute("""
                        INSERT INTO outlet_registrations
                            (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                             outlet_phone, address, city, state, pincode, registered_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                    """, (outlet_code, machine_id, md_username, md_fullname, group_name, shop_name,
                          phone, addr, city, state, pincode))
                    conn.commit()
            else:
                reg_exists = conn.execute("SELECT id FROM outlet_registrations WHERE machine_id = ?", (machine_id,)).fetchone()
                if not reg_exists:
                    conn.execute("""
                        INSERT INTO outlet_registrations
                            (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                             outlet_phone, address, city, state, pincode, registered_at, updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (outlet_code, machine_id, md_username, md_fullname, group_name, shop_name,
                          phone, addr, city, state, pincode, now_str, now_str))
                    conn.commit()

        # Upsert the local users list sent in the ping payload
        users_list = d.get('users') or []
        for u in users_list:
            u_username = (u.get('username') or '').strip()
            u_fullname = (u.get('full_name') or '').strip()
            u_role = (u.get('role') or '').strip()
            u_empid = (u.get('employee_id') or '').strip().upper()
            u_active = int(u.get('active')) if u.get('active') is not None else 1
            u_last_login = u.get('last_login')

            if u_username:
                if is_pg:
                    cur.execute("""
                        INSERT INTO outlet_users (machine_id, username, full_name, role, employee_id, active, last_login, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (machine_id, username) DO UPDATE SET
                            full_name = EXCLUDED.full_name,
                            role = EXCLUDED.role,
                            employee_id = EXCLUDED.employee_id,
                            active = EXCLUDED.active,
                            last_login = EXCLUDED.last_login,
                            updated_at = NOW()
                    """, (machine_id, u_username, u_fullname, u_role, u_empid, u_active, u_last_login))
                else:
                    conn.execute("""
                        INSERT INTO outlet_users (machine_id, username, full_name, role, employee_id, active, last_login, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (machine_id, username) DO UPDATE SET
                            full_name = excluded.full_name,
                            role = excluded.role,
                            employee_id = excluded.employee_id,
                            active = excluded.active,
                            last_login = excluded.last_login,
                            updated_at = excluded.updated_at
                    """, (machine_id, u_username, u_fullname, u_role, u_empid, u_active, u_last_login, now_str))

        if is_pg:
            conn.commit()
            # Refresh cursor
            cur = conn.cursor()

        if is_pg:
            cur.execute("SELECT * FROM outlets WHERE machine_id = %s", (machine_id,))
            outlet = cur.fetchone()
            if not outlet:
                cur.execute("""
                    INSERT INTO outlets (machine_id, shop_name, phone, status, last_ping)
                    VALUES (%s, %s, %s, 'trial', NOW())
                    RETURNING *
                """, (machine_id, shop_name, phone))
                conn.commit()
                outlet = cur.fetchone()
            else:
                cur.execute("""
                    UPDATE outlets SET shop_name = %s, phone = %s, last_ping = NOW() WHERE machine_id = %s
                """, (shop_name, phone, machine_id))
                conn.commit()
        else:
            outlet = conn.execute("SELECT * FROM outlets WHERE machine_id = ?", (machine_id,)).fetchone()
            if not outlet:
                conn.execute("""
                    INSERT INTO outlets (machine_id, shop_name, phone, status, last_ping)
                    VALUES (?, ?, ?, 'trial', ?)
                """, (machine_id, shop_name, phone, now_str))
                conn.commit()
                outlet = conn.execute("SELECT * FROM outlets WHERE machine_id = ?", (machine_id,)).fetchone()
            else:
                conn.execute("""
                    UPDATE outlets SET shop_name = ?, phone = ?, last_ping = ? WHERE machine_id = ?
                """, (shop_name, phone, now_str, machine_id))
                conn.commit()

        conn.close()
        outlet_dict = dict(outlet)

        return jsonify({
            'status': 'ok',
            'data': {
                'machine_id': outlet_dict['machine_id'],
                'license_status': outlet_dict['status'],
                'payment_status': outlet_dict['payment_status'],
                'activated_at': str(outlet_dict['activated_at'] or ''),
                'expires_at': str(outlet_dict['expires_at'] or ''),
                'grace_expires_at': str(outlet_dict['grace_expires_at'] or '')
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/v1/outlet/notify-payment', methods=['POST'])
def notify_payment():
    try:
        init_db()
        d = request.get_json() or {}
        machine_id = (d.get('machine_id') or '').strip().upper()
        utr = (d.get('utr_number') or '').strip()

        if not machine_id:
            return jsonify({'status': 'error', 'message': 'Machine ID required'}), 400

        conn, is_pg = get_db()
        if is_pg:
            cur = conn.cursor()
            cur.execute("UPDATE outlets SET payment_status = 'SUBMITTED', utr_number = %s WHERE machine_id = %s", (utr, machine_id))
        else:
            conn.execute("UPDATE outlets SET payment_status = 'SUBMITTED', utr_number = ? WHERE machine_id = ?", (utr, machine_id))
        conn.commit()
        conn.close()

        return jsonify({'status': 'ok', 'message': 'Payment notification received by developer server.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ─── Automated Webhook & Auto-Activation ────────────────────────────────────

@app.route('/api/v1/webhook/payment', methods=['POST'])
def webhook_payment():
    """
    Automated Webhook endpoint for Payment Gateways (Razorpay/Cashfree/Instamojo).
    Automatically activates subscription for 365 days upon successful ₹5,000 UPI payment.
    """
    try:
        init_db()
        d = request.get_json() or {}
        
        machine_id = (d.get('machine_id') or d.get('notes', {}).get('machine_id') or '').strip().upper()
        utr = d.get('payment_id') or d.get('utr') or 'WEBHOOK-AUTO-PAY'

        if not machine_id:
            return jsonify({'status': 'error', 'message': 'Missing machine_id in webhook'}), 400

        today_dt = date.today()
        exp_dt = today_dt + timedelta(days=365)
        grace_exp_dt = exp_dt + timedelta(days=10)

        conn, is_pg = get_db()
        if is_pg:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO outlets (machine_id, status, payment_status, utr_number, activated_at, expires_at, grace_expires_at)
                VALUES (%s, 'active', 'VERIFIED_AUTO_WEBHOOK', %s, %s, %s, %s)
                ON CONFLICT (machine_id) DO UPDATE SET
                    status = 'active', payment_status = 'VERIFIED_AUTO_WEBHOOK', utr_number = EXCLUDED.utr_number,
                    activated_at = EXCLUDED.activated_at, expires_at = EXCLUDED.expires_at, grace_expires_at = EXCLUDED.grace_expires_at
            """, (machine_id, utr, str(today_dt), str(exp_dt), str(grace_exp_dt)))
        else:
            conn.execute("""
                INSERT INTO outlets (machine_id, status, payment_status, utr_number, activated_at, expires_at, grace_expires_at)
                VALUES (?, 'active', 'VERIFIED_AUTO_WEBHOOK', ?, ?, ?, ?)
                ON CONFLICT(machine_id) DO UPDATE SET
                    status = 'active', payment_status = 'VERIFIED_AUTO_WEBHOOK', utr_number = excluded.utr_number,
                    activated_at = excluded.activated_at, expires_at = excluded.expires_at, grace_expires_at = excluded.grace_expires_at
            """, (machine_id, utr, str(today_dt), str(exp_dt), str(grace_exp_dt)))

        conn.commit()
        conn.close()

        return jsonify({
            'status': 'ok',
            'message': f'Automated payment verified! Outlet {machine_id} active for 365 days until {exp_dt}.'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ─── Automated 6-Hour Cloud DB Backup Upload ────────────────────────────────

@app.route('/api/v1/outlet/upload-backup', methods=['POST'])
def upload_backup():
    """Receives automated 6-hour compressed database zip file uploads from outlets."""
    try:
        machine_id = (request.form.get('machine_id') or '').strip().upper()
        if not machine_id:
            return jsonify({'status': 'error', 'message': 'Machine ID required'}), 400

        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No backup file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'Empty filename'}), 400

        backup_dir = os.path.join(os.path.dirname(__file__), 'cloud_backups', machine_id)
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"db_backup_{timestamp}.zip"
        save_path = os.path.join(backup_dir, filename)
        file.save(save_path)

        return jsonify({
            'status': 'ok',
            'message': 'Cloud database backup uploaded and secured successfully.',
            'saved_as': filename,
            'size_bytes': os.path.getsize(save_path)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ─── Developer Web Portal ───────────────────────────────────────────────────

@app.route('/')
def admin_portal():
    if not session.get('logged_in'):
        return render_template('login.html')

    try:
        init_db()
        conn, is_pg = get_db()
        sql = """
            SELECT 
                o.*,
                r.outlet_code,
                r.md_username,
                r.md_fullname,
                r.group_name,
                r.outlet_name as reg_outlet_name,
                r.outlet_phone as reg_outlet_phone,
                r.address as reg_address,
                r.city as reg_city,
                r.state as reg_state,
                r.pincode as reg_pincode,
                r.registered_at as reg_date
            FROM outlets o
            LEFT JOIN outlet_registrations r ON UPPER(o.machine_id) = UPPER(r.machine_id)
            ORDER BY o.id DESC
        """
        if is_pg:
            cur = conn.cursor()
            cur.execute(sql)
            outlets = cur.fetchall()
        else:
            outlets = conn.execute(sql).fetchall()

        # Query all users registered at outlets
        users_by_machine = {}
        try:
            if is_pg:
                c_users = conn.cursor()
                c_users.execute("SELECT machine_id, username, full_name, role, employee_id, active, last_login FROM outlet_users ORDER BY username")
                user_rows = c_users.fetchall()
            else:
                user_rows = conn.execute("SELECT machine_id, username, full_name, role, employee_id, active, last_login FROM outlet_users ORDER BY username").fetchall()
            for ur in user_rows:
                u_dict = dict(ur)
                mid = u_dict['machine_id'].strip().upper()
                if mid not in users_by_machine:
                    users_by_machine[mid] = []
                users_by_machine[mid].append(u_dict)
        except Exception as ue:
            print(f"[DB Error fetching users] {ue}")

        conn.close()

        outlets_list = []
        base_backup_dir = os.path.join(os.path.dirname(__file__), 'cloud_backups')

        for o in outlets:
            d = dict(o)
            mid = (d.get('machine_id') or '').strip().upper()
            d['users'] = users_by_machine.get(mid, [])
            outlet_dir = os.path.join(base_backup_dir, mid)

            d['has_backup'] = False
            d['backup_file'] = None
            d['backup_time'] = None
            d['backup_size_kb'] = 0

            if os.path.exists(outlet_dir):
                zips = sorted([f for f in os.listdir(outlet_dir) if f.endswith('.zip')], reverse=True)
                if zips:
                    latest_file = zips[0]
                    full_p = os.path.join(outlet_dir, latest_file)
                    d['has_backup'] = True
                    d['backup_file'] = latest_file
                    mtime = os.path.getmtime(full_p)
                    d['backup_time'] = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    d['backup_size_kb'] = round(os.path.getsize(full_p) / 1024, 1)

            outlets_list.append(d)

        return render_template('admin.html', outlets=outlets_list, is_sqlite=not is_pg)
    except Exception as e:
        return f"<div style='font-family:sans-serif;padding:20px;color:red'><h2>Database Error</h2><p>{str(e)}</p></div>", 500


@app.route('/admin/download-db/<machine_id>')
def download_latest_db(machine_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_portal'))

    machine_id = machine_id.strip().upper()
    backup_dir = os.path.join(os.path.dirname(__file__), 'cloud_backups', machine_id)
    if not os.path.exists(backup_dir):
        return "<div style='font-family:sans-serif;padding:20px;color:orange'><h2>No Backups</h2><p>No cloud database backups found for this machine ID.</p></div>", 404

    zip_files = sorted([f for f in os.listdir(backup_dir) if f.endswith('.zip')], reverse=True)
    if not zip_files:
        return "<div style='font-family:sans-serif;padding:20px;color:orange'><h2>No Zip Files</h2><p>No zip backup files found for this machine ID.</p></div>", 404

    latest_zip_path = os.path.join(backup_dir, zip_files[0])

    try:
        with zipfile.ZipFile(latest_zip_path, 'r') as zf:
            db_names = [name for name in zf.namelist() if name.endswith('.db')]
            target_name = db_names[0] if db_names else 'meatshop.db'
            if target_name in zf.namelist():
                db_data = zf.read(target_name)
                buffer = BytesIO(db_data)
                buffer.seek(0)
                download_filename = f"meatshop_{machine_id[:8]}.db"
                return send_file(
                    buffer,
                    mimetype='application/x-sqlite3',
                    as_attachment=True,
                    download_name=download_filename
                )
            else:
                return send_file(latest_zip_path, as_attachment=True)
    except Exception as e:
        return f"<div style='font-family:sans-serif;padding:20px;color:red'><h2>Extraction Error</h2><p>{str(e)}</p></div>", 500


@app.route('/admin/download-zip/<machine_id>')
def download_latest_zip(machine_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_portal'))

    machine_id = machine_id.strip().upper()
    backup_dir = os.path.join(os.path.dirname(__file__), 'cloud_backups', machine_id)
    if not os.path.exists(backup_dir):
        return "No backup directory found", 404

    zip_files = sorted([f for f in os.listdir(backup_dir) if f.endswith('.zip')], reverse=True)
    if not zip_files:
        return "No backup zip files found", 404

    latest_zip_path = os.path.join(backup_dir, zip_files[0])
    return send_file(latest_zip_path, as_attachment=True)


@app.route('/login', methods=['POST'])
def admin_login():
    pwd = request.form.get('password', '')
    if pwd == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('admin_portal'))
    return render_template('login.html', error="Invalid developer password")

@app.route('/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('admin_portal'))

@app.route('/admin/approve/<int:outlet_id>', methods=['POST'])
def approve_outlet(outlet_id):
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401

    try:
        init_db()
        today_dt = date.today()
        exp_dt = today_dt + timedelta(days=365)
        grace_exp_dt = exp_dt + timedelta(days=10)

        conn, is_pg = get_db()
        if is_pg:
            cur = conn.cursor()
            cur.execute("""
                UPDATE outlets
                SET status = 'active', payment_status = 'VERIFIED_BY_DEV',
                    activated_at = %s, expires_at = %s, grace_expires_at = %s
                WHERE id = %s
            """, (str(today_dt), str(exp_dt), str(grace_exp_dt), outlet_id))
        else:
            conn.execute("""
                UPDATE outlets
                SET status = 'active', payment_status = 'VERIFIED_BY_DEV',
                    activated_at = ?, expires_at = ?, grace_expires_at = ?
                WHERE id = ?
            """, (str(today_dt), str(exp_dt), str(grace_exp_dt), outlet_id))

        conn.commit()
        conn.close()
        return redirect(url_for('admin_portal'))
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)

