"""Regression tests for reversal-first bill correction controls."""

import unittest

from app import app, get_db


class TestBillPurgeSecurity(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('allow_bill_purge', 'false')")
        conn.commit()
        conn.close()

    def tearDown(self):
        conn = get_db()
        conn.execute("DELETE FROM shop_settings WHERE key='allow_bill_purge'")
        conn.commit()
        conn.close()

    def test_permanent_purge_is_disabled_by_default(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['username'] = 'test-admin'
            session['user_role'] = 'admin'

        response = self.client.delete('/api/bills/999999/purge')
        self.assertEqual(response.status_code, 403)
        self.assertIn('Cancel the bill instead', response.get_json()['message'])

    def test_purge_requires_reason_when_explicitly_enabled(self):
        conn = get_db()
        conn.execute("UPDATE shop_settings SET value='true' WHERE key='allow_bill_purge'")
        conn.commit()
        conn.close()

        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['username'] = 'test-admin'
            session['user_role'] = 'admin'

        response = self.client.delete('/api/bills/999999/purge', json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn('deletion reason is required', response.get_json()['message'])


if __name__ == '__main__':
    unittest.main()
