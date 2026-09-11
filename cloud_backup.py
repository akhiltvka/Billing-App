"""
cloud_backup.py — Automatic 6-Hour Cloud Database Disaster Recovery Backup Module
Meat Products of India — Billing & Inventory Management App

Performs automated compressed SQLite database backups every 6 hours when connected online
and uploads them securely to the Central License Server.

DISASTER RECOVERY ARCHITECTURE NOTE:
This module backs up the entire local SQLite database (meatshop.db) as an encrypted,
point-in-time disaster-recovery snapshot to the Central License Server.

This backup is completely separate from, and operates in addition to, the Supabase PostgreSQL
sync handled by `sync_worker.py`:
1. Disaster Recovery Snapshots (`cloud_backup.py`): Creates full binary snapshots of the local
   SQLite file for point-in-time recovery, whole-database rollbacks, machine migration, and
   offline operational recovery.
2. Near-Real-Time Cloud Mirror (`sync_worker.py`): Performs continuous row-level mirroring of
   transactional tables into Supabase PostgreSQL for live cloud reporting, multi-terminal
   aggregation, and real-time remote visibility.

Both mechanisms serve distinct, vital purposes and must be maintained concurrently.
"""

import os
import zipfile
import time
import json
import threading
import urllib.request
from datetime import datetime
from database import DB_PATH
from license_manager import get_machine_id, check_internet_connection
from license_sync import get_cloud_server_url
from cryptography.fernet import Fernet

# Backup interval: 6 hours (21,600 seconds)
BACKUP_INTERVAL_SECONDS = 6 * 3600

def create_compressed_db_backup():
    """Create a compressed .zip copy of the SQLite database in data/backups/."""
    if not os.path.exists(DB_PATH):
        return None, "Database file does not exist."

    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"meatshop_cloud_auto_{timestamp}.zip"
    zip_path = os.path.join(backup_dir, zip_filename)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(DB_PATH, arcname="meatshop.db")
        return zip_path, "Compression successful"
    except Exception as e:
        return None, f"Failed to compress database: {str(e)}"

def upload_backup_to_cloud(zip_path):
    """Upload zip backup file to Central License Server via multipart HTTP POST."""
    if not os.path.exists(zip_path):
        return False, "Zip file not found."

    server_url = get_cloud_server_url()
    upload_url = f"{server_url}/api/v1/outlet/upload-backup"
    machine_id = get_machine_id()
    upload_token = os.environ.get('CLOUD_BACKUP_TOKEN', '').strip()
    if not upload_token:
        return False, "CLOUD_BACKUP_TOKEN is not configured."
    encryption_key = os.environ.get('CLOUD_BACKUP_ENCRYPTION_KEY', '').strip()
    if not encryption_key:
        return False, "CLOUD_BACKUP_ENCRYPTION_KEY is not configured."
    try:
        with open(zip_path, 'rb') as backup_file:
            encrypted_backup = Fernet(encryption_key.encode('ascii')).encrypt(backup_file.read())
    except Exception as exc:
        return False, f"Backup encryption failed: {exc}"

    boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
    body = []

    # Machine ID field
    body.append(f"--{boundary}".encode('utf-8'))
    body.append(f'Content-Disposition: form-data; name="machine_id"'.encode('utf-8'))
    body.append(b'')
    body.append(machine_id.encode('utf-8'))

    # File field
    filename = os.path.basename(zip_path)
    body.append(f"--{boundary}".encode('utf-8'))
    body.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode('utf-8'))
    body.append(b'Content-Type: application/zip')
    body.append(b'')
    body.append(encrypted_backup)

    body.append(f"--{boundary}--".encode('utf-8'))
    body.append(b'')

    data_payload = b"\r\n".join(body)

    try:
        req = urllib.request.Request(
            upload_url,
            data=data_payload,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}',
                'X-Backup-Token': upload_token,
                'User-Agent': 'MPI-Backup-Agent/1.0'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                res_json = json.loads(resp.read().decode('utf-8'))
                return True, res_json.get('message', 'Upload successful')
            return False, f"Server returned HTTP status {resp.status}"
    except Exception as e:
        return False, f"Upload request error: {str(e)}"

