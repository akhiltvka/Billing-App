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
    u_rows = conn.execute("SELECT username, full_name, role, employee_id, active, last_login FROM users").fetchall()
    users_list = []
    for r in u_rows:
        users_list.append({
            'username': r['username'],
            'full_name': r['full_name'],
            'role': r['role'],
            'employee_id': r['employee_id'],
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

    payload = {
        'machine_id':   get_machine_id(),
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

        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                res_json = json.loads(resp.read().decode('utf-8'))
                if res_json.get('status') == 'ok':
                    data = res_json.get('data', {})
                    cloud_lic_status = data.get('license_status')
                    
                    if cloud_lic_status == 'active' and data.get('expires_at'):
                        # ⚡ Developer approved payment! Auto-activate local database!
                        conn = get_db()
                        exp_str = data['expires_at'][:10]
                        act_str = data.get('activated_at', str(date.today()))[:10]
                        grace_str = data.get('grace_expires_at', '')[:10]
                        
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
                    
                    return False, f"Cloud sync complete. License status: {cloud_lic_status.upper()}"
    except Exception as e:
        return False, f"Cloud server connection offline/unreachable: {str(e)}"

    return False, "Sync attempt finished."

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
