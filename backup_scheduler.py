"""
backup_scheduler.py — Daily Database Backup & Retention Script
Meat Products of India — Billing & Inventory App
"""
import os
import sqlite3
from datetime import datetime, timedelta

from database import DB_PATH

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')
RETENTION_DAYS = 30

def run_backup():
    if not os.path.exists(DB_PATH):
        print(f"[{datetime.now()}] ERROR: Source database file not found at {DB_PATH}")
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest_filename = f"meatshop_backup_{ts}.db"
    dest_path = os.path.join(BACKUP_DIR, dest_filename)

    try:
        source_conn = sqlite3.connect(DB_PATH, timeout=15)
        source_conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')

        dest_conn = sqlite3.connect(dest_path)
        with dest_conn:
            source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()

        # Verify integrity of the backup file
        chk_conn = sqlite3.connect(dest_path)
        res = chk_conn.execute('PRAGMA integrity_check').fetchone()
        chk_conn.close()

        if not res or res[0] != 'ok':
            raise RuntimeError(f"Integrity check failed: {res}")

        print(f"[{datetime.now()}] SUCCESS: Backup created & verified (integrity: ok) -> {dest_path}")
    except Exception as e:
        print(f"[{datetime.now()}] ERROR: Backup creation failed: {e}")
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        return

    # Retention cleanup: Delete backups older than 30 days
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted_count = 0
    for fname in os.listdir(BACKUP_DIR):
        if fname.startswith("meatshop_backup_") and fname.endswith(".db"):
            fpath = os.path.join(BACKUP_DIR, fname)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    os.remove(fpath)
                    deleted_count += 1
                    print(f"[{datetime.now()}] CLEANUP: Removed old backup {fname}")
            except Exception as e:
                print(f"[{datetime.now()}] ERROR: Failed to check/delete {fname}: {e}")

    print(f"[{datetime.now()}] Retention check complete. Cleaned up {deleted_count} old file(s).")

if __name__ == '__main__':
    run_backup()
