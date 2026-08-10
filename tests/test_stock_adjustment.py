"""
Regression Test Suite for POST /api/stock/adjustment
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db


class TestStockAdjustment(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_stock_secret_key'

        conn = get_db()
        cursor = conn.cursor()

        # Seed or reset test product
        cursor.execute("DELETE FROM products WHERE id=999")
        cursor.execute("""
            INSERT INTO products (id, name, code, selling_price, purchase_price, current_stock, active)
            VALUES (999, 'Adjustment Test Item', 'ADJ999', 150.0, 100.0, 50.0, 1)
        """)

        # Seed manager user with stock permissions
        cursor.execute("DELETE FROM users WHERE username='test_stock_manager'")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_stock_manager', 'dummy_hash', 'Stock Manager', 'manager', 2, 1)
        """)
        self.user_id = cursor.lastrowid

        conn.commit()
        conn.close()

    def tearDown(self):
        conn = get_db()
        conn.execute("DELETE FROM products WHERE id=999")
        conn.execute("DELETE FROM stock_transactions WHERE product_id=999")
        conn.commit()
        conn.close()

    def test_stock_adjustment_success_returns_200_and_updated_product(self):
        """POST /api/stock/adjustment must return 200 OK with updated product row in data."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_stock_manager'
            sess['user_role'] = 'manager'

        payload = {
            "product_id": 999,
            "new_quantity": 75.0,
            "notes": "Physical audit count correction"
        }

        response = self.client.post('/api/stock/adjustment',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')
        self.assertIn("Stock adjusted successfully", data.get('message', ''))

        # Verify product returned in data
        prod_data = data.get('data', {})
        self.assertEqual(prod_data.get('id'), 999)
        self.assertEqual(float(prod_data.get('current_stock', 0)), 75.0)

        # Verify database was committed
        conn = get_db()
        row = conn.execute("SELECT current_stock FROM products WHERE id=999").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(float(row['current_stock']), 75.0)

    def test_stock_adjustment_product_not_found(self):
        """POST /api/stock/adjustment with non-existent product ID must return 404."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_stock_manager'
            sess['user_role'] = 'manager'

        payload = {
            "product_id": 8888888,
            "new_quantity": 10.0
        }

        response = self.client.post('/api/stock/adjustment',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'error')

    def test_stock_adjustment_missing_required_params(self):
        """POST /api/stock/adjustment without product_id or new_quantity must return 400 error."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_stock_manager'
            sess['user_role'] = 'manager'

        response = self.client.post('/api/stock/adjustment',
                                    data=json.dumps({}),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
