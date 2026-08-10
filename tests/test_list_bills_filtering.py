"""
Regression Test Suite for Filtered Total Count in list_bills() (GET /api/bills)
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db


class TestListBillsFiltering(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key'

        conn = get_db()
        cursor = conn.cursor()

        # Clean existing test bills
        cursor.execute("DELETE FROM bills WHERE bill_no LIKE 'TEST-FILT-%'")

        # Create admin user for session
        cursor.execute("DELETE FROM users WHERE username='test_filter_admin'")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_filter_admin', 'dummy_hash', 'Filter Admin', 'admin', 1, 1)
        """)
        self.admin_id = cursor.lastrowid

        # Seed test bills with distinct dates, customers, statuses, and test flags
        test_bills = [
            ('TEST-FILT-001', 'Alice Wonderland', '9999900001', '2026-01-10 10:00:00', 'paid', 0, 500.0),
            ('TEST-FILT-002', 'Bob Builder',     '9999900002', '2026-02-15 11:00:00', 'paid', 0, 600.0),
            ('TEST-FILT-003', 'Charlie Chaplin', '9999900003', '2026-03-20 12:00:00', 'due',  0, 700.0),
            ('TEST-FILT-004', 'David Copperfield','9999900004', '2026-04-25 13:00:00', 'cancelled', 0, 800.0),
            ('TEST-FILT-005', 'Eve Tester',      '9999900005', '2026-05-30 14:00:00', 'paid', 1, 900.0),
        ]

        for b_no, name, phone, dt, status, is_test, total in test_bills:
            cursor.execute("""
                INSERT INTO bills (bill_no, customer_name, customer_phone, date, status, is_test, grand_total, subtotal, amount_paid, amount_due)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (b_no, name, phone, dt, status, is_test, total, total, total))

        conn.commit()
        conn.close()

    def tearDown(self):
        conn = get_db()
        conn.execute("DELETE FROM bills WHERE bill_no LIKE 'TEST-FILT-%'")
        conn.commit()
        conn.close()

    def test_search_query_filters_total_count(self):
        """Search query 'Alice' should return total = 1 matching the filtered count."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_filter_admin'
            sess['user_role'] = 'admin'

        response = self.client.get('/api/bills?q=Alice')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')

        res_data = data.get('data', {})
        self.assertEqual(res_data.get('total'), 1)
        self.assertEqual(len(res_data.get('bills', [])), 1)
        self.assertEqual(res_data['bills'][0]['customer_name'], 'Alice Wonderland')

    def test_date_range_filters_total_count(self):
        """Date range 2026-02-01 to 2026-03-31 should return total = 2 matching the filtered count."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_filter_admin'
            sess['user_role'] = 'admin'

        response = self.client.get('/api/bills?from=2026-02-01&to=2026-03-31&q=TEST-FILT')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')

        res_data = data.get('data', {})
        self.assertEqual(res_data.get('total'), 2)
        self.assertEqual(len(res_data.get('bills', [])), 2)
        bill_nos = {b['bill_no'] for b in res_data['bills']}
        self.assertEqual(bill_nos, {'TEST-FILT-002', 'TEST-FILT-003'})

    def test_status_filter_filters_total_count(self):
        """Status filter 'due' with search TEST-FILT should return total = 1."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_filter_admin'
            sess['user_role'] = 'admin'

        response = self.client.get('/api/bills?status=due&q=TEST-FILT')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')

        res_data = data.get('data', {})
        self.assertEqual(res_data.get('total'), 1)
        self.assertEqual(len(res_data.get('bills', [])), 1)
        self.assertEqual(res_data['bills'][0]['bill_no'], 'TEST-FILT-003')

    def test_pagination_limit_preserves_filtered_total(self):
        """With limit=1 on a 3-item date range filter, total must still equal 3 while returned bills count is 1."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_filter_admin'
            sess['user_role'] = 'admin'

        response = self.client.get('/api/bills?from=2026-01-01&to=2026-03-31&q=TEST-FILT&limit=1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')

        res_data = data.get('data', {})
        self.assertEqual(res_data.get('total'), 3)
        self.assertEqual(len(res_data.get('bills', [])), 1)


if __name__ == '__main__':
    unittest.main()
