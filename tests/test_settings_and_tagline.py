"""
Unit & Regression Tests for Settings Management, Outlet Profile, and Custom Tagline
"""

import unittest
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db


class TestSettingsAndTagline(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_settings_secret_key'

        conn = get_db()
        conn.execute("DELETE FROM users WHERE username='test_settings_admin'")
        conn.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_settings_admin', 'dummy_hash', 'Settings Admin User', 'admin', 1, 1)
        """)
        self.user_id = conn.execute("SELECT id FROM users WHERE username='test_settings_admin'").fetchone()['id']
        conn.commit()
        conn.close()

    def test_save_and_retrieve_outlet_profile_and_tagline(self):
        """Test saving outlet details including custom tagline, shop name, font, and logo."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_settings_admin'
            sess['user_role'] = 'admin'

        payload = {
            'shop_name': 'Akhilz Meat Products',
            'shop_tagline': 'Premium Fresh Cuts Daily',
            'shop_address': '456 Gourmet Street, Cochin',
            'shop_phone': '+91 94470 12345',
            'shop_email': 'contact@akhilzmeat.com',
            'shop_gstin': '32ABCDE1234F1Z5',
            'shop_fssai': '10012345678901',
            'shop_brand_font': 'Segoe Script',
            'shop_logo': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
        }

        # 1. Save settings
        res = self.client.post('/api/settings', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        json_data = json.loads(res.data)
        self.assertEqual(json_data['status'], 'ok')

        # 2. Get settings
        get_res = self.client.get('/api/settings')
        self.assertEqual(get_res.status_code, 200)
        settings_data = json.loads(get_res.data)['data']
        self.assertEqual(settings_data['shop_name'], 'Akhilz Meat Products')
        self.assertEqual(settings_data['shop_tagline'], 'Premium Fresh Cuts Daily')
        self.assertEqual(settings_data['shop_brand_font'], 'Segoe Script')
        self.assertEqual(settings_data['shop_phone'], '+91 94470 12345')

    def test_get_bill_includes_saved_settings(self):
        """Test that fetching a bill contains the latest shop settings (including custom tagline)."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_settings_admin'
            sess['user_role'] = 'admin'

        # Set custom tagline
        self.client.post('/api/settings', data=json.dumps({
            'shop_name': 'Akhilz Prime Meats',
            'shop_tagline': '100% Farm Fresh & Organic'
        }), content_type='application/json')

        # Create a sample customer & product & bill
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO customers (name, phone) VALUES ('John Doe', '9876543210')")
        cust_id = conn.execute("SELECT id FROM customers WHERE name='John Doe'").fetchone()['id']
        conn.execute("""
            INSERT OR IGNORE INTO products (code, name, purchase_unit, sale_unit, conversion_factor, purchase_price, selling_price, current_stock, active)
            VALUES ('TEST-ST', 'Test Product For Settings', 'kg', 'kg', 1.0, 100, 150, 50, 1)
        """)
        prod_id = conn.execute("SELECT id FROM products WHERE code='TEST-ST'").fetchone()['id']
        conn.commit()
        conn.close()

        bill_payload = {
            'customer_id': cust_id,
            'payment_mode': 'cash',
            'amount_paid': 150.0,
            'items': [{
                'product_id': prod_id,
                'quantity': 1,
                'unit_price': 150,
                'gst_rate': 0,
                'discount': 0
            }]
        }
        create_res = self.client.post('/api/bills', data=json.dumps(bill_payload), content_type='application/json')
        self.assertEqual(create_res.status_code, 201)
        bill_id = json.loads(create_res.data)['data']['id']

        # Fetch bill details
        bill_res = self.client.get(f'/api/bills/{bill_id}')
        self.assertEqual(bill_res.status_code, 200)
        bill_data = json.loads(bill_res.data)['data']
        self.assertIn('settings', bill_data)
        self.assertEqual(bill_data['settings'].get('shop_name'), 'Akhilz Prime Meats')
        self.assertEqual(bill_data['settings'].get('shop_tagline'), '100% Farm Fresh & Organic')


if __name__ == '__main__':
    unittest.main()
