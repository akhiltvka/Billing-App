"""
external_backup.py — Real-Time External Drive Backup Module
Meat Products of India — Billing & Inventory App

Handles real-time database backups to user-selected external USB drives or network drives,
monitors drive connectivity, manages retention, and tracks backup status.
"""

import os
import sys
import time
import json
import uuid
import sqlite3
import threading
from datetime import datetime, timedelta
from database import DB_PATH, get_db

STATUS_FILE_DIR = os.path.dirname(DB_PATH)
STATUS_FILE_PATH = os.path.join(STATUS_FILE_DIR, "external_backup_status.json")
_backup_lock = threading.Lock()
_status_lock = threading.Lock()
_last_backup_attempt_time = 0.0
DEFAULT_THROTTLE_SECONDS = 300  # 5 minutes


def get_available_drives():
    """Detect available drives with drive letter, label, and free space info."""
    import shutil
    drives = []
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            bitmask = kernel32.GetLogicalDrives()
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                if bitmask & 1:
                    drive_path = f"{letter}:\\"
                    if os.path.exists(drive_path):
                        label = "Drive"
                        try:
                            v_buf = ctypes.create_unicode_buffer(1024)
                            fs_buf = ctypes.create_unicode_buffer(1024)
                            kernel32.GetVolumeInformationW(
                                ctypes.c_wchar_p(drive_path),
                                v_buf, ctypes.sizeof(v_buf),
                                None, None, None,
                                fs_buf, ctypes.sizeof(fs_buf)
                            )
                            label = v_buf.value or ("Local Disk" if letter in "CD" else "Removable Drive")
                        except Exception:
                            pass

                        free_str = ""
                        try:
                            _, _, free = shutil.disk_usage(drive_path)
                            free_gb = round(free / (1024**3), 1)
                            free_str = f"{free_gb} GB free"
                        except Exception:
                            pass

                        display_name = f"{letter}:\\ ({label}" + (f" - {free_str})" if free_str else ")")
                        drives.append({
                            'path': drive_path,
                            'letter': f"{letter}:",
                            'label': label,
                            'free_str': free_str,
                            'display': display_name
                        })
                bitmask >>= 1
        except Exception:
            for letter in 'EFGHIJKLMNOPQRSTUVWXYZ':
                drive_path = f"{letter}:\\"
                if os.path.exists(drive_path):
                    drives.append({
                        'path': drive_path,
                        'letter': f"{letter}:",
                        'label': 'Drive',
                        'display': f"{letter}:\\"
                    })
    else:
        for root_dir in ['/media', '/Volumes', '/mnt']:
            if os.path.exists(root_dir):
                try:
                    for entry in os.listdir(root_dir):
                        full_p = os.path.join(root_dir, entry)
                        if os.path.isdir(full_p):
                            drives.append({
                                'path': full_p,
                                'display': full_p
                            })
                except Exception:
                    pass
    return drives


def get_external_backup_settings():
    """Fetch external backup settings from shop_settings table."""
    enabled = False
    path = ""
    retention_days = 30
    allow_network = False

    try:
        conn = get_db()
        r_enabled = conn.execute("SELECT value FROM shop_settings WHERE key='external_backup_enabled'").fetchone()
        r_path = conn.execute("SELECT value FROM shop_settings WHERE key='external_backup_path'").fetchone()
        r_retention = conn.execute("SELECT value FROM shop_settings WHERE key='external_backup_retention_days'").fetchone()
        r_network = conn.execute("SELECT value FROM shop_settings WHERE key='external_backup_allow_network'").fetchone()
        conn.close()

        if r_enabled and r_enabled['value'] and r_enabled['value'].lower() == 'true':
            enabled = True
        if r_path and r_path['value']:
            path = r_path['value'].strip()
        if r_retention and r_retention['value']:
            try:
                retention_days = int(r_retention['value'])
            except ValueError:
                pass
        if r_network and r_network['value'] and r_network['value'].lower() == 'true':
            allow_network = True
    except Exception as e:
        print(f"[External Backup Settings Error] {e}")

    return {
        'enabled': enabled,
        'path': path,
        'retention_days': retention_days,
        'allow_network': allow_network
    }


def is_drive_connected(target_path, allow_network=False):
    """Check if target external drive path exists and is accessible for writing."""
    if not target_path or not target_path.strip():
        return False, "Target path is empty."

    target_path = target_path.strip()

    # Reject UNC paths (\\server\share or //server/share) unless network drive backups are explicitly opted in
    if (target_path.startswith(r'\\') or target_path.startswith('//')) and not allow_network:
        return False, "UNC network paths are rejected unless network drive backups are explicitly enabled."

    # Check root drive letter if on Windows (e.g. "E:\" or "E:")
    drive_root = os.path.splitdrive(target_path)[0]
    if drive_root and not drive_root.endswith('\\') and not drive_root.endswith('/'):
        drive_root += '\\'

    if drive_root and not os.path.exists(drive_root):
        return False, f"External drive root '{drive_root}' is not connected."

    try:
        if not os.path.exists(target_path):
            os.makedirs(target_path, exist_ok=True)

        test_file = os.path.join(target_path, f".mpi_write_test_{uuid.uuid4().hex}.tmp")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return True, "Drive is connected and writable."
    except Exception as e:
        return False, f"Drive write error: {str(e)}"


def get_external_backup_throttle_seconds():
    """Read configured throttle interval in seconds, defaulting to 300s (5 minutes)."""
    try:
        conn = get_db()
        r = conn.execute("SELECT value FROM shop_settings WHERE key='external_backup_throttle_minutes'").fetchone()
        conn.close()
        if r and r['value']:
            return max(10, int(float(r['value']) * 60))
    except Exception:
        pass
    return DEFAULT_THROTTLE_SECONDS


