"""
cloud_backup.py — Automatic 6-Hour Cloud Database Backup Module
Meat Products of India — Billing & Inventory Management App

Performs automated compressed SQLite database backups every 6 hours when connected online
and uploads them securely to the Central License Server.
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
    with open(zip_path, 'rb') as f:
        body.append(f.read())

    body.append(f"--{boundary}--".encode('utf-8'))
    body.append(b'')

    data_payload = b"\r\n".join(body)

    try:
        req = urllib.request.Request(
            upload_url,
            data=data_payload,
            headers={
                'Content-Type': f'multipart/form-data; boundary={boundary}',
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

    return success, upload_msg

def _backup_loop():
    """Background thread loop running every 6 hours."""
    # Wait 10 seconds after app boot before first backup attempt
    time.sleep(10)
    while True:
        try:
            run_cloud_backup_job()
        except Exception as e:
            print(f"[Cloud Backup Error] {e}")
        time.sleep(BACKUP_INTERVAL_SECONDS)

def start_cloud_backup_scheduler():
    """Start the 6-hour background backup scheduler daemon thread."""
    t = threading.Thread(target=_backup_loop, daemon=True)
    t.start()
    return t
