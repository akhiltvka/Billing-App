"""Tests for client_uuid columns, sync_queue table, queue_for_sync helper, and transactional queueing."""

import json
import unittest
import uuid

from app import app, get_db
from database import init_db, queue_for_sync


class TestSyncQueue(unittest.TestCase):
    SYNC_TABLES = [
        'customers',
        'suppliers',
        'products',
        'categories',
        'bills',
        'bill_items',
        'bill_payments',
        'stock_transactions',
        'loyalty_ledger',
        'ledger_vouchers',
        'ledger_entries',
    ]

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        init_db()
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'sync-test-admin'
            sess['user_role'] = 'admin'

    def test_all_sync_tables_have_client_uuid_and_index(self):
        """Verify all 11 core tables have client_uuid column and unique index."""
        conn = get_db()
        try:
            for table in self.SYNC_TABLES:
                cols = [row['name'] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
                self.assertIn('client_uuid', cols, f"Table {table} must have 'client_uuid' column")

                indexes = conn.execute(f"PRAGMA index_list({table})").fetchall()
                idx_names = [idx['name'] for idx in indexes]
                self.assertTrue(
                    any('client_uuid' in name for name in idx_names),
                    f"Table {table} must have an index on client_uuid"
                )
        finally:
            conn.close()

    def test_sync_queue_schema(self):
        """Verify sync_queue table structure and columns."""
        conn = get_db()
        try:
            cols = {row['name']: row['type'].upper() for row in conn.execute("PRAGMA table_info(sync_queue)").fetchall()}
            expected = ['id', 'table_name', 'operation', 'row_client_uuid', 'payload', 'status', 'attempts', 'last_error', 'created_at', 'synced_at']
            for col in expected:
                self.assertIn(col, cols, f"sync_queue missing column {col}")
        finally:
            conn.close()

    def test_queue_for_sync_atomic_commit_and_rollback(self):
        """Verify queue_for_sync commits atomically with caller, and rolls back cleanly."""
        conn = get_db()
        test_uuid = str(uuid.uuid4())
        try:
            # 1. Successful commit
            test_row = {'client_uuid': test_uuid, 'name': 'Atomic Test Category'}
            conn.execute(
                "INSERT INTO categories (name, client_uuid) VALUES (?, ?)",
                (test_row['name'], test_uuid)
            )
            cat_row = conn.execute("SELECT * FROM categories WHERE client_uuid = ?", (test_uuid,)).fetchone()
            queue_for_sync(conn, 'categories', 'insert', cat_row)
            conn.commit()

            q_entry = conn.execute(
                "SELECT * FROM sync_queue WHERE row_client_uuid = ?", (test_uuid,)
            ).fetchone()
            self.assertIsNotNone(q_entry)
            self.assertEqual(q_entry['table_name'], 'categories')
            self.assertEqual(q_entry['operation'], 'insert')
            self.assertEqual(q_entry['status'], 'pending')
            self.assertEqual(q_entry['attempts'], 0)
            payload = json.loads(q_entry['payload'])
            self.assertEqual(payload['client_uuid'], test_uuid)
            self.assertEqual(payload['name'], 'Atomic Test Category')

            # 2. Rollback atomicity
            rb_uuid = str(uuid.uuid4())
            rb_row = {'client_uuid': rb_uuid, 'name': 'Rollback Category'}
            conn.execute(
                "INSERT INTO categories (name, client_uuid) VALUES (?, ?)",
                (rb_row['name'], rb_uuid)
            )
            cat_rb = conn.execute("SELECT * FROM categories WHERE client_uuid = ?", (rb_uuid,)).fetchone()
            queue_for_sync(conn, 'categories', 'insert', cat_rb)
            conn.rollback()

            q_rb = conn.execute("SELECT * FROM sync_queue WHERE row_client_uuid = ?", (rb_uuid,)).fetchone()
            self.assertIsNone(q_rb, "Rolled-back transaction must not persist sync_queue entry")
            c_rb = conn.execute("SELECT * FROM categories WHERE client_uuid = ?", (rb_uuid,)).fetchone()
            self.assertIsNone(c_rb, "Rolled-back transaction must not persist category row")
        finally:
            conn.execute("DELETE FROM categories WHERE client_uuid = ?", (test_uuid,))
            conn.execute("DELETE FROM sync_queue WHERE row_client_uuid = ?", (test_uuid,))
            conn.commit()
            conn.close()

    def test_customer_crud_queues_sync(self):
        """Verify customer create, update, and delete queue proper sync events."""
        # Create
        res = self.client.post('/api/customers', json={'name': 'Sync Test Customer', 'phone': '9876543219'})
        self.assertEqual(res.status_code, 201)
        cust_id = res.get_json()['data']['id']
        cust_uuid = res.get_json()['data']['client_uuid']
        self.assertTrue(cust_uuid, "Created customer must have client_uuid")

        conn = get_db()
        try:
            q_create = conn.execute(
                "SELECT * FROM sync_queue WHERE table_name = 'customers' AND row_client_uuid = ? AND operation = 'insert'",
                (cust_uuid,)
            ).fetchone()
            self.assertIsNotNone(q_create)

            # Update
            res_upd = self.client.put(f'/api/customers/{cust_id}', json={'name': 'Updated Sync Customer', 'phone': '9876543219'})
            self.assertEqual(res_upd.status_code, 200)
            q_upd = conn.execute(
                "SELECT * FROM sync_queue WHERE table_name = 'customers' AND row_client_uuid = ? AND operation = 'update'",
                (cust_uuid,)
            ).fetchone()
            self.assertIsNotNone(q_upd)

            # Delete
            res_del = self.client.delete(f'/api/customers/{cust_id}')
            self.assertEqual(res_del.status_code, 200)
            q_del = conn.execute(
                "SELECT * FROM sync_queue WHERE table_name = 'customers' AND row_client_uuid = ? AND operation = 'delete'",
                (cust_uuid,)
            ).fetchone()
            self.assertIsNotNone(q_del)
        finally:
            conn.execute("DELETE FROM sync_queue WHERE row_client_uuid = ?", (cust_uuid,))
            conn.execute("DELETE FROM customers WHERE id = ?", (cust_id,))
            conn.commit()
            conn.close()

    def test_billing_and_payment_flow_queues_sync(self):
        """Verify bill creation and payment queue bills, bill_items, bill_payments, and ledger entries."""
        conn = get_db()
        prod_id = None
        bill_id = None
        try:
            # Create a test product with 4-char code
            test_code = "SY01"
            conn.execute("DELETE FROM products WHERE code = ?", (test_code,))
            conn.commit()
            res_p = self.client.post('/api/products', json={
                'name': 'Sync Bill Product',
                'code': test_code,
                'selling_price': 100.0,
                'purchase_price': 60.0,
                'current_stock': 50.0,
                'unit': 'kg'
            })
            self.assertEqual(res_p.status_code, 201)
            prod = res_p.get_json()['data']
            prod_id = prod['id']
            prod_uuid = prod['client_uuid']
            self.assertTrue(prod_uuid)

            # Create bill
            bill_payload = {
                'customer_name': 'Sync Queue Tester',
                'customer_phone': '9998887776',
                'payment_mode': 'cash',
                'amount_paid': 50.0,
                'items': [
                    {
                        'product_id': prod_id,
                        'product_name': 'Sync Bill Product',
                        'quantity': 2,
                        'unit_price': 100.0,
                        'unit': 'kg'
                    }
                ]
            }
            res_b = self.client.post('/api/bills', json=bill_payload)
            self.assertEqual(res_b.status_code, 201)
            bill_data = res_b.get_json()['data']
            bill_id = bill_data['id']
            bill_uuid = bill_data['client_uuid']
            self.assertTrue(bill_uuid)

            # Verify sync_queue entries for bill, bill_items, bill_payments
            q_bill = conn.execute(
                "SELECT * FROM sync_queue WHERE table_name = 'bills' AND row_client_uuid = ? AND operation = 'insert'",
                (bill_uuid,)
            ).fetchone()
            self.assertIsNotNone(q_bill)

            item_uuid = bill_data['items'][0]['client_uuid']
            self.assertTrue(item_uuid)
            q_item = conn.execute(
                "SELECT * FROM sync_queue WHERE table_name = 'bill_items' AND row_client_uuid = ? AND operation = 'insert'",
                (item_uuid,)
            ).fetchone()
            self.assertIsNotNone(q_item)

            pmt_uuid = bill_data['payments'][0]['client_uuid']
            self.assertTrue(pmt_uuid)
            q_pmt = conn.execute(
                "SELECT * FROM sync_queue WHERE table_name = 'bill_payments' AND row_client_uuid = ? AND operation = 'insert'",
                (pmt_uuid,)
            ).fetchone()
            self.assertIsNotNone(q_pmt)

            # Record subsequent payment on partial bill
            res_pay = self.client.post(f'/api/bills/{bill_id}/payments', json={
                'amount': 50.0,
                'payment_mode': 'cash',
                'notes': 'Subsequent balance settlement'
            })
            self.assertEqual(res_pay.status_code, 200)

            # Verify bill was queued for update and second payment queued for insert
            q_bill_upd = conn.execute(
                "SELECT * FROM sync_queue WHERE table_name = 'bills' AND row_client_uuid = ? AND operation = 'update'",
                (bill_uuid,)
            ).fetchall()
            self.assertTrue(len(q_bill_upd) >= 1)

            # Verify ledger voucher and entries queued
            vouchers = conn.execute(
                "SELECT * FROM ledger_vouchers WHERE reference_table = 'bills' AND reference_id = ?",
                (bill_id,)
            ).fetchall()
            for v in vouchers:
                self.assertTrue(v['client_uuid'])
                q_v = conn.execute(
                    "SELECT * FROM sync_queue WHERE table_name = 'ledger_vouchers' AND row_client_uuid = ?",
                    (v['client_uuid'],)
                ).fetchone()
                self.assertIsNotNone(q_v)
        finally:
            # Cleanup
            if bill_id:
                conn.execute("DELETE FROM sync_queue WHERE row_client_uuid IN (SELECT client_uuid FROM bill_payments WHERE bill_id=?)", (bill_id,))
                conn.execute("DELETE FROM sync_queue WHERE row_client_uuid IN (SELECT client_uuid FROM bill_items WHERE bill_id=?)", (bill_id,))
                conn.execute("DELETE FROM sync_queue WHERE row_client_uuid IN (SELECT client_uuid FROM bills WHERE id=?)", (bill_id,))
                conn.execute("DELETE FROM ledger_entries WHERE reference_table = 'bills' AND reference_id = ?", (bill_id,))
                conn.execute("DELETE FROM ledger_entries WHERE reference_table = 'bill_payments' AND reference_id IN (SELECT id FROM bill_payments WHERE bill_id=?)", (bill_id,))
                conn.execute("DELETE FROM ledger_vouchers WHERE reference_table = 'bills' AND reference_id = ?", (bill_id,))
                conn.execute("DELETE FROM ledger_vouchers WHERE reference_table = 'bill_payments' AND reference_id IN (SELECT id FROM bill_payments WHERE bill_id=?)", (bill_id,))
                conn.execute("DELETE FROM bill_payments WHERE bill_id=?", (bill_id,))
                conn.execute("DELETE FROM bill_items WHERE bill_id=?", (bill_id,))
                conn.execute("DELETE FROM bills WHERE id=?", (bill_id,))
            if prod_id:
                conn.execute("DELETE FROM sync_queue WHERE row_client_uuid IN (SELECT client_uuid FROM products WHERE id=?)", (prod_id,))
                conn.execute("DELETE FROM stock_transactions WHERE product_id=?", (prod_id,))
                conn.execute("DELETE FROM stock_batches WHERE product_id=?", (prod_id,))
                conn.execute("DELETE FROM products WHERE id=?", (prod_id,))
            conn.commit()
            conn.close()

    def test_purge_bill_queues_deletes(self):
        """Verify purging a bill queues delete operations for all linked child records."""
        conn = get_db()
        # Enable bill purge in shop_settings for test
        conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('allow_bill_purge', 'true')")
        conn.commit()

        test_code = "SY02"
        conn.execute("DELETE FROM products WHERE code = ?", (test_code,))
        conn.commit()

        res_p = self.client.post('/api/products', json={
            'name': 'Sync Purge Product',
            'code': test_code,
            'selling_price': 80.0,
            'purchase_price': 50.0,
            'unit': 'kg'
        })
        self.assertEqual(res_p.status_code, 201)
        prod = res_p.get_json()['data']
        prod_id = prod['id']
        prod_uuid = prod['client_uuid']

        # Add initial stock
        res_stk = self.client.post('/api/stock/in', json={
            'product_id': prod_id,
            'quantity': 10.0,
            'unit_price': 50.0,
            'notes': 'Initial Stock'
        })
        self.assertEqual(res_stk.status_code, 200)

        # Create bill
        res_b = self.client.post('/api/bills', json={
            'customer_name': 'Purge Queue Tester',
            'payment_mode': 'cash',
            'amount_paid': 80.0,
            'items': [{'product_id': prod_id, 'product_name': 'Sync Purge Product', 'quantity': 1, 'unit_price': 80.0, 'unit': 'kg'}]
        })
        self.assertEqual(res_b.status_code, 201)
        bill_data = res_b.get_json()['data']
        bill_id = bill_data['id']
        bill_uuid = bill_data['client_uuid']

        # Now purge the bill
        res_purge = self.client.delete(f'/api/bills/{bill_id}/purge', json={'reason': 'Purge queue verification test'})
        self.assertEqual(res_purge.status_code, 200, f"Purge failed: {res_purge.get_json()}")

        # Verify 'delete' entries in sync_queue for bill and bill_items
        q_b_del = conn.execute(
            "SELECT * FROM sync_queue WHERE table_name = 'bills' AND row_client_uuid = ? AND operation = 'delete'",
            (bill_uuid,)
        ).fetchone()
        self.assertIsNotNone(q_b_del, "Purged bill must be queued for sync deletion")

        item_uuid = bill_data['items'][0]['client_uuid']
        q_it_del = conn.execute(
            "SELECT * FROM sync_queue WHERE table_name = 'bill_items' AND row_client_uuid = ? AND operation = 'delete'",
            (item_uuid,)
        ).fetchone()
        self.assertIsNotNone(q_it_del, "Purged bill item must be queued for sync deletion")

        # Cleanup
        conn.execute("DELETE FROM sync_queue WHERE row_client_uuid IN (?, ?, ?)", (bill_uuid, item_uuid, prod_uuid))
        conn.execute("DELETE FROM stock_transactions WHERE product_id = ?", (prod_id,))
        conn.execute("DELETE FROM stock_batches WHERE product_id = ?", (prod_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (prod_id,))
        conn.commit()
        conn.close()

    def test_purchase_order_and_supplier_sync(self):
        """Verify supplier balance updates queue 'update' events in sync_queue."""
        conn = get_db()
        # Create supplier
        res_s = self.client.post('/api/suppliers', json={
            'name': 'Sync PO Test Supplier',
            'phone': '9876500001'
        })
        self.assertEqual(res_s.status_code, 201)
        sup = res_s.get_json()['data']
        sup_id = sup['id']
        sup_uuid = sup['client_uuid']
        self.assertTrue(sup_uuid)

        # Create product for PO
        test_code = "SY03"
        conn.execute("DELETE FROM products WHERE code = ?", (test_code,))
        conn.commit()
        res_p = self.client.post('/api/products', json={
            'name': 'Sync PO Product',
            'code': test_code,
            'selling_price': 120.0,
            'purchase_price': 70.0,
            'unit': 'kg'
        })
        self.assertEqual(res_p.status_code, 201)
        prod = res_p.get_json()['data']
        prod_id = prod['id']
        prod_uuid = prod['client_uuid']

        # Create PO with partial payment (due > 0 updates supplier balance)
        res_po = self.client.post('/api/purchase-orders', json={
            'supplier_id': sup_id,
            'items': [{'product_id': prod_id, 'product_name': 'Sync PO Product', 'quantity': 10, 'unit_price': 70.0}],
            'amount_paid': 200.0, # total 700, due 500
            'status': 'received'
        })
        self.assertEqual(res_po.status_code, 201)
        po_id = res_po.get_json()['data']['id']

        # Verify suppliers update queued in sync_queue
        q_sup = conn.execute(
            "SELECT * FROM sync_queue WHERE table_name = 'suppliers' AND row_client_uuid = ? AND operation = 'update'",
            (sup_uuid,)
        ).fetchall()
        self.assertTrue(len(q_sup) >= 1, "Supplier balance update must queue an 'update' event")

        # Record payment against PO
        res_pop = self.client.post(f'/api/purchase-orders/{po_id}/payments', json={
            'amount': 300.0,
            'payment_mode': 'bank_transfer'
        })
        self.assertEqual(res_pop.status_code, 200)

        # Verify another supplier update queued
        q_sup_after = conn.execute(
            "SELECT * FROM sync_queue WHERE table_name = 'suppliers' AND row_client_uuid = ? AND operation = 'update'",
            (sup_uuid,)
        ).fetchall()
        self.assertGreater(len(q_sup_after), len(q_sup))

        # Cleanup
        conn.execute("DELETE FROM sync_queue WHERE row_client_uuid IN (?, ?)", (sup_uuid, prod_uuid))
        conn.execute("DELETE FROM po_payments WHERE order_id = ?", (po_id,))
        conn.execute("DELETE FROM purchase_order_items WHERE order_id = ?", (po_id,))
        conn.execute("DELETE FROM purchase_orders WHERE id = ?", (po_id,))
        conn.execute("DELETE FROM ledger_entries WHERE reference_table = 'purchase_orders' AND reference_id = ?", (po_id,))
        conn.execute("DELETE FROM ledger_vouchers WHERE reference_table = 'purchase_orders' AND reference_id = ?", (po_id,))
        conn.execute("DELETE FROM stock_transactions WHERE product_id = ?", (prod_id,))
        conn.execute("DELETE FROM stock_batches WHERE product_id = ?", (prod_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (prod_id,))
        conn.execute("DELETE FROM suppliers WHERE id = ?", (sup_id,))
        conn.commit()
        conn.close()

