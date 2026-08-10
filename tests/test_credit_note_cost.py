"""
Regression Test Suite for Credit Note Stock Cost Valuation Preservation
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db


class TestCreditNoteCost(unittest.TestCase):

    def _cleanup_test_data(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM credit_note_items WHERE bill_item_id IN (SELECT id FROM bill_items WHERE product_id IN (SELECT id FROM products WHERE code='CNC1'))")
        cursor.execute("DELETE FROM credit_notes WHERE bill_id IN (SELECT id FROM bills WHERE customer_name='CN Cost Test Customer')")
        cursor.execute("DELETE FROM bill_items WHERE product_id IN (SELECT id FROM products WHERE code='CNC1')")
        cursor.execute("DELETE FROM bill_payments WHERE bill_id IN (SELECT id FROM bills WHERE customer_name='CN Cost Test Customer')")
        cursor.execute("DELETE FROM bills WHERE customer_name='CN Cost Test Customer'")
        cursor.execute("DELETE FROM stock_batches WHERE product_id IN (SELECT id FROM products WHERE code='CNC1')")
        cursor.execute("DELETE FROM stock_transactions WHERE product_id IN (SELECT id FROM products WHERE code='CNC1')")
        cursor.execute("DELETE FROM products WHERE code='CNC1'")
        cursor.execute("DELETE FROM users WHERE username='test_cn_admin'")
        conn.commit()
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_cn_secret_key'

        self._cleanup_test_data()

        conn = get_db()
        cursor = conn.cursor()

        # Seed admin user
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_cn_admin', 'dummy_hash', 'CN Admin', 'admin', 1, 1)
        """)
        self.user_id = cursor.lastrowid

        # Seed test product: selling price 250, purchase price 180
        cursor.execute("""
            INSERT INTO products (name, code, selling_price, purchase_price, current_stock, purchase_unit, sale_unit, conversion_factor, active)
            VALUES ('Credit Note Cost Item', 'CNC1', 250.0, 180.0, 10.0, 'kg', 'kg', 1.0, 1)
        """)
        self.prod_id = cursor.lastrowid

        # Seed initial batch with cost 180.0
        cursor.execute("""
            INSERT INTO stock_batches (product_id, batch_no, quantity_remaining, unit_price, unit_cost, expiry_date)
            VALUES (?, 'BATCH-INIT-CNC', 10.0, 180.0, 180.0, '2026-12-31')
        """, (self.prod_id,))

        conn.commit()
        conn.close()

    def tearDown(self):
        self._cleanup_test_data()

    def test_credit_note_restores_stock_with_cost_price_not_selling_price(self):
        """Issuing a credit note must restore stock with original cost_price (180), NOT selling_price (250)."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_cn_admin'
            sess['user_role'] = 'admin'

        bill_payload = {
            "customer_name": "CN Cost Test Customer",
            "items": [
                {
                    "product_id": self.prod_id,
                    "product_name": "Credit Note Cost Item",
                    "quantity": 4.0,
                    "unit_price": 250.0,
                    "gst_rate": 0
                }
            ],
            "payment_mode": "cash"
        }

        # 1. Create Bill
        res1 = self.client.post('/api/bills', data=json.dumps(bill_payload), content_type='application/json')
        self.assertEqual(res1.status_code, 201)
        data1 = json.loads(res1.data.decode('utf-8'))
        bill1_id = data1['data']['id']
        bill1_no = data1['data']['bill_no']
        bill_item_id = data1['data']['items'][0]['id']

        # Verify Bill 1 cost_price was 180.0
        conn = get_db()
        item1 = conn.execute("SELECT cost_price FROM bill_items WHERE id=?", (bill_item_id,)).fetchone()
        self.assertEqual(float(item1['cost_price']), 180.0)

        # 2. Issue Credit Note returning 2 units
        cn_payload = {
            "reason": "Customer returned 2kg",
            "items": [
                {
                    "bill_item_id": bill_item_id,
                    "quantity": 2.0
                }
            ]
        }

        cn_res = self.client.post(f'/api/bills/{bill1_id}/credit-note',
                                  data=json.dumps(cn_payload),
                                  content_type='application/json')
        self.assertEqual(cn_res.status_code, 201)

        # 3. Verify stock_batches row created for the credit note has unit_cost = 180.0 (NOT 250.0!)
        restored_batch = conn.execute("""
            SELECT sb.unit_cost, sb.unit_price, sb.quantity_remaining
            FROM stock_batches sb
            JOIN stock_transactions st ON sb.stock_transaction_id = st.id
            WHERE sb.product_id = ? AND st.reference_id = ?
        """, (self.prod_id, bill1_no)).fetchone()

        self.assertIsNotNone(restored_batch, "Restored stock batch from credit note should exist")
        self.assertEqual(float(restored_batch['unit_cost']), 180.0)
        self.assertEqual(float(restored_batch['quantity_remaining']), 2.0)

        # 4. Create Bill 2 selling the returned 2 units
        res2 = self.client.post('/api/bills', data=json.dumps({
            "customer_name": "CN Cost Test Customer",
            "items": [
                {
                    "product_id": self.prod_id,
                    "product_name": "Credit Note Cost Item",
                    "quantity": 2.0,
                    "unit_price": 250.0,
                    "gst_rate": 0
                }
            ],
            "payment_mode": "cash"
        }), content_type='application/json')
        self.assertEqual(res2.status_code, 201)
        data2 = json.loads(res2.data.decode('utf-8'))
        bill2_id = data2['data']['id']

        # Verify Bill 2 recorded cost_price = 180.0 (and NOT 250.0!)
        item2 = conn.execute("SELECT cost_price FROM bill_items WHERE bill_id=?", (bill2_id,)).fetchone()
        conn.close()

        self.assertIsNotNone(item2['cost_price'])
        self.assertEqual(float(item2['cost_price']), 180.0)


if __name__ == '__main__':
    unittest.main()
