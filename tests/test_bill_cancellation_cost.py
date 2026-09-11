"""
Regression Test Suite for Bill Cancellation Stock Cost Preservation
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db


class TestBillCancellationCost(unittest.TestCase):

    def _cleanup_test_data(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bill_items WHERE product_id IN (SELECT id FROM products WHERE code='CAN1')")
        cursor.execute("DELETE FROM bill_payments WHERE bill_id IN (SELECT id FROM bills WHERE customer_name='Cancellation Test Customer')")
        cursor.execute("DELETE FROM bills WHERE customer_name='Cancellation Test Customer'")
        cursor.execute("DELETE FROM stock_batches WHERE product_id IN (SELECT id FROM products WHERE code='CAN1')")
        cursor.execute("DELETE FROM stock_transactions WHERE product_id IN (SELECT id FROM products WHERE code='CAN1')")
        cursor.execute("DELETE FROM products WHERE code='CAN1'")
        cursor.execute("DELETE FROM users WHERE username='test_cancel_admin'")
        conn.commit()
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_cancel_secret_key'

        self._cleanup_test_data()

        conn = get_db()
        cursor = conn.cursor()

        # Seed admin user
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_cancel_admin', 'dummy_hash', 'Cancel Admin', 'admin', 1, 1)
        """)
        self.user_id = cursor.lastrowid

        # Seed test product
        cursor.execute("""
            INSERT INTO products (name, code, selling_price, purchase_price, current_stock, purchase_unit, sale_unit, conversion_factor, active)
            VALUES ('Cancellation Cost Product', 'CAN1', 250.0, 180.0, 10.0, 'kg', 'kg', 1.0, 1)
        """)
        self.prod_id = cursor.lastrowid

        # Seed initial stock batch with cost 180.0
        cursor.execute("""
            INSERT INTO stock_batches (product_id, batch_no, quantity_remaining, unit_price, unit_cost, expiry_date)
            VALUES (?, 'BATCH-INIT-CAN', 10.0, 180.0, 180.0, '2026-12-31')
        """, (self.prod_id,))

        conn.commit()
        conn.close()

    def tearDown(self):
        self._cleanup_test_data()

    def test_cancel_bill_restores_cost_price_to_stock_batches_and_future_bills(self):
        """Cancelling a bill must restore stock with original cost_price so subsequent sales retain the non-zero cost."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_cancel_admin'
            sess['user_role'] = 'admin'

        bill_payload = {
            "customer_name": "Cancellation Test Customer",
            "items": [
                {
                    "product_id": self.prod_id,
                    "product_name": "Cancellation Cost Product",
                    "quantity": 2.0,
                    "unit_price": 250.0,
                    "gst_rate": 0
                }
            ],
            "payment_mode": "cash"
        }

        # 1. Create Bill 1
        res1 = self.client.post('/api/bills', data=json.dumps(bill_payload), content_type='application/json')
        self.assertEqual(res1.status_code, 201)
        data1 = json.loads(res1.data.decode('utf-8'))
        bill1_id = data1['data']['id']
        bill1_no = data1['data']['bill_no']

        # Verify Bill 1 recorded cost_price 180.0
        conn = get_db()
        item1 = conn.execute("SELECT cost_price FROM bill_items WHERE bill_id=?", (bill1_id,)).fetchone()
        self.assertEqual(float(item1['cost_price']), 180.0)

        # 2. Cancel Bill 1
        cancel_res = self.client.delete(f'/api/bills/{bill1_id}',
                                        data=json.dumps({"reason": "Customer changed mind"}),
                                        content_type='application/json')
        self.assertEqual(cancel_res.status_code, 200)

        reversal = conn.execute('''
            SELECT le.debit, le.credit, le.narration
            FROM ledger_entries le
            JOIN ledger_vouchers lv ON lv.voucher_type = 'journal' AND lv.voucher_no = le.voucher_no
            WHERE lv.voucher_no = ?
            ORDER BY le.id
        ''', (f"REV-{bill1_no}",)).fetchall()
        self.assertGreater(len(reversal), 0, "Bill cancellation should post a reversal journal")
        self.assertAlmostEqual(sum(float(row['debit']) for row in reversal), sum(float(row['credit']) for row in reversal), places=2)

        second_cancel = self.client.delete(f'/api/bills/{bill1_id}',
                                            data=json.dumps({"reason": "Duplicate cancellation"}),
                                            content_type='application/json')
        self.assertEqual(second_cancel.status_code, 400)

        # 3. Verify the restored batch in stock_batches has unit_cost 180.0 (NOT 0.0!)
        restored_batch = conn.execute("""
            SELECT unit_cost, unit_price, quantity_remaining
            FROM stock_batches
            WHERE product_id = ? AND batch_no LIKE ?
        """, (self.prod_id, f"%{bill1_no}%")).fetchone()

        self.assertIsNotNone(restored_batch, "Restored stock batch should exist")
        self.assertEqual(float(restored_batch['unit_cost']), 180.0)
        self.assertEqual(float(restored_batch['unit_price']), 180.0)
        self.assertEqual(float(restored_batch['quantity_remaining']), 2.0)

        # 4. Create Bill 2 selling the restored 2 units
        res2 = self.client.post('/api/bills', data=json.dumps(bill_payload), content_type='application/json')
        self.assertEqual(res2.status_code, 201)
        data2 = json.loads(res2.data.decode('utf-8'))
        bill2_id = data2['data']['id']

        # Verify Bill 2 recorded cost_price = 180.0 (and NOT 0.0)
        item2 = conn.execute("SELECT cost_price FROM bill_items WHERE bill_id=?", (bill2_id,)).fetchone()
        conn.close()

        self.assertIsNotNone(item2['cost_price'])
        self.assertEqual(float(item2['cost_price']), 180.0)


if __name__ == '__main__':
    unittest.main()
