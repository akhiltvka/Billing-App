import sys
import os
import unittest
import tempfile
from unittest.mock import patch

# Set environment DB_PATH to a temporary DB
tmp_db_fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(tmp_db_fd)
os.environ['DB_PATH'] = tmp_db_path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import database
import app

class TestTransactionSafety(unittest.TestCase):
    def setUp(self):
        database.init_db()
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['user_role'] = 'admin'

    def test_create_bill_success_and_error_handling(self):
        conn = database.get_db()
        c = conn.execute(
            "INSERT INTO products (name, code, current_stock, selling_price) VALUES ('Tx Safety Item', 'TXS1', 100.0, 100.0)"
        )
        pid = c.lastrowid
        conn.commit()
        conn.close()

        # Success path
        res_ok = self.client.post('/api/bills', json={
            'items': [{'product_id': pid, 'product_name': 'Tx Safety Item', 'quantity': 2.0, 'unit_price': 100.0}],
            'payment_mode': 'cash'
        })
        self.assertEqual(res_ok.status_code, 201)

        # Exception path mid-transaction (simulating error during post_ledger_entry)
        with patch('app.post_ledger_entry', side_effect=RuntimeError("Simulated ledger posting crash")):
            res_err = self.client.post('/api/bills', json={
                'items': [{'product_id': pid, 'product_name': 'Tx Safety Item', 'quantity': 1.0, 'unit_price': 100.0}],
                'payment_mode': 'cash'
            })
            self.assertEqual(res_err.status_code, 500)
            self.assertIn("Bill creation failed", res_err.get_json()['message'])

        # Verify stock remained at 98.0 (the second 1.0 item was rolled back cleanly!)
        conn2 = database.get_db()
        p = conn2.execute("SELECT current_stock FROM products WHERE id=?", (pid,)).fetchone()
        conn2.close()
        self.assertEqual(p['current_stock'], 98.0)

    def test_create_stock_conversion_transaction_safety(self):
        conn = database.get_db()
        c1 = conn.execute("INSERT INTO products (name, code, current_stock, purchase_price) VALUES ('Raw Chicken', 'RAW', 50.0, 150.0)")
        input_pid = c1.lastrowid
        c2 = conn.execute("INSERT INTO products (name, code, current_stock, purchase_price) VALUES ('Boneless Chicken', 'BONELESS', 0.0, 250.0)")
        output_pid = c2.lastrowid
        conn.commit()
        conn.close()

        # Success path
        res_cnv = self.client.post('/api/stock/conversions', json={
            'input_product_id': input_pid,
            'input_quantity': 10.0,
            'outputs': [{'output_product_id': output_pid, 'output_quantity': 8.0}],
            'notes': 'Test conversion safety'
        })
        self.assertEqual(res_cnv.status_code, 201)

        # Simulated exception path
        with patch('app.update_stock', side_effect=RuntimeError("Stock update crash")):
            res_fail = self.client.post('/api/stock/conversions', json={
                'input_product_id': input_pid,
                'input_quantity': 5.0,
                'outputs': [{'output_product_id': output_pid, 'output_quantity': 4.0}]
            })
            self.assertEqual(res_fail.status_code, 500)
            self.assertIn("Stock conversion failed", res_fail.get_json()['message'])

if __name__ == '__main__':
    unittest.main()
