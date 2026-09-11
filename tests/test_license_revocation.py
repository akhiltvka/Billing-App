"""
Unit & Regression Test Suite for Cloud License 403 Revocation Handling
"""

import unittest
import json
import os
import sys
import io
import urllib.error
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db
from license_manager import get_license_info
from license_sync import sync_with_cloud_server


class TestLicenseRevocation(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key'

        # Ensure database is clean before each test
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_revoked', '0')")
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_needs_reregister', '0')")
        
        # Ensure a test product and admin user exist
        conn.execute("""
            INSERT OR REPLACE INTO products (id, name, code, selling_price, purchase_price, current_stock, active)
            VALUES (1, 'Test Chicken Curry Cut', 'T1001', 250.0, 180.0, 100.0, 1)
        """)
        conn.execute("DELETE FROM users WHERE username='test_admin_user'")
        conn.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_admin_user', 'dummy_hash', 'Test Admin', 'admin', 1, 1)
        """)
        self.admin_id = conn.execute("SELECT id FROM users WHERE username='test_admin_user'").fetchone()['id']
        conn.commit()
        conn.close()

    def tearDown(self):
        # Restore revocation flag to 0
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_revoked', '0')")
        conn.commit()
        conn.close()

    def test_get_license_info_returns_revoked_status_when_flag_is_1(self):
        """When shop_settings outlet_revoked is '1', get_license_info() must return status 'revoked' and is_locked True."""
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_revoked', '1')")
        conn.commit()
        conn.close()

        lic = get_license_info()
        self.assertEqual(lic['status'], 'revoked')
        self.assertTrue(lic['is_locked'])
        self.assertEqual(lic['days_left'], 0)

    def test_create_bill_blocked_with_403_when_outlet_is_revoked(self):
        """create_bill() route must block bill creation with HTTP 403 when outlet is revoked."""
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_revoked', '1')")
        conn.commit()
        conn.close()

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_admin_user'
            sess['user_role'] = 'admin'

        payload = {
            "customer_name": "Walk-in Customer",
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Test Chicken Curry Cut",
                    "quantity": 1,
                    "unit_price": 250.0,
                    "gst_rate": 0
                }
            ],
            "payment_mode": "cash"
        }

        response = self.client.post('/api/bills',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'error')
        self.assertIn("revoked", data.get('message', '').lower())

    @patch('database.get_database_url', return_value=None)
    @patch('urllib.request.urlopen')
    def test_sync_with_cloud_server_persists_403_revocation(self, mock_urlopen, mock_get_url):
        """When cloud server returns HTTP 403, sync_with_cloud_server() must set outlet_revoked = '1' and return False."""
        error_body = json.dumps({
            "status": "error",
            "message": "Outlet registration has been terminated by developer portal"
        }).encode('utf-8')

        http_err = urllib.error.HTTPError(
            url="http://test-server/api/v1/outlet/ping",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=io.BytesIO(error_body)
        )
        mock_urlopen.side_effect = http_err

        success, message = sync_with_cloud_server()

        self.assertFalse(success)
        self.assertIn("OUTLET_REVOKED", message)
        self.assertIn("Outlet registration has been terminated", message)

        # Verify database flag was persisted
        conn = get_db()
        row = conn.execute("SELECT value FROM shop_settings WHERE key = 'outlet_revoked'").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['value'], '1')

        # Verify get_license_info() now reflects revoked state
        lic = get_license_info()
        self.assertEqual(lic['status'], 'revoked')
        self.assertTrue(lic['is_locked'])

    def test_sync_license_with_supabase_and_razorpay_link(self):
        """sync_license_with_supabase() updates local status and razorpay_payment_link."""
        mock_pg_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_pg_conn.__enter__.return_value = mock_pg_conn
        mock_pg_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (
            'active', '2026-01-01', '2027-01-01', '2027-01-11', 'https://rzp.io/l/custom-link', 12000.00
        )
        with patch('database.get_database_url', return_value='postgresql://test:test@localhost:5432/test'):
            with patch('psycopg2.connect', return_value=mock_pg_conn):
                from license_manager import sync_license_with_supabase
                success, msg = sync_license_with_supabase()
                self.assertTrue(success)

        lic = get_license_info()
        self.assertEqual(lic['status'], 'active')
        self.assertEqual(lic['razorpay_payment_link'], 'https://rzp.io/l/custom-link')


if __name__ == '__main__':
    unittest.main()

