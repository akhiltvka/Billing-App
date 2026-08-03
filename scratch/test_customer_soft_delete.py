import sys
import os
import unittest
import tempfile
import sqlite3

# Set environment DB_PATH to a temporary DB
tmp_db_fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(tmp_db_fd)
os.environ['DB_PATH'] = tmp_db_path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import database
import app

class TestCustomerSoftDelete(unittest.TestCase):
    def setUp(self):
        database.init_db()
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['user_role'] = 'admin'

    def test_01_hard_delete_customer_without_bills(self):
        # Create customer with no bills
        res = self.client.post('/api/customers', json={
            'name': 'No Bills Customer',
            'phone': '9111111111'
        })
        self.assertEqual(res.status_code, 201)
        cid = res.get_json()['data']['id']

        # Delete customer
        del_res = self.client.delete(f'/api/customers/{cid}')
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.get_json()['message'], "Customer permanently deleted")

        # Check DB record is gone
        conn = database.get_db()
        row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
        conn.close()
        self.assertIsNone(row)

    def test_02_soft_delete_customer_with_bills(self):
        # Create customer with bills
        res = self.client.post('/api/customers', json={
            'name': 'Customer With Bills',
            'phone': '9222222222'
        })
        self.assertEqual(res.status_code, 201)
        cid = res.get_json()['data']['id']

        # Add a bill associated with this customer
        conn = database.get_db()
        conn.execute("INSERT INTO bills (bill_no, customer_id, grand_total) VALUES ('BILL-DEL-1', ?, 250)", (cid,))
        conn.commit()
        conn.close()

        # Delete customer
        del_res = self.client.delete(f'/api/customers/{cid}')
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.get_json()['message'], "Customer archived (had bill history)")

        # Check DB record still exists but is_active is 0
        conn = database.get_db()
        row = conn.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['is_active'], 0)

        # Verify GET /api/customers excludes is_active=0 by default
        get_res_default = self.client.get('/api/customers')
        self.assertEqual(get_res_default.status_code, 200)
        default_ids = [c['id'] for c in get_res_default.get_json()['data']]
        self.assertNotIn(cid, default_ids)

        # Verify GET /api/customers?include_inactive=1 includes is_active=0
        get_res_all = self.client.get('/api/customers?include_inactive=1')
        self.assertEqual(get_res_all.status_code, 200)
        all_ids = [c['id'] for c in get_res_all.get_json()['data']]
        self.assertIn(cid, all_ids)

if __name__ == '__main__':
    unittest.main()
