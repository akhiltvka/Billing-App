"""
Regression Test Suite for Custom Unit Master Management
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db, is_discrete_unit
from database import init_db


class TestCustomUnits(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_custom_unit_key'

        # Ensure database tables and initial units are initialized
        init_db()

        conn = get_db()
        cursor = conn.cursor()

        # Seed admin user
        cursor.execute("DELETE FROM users WHERE username='test_unit_admin'")
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_unit_admin', 'dummy_hash', 'Unit Admin', 'admin', 1, 1)
        """)
        self.admin_id = cursor.lastrowid

        # Clean existing test products and test units
        cursor.execute("DELETE FROM products WHERE code LIKE 'TEST_CUNIT_%'")
        cursor.execute("DELETE FROM units WHERE name IN ('test_carton', 'test_sqmeter', 'test_bundle')")
        conn.commit()
        conn.close()

    def tearDown(self):
        conn = get_db()
        conn.execute("DELETE FROM users WHERE username='test_unit_admin'")
        conn.execute("DELETE FROM products WHERE code LIKE 'TEST_CUNIT_%'")
        conn.execute("DELETE FROM units WHERE name IN ('test_carton', 'test_sqmeter', 'test_bundle')")
        conn.commit()
        conn.close()

    def _login_admin(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['username'] = 'test_unit_admin'
            sess['user_role'] = 'admin'

    def test_list_default_units(self):
        """GET /api/units must return standard pre-seeded continuous and discrete units."""
        self._login_admin()
        res = self.client.get('/api/units')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode('utf-8'))
        units = data.get('data', {}).get('units', [])
        unit_names = [u['name'] for u in units]

        self.assertIn('kg', unit_names)
        self.assertIn('g', unit_names)
        self.assertIn('pack', unit_names)
        self.assertIn('dozen', unit_names)
        self.assertIn('piece', unit_names)

    def test_create_and_delete_custom_units(self):
        """POST /api/units creates custom unit, DELETE /api/units/<id> removes it."""
        self._login_admin()

        # 1. Create discrete custom unit
        res = self.client.post('/api/units',
                               data=json.dumps({
                                   "name": "test_carton",
                                   "symbol": "ctn",
                                   "is_discrete": 1
                               }),
                               content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = json.loads(res.data.decode('utf-8'))
        carton_id = data['data']['id']
        self.assertEqual(data['data']['name'], 'test_carton')
        self.assertEqual(data['data']['is_discrete'], 1)

        # 2. Verify is_discrete_unit helper recognizes custom unit
        self.assertTrue(is_discrete_unit('test_carton'))

        # 3. Duplicate creation should be rejected
        dup = self.client.post('/api/units',
                               data=json.dumps({
                                   "name": "test_carton",
                                   "symbol": "ctn",
                                   "is_discrete": 1
                               }),
                               content_type='application/json')
        self.assertEqual(dup.status_code, 400)

        # 4. Create decimal/continuous custom unit
        res2 = self.client.post('/api/units',
                                data=json.dumps({
                                    "name": "test_sqmeter",
                                    "symbol": "sqm",
                                    "is_discrete": 0
                                }),
                                content_type='application/json')
        self.assertEqual(res2.status_code, 201)
        self.assertFalse(is_discrete_unit('test_sqmeter'))

        # 5. Delete unused unit succeeds
        del_res = self.client.delete(f'/api/units/{carton_id}')
        self.assertEqual(del_res.status_code, 200)

    def test_delete_unit_prevented_when_in_use(self):
        """Deleting a unit assigned to an active product must be blocked with HTTP 400."""
        self._login_admin()

        # Create custom unit
        res = self.client.post('/api/units',
                               data=json.dumps({
                                   "name": "test_bundle",
                                   "symbol": "bdl",
                                   "is_discrete": 1
                               }),
                               content_type='application/json')
        bundle_id = json.loads(res.data.decode('utf-8'))['data']['id']

        # Create product with this unit
        conn = get_db()
        conn.execute("""
            INSERT INTO products (name, code, unit, purchase_unit, sale_unit, conversion_factor, selling_price, purchase_price, current_stock, active)
            VALUES ('Test Wire Bundle', 'TEST_CUNIT_BDL', 'test_bundle', 'test_bundle', 'test_bundle', 1.0, 300.0, 200.0, 10.0, 1)
        """)
        conn.commit()
        conn.close()

        # Attempt delete
        del_res = self.client.delete(f'/api/units/{bundle_id}')
        self.assertEqual(del_res.status_code, 400)
        data = json.loads(del_res.data.decode('utf-8'))
        self.assertIn("assigned to", data.get('message', ''))

    def test_custom_unit_billing_quantity_enforcement(self):
        """Custom discrete unit must enforce whole-number quantities on billing."""
        self._login_admin()

        # Create custom discrete unit
        self.client.post('/api/units',
                         data=json.dumps({
                             "name": "test_carton",
                             "symbol": "ctn",
                             "is_discrete": 1
                         }),
                         content_type='application/json')

        # Create product using test_carton
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (name, code, unit, purchase_unit, sale_unit, conversion_factor, selling_price, purchase_price, current_stock, active)
            VALUES ('Frozen Wings Carton', 'TEST_CUNIT_CTN', 'test_carton', 'test_carton', 'test_carton', 1.0, 1200.0, 900.0, 20.0, 1)
        """)
        prod_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # 1. Decimal billing rejected
        res_fail = self.client.post('/api/bills',
                                    data=json.dumps({
                                        "items": [{
                                            "product_id": prod_id,
                                            "quantity": 1.5,
                                            "unit_price": 1200.0,
                                            "unit": "test_carton"
                                        }],
                                        "amount_paid": 1800.0,
                                        "payment_mode": "cash"
                                    }),
                                    content_type='application/json')
        self.assertEqual(res_fail.status_code, 400)
        data = json.loads(res_fail.data.decode('utf-8'))
        self.assertIn("whole number quantities", data.get('message', ''))

        # 2. Integer billing succeeds
        res_ok = self.client.post('/api/bills',
                                  data=json.dumps({
                                      "items": [{
                                          "product_id": prod_id,
                                          "quantity": 2,
                                          "unit_price": 1200.0,
                                          "unit": "test_carton"
                                      }],
                                      "amount_paid": 2400.0,
                                      "payment_mode": "cash"
                                  }),
                                  content_type='application/json')
        self.assertEqual(res_ok.status_code, 201)


if __name__ == '__main__':
    unittest.main()
