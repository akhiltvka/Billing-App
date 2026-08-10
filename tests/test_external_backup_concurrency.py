"""
Regression Test Suite for External Backup Concurrency, Throttling & Collision Prevention
"""

import unittest
import json
import os
import sys
import time
import tempfile
import threading

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db
import external_backup
from external_backup import (
    perform_external_backup,
    trigger_external_backup_async,
    STATUS_FILE_PATH
)


class TestExternalBackupConcurrency(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backup_target = self.temp_dir.name

        # Enable external backup pointing to temp directory
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('external_backup_enabled', 'true')")
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('external_backup_path', ?)", (self.backup_target,))
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('external_backup_retention_days', '30')")
        conn.commit()
        conn.close()

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_concurrent_manual_backups_produce_valid_json_and_unique_files(self):
        """Concurrent multi-threaded backups must create collision-free files and maintain valid JSON in status file."""
        results = []
        threads = []
        num_threads = 8

        def worker():
            res = perform_external_backup(is_manual=True)
            results.append(res)

        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All 8 manual runs should succeed
        self.assertEqual(len(results), num_threads)
        for success, msg in results:
            self.assertTrue(success, f"Backup worker failed: {msg}")

        # Check status file is valid, uncorrupted JSON
        self.assertTrue(os.path.exists(STATUS_FILE_PATH), "Status file must exist")
        with open(STATUS_FILE_PATH, 'r', encoding='utf-8') as f:
            status = json.load(f)

        self.assertIsInstance(status, dict)
        self.assertTrue(status.get('is_connected'))
        self.assertTrue(status.get('last_backup_success'))
        self.assertIn("Backup saved successfully", status.get('last_backup_message', ''))

        # Check all 8 distinct backup files exist in target directory (no collisions)
        backup_files = [f for f in os.listdir(self.backup_target) if f.startswith("meatshop_ext_backup_") and f.endswith(".db")]
        self.assertEqual(len(backup_files), num_threads, f"Expected {num_threads} unique backup files, found {len(backup_files)}")

    def test_throttle_skips_automatic_runs_but_allows_manual_runs(self):
        """Automatic backup triggers must be throttled if called too soon, while manual runs bypass the throttle."""
        # Set last backup time to current time
        external_backup._last_backup_attempt_time = time.time()

        # Automatic run within 300s throttle window should be skipped
        success, msg = perform_external_backup(is_manual=False, throttle_seconds=300)
        self.assertFalse(success)
        self.assertIn("Throttled", msg)

        # Manual run must bypass throttle and succeed immediately
        manual_success, manual_msg = perform_external_backup(is_manual=True)
        self.assertTrue(manual_success, f"Manual backup should bypass throttle: {manual_msg}")


if __name__ == '__main__':
    unittest.main()