def update_status_file(is_connected, message, success=None, backup_file=None):
    """Persist status information to status JSON file atomically for API/UI polling."""
    with _status_lock:
        status_data = {}
        if os.path.exists(STATUS_FILE_PATH):
            try:
                with open(STATUS_FILE_PATH, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
            except Exception:
                status_data = {}

        try:
            settings = get_external_backup_settings()
        except Exception:
            settings = {'enabled': False, 'path': '', 'retention_days': 30, 'allow_network': False}

        status_data['enabled'] = settings['enabled']
        status_data['path'] = settings['path']
        status_data['is_connected'] = is_connected
        status_data['message'] = message
        status_data['last_check_time'] = datetime.now().isoformat()

        if success is not None:
            status_data['last_backup_success'] = success
            status_data['last_backup_time'] = datetime.now().isoformat()
            status_data['last_backup_message'] = message
            if backup_file:
                status_data['last_backup_file'] = backup_file

        tmp_file = f"{STATUS_FILE_PATH}.tmp.{uuid.uuid4().hex}"
        try:
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2)
            os.replace(tmp_file, STATUS_FILE_PATH)
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            print(f"[External Backup Status Save Error] {e}")


def prune_external_backups(target_dir, retention_days=30):
    """Delete backups on external drive older than retention_days."""
    if not os.path.exists(target_dir):
        return 0

    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted_count = 0

    try:
        for fname in os.listdir(target_dir):
            if fname.startswith("meatshop_ext_backup_") and fname.endswith(".db"):
                fpath = os.path.join(target_dir, fname)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                    if mtime < cutoff:
                        os.remove(fpath)
                        deleted_count += 1
                except Exception:
                    pass
    except Exception as e:
        print(f"[External Backup Prune Error] {e}")

    return deleted_count


def perform_external_backup(is_manual=False, throttle_seconds=None):
    """
    Executes database backup to configured external drive using sqlite3 backup API.
    Thread-safe & non-blocking for caller.
    """
    global _last_backup_attempt_time

    settings = get_external_backup_settings()
    if not settings['enabled'] and not is_manual:
        return False, "External drive backup is disabled."

    if not is_manual:
        limit = throttle_seconds if throttle_seconds is not None else get_external_backup_throttle_seconds()
        now = time.time()
        if (now - _last_backup_attempt_time) < limit:
            return False, f"Throttled: last backup was within {int(limit)} seconds."

    target_path = settings['path']
    if not target_path:
        msg = "No external drive path configured."
        update_status_file(False, msg, success=False)
        return False, msg

    connected, conn_msg = is_drive_connected(target_path, allow_network=settings.get('allow_network', False))
    if not connected:
        update_status_file(False, conn_msg, success=False)
        return False, conn_msg

    if not os.path.exists(DB_PATH):
        msg = f"Source database file not found at {DB_PATH}"
        update_status_file(True, msg, success=False)
        return False, msg

    with _backup_lock:
        _last_backup_attempt_time = time.time()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rand_suffix = uuid.uuid4().hex[:6]
        dest_filename = f"meatshop_ext_backup_{timestamp}_{rand_suffix}.db"
        dest_filepath = os.path.join(target_path, dest_filename)

        try:
            src_conn = sqlite3.connect(DB_PATH, timeout=10)
            dst_conn = sqlite3.connect(dest_filepath)

            with dst_conn:
                src_conn.backup(dst_conn)

            dst_conn.close()
            src_conn.close()

            pruned = prune_external_backups(target_path, settings['retention_days'])

            msg = f"Backup saved successfully to {dest_filename} (Pruned {pruned} old file(s))."
            update_status_file(True, msg, success=True, backup_file=dest_filepath)
            return True, msg

        except Exception as e:
            msg = f"Backup failed: {str(e)}"
            update_status_file(True, msg, success=False)
            return False, msg


def trigger_external_backup_async(throttle_seconds=None):
    """Trigger external backup in a background thread with throttle check so UI calls never block."""
    global _last_backup_attempt_time
    settings = get_external_backup_settings()
    if not settings['enabled']:
        return

    limit = throttle_seconds if throttle_seconds is not None else get_external_backup_throttle_seconds()
    now = time.time()
    if (now - _last_backup_attempt_time) < limit:
        return

    t = threading.Thread(
        target=perform_external_backup,
        kwargs={'is_manual': False, 'throttle_seconds': limit},
        daemon=True
    )
    t.start()


def get_external_backup_status():
    """Retrieve external backup status for UI / API endpoints."""
    settings = get_external_backup_settings()
    target_path = settings['path']
    connected, conn_msg = is_drive_connected(target_path, allow_network=settings.get('allow_network', False)) if target_path else (False, "No path configured.")

    status_data = {
        'enabled': settings['enabled'],
        'path': target_path,
        'retention_days': settings['retention_days'],
        'allow_network': settings.get('allow_network', False),
        'is_connected': connected,
        'connection_message': conn_msg,
        'available_drives': get_available_drives(),
        'last_backup_time': None,
        'last_backup_success': None,
        'last_backup_message': None,
        'last_backup_file': None
    }

    if os.path.exists(STATUS_FILE_PATH):
        try:
            with open(STATUS_FILE_PATH, 'r') as f:
                saved = json.load(f)
                status_data['last_backup_time'] = saved.get('last_backup_time')
                status_data['last_backup_success'] = saved.get('last_backup_success')
                status_data['last_backup_message'] = saved.get('last_backup_message')
                status_data['last_backup_file'] = saved.get('last_backup_file')
        except Exception:
            pass

    return status_data
