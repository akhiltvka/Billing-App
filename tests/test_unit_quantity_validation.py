"""
Regression Test Suite for Discrete Unit Whole-Number Quantity Enforcement
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db, is_discrete_unit


class TestUnitQuantityValidation(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_unit_qty_key'

        conn = get_db()
        cursor = conn.cursor()

        # Seed admin user
        cursor.execute("DELETE FROM users WHERE username='test_qty_admin'")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_qty_admin', 'dummy_hash', 'Qty Admin', 'admin', 1, 1)
        """)
        self.admin_id = cursor.lastrowid

        # Clean existing test products
        cursor.execute("DELETE FROM products WHERE code LIKE 'TEST_UNIT_%'")

        # Create discrete unit products (pack, dozen, piece, box)
        cursor.execute("""
            INSERT INTO products (name, code, unit, purchase_unit, sale_unit, conversion_factor, selling_price, purchase_price, current_stock, active)
            VALUES ('Test Chicken Pack', 'TEST_UNIT_PACK', 'pack', 'pack', 'pack', 1.0, 150.0, 100.0, 50.0, 1)
        """)
        self.prod_pack_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO products (name, code, unit, purchase_unit, sale_unit, conversion_factor, selling_price, purchase_price, current_stock, active)
            VALUES ('Test Eggs Dozen', 'TEST_UNIT_DOZ', 'dozen', 'dozen', 'dozen', 1.0, 90.0, 70.0, 50.0, 1)
        """)
        self.prod_doz_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO products (name, code, unit, purchase_unit, sale_unit, conversion_factor, selling_price, purchase_price, current_stock, active)
            VALUES ('Test Samosa Piece', 'TEST_UNIT_PCS', 'piece', 'piece', 'piece', 1.0, 20.0, 10.0, 100.0, 1)
        """)
        self.prod_pcs_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO products (name, code, unit, purchase_unit, sale_unit, conversion_factor, selling_price, purchase_price, current_stock, active)
            VALUES ('Test Gift Box', 'TEST_UNIT_BOX', 'box', 'box', 'box', 1.0, 500.0, 350.0, 20.0, 1)
        """)
        self.prod_box_id = cursor.lastrowid

        # Create continuous unit products (kg, litre)
        cursor.execute("""
            INSERT INTO products (name, code, unit, purchase_unit, sale_unit, conversion_factor, selling_price, purchase_price, current_stock, active)
            VALUES ('Test Mutton Fresh', 'TEST_UNIT_KG', 'kg', 'kg', 'kg', 1.0, 700.0, 550.0, 50.0, 1)
        """)
        self.prod_kg_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO products (name, code, unit, purchase_unit, sale_unit, conversion_factor, selling_price, purchase_price, current_stock, active)
            VALUES ('Test Milk Fresh', 'TEST_UNIT_LTR', 'litre', 'litre', 'litre', 1.0, 60.0, 45.0, 50.0, 1)
        """)
        self.prod_ltr_id = cursor.lastrowid

        conn.commit()
        conn.close()

    def tearDown(self):
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username='test_qty_admin'")
        conn.execute("DELETE FROM products WHERE code LIKE 'TEST_UNIT_%'")
        conn.commit()
        conn.close()

    def _login_admin(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_qty_admin'
            sess['user_role'] = 'admin'

    def test_is_discrete_unit_helper(self):
        """Helper must accurately identify discrete units vs continuous fractional units."""
        self.assertTrue(is_discrete_unit('pack'))
        self.assertTrue(is_discrete_unit('packs'))
        self.assertTrue(is_discrete_unit('dozen'))
        self.assertTrue(is_discrete_unit('doz'))
        self.assertTrue(is_discrete_unit('piece'))
        self.assertTrue(is_discrete_unit('pcs'))
        self.assertTrue(is_discrete_unit('box'))
        self.assertTrue(is_discrete_unit('bottle'))
        self.assertTrue(is_discrete_unit('can'))
        self.assertTrue(is_discrete_unit('nos'))

        self.assertFalse(is_discrete_unit('kg'))
        self.assertFalse(is_discrete_unit('g'))
        self.assertFalse(is_discrete_unit('litre'))
        self.assertFalse(is_discrete_unit('ml'))
        self.assertFalse(is_discrete_unit(''))

    def test_discrete_units_reject_decimal_quantities_in_bill(self):
        """Billing discrete units (pack, dozen, piece, box) with decimals must be rejected with HTTP 400."""
        self._login_admin()

        # 1. Pack with 1.5
        res = self.client.post('/api/bills',
                               data=json.dumps({
                                   "items": [{
                                       "product_id": self.prod_pack_id,
                                       "quantity": 1.5,
                                       "unit_price": 150.0,
                                       "unit": "pack"
                                   }],
                                   "amount_paid": 225.0,
                                   "payment_mode": "cash"
                               }),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data.decode('utf-8'))
        self.assertIn("whole number quantities", data.get('message', ''))

        # 2. Dozen with 0.5
        res2 = self.client.post('/api/bills',
                                data=json.dumps({
                                    "items": [{
                                        "product_id": self.prod_doz_id,
                                        "quantity": 0.5,
                                        "unit_price": 90.0,
                                        "unit": "dozen"
                                    }],
                                    "amount_paid": 45.0,
                                    "payment_mode": "cash"
                                }),
                                content_type='application/json')
        self.assertEqual(res2.status_code, 400)

        # 3. Piece with 2.25
        res3 = self.client.post('/api/bills',
                                data=json.dumps({
                                    "items": [{
                                        "product_id": self.prod_pcs_id,
                                        "quantity": 2.25,
                                        "unit_price": 20.0,
                                        "unit": "piece"
                                    }],
                                    "amount_paid": 45.0,
                                    "payment_mode": "cash"
                                }),
                                content_type='application/json')
        self.assertEqual(res3.status_code, 400)

    def test_discrete_units_accept_integer_quantities_in_bill(self):
        """Billing discrete units with whole numbers must succeed."""
        self._login_admin()

        res = self.client.post('/api/bills',
                               data=json.dumps({
                                   "items": [{
                                       "product_id": self.prod_pack_id,
                                       "quantity": 2.0,
                                       "unit_price": 150.0,
                                       "unit": "pack"
                                   }, {
                                       "product_id": self.prod_doz_id,
                                       "quantity": 1,
                                       "unit_price": 90.0,
                                       "unit": "dozen"
                                   }],
                                   "amount_paid": 390.0,
                                   "payment_mode": "cash"
                               }),
                               content_type='application/json')
        self.assertEqual(res.status_code, 201, f"Expected 201, got: {res.data.decode('utf-8')}")
        data = json.loads(res.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')

    def test_continuous_units_accept_decimal_quantities_in_bill(self):
        """Billing continuous units (kg, litre) with decimals must succeed."""
        self._login_admin()

        res = self.client.post('/api/bills',
                               data=json.dumps({
                                   "items": [{
                                       "product_id": self.prod_kg_id,
                                       "quantity": 1.750,
                                       "unit_price": 700.0,
                                       "unit": "kg"
                                   }, {
                                       "product_id": self.prod_ltr_id,
                                       "quantity": 0.500,
                                       "unit_price": 60.0,
                                       "unit": "litre"
                                   }],
                                   "amount_paid": 1255.0,
                                   "payment_mode": "cash"
                               }),
                               content_type='application/json')
        self.assertEqual(res.status_code, 201, f"Expected 201, got: {res.data.decode('utf-8')}")

    def test_stock_adjustment_rejects_decimal_for_discrete_units(self):
        """Stock adjustment on discrete unit items must reject decimal quantities."""
        self._login_admin()

        # Decimal adjustment rejected
        res = self.client.post('/api/stock/adjustment',
                               data=json.dumps({
                                   "product_id": self.prod_pack_id,
                                   "new_quantity": 48.5,
                                   "notes": "Invalid decimal adjustment"
                               }),
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data.decode('utf-8'))
        self.assertIn("whole number quantities", data.get('message', ''))

        # Integer adjustment succeeds
        res_ok = self.client.post('/api/stock/adjustment',
                                  data=json.dumps({
                                      "product_id": self.prod_pack_id,
                                      "new_quantity": 48.0,
                                      "notes": "Valid integer adjustment"
                                  }),
                                  content_type='application/json')
        self.assertEqual(res_ok.status_code, 200)


if __name__ == '__main__':
    unittest.main()
