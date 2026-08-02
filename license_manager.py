"""
license_manager.py — Licensing, Subscription, Grace Period & Key Verification Module
Meat Products of India — Billing & Inventory Management App
"""

import os
import re
import hmac
import hashlib
import uuid
import platform
import sqlite3
import urllib.request
from datetime import datetime, date, timedelta
from database import get_db

# Cryptographic Salt for Developer HMAC key signing (12-digit verification)
LICENSE_SECRET_SALT = "MPI_MEATSHOP_SUB_KEY_SALT_2025_SECRET_#99!"

# Subscription parameters
TRIAL_DAYS = 10
SUBSCRIPTION_DAYS = 365
GRACE_PERIOD_DAYS = 10
YEARLY_PRICE_INR = 12000

def _get_hwid_cache_path():
    """Return a system-wide or user-wide persistent path for machine ID caching."""
    base_dir = os.environ.get('PROGRAMDATA') or os.environ.get('APPDATA') or os.path.expanduser('~')
    app_dir = os.path.join(base_dir, 'MPI_Billing_App')
    return os.path.join(app_dir, 'system_hwid.dat')

def _get_cached_machine_id():
    """Retrieve cached machine hardware ID if available."""
    try:
        path = _get_hwid_cache_path()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                val = f.read().strip().upper()
                if len(val) == 16 and val.isalnum():
                    return val
    except Exception:
        pass
    return None

def _save_cached_machine_id(hwid):
    """Save generated machine hardware ID to persistent cache file."""
    try:
        path = _get_hwid_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(hwid)
    except Exception:
        pass

def get_machine_id():
    """
    Generate a deterministic, immutable 16-character hardware ID for single-outlet machine locking.
    Guarantees the exact same ID on the same physical system across reinstalls, folder changes,
    python environment changes, and network adapter state changes (WiFi/Ethernet/VPN/offline).
    """
    components = []

    # 1. Windows Registry MachineGuid & C: Drive Volume Serial Number
    if platform.system() == 'Windows':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            if guid and len(str(guid).strip()) > 5:
                components.append(f"WIN_GUID:{str(guid).strip()}")
        except Exception:
            pass

        try:
            import ctypes
            serial = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetVolumeInformationW("C:\\", None, 0, ctypes.byref(serial), None, None, None, 0):
                components.append(f"VOL_SERIAL:{hex(serial.value)}")
        except Exception:
            pass

    # 2. Linux Machine ID (/etc/machine-id or /var/lib/dbus/machine-id)
    elif platform.system() == 'Linux':
        for path in ['/etc/machine-id', '/var/lib/dbus/machine-id', '/sys/class/dmi/id/product_uuid']:
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        val = f.read().strip()
                        if val:
                            components.append(f"LINUX_ID:{val}")
                            break
            except Exception:
                pass

    # 3. macOS System UUID (IOPlatformUUID)
    elif platform.system() == 'Darwin':
        try:
            import subprocess
            cmd = "ioreg -rd1 -c IOPlatformExpertDevice | grep IOPlatformUUID"
            out = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore').strip()
            if out:
                components.append(f"MAC_UUID:{out}")
        except Exception:
            pass

    # 4. CPU / Processor details (stable hardware spec)
    try:
        processor = platform.processor() or os.environ.get('PROCESSOR_IDENTIFIER', '')
        if processor:
            components.append(f"PROC:{processor.strip()}")
    except Exception:
        pass

    # 5. Computer Node Name (Hostname)
    try:
        node = platform.node()
        if node:
            components.append(f"NODE:{node.strip()}")
    except Exception:
        pass

    if components:
        raw_id = "|".join(components)
        computed_id = hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:16].upper()
        # Save to persistent cache file for extra anchor stability
        _save_cached_machine_id(computed_id)
        return computed_id

    # Fallback to cached ID if hardware queries unexpectedly returned empty
    cached_id = _get_cached_machine_id()
    if cached_id:
        return cached_id

    return "DEFAULT-MACHINE-ID-01"

def check_internet_connection():
    """
    Verify active internet connectivity required for key activation.
    Primary check: Pings central license server reachability.
    Fallback: Checks third-party endpoints if central server is unreachable.
    """
    primary_endpoints = []
    try:
        from license_sync import get_cloud_server_url
        cloud_url = get_cloud_server_url()
        if cloud_url:
            primary_endpoints = [
                f"{cloud_url}/health",
                f"{cloud_url}/api/v1/outlet/ping",
                cloud_url,
            ]
    except Exception:
        pass

    fallback_endpoints = [
        "http://httpbin.org/ip",
        "https://1.1.1.1",
        "https://www.google.com"
    ]

    endpoints = primary_endpoints + fallback_endpoints
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'MPI-Billing-App/1.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status in (200, 204):
                    return True
        except Exception:
            continue
    return False

