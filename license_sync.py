"""
license_sync.py — Outlet App Cloud License Sync Module
Meat Products of India — Billing & Inventory Management App

Handles background auto-pinging and instant cloud payment verification from Central License Server.
"""

import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, date, timedelta
from database import get_db
from license_manager import get_machine_id, SUBSCRIPTION_DAYS, GRACE_PERIOD_DAYS

# Default Central License Server URL (Configurable in shop_settings or env)
DEFAULT_CLOUD_SERVER_URL = os.environ.get('CLOUD_LICENSE_SERVER_URL', 'https://mpi-license-server.onrender.com')

def get_cloud_server_url():
    conn = get_db()
    row = conn.execute("SELECT value FROM shop_settings WHERE key = 'cloud_license_server_url'").fetchone()
    conn.close()
    if row and row['value']:
        return row['value'].strip().rstrip('/')
    return DEFAULT_CLOUD_SERVER_URL.rstrip('/')

def sync_with_cloud_server():
    """
    Ping central cloud license server.
    If developer approved payment on central dashboard, auto-activates local app for 365 days!
    """
    server_url = get_cloud_server_url()
    ping_endpoint = f"{server_url}/api/v1/outlet/ping"
    conn = get_db()
    # MD details
    md_row = conn.execute("SELECT username, full_name FROM users WHERE role='md'").fetchone()
    md_username = md_row['username'] if md_row else None
    md_fullname = md_row['full_name'] if md_row else None

    # Fetch all users created locally to sync back to central developer dashboard
    u_rows = conn.execute("SELECT username, full_name, role, active, last_login FROM users").fetchall()
    users_list = []
    for r in u_rows:
        users_list.append({
            'username': r['username'],
            'full_name': r['full_name'],
            'role': r['role'],
            'employee_id': '',
            'active': r['active'],
            'last_login': r['last_login']
        })

    # Shop settings
    keys = [
        'outlet_code', 'md_group_name', 'outlet_name', 
        'outlet_phone', 'shop_address', 'outlet_city', 
        'outlet_state', 'outlet_pincode'
    ]
    settings = {}
    for key in keys:
        row = conn.execute("SELECT value FROM shop_settings WHERE key=?", (key,)).fetchone()
        settings[key] = row['value'].strip() if row and row['value'] else None
    conn.close()

    shop_name = settings['outlet_name'] or 'Meat Products Outlet'
    shop_phone = settings['outlet_phone'] or ''
    machine_id = get_machine_id()

    payload = {
        'machine_id':   machine_id,
        'shop_name':    shop_name,
        'phone':        shop_phone,
        # Auto-healing cloud sync fields
        'outlet_code':  settings['outlet_code'],
        'md_username':  md_username,
        'md_fullname':  md_fullname,
        'group_name':   settings['md_group_name'],
        'address':      settings['shop_address'],
        'city':         settings['outlet_city'],
        'state':        settings['outlet_state'],
        'pincode':      settings['outlet_pincode'],
        'users':        users_list
    }

    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            ping_endpoint,
            data=data_bytes,
            headers={'Content-Type': 'application/json', 'User-Agent': 'MPI-Outlet-App/1.0'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_body = resp.read().decode('utf-8')
                resp_status = resp.status
        except urllib.error.HTTPError as http_err:
            # 403 = outlet has been revoked/deleted by the developer
            if http_err.code == 403:
                resp_body = http_err.read().decode('utf-8', errors='ignore')
                resp_status = 403
            else:
                raise

        res_json = json.loads(resp_body)

        # ── NEEDS RE-REGISTER: Developer deleted this outlet from the admin portal ──
        # The server returns license_status='needs_reregister'; we clear local data so
        # the user sees the fresh MD registration screen on next app load.
        cloud_lic_status_raw = ''
        if resp_status == 200 and res_json.get('status') == 'ok':
            cloud_lic_status_raw = (res_json.get('data') or {}).get('license_status', '')

        if cloud_lic_status_raw == 'needs_reregister':
            conn = get_db()
            # Clear all registration & license data so user must re-register
            keys_to_clear = [
                'active_license_json', 'outlet_code', 'outlet_revoked',
                'outlet_name', 'outlet_phone', 'outlet_city', 'outlet_state',
                'outlet_pincode', 'shop_address', 'shop_phone', 'shop_name',
                'md_group_name', 'system_machine_id'
            ]
            for k in keys_to_clear:
                conn.execute("DELETE FROM shop_settings WHERE key = ?", (k,))
            conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_needs_reregister', '1')")
            conn.commit()
            conn.close()
            msg = (res_json.get('data') or {}).get('message', 'Outlet deleted. Please re-register.')
            return False, f"NEEDS_REREGISTER: {msg}"

        if resp_status == 200 and res_json.get('status') == 'ok':
            # Clear any stale re-register / revocation flags since server returned 200 OK
            conn = get_db()
            conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_needs_reregister', '0')")
            conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_revoked', '0')")
            conn.commit()
            conn.close()

            data = res_json.get('data', {})
            cloud_lic_status = data.get('license_status')
            
            if cloud_lic_status == 'active' and data.get('expires_at'):
                # ⚡ Developer approved payment! Auto-activate local database!
                conn = get_db()
                exp_str = str(data['expires_at'])[:10]
                act_str = str(data.get('activated_at') or date.today())[:10]
                grace_str = str(data.get('grace_expires_at') or '')[:10]
                
                if not grace_str:
                    try:
                        exp_dt = datetime.strptime(exp_str, "%Y-%m-%d").date()
                        grace_str = str(exp_dt + timedelta(days=GRACE_PERIOD_DAYS))
                    except Exception:
                        grace_str = exp_str

                lic_payload = {
                    'key': 'CLOUD-AUTO-ACTIVATED',
                    'activated_at': act_str,
                    'expires_at': exp_str,
                    'grace_expires_at': grace_str,
                    'machine_id': machine_id,
                    'subscription_days': SUBSCRIPTION_DAYS
                }

                conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('active_license_json', ?)", (json.dumps(lic_payload),))
                conn.commit()
                conn.close()
                return True, f"Cloud Auto-Activation Verified! Active until {exp_str}."
            
            status_display = str(cloud_lic_status).upper() if cloud_lic_status else "UNKNOWN"
            return True, f"Cloud sync complete. License status: {status_display}"
    except Exception as e:
        return False, f"Cloud server connection offline/unreachable: {str(e)}"

    return False, "Sync attempt finished."


def re_register_with_cloud():
    """
    Push local outlet registration details to the central server.
    Called when internet comes back after an offline re-registration,
    or after a successful ping following a deletion+re-register cycle.
    Returns (success: bool, message: str)
    """
    server_url = get_cloud_server_url()
    reg_endpoint = f"{server_url}/api/v1/outlet/register"
    machine_id = get_machine_id()

    conn = get_db()
    md_row = conn.execute("SELECT username, full_name FROM users WHERE role='md' LIMIT 1").fetchone()
    if not md_row:
        conn.close()
        return False, "No MD account found — re-registration skipped."

    keys = ['outlet_code', 'md_group_name', 'outlet_name', 'outlet_phone',
            'shop_address', 'outlet_city', 'outlet_state', 'outlet_pincode']
    settings = {}
    for key in keys:
        row = conn.execute("SELECT value FROM shop_settings WHERE key=?", (key,)).fetchone()
        settings[key] = row['value'].strip() if row and row['value'] else ''
    conn.close()

    if not settings.get('outlet_name'):
        return False, "No outlet name found — re-registration skipped."

    payload = {
        'machine_id':   machine_id,
        'md_username':  md_row['username'],
        'md_fullname':  md_row['full_name'],
        'group_name':   settings.get('md_group_name', ''),
        'outlet_name':  settings.get('outlet_name', ''),
        'outlet_phone': settings.get('outlet_phone', ''),
        'address':      settings.get('shop_address', ''),
        'city':         settings.get('outlet_city', ''),
        'state':        settings.get('outlet_state', ''),
        'pincode':      settings.get('outlet_pincode', ''),
    }

    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            reg_endpoint,
            data=data_bytes,
            headers={'Content-Type': 'application/json', 'User-Agent': 'MPI-Outlet-App/1.0'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_data = json.loads(resp.read().decode('utf-8'))
            if res_data.get('status') == 'ok':
                new_outlet_code = res_data.get('outlet_code', '')
                if new_outlet_code:
                    # Save the server-assigned outlet code locally
                    conn = get_db()
                    conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_code', ?)", (new_outlet_code,))
                    conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_needs_reregister', '0')")
                    conn.commit()
                    conn.close()
                return True, f"Re-registration synced to server. Outlet Code: {new_outlet_code or settings.get('outlet_code', 'N/A')}"
    except Exception as e:
        return False, f"Could not re-register with cloud: {str(e)}"

    return False, "Re-registration sync failed."

def notify_cloud_payment(utr_number):
    """Notify central developer server of submitted UPI payment UTR/Ref number."""
    server_url = get_cloud_server_url()
    notify_endpoint = f"{server_url}/api/v1/outlet/notify-payment"
    machine_id = get_machine_id()

    payload = {
        'machine_id': machine_id,
        'utr_number': utr_number
    }

    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            notify_endpoint,
            data=data_bytes,
            headers={'Content-Type': 'application/json', 'User-Agent': 'MPI-Outlet-App/1.0'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return True, "Payment notification submitted to developer portal successfully!"
    except Exception as e:
        return False, f"Could not notify central server: {str(e)}"

    return False, "Could not send payment notification."
