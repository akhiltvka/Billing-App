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
from merge_duplicate_customers import main as merge_main

class TestCustomerUniqueness(unittest.TestCase):
    def setUp(self):
        database.init_db()
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['user_role'] = 'admin'

    def tearDown(self):
        pass

    def test_01_create_duplicate_phone_returns_existing(self):
        # First creation
        res1 = self.client.post('/api/customers', json={
            'name': 'Customer One',
            'phone': '9876543210'
        })
        self.assertEqual(res1.status_code, 201)
        data1 = res1.get_json()
        cid1 = data1['data']['id']

        # Second creation with SAME phone
        res2 = self.client.post('/api/customers', json={
            'name': 'Customer One Duplicate',
            'phone': '9876543210'
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2['message'], "Existing customer matched by phone")
        self.assertEqual(data2['data']['id'], cid1)

    def test_02_update_phone_collision(self):
        # Create customer A
        res_a = self.client.post('/api/customers', json={
            'name': 'Alice',
            'phone': '9998887771'
        })
        cid_a = res_a.get_json()['data']['id']

        # Create customer B
        res_b = self.client.post('/api/customers', json={
            'name': 'Bob',
            'phone': '9998887772'
        })
        cid_b = res_b.get_json()['data']['id']

        # Try to update Bob's phone to Alice's phone -> should fail with 400
        res_update = self.client.put(f'/api/customers/{cid_b}', json={
            'name': 'Bob Updated',
            'phone': '9998887771'
        })
        self.assertEqual(res_update.status_code, 400)
        self.assertIn("already registered", res_update.get_json()['message'])

    def test_03_merge_script(self):
        # Manually bypass route to insert duplicate customers into DB directly (simulating pre-existing DB state)
        conn = database.get_db()
        conn.execute("DROP INDEX IF EXISTS idx_customers_phone_unique")
        conn.execute("INSERT INTO customers (name, phone) VALUES ('Old Dup 1', '9000000001')")
        c1 = conn.execute("SELECT id FROM customers WHERE name='Old Dup 1'").fetchone()['id']
        conn.execute("INSERT INTO customers (name, phone) VALUES ('Old Dup 2', '9000000001')")
        c2 = conn.execute("SELECT id FROM customers WHERE name='Old Dup 2'").fetchone()['id']
        
        # Add bill to c1 so c1 becomes survivor
        conn.execute("INSERT INTO bills (bill_no, customer_id, grand_total) VALUES ('TEST-BILL-1', ?, 500)", (c1,))
        conn.commit()
        conn.close()

        # Run merge script in --dry-run
        sys.argv = ['merge_duplicate_customers.py', '--db-path', tmp_db_path, '--dry-run']
        merge_main()

        # Check DB still has 2 records after dry run
        conn = database.get_db()
        cnt_dry = conn.execute("SELECT COUNT(*) FROM customers WHERE phone='9000000001'").fetchone()[0]
        self.assertEqual(cnt_dry, 2)
        conn.close()

        # Run merge script with --apply
        sys.argv = ['merge_duplicate_customers.py', '--db-path', tmp_db_path, '--apply']
        merge_main()

        # Check DB now has 1 survivor record
        conn = database.get_db()
        cnt_apply = conn.execute("SELECT COUNT(*) FROM customers WHERE phone='9000000001'").fetchone()[0]
        self.assertEqual(cnt_apply, 1)
        conn.close()

if __name__ == '__main__':
    unittest.main()
