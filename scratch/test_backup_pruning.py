import sys
import os
import time
import unittest
import tempfile
import sqlite3

# Set environment DB_PATH to a temporary DB
tmp_db_fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(tmp_db_fd)
os.environ['DB_PATH'] = tmp_db_path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import database
import cloud_backup

class TestBackupPruning(unittest.TestCase):
    def setUp(self):
        database.init_db()
        self.backup_dir = os.path.join(os.path.dirname(tmp_db_path), "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        # Clear existing backup files in temp directory
        for f in os.listdir(self.backup_dir):
            if f.startswith("meatshop_cloud_auto_"):
                try: os.remove(os.path.join(self.backup_dir, f))
                except Exception: pass

    def test_01_prune_files_older_than_retention_days(self):
        now = time.time()
        # Create file 40 days old (older than default 30 days)
        old_file = os.path.join(self.backup_dir, "meatshop_cloud_auto_20260101_100000.zip")
        with open(old_file, "w") as f:
            f.write("old data")
        os.utime(old_file, (now - 40 * 86400, now - 40 * 86400))

        # Create file 5 days old (should be kept)
        fresh_file = os.path.join(self.backup_dir, "meatshop_cloud_auto_20260729_100000.zip")
        with open(fresh_file, "w") as f:
            f.write("fresh data")
        os.utime(fresh_file, (now - 5 * 86400, now - 5 * 86400))

        pruned = cloud_backup.prune_old_backups(retention_days=30, max_files=60)
        self.assertEqual(pruned, 1)
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.exists(fresh_file))

    def test_02_prune_excess_files_over_max_files(self):
        now = time.time()
        created_files = []
        # Create 10 files all under 30 days old
        for i in range(10):
            fp = os.path.join(self.backup_dir, f"meatshop_cloud_auto_20260801_{i:02d}0000.zip")
            with open(fp, "w") as f:
                f.write(f"data {i}")
            mtime = now - (10 - i) * 3600  # spaced 1 hour apart
            os.utime(fp, (mtime, mtime))
            created_files.append(fp)

        # Prune with max_files=5 -> should remove 5 oldest files
        pruned = cloud_backup.prune_old_backups(retention_days=30, max_files=5)
        self.assertEqual(pruned, 5)

        # 5 oldest files should be deleted
        for fp in created_files[:5]:
            self.assertFalse(os.path.exists(fp))
        # 5 newest files should remain
        for fp in created_files[5:]:
            self.assertTrue(os.path.exists(fp))

    def test_03_db_settings_override(self):
        conn = database.get_db()
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('backup_retention_days', '15')")
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('backup_max_files', '3')")
        conn.commit()
        conn.close()

        r_days, m_files = cloud_backup.get_backup_retention_settings()
        self.assertEqual(r_days, 15)
        self.assertEqual(m_files, 3)

if __name__ == '__main__':
    unittest.main()
