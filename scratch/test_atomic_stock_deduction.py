import sys
import os
import unittest
import tempfile
import threading

# Set environment DB_PATH to a temporary DB
tmp_db_fd, tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(tmp_db_fd)
os.environ['DB_PATH'] = tmp_db_path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

import database
import app
from app import InsufficientStockError, update_stock

class TestAtomicStockDeduction(unittest.TestCase):
    def setUp(self):
        database.init_db()
        self.app = app.app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['user_role'] = 'admin'

    def test_01_direct_update_stock_success_and_failure(self):
        conn = database.get_db()
        # Create product with 10 kg stock
        c = conn.execute(
            "INSERT INTO products (name, code, current_stock, selling_price) VALUES ('Atomic Chicken', 'ATCH', 10.0, 200.0)"
        )
        pid = c.lastrowid
        conn.commit()

        # Deduct 4.0 kg -> succeeds, 6.0 kg left
        update_stock(conn, pid, -4.0, 'out')
        conn.commit()
        p = conn.execute("SELECT current_stock FROM products WHERE id=?", (pid,)).fetchone()
        self.assertEqual(p['current_stock'], 6.0)

        # Deduct 6.0 kg -> succeeds, 0.0 kg left
        update_stock(conn, pid, -6.0, 'out')
        conn.commit()
        p = conn.execute("SELECT current_stock FROM products WHERE id=?", (pid,)).fetchone()
        self.assertEqual(p['current_stock'], 0.0)

        # Try to deduct 1.0 kg -> raises InsufficientStockError
        with self.assertRaises(InsufficientStockError):
            update_stock(conn, pid, -1.0, 'out')

        conn.close()

    def test_02_create_bill_insufficient_stock_returns_409(self):
        conn = database.get_db()
        c = conn.execute(
            "INSERT INTO products (name, code, current_stock, selling_price) VALUES ('Limited Fish', 'LFSH', 2.0, 150.0)"
        )
        pid = c.lastrowid
        conn.commit()

        # Non-concurrent fast-path pre-check rejection -> returns 400
        res_fast = self.client.post('/api/bills', json={
            'items': [{'product_id': pid, 'product_name': 'Limited Fish', 'quantity': 10.0, 'unit_price': 150.0}],
            'payment_mode': 'cash'
        })
        self.assertEqual(res_fast.status_code, 400)
        self.assertIn("Insufficient stock for Limited Fish", res_fast.get_json()['message'])

        # Concurrent race condition simulation:
        # Pre-check sees current_stock = 2.0 (bill for 2.0 passes pre-check).
        # Before update_stock runs, another thread/process reduces current_stock to 0.0.
        # update_stock will fail with rowcount == 0 and raise InsufficientStockError -> returns 409 Conflict.
        conn.execute("UPDATE products SET current_stock = 0.0 WHERE id=?", (pid,))
        conn.commit()
        conn.close()

        # Call update_stock directly or test create_bill race
        try:
            conn_test = database.get_db()
            update_stock(conn_test, pid, -2.0, 'out')
        except InsufficientStockError as e:
            self.assertIn("Insufficient stock for product 'Limited Fish'", str(e))
        finally:
            conn_test.close()

if __name__ == '__main__':
    unittest.main()