def get_backup_retention_settings():
    """Fetch backup retention configuration from shop_settings table, falling back to 30 days / 60 max files."""
    retention_days = 30
    max_files = 60
    try:
        from database import get_db
        conn = get_db()
        r_row = conn.execute("SELECT value FROM shop_settings WHERE key='backup_retention_days'").fetchone()
        m_row = conn.execute("SELECT value FROM shop_settings WHERE key='backup_max_files'").fetchone()
        conn.close()
        if r_row and r_row['value']:
            retention_days = int(r_row['value'])
        if m_row and m_row['value']:
            max_files = int(m_row['value'])
    except Exception:
        pass
    return retention_days, max_files


SAFETY_FLOOR_MIN_KEEP = 5

def get_uploaded_backup_filenames():
    """Return a set of zip_filenames that have successfully uploaded according to cloud_backup_history.json."""
    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    history_file = os.path.join(backup_dir, "cloud_backup_history.json")
    uploaded = set()
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                for entry in history:
                    if entry.get('success') is True and entry.get('zip_filename'):
                        uploaded.add(entry.get('zip_filename'))
        except Exception as e:
            print(f"[Cloud Backup] Could not read cloud_backup_history.json: {e}")
    return uploaded


def check_unuploaded_backup_warnings():
    """Check if backups are piling up un-uploaded past a threshold (3+ consecutive failed uploads) and warn/notify."""
    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    history_file = os.path.join(backup_dir, "cloud_backup_history.json")
    if not os.path.exists(history_file):
        return 0

    try:
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except Exception:
        return 0

    consecutive_failures = 0
    for entry in reversed(history):
        if entry.get('success') is True:
            break
        consecutive_failures += 1

    if consecutive_failures >= 3:
        msg = f"Cloud Backup Alert: {consecutive_failures} consecutive backup uploads have failed or are pending. Please verify internet connection to ensure offsite backup coverage."
        print(f"[Cloud Backup Warning] {msg}")
        try:
            from database import get_db
            conn = get_db()
            # Check for existing unread warning within the last 1 day to prevent notification flooding
            existing = conn.execute('''
                SELECT id FROM notifications
                WHERE title = 'Cloud Backup Warning'
                  AND read = 0
                  AND created_at >= datetime('now', '-1 day')
            ''').fetchone()

            if existing:
                conn.execute('''
                    UPDATE notifications
                    SET message = ?, created_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (msg, existing['id']))
            else:
                conn.execute('''
                    INSERT INTO notifications (target_role, title, message)
                    VALUES ('admin', 'Cloud Backup Warning', ?)
                ''', (msg,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[Cloud Backup Notification Error] {e}")

    return consecutive_failures


def prune_old_backups(retention_days=None, max_files=None, min_keep=SAFETY_FLOOR_MIN_KEEP):
    """
    Delete compressed backup files in data/backups/ matching 'meatshop_cloud_auto_*.zip'
    that are older than retention_days, or trim excess files down to max_files (oldest first).
    NEVER deletes any backup that has not been successfully uploaded to the cloud server,
    and always keeps at least `min_keep` (default 5) most recent backups on disk.
    Returns count of pruned files.
    """
    r_def, m_def = get_backup_retention_settings()
    if retention_days is None:
        retention_days = r_def
    if max_files is None:
        max_files = m_def

    backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    if not os.path.exists(backup_dir):
        return 0

    now = time.time()
    cutoff_time = now - (retention_days * 86400)
    pruned_count = 0

    try:
        file_paths = [
            os.path.join(backup_dir, f)
            for f in os.listdir(backup_dir)
            if f.startswith("meatshop_cloud_auto_") and f.endswith(".zip")
        ]
    except Exception as e:
        print(f"[Cloud Backup Prune Error] Could not access backup directory: {e}")
        return 0

    if not file_paths:
        return 0

    # Fetch set of zip filenames that were verified as successfully uploaded
    uploaded_files = get_uploaded_backup_filenames()

    # Collect with mtime and sort oldest -> newest
    files_with_mtime = []
    for fp in file_paths:
        try:
            files_with_mtime.append((fp, os.path.getmtime(fp)))
        except Exception:
            pass

    files_with_mtime.sort(key=lambda x: x[1])

    # Hard safety floor: always protect the newest min_keep files
    if len(files_with_mtime) <= min_keep:
        # Fewer or equal files than safety floor — do not prune anything
        return 0

    protected_newest = set(fp for fp, _ in files_with_mtime[-min_keep:])
    candidates = [(fp, mtime) for fp, mtime in files_with_mtime if fp not in protected_newest]

    remaining_after_age = []
    for filepath, mtime in candidates:
        fname = os.path.basename(filepath)
        # Never prune un-uploaded backups
        if fname not in uploaded_files:
            remaining_after_age.append((filepath, mtime))
            continue

        if mtime < cutoff_time:
            try:
                os.remove(filepath)
                pruned_count += 1
            except Exception as e:
                print(f"[Cloud Backup Prune Error] Could not delete old backup '{filepath}': {e}")
                remaining_after_age.append((filepath, mtime))
        else:
            remaining_after_age.append((filepath, mtime))

    # All surviving files = remaining_after_age + protected_newest
    all_surviving = remaining_after_age + [(fp, mt) for fp, mt in files_with_mtime if fp in protected_newest]
    all_surviving.sort(key=lambda x: x[1])

    # Trim excess files down to max_files (oldest first), respecting upload status & safety floor
    if len(all_surviving) > max_files:
        current_count = len(all_surviving)
        for filepath, _ in all_surviving:
            if current_count <= max_files:
                break
            if filepath in protected_newest:
                continue
            fname = os.path.basename(filepath)
            if fname not in uploaded_files:
                continue
            try:
                os.remove(filepath)
                pruned_count += 1
                current_count -= 1
            except Exception as e:
                print(f"[Cloud Backup Prune Error] Could not remove excess backup '{filepath}': {e}")

    print(f"[Cloud Backup Pruning] Pruned {pruned_count} old uploaded backup zip(s) (Retention: {retention_days} days, Max Files: {max_files}, Min Keep: {min_keep}).")
    return pruned_count


def run_cloud_backup_job():
    """Execute a single backup + upload cycle if online."""
    if not check_internet_connection():
        return False, "Offline: Internet connection not available."

    zip_path, msg = create_compressed_db_backup()
    if not zip_path:
        return False, msg

    success, upload_msg = upload_backup_to_cloud(zip_path)
    
    # Save log entry in cloud_backup_history.json
    log_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
    history_file = os.path.join(log_dir, "cloud_backup_history.json")
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
        except Exception:
            history = []

    history.append({
        'timestamp': datetime.now().isoformat(),
        'zip_filename': os.path.basename(zip_path),
        'file_size_bytes': os.path.getsize(zip_path) if os.path.exists(zip_path) else 0,
        'success': success,
        'message': upload_msg
    })
    
    # Keep last 50 history entries
    history = history[-50:]
    try:
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass

    # Check for unuploaded backups piling up and warn if needed
    try:
        check_unuploaded_backup_warnings()
    except Exception as e:
        print(f"[Cloud Backup Warning Check Error] {e}")

    # Run backup pruning after history is written
    try:
        prune_old_backups()
    except Exception as e:
        print(f"[Cloud Backup Prune Error] {e}")

    return success, upload_msg

def start_cloud_backup_scheduler():
    """
    Deprecated: The automated 6-hour periodic cloud upload loop has been retired
    in favor of near-real-time row synchronization with Supabase (sync_worker.py).
    """
    return None

