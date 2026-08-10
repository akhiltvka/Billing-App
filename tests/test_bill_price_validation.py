"""
Regression Test Suite for Server-Side Selling Price Verification in create_bill()
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db


class TestBillPriceValidation(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key'

        # Ensure a test product with known price exists in the database
        conn = get_db()
        cursor = conn.cursor()

        # Check or create product
        prod = cursor.execute("SELECT id, name, selling_price, current_stock FROM products WHERE id=1").fetchone()
        if not prod:
            cursor.execute("""
                INSERT OR REPLACE INTO products (id, name, code, selling_price, purchase_price, current_stock, active)
                VALUES (1, 'Test Chicken Curry Cut', 'T1001', 250.0, 180.0, 100.0, 1)
            """)
        else:
            cursor.execute("UPDATE products SET selling_price = 250.0, current_stock = 100.0, active = 1 WHERE id=1")

        # Check or create counter staff user (non-privileged)
        cursor.execute("DELETE FROM users WHERE username='test_cashier'")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_cashier', 'dummy_hash', 'Test Cashier', 'counter_staff', 4, 1)
        """)
        self.cashier_id = cursor.lastrowid

        # Check or create admin user (privileged)
        cursor.execute("DELETE FROM users WHERE username='test_admin_user'")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_admin_user', 'dummy_hash', 'Test Admin', 'admin', 1, 1)
        """)
        self.admin_id = cursor.lastrowid

        conn.commit()
        conn.close()

    def test_non_privileged_user_with_correct_price_succeeds(self):
        """Counter staff submitting exact product selling_price should succeed."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.cashier_id
            sess['username'] = 'test_cashier'
            sess['user_role'] = 'counter_staff'

        payload = {
            "customer_name": "Test Customer",
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Test Chicken Curry Cut",
                    "quantity": 2,
                    "unit_price": 250.0,
                    "gst_rate": 0
                }
            ],
            "payment_mode": "cash"
        }

        response = self.client.post('/api/bills',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('data', {}).get('grand_total'), 500.0)

    def test_non_privileged_user_with_tampered_price_is_rejected(self):
        """Counter staff submitting altered unit_price should be rejected with 400 error."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.cashier_id
            sess['username'] = 'test_cashier'
            sess['user_role'] = 'counter_staff'

        payload = {
            "customer_name": "Test Customer",
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Test Chicken Curry Cut",
                    "quantity": 2,
                    "unit_price": 10.0,  # Tampered price (actual is 250.0)
                    "gst_rate": 0
                }
            ],
            "payment_mode": "cash"
        }

        response = self.client.post('/api/bills',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'error')
        self.assertIn("Price mismatch", data.get('message', ''))
        self.assertIn("inventory.edit_price", data.get('message', ''))

    def test_privileged_user_with_custom_price_is_allowed(self):
        """Admin or user with inventory.edit_price permission submitting custom unit_price should be allowed."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_admin_user'
            sess['user_role'] = 'admin'

        payload = {
            "customer_name": "VIP Customer",
            "items": [
                {
                    "product_id": 1,
                    "product_name": "Test Chicken Curry Cut",
                    "quantity": 2,
                    "unit_price": 220.0,  # Custom overridden price by Admin
                    "gst_rate": 0
                }
            ],
            "payment_mode": "cash"
        }

        response = self.client.post('/api/bills',
                                    data=json.dumps(payload),
                                    content_type='application/json')

        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')
        self.assertEqual(data.get('data', {}).get('grand_total'), 440.0)


if __name__ == '__main__':
    unittest.main()
