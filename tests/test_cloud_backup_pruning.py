"""
Regression Test Suite for Cloud Backup Upload-Aware Pruning, Safety Floor & Outage Warnings
"""

import unittest
import json
import os
import sys
import time
import tempfile
import zipfile

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import cloud_backup
from cloud_backup import (
    prune_old_backups,
    get_uploaded_backup_filenames,
    check_unuploaded_backup_warnings
)
from database import get_db, DB_PATH


class TestCloudBackupPruning(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backup_dir = os.path.join(self.temp_dir.name, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

        # Mock DB_PATH directory for cloud_backup to use our temp backup dir
        self.orig_db_path = cloud_backup.DB_PATH
        cloud_backup.DB_PATH = os.path.join(self.temp_dir.name, "meatshop.db")

        # Clean notifications
        conn = get_db()
        conn.execute("DELETE FROM notifications WHERE title LIKE '%Cloud Backup Warning%'")
        conn.commit()
        conn.close()

    def tearDown(self):
        cloud_backup.DB_PATH = self.orig_db_path
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def _create_mock_zip(self, filename, age_days=0):
        filepath = os.path.join(self.backup_dir, filename)
        with zipfile.ZipFile(filepath, 'w') as zf:
            zf.writestr("dummy.txt", "backup content")
        if age_days > 0:
            mtime = time.time() - (age_days * 86400)
            os.utime(filepath, (mtime, mtime))
        return filepath

    def test_unuploaded_backups_never_pruned_despite_old_age_or_count(self):
        """Backups that failed upload or were never uploaded must NEVER be deleted during pruning."""
        # Create 8 old zip files (60 days old, well past 30 days retention)
        files = []
        for i in range(1, 9):
            fname = f"meatshop_cloud_auto_2026010{i}_120000.zip"
            files.append(self._create_mock_zip(fname, age_days=60 - i))

        # Record first 3 as successfully uploaded, and remaining 5 as failed (or unrecorded)
        history = [
            {"zip_filename": "meatshop_cloud_auto_20260101_120000.zip", "success": True},
            {"zip_filename": "meatshop_cloud_auto_20260102_120000.zip", "success": True},
            {"zip_filename": "meatshop_cloud_auto_20260103_120000.zip", "success": True},
            {"zip_filename": "meatshop_cloud_auto_20260104_120000.zip", "success": False},
            {"zip_filename": "meatshop_cloud_auto_20260105_120000.zip", "success": False},
            {"zip_filename": "meatshop_cloud_auto_20260106_120000.zip", "success": False},
            {"zip_filename": "meatshop_cloud_auto_20260107_120000.zip", "success": False},
            {"zip_filename": "meatshop_cloud_auto_20260108_120000.zip", "success": False},
        ]
        history_file = os.path.join(self.backup_dir, "cloud_backup_history.json")
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

        # Run pruning with retention_days=30, max_files=2, min_keep=2
        pruned_count = prune_old_backups(retention_days=30, max_files=2, min_keep=2)

        # The 5 un-uploaded files must STILL exist on disk!
        for i in range(4, 9):
            fname = f"meatshop_cloud_auto_2026010{i}_120000.zip"
            fpath = os.path.join(self.backup_dir, fname)
            self.assertTrue(os.path.exists(fpath), f"Un-uploaded backup '{fname}' should NOT have been pruned!")

    def test_safety_floor_preserves_minimum_backups(self):
        """Hard safety floor (min_keep=5) must ensure the 5 newest backups are kept even if all are old and uploaded."""
        for i in range(1, 6):
            self._create_mock_zip(f"meatshop_cloud_auto_2026010{i}_120000.zip", age_days=60)

        history = [{"zip_filename": f"meatshop_cloud_auto_2026010{i}_120000.zip", "success": True} for i in range(1, 6)]
        history_file = os.path.join(self.backup_dir, "cloud_backup_history.json")
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

        # Run pruning with aggressive retention (retention_days=30, max_files=1, min_keep=5)
        pruned = prune_old_backups(retention_days=30, max_files=1, min_keep=5)
        self.assertEqual(pruned, 0, "Safety floor min_keep=5 should prevent deleting any files when only 5 exist")

        surviving = [f for f in os.listdir(self.backup_dir) if f.endswith('.zip')]
        self.assertEqual(len(surviving), 5)

    def test_consecutive_failure_warning_alert_and_deduplication(self):
        """3+ consecutive failed backup uploads must trigger warning alert, and subsequent calls must update existing row without duplicating."""
        history = [
            {"zip_filename": "meatshop_cloud_auto_1.zip", "success": True},
            {"zip_filename": "meatshop_cloud_auto_2.zip", "success": False},
            {"zip_filename": "meatshop_cloud_auto_3.zip", "success": False},
            {"zip_filename": "meatshop_cloud_auto_4.zip", "success": False},
            {"zip_filename": "meatshop_cloud_auto_5.zip", "success": False},
        ]
        history_file = os.path.join(self.backup_dir, "cloud_backup_history.json")
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

        # 1. First invocation: 4 failures
        failures = check_unuploaded_backup_warnings()
        self.assertEqual(failures, 4)

        # Check exactly 1 notification in DB
        conn = get_db()
        notifs = conn.execute("SELECT * FROM notifications WHERE title = 'Cloud Backup Warning'").fetchall()
        self.assertEqual(len(notifs), 1)
        self.assertIn("4 consecutive backup uploads have failed", notifs[0]['message'])

        # 2. Second invocation: 5 failures (simulating another 6 hours of outage)
        history.append({"zip_filename": "meatshop_cloud_auto_6.zip", "success": False})
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

        failures2 = check_unuploaded_backup_warnings()
        self.assertEqual(failures2, 5)

        # Verify still exactly 1 notification (no duplicates) and message updated to 5 failures
        notifs2 = conn.execute("SELECT * FROM notifications WHERE title = 'Cloud Backup Warning'").fetchall()
        conn.close()

        self.assertEqual(len(notifs2), 1, "Should NOT create duplicate notifications during ongoing outage")
        self.assertIn("5 consecutive backup uploads have failed", notifs2[0]['message'])


if __name__ == '__main__':
    unittest.main()
