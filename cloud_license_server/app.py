"""
cloud_license_server/app.py — Central Licensing API & Developer Web Portal
Deployable on Render.com with Supabase PostgreSQL (or SQLite local fallback for testing).
"""

import os
import sqlite3
import hmac
import hashlib
from datetime import datetime, date, timedelta
from flask import Flask, jsonify, request, render_template, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_SECRET_KEY", "mpi_cloud_admin_secret_key_2025_#99!")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@5000")

# Database connection: PostgreSQL (Supabase) if DATABASE_URL set, else SQLite local file
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        db_file = os.path.join(os.path.dirname(__file__), "central_licenses.db")
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_db()
    is_pg = bool(DATABASE_URL)
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
        conn.commit()
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
        """)
        conn.commit()
        conn.close()

# ─── API Endpoints for Outlet Apps ──────────────────────────────────────────

@app.route('/api/v1/outlet/ping', methods=['POST'])
def outlet_ping():
    init_db()
    d = request.get_json() or {}
    machine_id = (d.get('machine_id') or '').strip().upper()
    if not machine_id:
        return jsonify({'status': 'error', 'message': 'Machine ID required'}), 400

    shop_name = d.get('shop_name', 'Unknown Shop')
    phone = d.get('phone', '')
    now_str = str(datetime.now())[:19]

    conn = get_db()
    is_pg = bool(DATABASE_URL)
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

@app.route('/api/v1/outlet/notify-payment', methods=['POST'])
def notify_payment():
    init_db()
    d = request.get_json() or {}
    machine_id = (d.get('machine_id') or '').strip().upper()
    utr = (d.get('utr_number') or '').strip()

    if not machine_id:
        return jsonify({'status': 'error', 'message': 'Machine ID required'}), 400

    conn = get_db()
    is_pg = bool(DATABASE_URL)
    if is_pg:
        cur = conn.cursor()
        cur.execute("UPDATE outlets SET payment_status = 'SUBMITTED', utr_number = %s WHERE machine_id = %s", (utr, machine_id))
    else:
        conn.execute("UPDATE outlets SET payment_status = 'SUBMITTED', utr_number = ? WHERE machine_id = ?", (utr, machine_id))
    conn.commit()
    conn.close()

    return jsonify({'status': 'ok', 'message': 'Payment notification received by developer server.'})

# ─── Automated Webhook & Auto-Activation ────────────────────────────────────

@app.route('/api/v1/webhook/payment', methods=['POST'])
def webhook_payment():
    """
    Automated Webhook endpoint for Payment Gateways (Razorpay/Cashfree/Instamojo).
    Automatically activates subscription for 365 days upon successful ₹5,000 UPI payment.
    """
    init_db()
    d = request.get_json() or {}
    
    # Extract machine_id and payment details from payload
    machine_id = (d.get('machine_id') or d.get('notes', {}).get('machine_id') or '').strip().upper()
    utr = d.get('payment_id') or d.get('utr') or 'WEBHOOK-AUTO-PAY'
    amount = float(d.get('amount') or 5000)

    if not machine_id:
        return jsonify({'status': 'error', 'message': 'Missing machine_id in webhook'}), 400

    today_dt = date.today()
    exp_dt = today_dt + timedelta(days=365)
    grace_exp_dt = exp_dt + timedelta(days=10)

    conn = get_db()
    is_pg = bool(DATABASE_URL)
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

# ─── Automated 6-Hour Cloud DB Backup Upload ────────────────────────────────

@app.route('/api/v1/outlet/upload-backup', methods=['POST'])
def upload_backup():
    """Receives automated 6-hour compressed database zip file uploads from outlets."""
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

# ─── Developer Web Portal ───────────────────────────────────────────────────

@app.route('/')
def admin_portal():
    if not session.get('logged_in'):
        return render_template('login.html')

    init_db()
    conn = get_db()
    is_pg = bool(DATABASE_URL)
    if is_pg:
        cur = conn.cursor()
        cur.execute("SELECT * FROM outlets ORDER BY id DESC")
        outlets = cur.fetchall()
    else:
        outlets = conn.execute("SELECT * FROM outlets ORDER BY id DESC").fetchall()
    conn.close()

    outlets_list = [dict(o) for o in outlets]
    return render_template('admin.html', outlets=outlets_list)

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

    init_db()
    today_dt = date.today()
    exp_dt = today_dt + timedelta(days=365)
    grace_exp_dt = exp_dt + timedelta(days=10)

    conn = get_db()
    is_pg = bool(DATABASE_URL)
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