def clean_key(key_str):
    """Sanitize key string to uppercase 12 alphanumeric characters."""
    if not key_str:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(key_str).upper())

def verify_12digit_key(raw_key_str):
    """
    Format sanity check for 12-digit key (12 uppercase chars [A-Z0-9]{12}).
    NOTE: This function performs format validation only. The central cloud server
    (/api/v1/outlet/activate-key) is the sole authority for key validity.
    """
    clean = clean_key(raw_key_str)
    if len(clean) != 12:
        return False, "Activation key must be 12 alphanumeric characters (e.g. A9K2-M7W3-P4X8)"

    return True, "Key format valid"

def format_key(raw_key_str):
    """Format key into XXXX-XXXX-XXXX for readable UI display."""
    c = clean_key(raw_key_str)
    if len(c) == 12:
        return f"{c[:4]}-{c[4:8]}-{c[8:]}"
    return raw_key_str

def get_license_info():
    """
    Compute current subscription state:
    Returns dict:
      - status: 'trial' | 'active' | 'grace' | 'expired' | 'revoked'
      - days_left: int
      - is_locked: bool (True if expired & grace period over, or if revoked)
      - installed_at: string YYYY-MM-DD
      - activated_at: string YYYY-MM-DD or None
      - expires_at: string YYYY-MM-DD
      - grace_expires_at: string YYYY-MM-DD
      - active_key: string or None
      - machine_id: string
      - price_inr: 12000
    """
    conn = get_db()
    today_dt = date.today()
    today_str = str(today_dt)

    # 1. Fetch or initialize installation_date
    row_inst = conn.execute("SELECT value FROM shop_settings WHERE key = 'installation_date'").fetchone()
    if not row_inst:
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('installation_date', ?)", (today_str,))
        conn.commit()
        inst_str = today_str
    else:
        inst_str = row_inst['value'] or today_str

    try:
        inst_date = datetime.strptime(inst_str[:10], "%Y-%m-%d").date()
    except Exception:
        inst_date = today_dt

    # 2. Fetch active license record
    row_lic = conn.execute("SELECT value FROM shop_settings WHERE key = 'active_license_json'").fetchone()
    lic_data = None
    if row_lic and row_lic['value']:
        try:
            import json
            lic_data = json.loads(row_lic['value'])
        except Exception:
            lic_data = None

    # 2b. Check re-registration flag (set when server signals outlet was deleted)
    row_rereg = conn.execute("SELECT value FROM shop_settings WHERE key = 'outlet_needs_reregister'").fetchone()
    needs_reregister = row_rereg and str(row_rereg['value']).strip() == '1'

    machine_id = get_machine_id()

    if needs_reregister:
        conn.close()
        return {
            'status': 'needs_reregister',
            'days_left': 0,
            'is_locked': True,
            'installed_at': inst_str,
            'activated_at': None,
            'expires_at': '',
            'grace_expires_at': '',
            'active_key': None,
            'machine_id': machine_id,
            'price_inr': YEARLY_PRICE_INR,
            'upi_id': '9809840548@axisb',
            'upi_name': 'MPI Billing Software'
        }

    if lic_data and lic_data.get('expires_at'):
        # ── ACTIVE / GRACE / EXPIRED ─────────────────────────────────────
        try:
            exp_date = datetime.strptime(lic_data['expires_at'][:10], "%Y-%m-%d").date()
        except Exception:
            exp_date = today_dt

        try:
            grace_exp_date = datetime.strptime(lic_data.get('grace_expires_at', '')[:10], "%Y-%m-%d").date()
        except Exception:
            grace_exp_date = exp_date + timedelta(days=GRACE_PERIOD_DAYS)

        activated_at = lic_data.get('activated_at', inst_str)
        active_key = lic_data.get('key', '')

        if today_dt <= exp_date:
            status = 'active'
            days_left = (exp_date - today_dt).days
            is_locked = False
        elif today_dt <= grace_exp_date:
            status = 'grace'
            days_left = (grace_exp_date - today_dt).days
            is_locked = False
        else:
            status = 'expired'
            days_left = 0
            is_locked = True

        conn.close()
        return {
            'status': status,
            'days_left': days_left,
            'is_locked': is_locked,
            'installed_at': inst_str,
            'activated_at': activated_at,
            'expires_at': str(exp_date),
            'grace_expires_at': str(grace_exp_date),
            'active_key': format_key(active_key),
            'machine_id': machine_id,
            'price_inr': YEARLY_PRICE_INR,
            'upi_id': '9809840548@axisb',
            'upi_name': 'MPI Billing Software'
        }

    else:
        # ── TRIAL PERIOD ──────────────────────────────────────────────────
        trial_exp_date = inst_date + timedelta(days=TRIAL_DAYS)
        if today_dt <= trial_exp_date:
            status = 'trial'
            days_left = (trial_exp_date - today_dt).days
            is_locked = False
        else:
            status = 'expired'
            days_left = 0
            is_locked = True

        conn.close()
        return {
            'status': status,
            'days_left': days_left,
            'is_locked': is_locked,
            'installed_at': inst_str,
            'activated_at': None,
            'expires_at': str(trial_exp_date),
            'grace_expires_at': str(trial_exp_date),
            'active_key': None,
            'machine_id': machine_id,
            'price_inr': YEARLY_PRICE_INR,
            'upi_id': '9809840548@axisb',
            'upi_name': 'MPI Billing Software'
        }

