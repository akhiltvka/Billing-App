"""
Regression Test Suite for SQLite Online Backup in backup_scheduler.py
"""

import unittest
import os
import sys
import sqlite3
import time
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import DB_PATH
import backup_scheduler


class TestBackupScheduler(unittest.TestCase):

    def setUp(self):
        self.backup_dir = backup_scheduler.BACKUP_DIR
        os.makedirs(self.backup_dir, exist_ok=True)
        self.created_test_files = []

    def tearDown(self):
        for fpath in self.created_test_files:
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    def test_run_backup_creates_valid_sqlite_backup(self):
        """run_backup() must produce a valid SQLite database with PRAGMA integrity_check returning ok."""
        # Record time before backup
        t_before = time.time() - 2

        backup_scheduler.run_backup()

        # Find the newly created backup file
        newest_file = None
        newest_mtime = 0
        for fname in os.listdir(self.backup_dir):
            if fname.startswith("meatshop_backup_") and fname.endswith(".db"):
                fpath = os.path.join(self.backup_dir, fname)
                mtime = os.path.getmtime(fpath)
                if mtime >= t_before and mtime > newest_mtime:
                    newest_mtime = mtime
                    newest_file = fpath

        self.assertIsNotNone(newest_file, "Backup file should have been created")
        self.created_test_files.append(newest_file)

        # 1. Verify PRAGMA integrity_check on the created backup
        conn = sqlite3.connect(newest_file)
        integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
        self.assertIsNotNone(integrity_row)
        self.assertEqual(integrity_row[0], "ok")

        # 2. Verify schema and table contents in backup match source DB
        src_conn = sqlite3.connect(DB_PATH)
        src_count = src_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        src_conn.close()

        backup_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        conn.close()

        self.assertEqual(backup_count, src_count)

    def test_retention_cleanup_removes_old_backups(self):
        """run_backup() must prune backup files older than 30 days."""
        old_filename = "meatshop_backup_20200101_000000.db"
        old_filepath = os.path.join(self.backup_dir, old_filename)

        # Create a dummy old backup file
        with open(old_filepath, 'w', encoding='utf-8') as f:
            f.write("dummy sqlite header")

        # Set modification time to 40 days ago
        old_time = time.time() - (40 * 86400)
        os.utime(old_filepath, (old_time, old_time))
        self.created_test_files.append(old_filepath)

        self.assertTrue(os.path.exists(old_filepath))

        # Run backup which includes retention cleanup
        backup_scheduler.run_backup()

        # Verify old file was purged
        self.assertFalse(os.path.exists(old_filepath), "Old backup older than 30 days should have been purged")


if __name__ == '__main__':
    unittest.main()
