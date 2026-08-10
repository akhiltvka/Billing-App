"""
Regression Test Suite for External Backup Route Security & UNC Path Validation
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db
from external_backup import is_drive_connected


class TestExternalBackupSecurity(unittest.TestCase):

    def _cleanup_test_data(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username IN ('test_ext_admin', 'test_ext_staff')")
        conn.commit()
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_ext_sec_key'

        self._cleanup_test_data()

        conn = get_db()
        cursor = conn.cursor()

        # Seed admin user
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_ext_admin', 'dummy_hash', 'Ext Admin', 'admin', 1, 1)
        """)
        self.admin_id = cursor.lastrowid

        # Seed counter_staff user (no backup.manage permission)
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_ext_staff', 'dummy_hash', 'Ext Staff', 'counter_staff', 4, 1)
        """)
        self.staff_id = cursor.lastrowid

        conn.commit()
        conn.close()

    def tearDown(self):
        self._cleanup_test_data()

    def test_unauthenticated_requests_return_401(self):
        """All three external backup endpoints must return 401 when accessed without an authenticated session."""
        # 1. GET /api/backup/external/status
        res1 = self.client.get('/api/backup/external/status')
        self.assertEqual(res1.status_code, 401, "Unauthenticated GET /api/backup/external/status must return 401")

        # 2. POST /api/backup/external/config
        res2 = self.client.post('/api/backup/external/config',
                                data=json.dumps({"enabled": True, "path": "D:\\backups"}),
                                content_type='application/json')
        self.assertEqual(res2.status_code, 401, "Unauthenticated POST /api/backup/external/config must return 401")

        # 3. POST /api/backup/external/test
        res3 = self.client.post('/api/backup/external/test')
        self.assertEqual(res3.status_code, 401, "Unauthenticated POST /api/backup/external/test must return 401")

    def test_unprivileged_role_returns_403(self):
        """Users without backup.manage permission must be rejected with 403."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.staff_id
            sess['username'] = 'test_ext_staff'
            sess['user_role'] = 'counter_staff'

        res1 = self.client.get('/api/backup/external/status')
        self.assertEqual(res1.status_code, 403)

        res2 = self.client.post('/api/backup/external/config',
                                data=json.dumps({"enabled": True, "path": "D:\\backups"}),
                                content_type='application/json')
        self.assertEqual(res2.status_code, 403)

        res3 = self.client.post('/api/backup/external/test')
        self.assertEqual(res3.status_code, 403)

    def test_authorized_admin_can_access_status(self):
        """Admin users with backup.manage permission can successfully access external backup routes."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_ext_admin'
            sess['user_role'] = 'admin'

        res = self.client.get('/api/backup/external/status')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')

    def test_unc_path_rejected_by_default(self):
        r"""UNC paths (e.g. \\attacker-server\share) must be rejected unless allow_network is explicitly set."""
        # Direct check on is_drive_connected
        connected, msg = is_drive_connected(r"\\attacker-server\share", allow_network=False)
        self.assertFalse(connected)
        self.assertIn("UNC network paths are rejected", msg)

        # Route check via POST /api/backup/external/config
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_ext_admin'
            sess['user_role'] = 'admin'

        res = self.client.post('/api/backup/external/config',
                                data=json.dumps({
                                    "enabled": True,
                                    "path": r"\\attacker-server\share",
                                    "allow_network": False
                                }),
                                content_type='application/json')
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data.decode('utf-8'))
        self.assertIn("UNC network paths are rejected", data.get('message', ''))


if __name__ == '__main__':
    unittest.main()
