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
YEARLY_PRICE_INR = 5000

def get_machine_id():
    """Generate a deterministic 16-character hardware ID for single-outlet machine locking."""
    try:
        raw_id = f"{platform.node()}-{uuid.getnode()}-{platform.processor()}"
        return hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:16].upper()
    except Exception:
        return "DEFAULT-MACHINE-ID-01"

def check_internet_connection():
    """Verify active internet connectivity required for key activation."""
    endpoints = [
        "http://httpbin.org/ip",
        "https://1.1.1.1",
        "https://www.google.com"
    ]
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
    Validate a 12-digit alphanumeric key using HMAC signature & checksum verification.
    Key format: 12 uppercase chars [A-Z0-9]{12} (e.g. A9K2-M7W3-P4X8).
    First 8 chars = Payload, Last 4 chars = HMAC Signature Checksum.
    """
    clean = clean_key(raw_key_str)
    if len(clean) != 12:
        return False, "Activation key must be 12 alphanumeric characters (e.g. A9K2-M7W3-P4X8)"

    payload = clean[:8]
    checksum = clean[8:]

    expected_sig = hmac.new(
        LICENSE_SECRET_SALT.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()[:4].upper()

    if checksum != expected_sig:
        return False, "Invalid activation key signature"

    return True, "Key signature valid"

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
      - status: 'trial' | 'active' | 'grace' | 'expired'
      - days_left: int
      - is_locked: bool (True if expired & grace period over)
      - installed_at: string YYYY-MM-DD
      - activated_at: string YYYY-MM-DD or None
      - expires_at: string YYYY-MM-DD
      - grace_expires_at: string YYYY-MM-DD
      - active_key: string or None
      - machine_id: string
      - price_inr: 5000
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

    machine_id = get_machine_id()

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
            'upi_id': 'mpi.billing@upi',
            'upi_name': 'Meat Products of India Billing App'
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
            'upi_id': 'mpi.billing@upi',
            'upi_name': 'Meat Products of India Billing App'
        }

MASTER_DEVELOPER_KEY = "Revathyr@j6123"

def activate_subscription(raw_key_str):
    """
    Redeem a 12-digit activation key online OR Master Developer Secret Key offline.
    Extends subscription by 365 days + sets 10-day grace period.
    """
    raw_clean = (raw_key_str or '').strip()

    # ── 1. Check Master Developer Secret Key (100% Offline Activation) ───────
    if raw_clean == MASTER_DEVELOPER_KEY:
        today_dt = date.today()
        exp_dt = today_dt + timedelta(days=SUBSCRIPTION_DAYS)
        grace_exp_dt = exp_dt + timedelta(days=GRACE_PERIOD_DAYS)

        lic_payload = {
            'key': 'MASTER-DEV-OFFLINE-BYPASS',
            'activated_at': str(today_dt),
            'expires_at': str(exp_dt),
            'grace_expires_at': str(grace_exp_dt),
            'machine_id': get_machine_id(),
            'subscription_days': SUBSCRIPTION_DAYS
        }

        conn = get_db()
        import json
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('active_license_json', ?)", (json.dumps(lic_payload),))
        conn.commit()
        conn.close()

        return True, f"Master Developer Key Accepted! Subscription activated offline for 365 days until {str(exp_dt)}."

    # ── 2. Require Internet Connection for 12-Digit Key Online Verification ──
    if not check_internet_connection():
        return False, "Internet connection is required to verify and activate subscription online. Please connect to the internet and try again."

    # 2. Validate 12-digit Key Format & Signature
    valid, msg = verify_12digit_key(raw_key_str)
    if not valid:
        return False, msg

    clean_k = clean_key(raw_key_str)

    # 3. Check if key was already redeemed on this DB
    conn = get_db()
    row_used = conn.execute("SELECT value FROM shop_settings WHERE key = 'used_keys_json'").fetchone()
    import json
    used_keys = []
    if row_used and row_used['value']:
        try:
            used_keys = json.loads(row_used['value'])
        except Exception:
            used_keys = []

    if clean_k in used_keys:
        conn.close()
        return False, "This activation key has already been redeemed on this outlet."

    # 4. Calculate subscription dates (365 days active + 10 days grace)
    today_dt = date.today()
    exp_dt = today_dt + timedelta(days=SUBSCRIPTION_DAYS)
    grace_exp_dt = exp_dt + timedelta(days=GRACE_PERIOD_DAYS)

    lic_payload = {
        'key': clean_k,
        'activated_at': str(today_dt),
        'expires_at': str(exp_dt),
        'grace_expires_at': str(grace_exp_dt),
        'machine_id': get_machine_id(),
        'subscription_days': SUBSCRIPTION_DAYS
    }

    used_keys.append(clean_k)

    conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('active_license_json', ?)", (json.dumps(lic_payload),))
    conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('used_keys_json', ?)", (json.dumps(used_keys),))
    conn.commit()
    conn.close()

    return True, f"Subscription successfully activated! Valid for 365 days until {str(exp_dt)}."
