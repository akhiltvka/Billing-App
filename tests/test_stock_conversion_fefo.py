"""
Regression Test Suite for Shelf Life Days, Stock Conversion Auto-Expiry, and FEFO Rotation
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db, deduct_fefo_stock


class TestStockConversionFefo(unittest.TestCase):

    def _cleanup_test_data(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stock_conversion_outputs WHERE output_product_id IN (SELECT id FROM products WHERE code IN ('INP1', 'OUT1', 'SLP1'))")
        cursor.execute("DELETE FROM stock_conversions WHERE input_product_id IN (SELECT id FROM products WHERE code IN ('INP1', 'OUT1', 'SLP1'))")
        cursor.execute("DELETE FROM stock_batches WHERE product_id IN (SELECT id FROM products WHERE code IN ('INP1', 'OUT1', 'SLP1'))")
        cursor.execute("DELETE FROM stock_transactions WHERE product_id IN (SELECT id FROM products WHERE code IN ('INP1', 'OUT1', 'SLP1'))")
        cursor.execute("DELETE FROM products WHERE code IN ('INP1', 'OUT1', 'SLP1')")
        conn.commit()
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_fefo_secret_key'

        self._cleanup_test_data()

        conn = get_db()
        cursor = conn.cursor()

        # Seed admin user
        cursor.execute("DELETE FROM users WHERE username='test_fefo_admin'")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_fefo_admin', 'dummy_hash', 'FEFO Admin', 'admin', 1, 1)
        """)
        self.user_id = cursor.lastrowid
        conn.commit()
        conn.close()

    def tearDown(self):
        self._cleanup_test_data()

    def test_product_crud_persists_shelf_life_days(self):
        """Creating and updating products with shelf_life_days must persist the column accurately."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_fefo_admin'
            sess['user_role'] = 'admin'

        payload = {
            "name": "Shelf Life Test Item",
            "code": "SLP1",
            "purchase_price": 100.0,
            "selling_price": 140.0,
            "shelf_life_days": 4
        }

        # 1. Create product
        res = self.client.post('/api/products', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data.decode('utf-8'))
        pid = data['data']['id']
        self.assertEqual(data['data']['shelf_life_days'], 4)

        # 2. Update product
        payload['shelf_life_days'] = 7
        res2 = self.client.put(f'/api/products/{pid}', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res2.status_code, 200)
        data2 = json.loads(res2.data.decode('utf-8'))
        self.assertEqual(data2['data']['shelf_life_days'], 7)

    def test_stock_conversion_auto_computes_expiry_and_fefo_rotates(self):
        """Stock conversion must calculate expiry_date using shelf_life_days, and FEFO must consume earlier expiring batches first."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_fefo_admin'
            sess['user_role'] = 'admin'

        conn = get_db()
        cursor = conn.cursor()

        # Seed input product with 20 kg stock
        cursor.execute("""
            INSERT INTO products (name, code, purchase_price, selling_price, current_stock, purchase_unit, sale_unit, conversion_factor, active)
            VALUES ('Whole Chicken Raw', 'INP1', 120.0, 160.0, 20.0, 'kg', 'kg', 1.0, 1)
        """)
        inp_id = cursor.lastrowid

        # Seed output product with shelf_life_days = 5
        cursor.execute("""
            INSERT INTO products (name, code, purchase_price, selling_price, current_stock, purchase_unit, sale_unit, conversion_factor, shelf_life_days, active)
            VALUES ('Chicken Curry Cut', 'OUT1', 150.0, 200.0, 0.0, 'kg', 'kg', 1.0, 5, 1)
        """)
        out_id = cursor.lastrowid

        # Insert a pre-existing batch for output product with a later expiry date (e.g. 2026-08-30)
        cursor.execute("""
            INSERT INTO stock_batches (product_id, batch_no, quantity_remaining, unit_price, unit_cost, expiry_date)
            VALUES (?, 'BATCH-LATER', 10.0, 150.0, 150.0, '2026-08-30')
        """, (out_id,))
        cursor.execute("UPDATE products SET current_stock = 10.0 WHERE id = ?", (out_id,))
        conn.commit()

        # Run conversion on date 2026-08-10
        conv_payload = {
            "input_product_id": inp_id,
            "input_quantity": 10.0,
            "conversion_date": "2026-08-10",
            "outputs": [
                {
                    "output_product_id": out_id,
                    "output_quantity": 8.0
                }
            ],
            "notes": "Test Conversion"
        }

        res = self.client.post('/api/stock/conversions', data=json.dumps(conv_payload), content_type='application/json')
        self.assertEqual(res.status_code, 201)

        # Verify the conversion output batch was created with auto-calculated expiry date = 2026-08-10 + 5 days = 2026-08-15
        batches = conn.execute("""
            SELECT id, batch_no, quantity_remaining, expiry_date
            FROM stock_batches
            WHERE product_id = ?
            ORDER BY id ASC
        """, (out_id,)).fetchall()

        self.assertEqual(len(batches), 2)
        conv_batch = [b for b in batches if b['batch_no'] != 'BATCH-LATER'][0]
        self.assertEqual(conv_batch['expiry_date'], '2026-08-15')
        self.assertEqual(float(conv_batch['quantity_remaining']), 8.0)

        # Deduct 5 kg using FEFO — should take from the earlier expiry batch (2026-08-15) first!
        deduct_fefo_stock(conn, out_id, 5.0)
        conn.commit()

        # Check remaining quantities
        b_early = conn.execute("SELECT quantity_remaining FROM stock_batches WHERE id = ?", (conv_batch['id'],)).fetchone()
        b_later = conn.execute("SELECT quantity_remaining FROM stock_batches WHERE batch_no = 'BATCH-LATER'").fetchone()

        # Early batch (8.0 - 5.0 = 3.0)
        self.assertEqual(float(b_early['quantity_remaining']), 3.0)
        # Later batch remains untouched (10.0)
        self.assertEqual(float(b_later['quantity_remaining']), 10.0)

        conn.close()


if __name__ == '__main__':
    unittest.main()
