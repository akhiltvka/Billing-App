"""Regression tests for purchase accounting and supplier balances."""

import unittest

from app import app, get_db
from database import init_db


class TestPurchaseSupplierBalance(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        init_db()
        conn = get_db()
        conn.execute("DELETE FROM suppliers WHERE name='Purchase Balance Test Supplier'")
        conn.execute("DELETE FROM products WHERE code='PUR-BAL-001'")
        conn.commit()
        conn.execute("INSERT INTO suppliers (name, balance) VALUES (?, 0)", ('Purchase Balance Test Supplier',))
        self.supplier_id = conn.execute(
            "SELECT id FROM suppliers WHERE name='Purchase Balance Test Supplier'"
        ).fetchone()['id']
        conn.execute('''
            INSERT INTO products (name, code, purchase_price, selling_price, current_stock, active)
            VALUES ('Purchase Balance Test Product', 'PUR-BAL-001', 50, 75, 0, 1)
        ''')
        self.product_id = conn.execute("SELECT id FROM products WHERE code='PUR-BAL-001'").fetchone()['id']
        conn.commit()
        conn.close()

        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['username'] = 'purchase-test-admin'
            session['user_role'] = 'admin'

    def tearDown(self):
        conn = get_db()
        conn.execute('''
            DELETE FROM ledger_entries
            WHERE reference_table='purchase_orders'
               OR reference_table='purchase_returns'
               OR reference_id IN (SELECT id FROM po_payments WHERE order_id IN (
                   SELECT id FROM purchase_orders WHERE supplier_id=?
               ))
        ''', (self.supplier_id,))
        conn.execute('DELETE FROM ledger_vouchers WHERE voucher_no LIKE ?', ('PO-%',))
        conn.execute('DELETE FROM ledger_vouchers WHERE voucher_no LIKE ?', ('DN-%',))
        conn.execute('DELETE FROM purchase_return_items WHERE return_id IN (SELECT id FROM purchase_returns WHERE order_id IN (SELECT id FROM purchase_orders WHERE supplier_id=?))', (self.supplier_id,))
        conn.execute('DELETE FROM purchase_returns WHERE order_id IN (SELECT id FROM purchase_orders WHERE supplier_id=?)', (self.supplier_id,))
        conn.execute('DELETE FROM po_payments WHERE order_id IN (SELECT id FROM purchase_orders WHERE supplier_id=?)', (self.supplier_id,))
        conn.execute('DELETE FROM purchase_order_items WHERE order_id IN (SELECT id FROM purchase_orders WHERE supplier_id=?)', (self.supplier_id,))
        conn.execute('DELETE FROM purchase_orders WHERE supplier_id=?', (self.supplier_id,))
        conn.execute('DELETE FROM stock_transactions WHERE product_id=?', (self.product_id,))
        conn.execute('DELETE FROM stock_batches WHERE product_id=?', (self.product_id,))
        conn.execute('DELETE FROM products WHERE id=?', (self.product_id,))
        conn.execute('DELETE FROM suppliers WHERE id=?', (self.supplier_id,))
        conn.commit()
        conn.close()

    def test_purchase_return_reduces_stock_supplier_balance_and_posts_debit_note(self):
        response = self.client.post('/api/purchase-orders', json={
            'supplier_id': self.supplier_id,
            'status': 'received',
            'amount_paid': 0,
            'items': [{
                'product_id': self.product_id,
                'product_name': 'Purchase Balance Test Product',
                'quantity': 2,
                'unit_price': 50,
            }],
        })
        self.assertEqual(response.status_code, 201)
        order = response.get_json()['data']
        item_id = order['items'][0]['id']

        returned = self.client.post(f"/api/purchase-orders/{order['id']}/return", json={
            'reason': 'Damaged goods',
            'items': [{'purchase_order_item_id': item_id, 'quantity': 1}],
        })
        self.assertEqual(returned.status_code, 201)
        debit_note = returned.get_json()['data']

        conn = get_db()
        product = conn.execute('SELECT current_stock FROM products WHERE id=?', (self.product_id,)).fetchone()
        supplier = conn.execute('SELECT balance FROM suppliers WHERE id=?', (self.supplier_id,)).fetchone()
        ledger = conn.execute(
            "SELECT debit, credit FROM ledger_entries WHERE reference_table='purchase_returns' AND reference_id=?",
            (debit_note['id'],),
        ).fetchall()
        conn.close()
        self.assertEqual(float(product['current_stock']), 1)
        self.assertEqual(float(supplier['balance']), 50)
        self.assertAlmostEqual(sum(float(row['debit']) for row in ledger), sum(float(row['credit']) for row in ledger), places=2)

        oversized = self.client.post(f"/api/purchase-orders/{order['id']}/return", json={
            'reason': 'Over return',
            'items': [{'purchase_order_item_id': item_id, 'quantity': 2}],
        })
        self.assertEqual(oversized.status_code, 400)

        reversed_note = self.client.post(f"/api/purchase-returns/{debit_note['id']}/reverse", json={
            'reason': 'Supplier accepted replacement instead',
        })
        self.assertEqual(reversed_note.status_code, 200)
        conn = get_db()
        product = conn.execute('SELECT current_stock FROM products WHERE id=?', (self.product_id,)).fetchone()
        supplier = conn.execute('SELECT balance FROM suppliers WHERE id=?', (self.supplier_id,)).fetchone()
        status = conn.execute('SELECT status FROM purchase_returns WHERE id=?', (debit_note['id'],)).fetchone()
        conn.close()
        self.assertEqual(float(product['current_stock']), 2)
        self.assertEqual(float(supplier['balance']), 100)
        self.assertEqual(status['status'], 'reversed')

        duplicate_reverse = self.client.post(f"/api/purchase-returns/{debit_note['id']}/reverse", json={
            'reason': 'Duplicate reversal',
        })
        self.assertEqual(duplicate_reverse.status_code, 400)

    def test_purchase_and_payment_update_supplier_balance_and_ledger(self):
        response = self.client.post('/api/purchase-orders', json={
            'supplier_id': self.supplier_id,
            'status': 'received',
            'amount_paid': 40,
            'payment_mode': 'bank_transfer',
            'items': [{
                'product_id': self.product_id,
                'product_name': 'Purchase Balance Test Product',
                'quantity': 2,
                'unit_price': 50,
            }],
        })
        self.assertEqual(response.status_code, 201)
        order = response.get_json()['data']
        self.assertEqual(order['amount_due'], 60)

        conn = get_db()
        supplier = conn.execute('SELECT balance FROM suppliers WHERE id=?', (self.supplier_id,)).fetchone()
        self.assertEqual(float(supplier['balance']), 60)
        ledger = conn.execute(
            "SELECT debit, credit FROM ledger_entries WHERE reference_table='purchase_orders' AND reference_id=?",
            (order['id'],),
        ).fetchall()
        self.assertAlmostEqual(sum(float(row['debit']) for row in ledger), sum(float(row['credit']) for row in ledger), places=2)
        conn.close()

        payment = self.client.post(f"/api/purchase-orders/{order['id']}/payments", json={
            'amount': 60,
            'payment_mode': 'bank_transfer',
        })
        self.assertEqual(payment.status_code, 200)

        conn = get_db()
        supplier = conn.execute('SELECT balance FROM suppliers WHERE id=?', (self.supplier_id,)).fetchone()
        self.assertEqual(float(supplier['balance']), 0)
        conn.close()


if __name__ == '__main__':
    unittest.main()
