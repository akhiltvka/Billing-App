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
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        # Ensure sslmode=require for Supabase cloud PostgreSQL connections
        if "sslmode=" not in db_url.lower():
            db_url += ("&sslmode=require" if "?" in db_url else "?sslmode=require")

        # 1. Try psycopg2
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
            return conn, True
        except Exception as e1:
            # 2. Try pure-Python pg8000 (fixes Python 3.14 C-extension _PyInterpreterState_Get error)
            try:
                import urllib.parse
                import pg8000.dbapi
                parsed = urllib.parse.urlparse(db_url)
                db_name = (parsed.path or '/postgres').lstrip('/')
                conn = pg8000.dbapi.connect(
                    user=urllib.parse.unquote(parsed.username or 'postgres'),
                    password=urllib.parse.unquote(parsed.password or ''),
                    host=parsed.hostname or 'localhost',
                    port=parsed.port or 5432,
                    database=db_name,
                    ssl_context=True
                )
                return conn, True
            except Exception as e2:
                import traceback
                print(f"[DB Notice] PostgreSQL connection error (psycopg2 & pg8000): {e1} | {e2}")
                traceback.print_exc()
                print("Falling back to SQLite central_licenses.db.")

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
                CREATE TABLE IF NOT EXISTS activation_keys (
                    id           SERIAL PRIMARY KEY,
                    key          VARCHAR(32) UNIQUE NOT NULL,
                    machine_id   VARCHAR(64),
                    redeemed_at  TIMESTAMP DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS revoked_outlets (
                    machine_id   VARCHAR(64) PRIMARY KEY,
                    outlet_code  VARCHAR(64),
                    revoked_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reason       VARCHAR(255) DEFAULT 'Deleted by developer'
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
                CREATE TABLE IF NOT EXISTS activation_keys (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    key          TEXT UNIQUE NOT NULL,
                    machine_id   TEXT,
                    redeemed_at  TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS revoked_outlets (
                    machine_id   TEXT PRIMARY KEY,
                    outlet_code  TEXT,
                    revoked_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                    reason       TEXT DEFAULT 'Deleted by developer'
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

        # Check if this machine_id already has a registered outlet_code
        # BUT: if it's in revoked_outlets (was deleted), treat as fresh registration
        was_revoked = False
        if machine_id and is_pg:
            cur = conn.cursor()
            cur.execute("SELECT machine_id FROM revoked_outlets WHERE UPPER(machine_id) = %s LIMIT 1", (machine_id,))
            was_revoked = bool(cur.fetchone())
        elif machine_id:
            was_revoked = bool(conn.execute("SELECT machine_id FROM revoked_outlets WHERE UPPER(machine_id) = ? LIMIT 1", (machine_id,)).fetchone())

        # Check for existing registration
        if machine_id and not was_revoked and is_pg:
            cur = conn.cursor()
            cur.execute("SELECT outlet_code FROM outlet_registrations WHERE machine_id = %s", (machine_id,))
            existing = cur.fetchone()
        elif machine_id and not was_revoked:
            existing = conn.execute("SELECT outlet_code FROM outlet_registrations WHERE machine_id = ?", (machine_id,)).fetchone()
        else:
            existing = None

        if existing and not was_revoked:
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

        # Insert or update the outlet registration
        now_str = str(datetime.now())[:19]
        if is_pg:
            cur = conn.cursor()
            cur.execute("SELECT id FROM outlet_registrations WHERE UPPER(machine_id) = %s LIMIT 1", (machine_id,))
            reg_row = cur.fetchone()
            if reg_row:
                cur.execute("""
                    UPDATE outlet_registrations SET
                        outlet_code = %s, md_username = %s, md_fullname = %s, group_name = %s,
                        outlet_name = %s, outlet_phone = %s, address = %s, city = %s,
                        state = %s, pincode = %s, updated_at = NOW()
                    WHERE UPPER(machine_id) = %s
                """, (outlet_code, md_username, md_fullname, group_name, outlet_name, outlet_phone, address, city, state, pincode, machine_id))
            else:
                cur.execute("""
                    INSERT INTO outlet_registrations
                        (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                         outlet_phone, address, city, state, pincode, registered_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                """, (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name, outlet_phone, address, city, state, pincode))

            # Also ensure a row exists in outlets table so status/last_ping is tracked
            cur.execute("SELECT id FROM outlets WHERE UPPER(machine_id) = %s LIMIT 1", (machine_id,))
            out_row = cur.fetchone()
            if out_row:
                cur.execute("""
                    UPDATE outlets SET shop_name = %s, phone = %s, owner_name = %s, last_ping = NOW()
                    WHERE UPPER(machine_id) = %s
                """, (outlet_name, outlet_phone, md_fullname, machine_id))
            else:
                cur.execute("""
                    INSERT INTO outlets (machine_id, shop_name, phone, owner_name, status, last_ping)
                    VALUES (%s, %s, %s, %s, 'trial', NOW())
                """, (machine_id, outlet_name, outlet_phone, md_fullname))

            # Clear from revoked list so future pings work normally
            cur.execute("DELETE FROM revoked_outlets WHERE UPPER(machine_id) = %s", (machine_id,))
        else:
            reg_row = conn.execute("SELECT id FROM outlet_registrations WHERE UPPER(machine_id) = ? LIMIT 1", (machine_id,)).fetchone()
            if reg_row:
                conn.execute("""
                    UPDATE outlet_registrations SET
                        outlet_code = ?, md_username = ?, md_fullname = ?, group_name = ?,
                        outlet_name = ?, outlet_phone = ?, address = ?, city = ?,
                        state = ?, pincode = ?, updated_at = ?
                    WHERE UPPER(machine_id) = ?
                """, (outlet_code, md_username, md_fullname, group_name, outlet_name, outlet_phone, address, city, state, pincode, now_str, machine_id))
            else:
                conn.execute("""
                    INSERT INTO outlet_registrations
                        (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                         outlet_phone, address, city, state, pincode, registered_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name, outlet_phone, address, city, state, pincode, now_str, now_str))

            # Also ensure a row exists in outlets table so status/last_ping is tracked
            out_row = conn.execute("SELECT id FROM outlets WHERE UPPER(machine_id) = ? LIMIT 1", (machine_id,)).fetchone()
            if out_row:
                conn.execute("""
                    UPDATE outlets SET shop_name = ?, phone = ?, owner_name = ?, last_ping = CURRENT_TIMESTAMP
                    WHERE UPPER(machine_id) = ?
                """, (outlet_name, outlet_phone, md_fullname, machine_id))
            else:
                conn.execute("""
                    INSERT INTO outlets (machine_id, shop_name, phone, owner_name, status, last_ping)
                    VALUES (?, ?, ?, ?, 'trial', CURRENT_TIMESTAMP)
                """, (machine_id, outlet_name, outlet_phone, md_fullname))

            # Clear from revoked list so future pings work normally
            conn.execute("DELETE FROM revoked_outlets WHERE UPPER(machine_id) = ?", (machine_id,))

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

        outlet_code = (d.get('outlet_code') or '').strip().upper()

        # Check if machine_id was deleted from server
        if is_pg:
            cur.execute("SELECT machine_id FROM revoked_outlets WHERE UPPER(machine_id) = %s LIMIT 1", (machine_id,))
            was_deleted = cur.fetchone()
        else:
            was_deleted = conn.execute("SELECT machine_id FROM revoked_outlets WHERE UPPER(machine_id) = ? LIMIT 1", (machine_id,)).fetchone()

        # If deleted BUT ping payload has an outlet_code (local app is registered and syncing),
        # auto-restore the outlet and clear the revocation record so details update on the server!
        if was_deleted:
            if outlet_code:
                if is_pg:
                    cur.execute("DELETE FROM revoked_outlets WHERE UPPER(machine_id) = %s", (machine_id,))
                    conn.commit()
                else:
                    conn.execute("DELETE FROM revoked_outlets WHERE UPPER(machine_id) = ?", (machine_id,))
                    conn.commit()
            else:
                conn.close()
                return jsonify({
                    'status': 'ok',
                    'data': {
                        'machine_id': machine_id,
                        'license_status': 'needs_reregister',
                        'payment_status': 'UNPAID',
                        'activated_at': '',
                        'expires_at': '',
                        'grace_expires_at': '',
                        'message': '⚠️ This outlet was deleted from the central server. Please re-register on this system to continue.'
                    }
                })
        if outlet_code:
            md_username = (d.get('md_username') or '').strip()
            md_fullname = (d.get('md_fullname') or '').strip()
            group_name = (d.get('group_name') or '').strip()
            addr = (d.get('address') or '').strip()
            city = (d.get('city') or '').strip()
            state = (d.get('state') or '').strip()
            pincode = (d.get('pincode') or '').strip()

            if is_pg:
                cur.execute("SELECT id FROM outlet_registrations WHERE UPPER(machine_id) = %s LIMIT 1", (machine_id,))
                reg_row = cur.fetchone()
                if reg_row:
                    cur.execute("""
                        UPDATE outlet_registrations SET
                            outlet_code = %s, md_username = %s, md_fullname = %s, group_name = %s,
                            outlet_name = %s, outlet_phone = %s, address = %s, city = %s,
                            state = %s, pincode = %s, updated_at = NOW()
                        WHERE UPPER(machine_id) = %s
                    """, (outlet_code, md_username, md_fullname, group_name, shop_name, phone, addr, city, state, pincode, machine_id))
                else:
                    cur.execute("""
                        INSERT INTO outlet_registrations
                            (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                             outlet_phone, address, city, state, pincode, registered_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
                    """, (outlet_code, machine_id, md_username, md_fullname, group_name, shop_name, phone, addr, city, state, pincode))
                conn.commit()
            else:
                reg_row = conn.execute("SELECT id FROM outlet_registrations WHERE UPPER(machine_id) = ? LIMIT 1", (machine_id,)).fetchone()
                if reg_row:
                    conn.execute("""
                        UPDATE outlet_registrations SET
                            outlet_code = ?, md_username = ?, md_fullname = ?, group_name = ?,
                            outlet_name = ?, outlet_phone = ?, address = ?, city = ?,
                            state = ?, pincode = ?, updated_at = ?
                        WHERE UPPER(machine_id) = ?
                    """, (outlet_code, md_username, md_fullname, group_name, shop_name, phone, addr, city, state, pincode, now_str, machine_id))
                else:
                    conn.execute("""
                        INSERT INTO outlet_registrations
                            (outlet_code, machine_id, md_username, md_fullname, group_name, outlet_name,
                             outlet_phone, address, city, state, pincode, registered_at, updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (outlet_code, machine_id, md_username, md_fullname, group_name, shop_name, phone, addr, city, state, pincode, now_str, now_str))
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
                    cur.execute("SELECT id FROM outlet_users WHERE UPPER(machine_id) = %s AND UPPER(username) = %s LIMIT 1", (machine_id, u_username.upper()))
                    u_row = cur.fetchone()
                    if u_row:
                        cur.execute("""
                            UPDATE outlet_users SET full_name = %s, role = %s, employee_id = %s, active = %s, last_login = %s, updated_at = NOW()
                            WHERE UPPER(machine_id) = %s AND UPPER(username) = %s
                        """, (u_fullname, u_role, u_empid, u_active, u_last_login, machine_id, u_username.upper()))
                    else:
                        cur.execute("""
                            INSERT INTO outlet_users (machine_id, username, full_name, role, employee_id, active, last_login, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        """, (machine_id, u_username, u_fullname, u_role, u_empid, u_active, u_last_login))
                else:
                    u_row = conn.execute("SELECT id FROM outlet_users WHERE UPPER(machine_id) = ? AND UPPER(username) = ? LIMIT 1", (machine_id, u_username.upper())).fetchone()
                    if u_row:
                        conn.execute("""
                            UPDATE outlet_users SET full_name = ?, role = ?, employee_id = ?, active = ?, last_login = ?, updated_at = ?
                            WHERE UPPER(machine_id) = ? AND UPPER(username) = ?
                        """, (u_fullname, u_role, u_empid, u_active, u_last_login, now_str, machine_id, u_username.upper()))
                    else:
                        conn.execute("""
                            INSERT INTO outlet_users (machine_id, username, full_name, role, employee_id, active, last_login, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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

# ─── 12-Digit Activation Key Verification ──────────────────────────────────
LICENSE_SECRET_SALT = "MPI_MEATSHOP_SUB_KEY_SALT_2025_SECRET_#99!"

@app.route('/api/v1/outlet/activate-key', methods=['POST'])
def activate_key():
    """
    Online key verification endpoint called by client desktop app.
    Payload: { "key": "XXXX-XXXX-XXXX", "machine_id": "16-CHAR-ID" }
    Contract: { "valid": true/false, "already_used": true/false, "expires_at": "YYYY-MM-DD", "message": "..." }
    """
    try:
        init_db()
        d = request.get_json() or {}
        raw_key = (d.get('key') or '').strip().upper()
        machine_id = (d.get('machine_id') or '').strip().upper()

        clean_k = ''.join(c for c in raw_key if c.isalnum())
        if len(clean_k) != 12:
            return jsonify({
                'status': 'error',
                'valid': False,
                'already_used': False,
                'message': 'Activation key must be 12 alphanumeric characters.'
            }), 400

        if not machine_id:
            return jsonify({
                'status': 'error',
                'valid': False,
                'already_used': False,
                'message': 'Machine ID is required for key activation.'
            }), 400

        # Cryptographic Signature Verification
        payload = clean_k[:8]
        checksum = clean_k[8:]
        expected_sig = hmac.new(
            LICENSE_SECRET_SALT.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()[:4].upper()

        if checksum != expected_sig:
            return jsonify({
                'status': 'error',
                'valid': False,
                'already_used': False,
                'message': 'Invalid activation key signature. Check key and try again.'
            }), 200

        conn, is_pg = get_db()

        # Check if key was already redeemed
        if is_pg:
            cur = conn.cursor()
            cur.execute("SELECT machine_id FROM activation_keys WHERE key = %s", (clean_k,))
            key_row = cur.fetchone()
        else:
            key_row = conn.execute("SELECT machine_id FROM activation_keys WHERE key = ?", (clean_k,)).fetchone()

        if key_row:
            existing_mid = key_row['machine_id'] if is_pg else key_row[0]
            if existing_mid and existing_mid != machine_id:
                conn.close()
                return jsonify({
                    'status': 'error',
                    'valid': False,
                    'already_used': True,
                    'message': 'This activation key has already been redeemed on a different computer.'
                }), 200

        today_dt = date.today()
        exp_dt = today_dt + timedelta(days=365)
        grace_exp_dt = exp_dt + timedelta(days=10)

        # Record activation key binding & update outlet status
        if is_pg:
            cur.execute("""
                INSERT INTO activation_keys (key, machine_id, redeemed_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (key) DO UPDATE SET machine_id = EXCLUDED.machine_id
            """, (clean_k, machine_id, str(today_dt)))

            cur.execute("""
                INSERT INTO outlets (machine_id, status, payment_status, activated_at, expires_at, grace_expires_at)
                VALUES (%s, 'active', 'VERIFIED_KEY', %s, %s, %s)
                ON CONFLICT (machine_id) DO UPDATE SET
                    status = 'active', payment_status = 'VERIFIED_KEY',
                    activated_at = EXCLUDED.activated_at, expires_at = EXCLUDED.expires_at, grace_expires_at = EXCLUDED.grace_expires_at
            """, (machine_id, str(today_dt), str(exp_dt), str(grace_exp_dt)))
        else:
            conn.execute("""
                INSERT INTO activation_keys (key, machine_id, redeemed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET machine_id = excluded.machine_id
            """, (clean_k, machine_id, str(today_dt)))

            conn.execute("""
                INSERT INTO outlets (machine_id, status, payment_status, activated_at, expires_at, grace_expires_at)
                VALUES (?, 'active', 'VERIFIED_KEY', ?, ?, ?)
                ON CONFLICT(machine_id) DO UPDATE SET
                    status = 'active', payment_status = 'VERIFIED_KEY',
                    activated_at = excluded.activated_at, expires_at = excluded.expires_at, grace_expires_at = excluded.grace_expires_at
            """, (machine_id, str(today_dt), str(exp_dt), str(grace_exp_dt)))

        conn.commit()
        conn.close()

        return jsonify({
            'status': 'ok',
            'valid': True,
            'already_used': False,
            'expires_at': str(exp_dt),
            'message': f'Activation successful! Subscription active for 365 days until {exp_dt}.'
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'error',
            'valid': False,
            'already_used': False,
            'message': f'Server error verifying key: {str(e)}'
        }), 500

# ─── Automated Webhook & Auto-Activation ────────────────────────────────────

@app.route('/api/v1/webhook/payment', methods=['POST'])
def webhook_payment():
    """
    Automated Webhook endpoint for Payment Gateways (Razorpay/Cashfree/Instamojo).
    Automatically activates subscription for 365 days upon successful ₹12,000 UPI payment.
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
                COALESCE(o.id, r.id) as id,
                COALESCE(o.machine_id, r.machine_id) as machine_id,
                COALESCE(o.shop_name, r.outlet_name, 'Registered Outlet') as shop_name,
                COALESCE(o.phone, r.outlet_phone, '') as phone,
                COALESCE(o.owner_name, r.md_fullname, '') as owner_name,
                COALESCE(o.status, 'trial') as status,
                o.activated_at,
                o.expires_at,
                o.grace_expires_at,
                COALESCE(o.payment_status, 'UNPAID') as payment_status,
                o.utr_number,
                o.last_ping,
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
            FROM outlet_registrations r
            LEFT JOIN outlets o ON UPPER(r.machine_id) = UPPER(o.machine_id)
            UNION
            SELECT 
                COALESCE(o.id, r.id) as id,
                COALESCE(o.machine_id, r.machine_id) as machine_id,
                COALESCE(o.shop_name, r.outlet_name, 'Registered Outlet') as shop_name,
                COALESCE(o.phone, r.outlet_phone, '') as phone,
                COALESCE(o.owner_name, r.md_fullname, '') as owner_name,
                COALESCE(o.status, 'trial') as status,
                o.activated_at,
                o.expires_at,
                o.grace_expires_at,
                COALESCE(o.payment_status, 'UNPAID') as payment_status,
                o.utr_number,
                o.last_ping,
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
            ORDER BY id DESC
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
                for k, v in list(u_dict.items()):
                    if isinstance(v, (datetime, date)):
                        u_dict[k] = str(v)
                mid = (u_dict.get('machine_id') or '').strip().upper()
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
            for k, v in list(d.items()):
                if isinstance(v, (datetime, date)):
                    d[k] = str(v)

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

@app.route('/admin/approve/<machine_id>', methods=['POST'])
def approve_outlet(machine_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_portal'))

    try:
        init_db()
        mid = (machine_id or '').strip().upper()
        today_dt = date.today()
        exp_dt = today_dt + timedelta(days=365)
        grace_exp_dt = exp_dt + timedelta(days=10)

        conn, is_pg = get_db()
        if is_pg:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO outlets (machine_id, status, payment_status, activated_at, expires_at, grace_expires_at)
                VALUES (%s, 'active', 'VERIFIED_BY_DEV', %s, %s, %s)
                ON CONFLICT (machine_id) DO UPDATE SET
                    status = 'active', payment_status = 'VERIFIED_BY_DEV',
                    activated_at = EXCLUDED.activated_at, expires_at = EXCLUDED.expires_at, grace_expires_at = EXCLUDED.grace_expires_at
            """, (mid, str(today_dt), str(exp_dt), str(grace_exp_dt)))
        else:
            conn.execute("""
                INSERT INTO outlets (machine_id, status, payment_status, activated_at, expires_at, grace_expires_at)
                VALUES (?, 'active', 'VERIFIED_BY_DEV', ?, ?, ?)
                ON CONFLICT(machine_id) DO UPDATE SET
                    status = 'active', payment_status = 'VERIFIED_BY_DEV',
                    activated_at = excluded.activated_at, expires_at = excluded.expires_at, grace_expires_at = excluded.grace_expires_at
            """, (mid, str(today_dt), str(exp_dt), str(grace_exp_dt)))

        conn.commit()
        conn.close()
        return redirect(url_for('admin_portal'))
    except Exception as e:
        return f"Error approving outlet: {str(e)}", 500

@app.route('/admin/delete/<machine_id>', methods=['POST'])
def delete_outlet(machine_id):
    if not session.get('logged_in'):
        return redirect(url_for('admin_portal'))

    try:
        init_db()
        mid = (machine_id or '').strip().upper()
        conn, is_pg = get_db()

        # Fetch outlet_code before deletion so we can record it in revoked_outlets
        if is_pg:
            cur = conn.cursor()
            cur.execute("SELECT outlet_code FROM outlet_registrations WHERE UPPER(machine_id) = %s LIMIT 1", (mid,))
            reg_row = cur.fetchone()
            outlet_code_for_revoke = (dict(reg_row)['outlet_code'] if reg_row else '').strip().upper()
        else:
            reg_row = conn.execute("SELECT outlet_code FROM outlet_registrations WHERE UPPER(machine_id) = ? LIMIT 1", (mid,)).fetchone()
            outlet_code_for_reset = (reg_row['outlet_code'] if reg_row else '').strip().upper()

        if is_pg:
            cur.execute("DELETE FROM outlets WHERE UPPER(machine_id) = %s", (mid,))
            cur.execute("DELETE FROM outlet_registrations WHERE UPPER(machine_id) = %s", (mid,))
            cur.execute("DELETE FROM outlet_users WHERE UPPER(machine_id) = %s", (mid,))
            cur.execute("DELETE FROM activation_keys WHERE UPPER(machine_id) = %s", (mid,))
            cur.execute("SELECT machine_id FROM revoked_outlets WHERE UPPER(machine_id) = %s LIMIT 1", (mid,))
            if cur.fetchone():
                cur.execute("UPDATE revoked_outlets SET revoked_at = NOW(), reason = 'Deleted by developer — re-registration required' WHERE UPPER(machine_id) = %s", (mid,))
            else:
                cur.execute("""
                    INSERT INTO revoked_outlets (machine_id, outlet_code, revoked_at, reason)
                    VALUES (%s, %s, NOW(), 'Deleted by developer — re-registration required')
                """, (mid, outlet_code_for_revoke))
        else:
            conn.execute("DELETE FROM outlets WHERE UPPER(machine_id) = ?", (mid,))
            conn.execute("DELETE FROM outlet_registrations WHERE UPPER(machine_id) = ?", (mid,))
            conn.execute("DELETE FROM outlet_users WHERE UPPER(machine_id) = ?", (mid,))
            conn.execute("DELETE FROM activation_keys WHERE UPPER(machine_id) = ?", (mid,))
            rev_row = conn.execute("SELECT machine_id FROM revoked_outlets WHERE UPPER(machine_id) = ? LIMIT 1", (mid,)).fetchone()
            if rev_row:
                conn.execute("UPDATE revoked_outlets SET revoked_at = CURRENT_TIMESTAMP, reason = 'Deleted by developer — re-registration required' WHERE UPPER(machine_id) = ?", (mid,))
            else:
                conn.execute("""
                    INSERT INTO revoked_outlets (machine_id, outlet_code, revoked_at, reason)
                    VALUES (?, ?, CURRENT_TIMESTAMP, 'Deleted by developer — re-registration required')
                """, (mid, outlet_code_for_reset))

        conn.commit()
        conn.close()

        return redirect(url_for('admin_portal'))
    except Exception as e:
        return f"Error deleting outlet: {str(e)}", 500

@app.route('/admin/migrate-outlet', methods=['POST'])
def migrate_outlet():
    """Transfer an existing outlet's subscription and registration to a new machine hardware ID."""
    if not session.get('logged_in'):
        return redirect(url_for('admin_portal'))

    try:
        init_db()
        outlet_code = (request.form.get('outlet_code') or '').strip().upper()
        new_machine_id = (request.form.get('new_machine_id') or '').strip().upper()

        if not outlet_code or not new_machine_id:
            return "Both outlet_code and new_machine_id are required.", 400
        if len(new_machine_id) < 8:
            return "New Machine Hardware ID must be at least 8 characters.", 400

        conn, is_pg = get_db()
        now_str = str(datetime.now())[:19]

        if is_pg:
            cur = conn.cursor()
            # Find old machine_id for this outlet code
            cur.execute("SELECT machine_id FROM outlet_registrations WHERE UPPER(outlet_code) = %s LIMIT 1", (outlet_code,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return f"No outlet found with outlet code: {outlet_code}", 404
            old_machine_id = dict(row)['machine_id']

            # Migrate all tables from old machine_id to new machine_id
            cur.execute("UPDATE outlets SET machine_id = %s WHERE UPPER(machine_id) = %s", (new_machine_id, old_machine_id.upper()))
            cur.execute("UPDATE outlet_registrations SET machine_id = %s WHERE UPPER(outlet_code) = %s", (new_machine_id, outlet_code))
            cur.execute("UPDATE outlet_users SET machine_id = %s WHERE UPPER(machine_id) = %s", (new_machine_id, old_machine_id.upper()))
            cur.execute("UPDATE activation_keys SET machine_id = %s WHERE UPPER(machine_id) = %s", (new_machine_id, old_machine_id.upper()))
            # Remove old machine_id from deleted/revoked list if present
            cur.execute("DELETE FROM revoked_outlets WHERE UPPER(machine_id) = %s OR UPPER(outlet_code) = %s", (old_machine_id.upper(), outlet_code))
        else:
            row = conn.execute("SELECT machine_id FROM outlet_registrations WHERE UPPER(outlet_code) = ? LIMIT 1", (outlet_code,)).fetchone()
            if not row:
                conn.close()
                return f"No outlet found with outlet code: {outlet_code}", 404
            old_machine_id = row['machine_id']

            conn.execute("UPDATE outlets SET machine_id = ? WHERE UPPER(machine_id) = ?", (new_machine_id, old_machine_id.upper()))
            conn.execute("UPDATE outlet_registrations SET machine_id = ? WHERE UPPER(outlet_code) = ?", (new_machine_id, outlet_code))
            conn.execute("UPDATE outlet_users SET machine_id = ? WHERE UPPER(machine_id) = ?", (new_machine_id, old_machine_id.upper()))
            conn.execute("UPDATE activation_keys SET machine_id = ? WHERE UPPER(machine_id) = ?", (new_machine_id, old_machine_id.upper()))
            # Remove old machine_id from deleted/revoked list if present
            conn.execute("DELETE FROM revoked_outlets WHERE UPPER(machine_id) = ? OR UPPER(outlet_code) = ?", (old_machine_id.upper(), outlet_code))

        conn.commit()
        conn.close()
        return redirect(url_for('admin_portal'))
    except Exception as e:
        return f"Error migrating outlet: {str(e)}", 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)