# NOTE: The hardcoded Master Developer Secret Key offline bypass has been removed for security.
# If a secure per-machine emergency activation path is required for support, a proper signature-based offline mechanism can be implemented upon request.

def activate_subscription(raw_key_str):
    """
    Redeem a 12-digit activation key online via Central Cloud License Server.
    Server Contract: POST {cloud_url}/api/v1/outlet/activate-key with { "key": clean_k, "machine_id": machine_id }
    Returns: { "valid": true/false, "already_used": true/false, "expires_at": "YYYY-MM-DD", "message": "..." }
    """
    # 1. Format Sanity Check (Length & Allowed Characters)
    valid, msg = verify_12digit_key(raw_key_str)
    if not valid:
        return False, msg

    clean_k = clean_key(raw_key_str)
    machine_id = get_machine_id()

    # 2. Check Internet / Server Connectivity
    if not check_internet_connection():
        return False, "Internet connection is required to verify and activate subscription online. Please connect to the internet and try again."

    # 3. Request Verification from Central Cloud License Server
    try:
        import json as _json
        import urllib.request as _req
        from license_sync import get_cloud_server_url
        cloud_url = get_cloud_server_url()
        activate_endpoint = f"{cloud_url}/api/v1/outlet/activate-key"

        payload_bytes = _json.dumps({
            'key': clean_k,
            'machine_id': machine_id
        }).encode('utf-8')

        request_obj = _req.Request(
            activate_endpoint,
            data=payload_bytes,
            headers={'Content-Type': 'application/json', 'User-Agent': 'MPI-Billing-App/1.0'},
            method='POST'
        )

        with _req.urlopen(request_obj, timeout=8) as resp:
            resp_data = _json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return False, f"Could not reach cloud activation server: {str(e)}"

    # 4. Handle Server Response Contract
    # { "valid": true/false, "already_used": true/false, "expires_at": "YYYY-MM-DD", "message": "..." }
    is_valid = resp_data.get('valid') is True or resp_data.get('status') == 'ok'
    already_used = resp_data.get('already_used') is True
    server_msg = resp_data.get('message') or ("Key verified and activated!" if is_valid else "Invalid activation key")

    if not is_valid or already_used:
        return False, server_msg

    exp_str = str(resp_data.get('expires_at') or (date.today() + timedelta(days=SUBSCRIPTION_DAYS)))[:10]
    act_str = str(date.today())

    try:
        exp_dt = datetime.strptime(exp_str, "%Y-%m-%d").date()
        grace_str = str(exp_dt + timedelta(days=GRACE_PERIOD_DAYS))
    except Exception:
        grace_str = exp_str

    # 5. Store Activated License & Update Local Database
    lic_payload = {
        'key': clean_k,
        'activated_at': act_str,
        'expires_at': exp_str,
        'grace_expires_at': grace_str,
        'machine_id': machine_id,
        'subscription_days': SUBSCRIPTION_DAYS
    }

    conn = get_db()
    row_used = conn.execute("SELECT value FROM shop_settings WHERE key = 'used_keys_json'").fetchone()
    used_keys = []
    if row_used and row_used['value']:
        try:
            used_keys = _json.loads(row_used['value'])
        except Exception:
            used_keys = []

    if clean_k not in used_keys:
        used_keys.append(clean_k)

    conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('active_license_json', ?)", (_json.dumps(lic_payload),))
    conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('used_keys_json', ?)", (_json.dumps(used_keys),))
    conn.commit()
    conn.close()

    return True, server_msg
