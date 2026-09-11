"""
Unit tests for sync_worker.py
Tests background synchronization, queue sorting, FK resolution, upsert generation,
failure tolerance, and telemetry status reporting.
"""

import os
import json
import uuid
import sqlite3
import pytest
from unittest.mock import patch, MagicMock

import time

import sync_worker
from database import init_db, get_db, queue_for_sync
from app import app


@pytest.fixture(autouse=True)
def clean_sync_state():
    """Ensure sync lock is released and state is clean before and after each test."""
    sync_worker._is_syncing = False
    if sync_worker._sync_lock.locked():
        try:
            sync_worker._sync_lock.release()
        except RuntimeError:
            pass
    yield
    sync_worker._is_syncing = False
    if sync_worker._sync_lock.locked():
        try:
            sync_worker._sync_lock.release()
        except RuntimeError:
            pass
    sync_worker.close_pg_pool()


@pytest.fixture
def test_db():
    """Ensure database is initialized for test and shop_settings license flags are clean."""
    app.config['TESTING'] = True
    init_db()
    conn = get_db()
    # Clean up sync_queue for isolation
    conn.execute("DELETE FROM sync_queue")
    # Reset shop_settings keys outlet_revoked and outlet_needs_reregister to '0' before test
    conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_revoked', '0')")
    conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_needs_reregister', '0')")
    conn.commit()
    try:
        yield conn
    finally:
        # Reset shop_settings keys outlet_revoked and outlet_needs_reregister to '0' after test
        try:
            conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_revoked', '0')")
            conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_needs_reregister', '0')")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
            # Double check with an independent connection in case conn was modified or closed
            cleanup_conn = get_db()
            cleanup_conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_revoked', '0')")
            cleanup_conn.execute("INSERT OR REPLACE INTO shop_settings (key, value) VALUES ('outlet_needs_reregister', '0')")
            cleanup_conn.commit()
            cleanup_conn.close()


def test_offline_skips_silently(test_db):
    """When offline, process_sync_queue skips silently and does not attempt any remote operations."""
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status) VALUES (?, ?, ?, ?, ?)",
        ("customers", "insert", str(uuid.uuid4()), json.dumps({"name": "Offline Customer"}), "pending")
    )
    test_db.commit()

    with patch('sync_worker.check_internet_connection', return_value=False):
        with patch('sync_worker.get_supabase_connection') as mock_conn:
            synced, failed = sync_worker.process_sync_queue()
            assert synced == 0
            assert failed == 0
            mock_conn.assert_not_called()

    # Verify row is still pending
    row = test_db.execute("SELECT status, attempts FROM sync_queue WHERE table_name = 'customers'").fetchone()
    assert row['status'] == 'pending'
    assert row['attempts'] == 0


def test_queue_sorting_parent_before_child(test_db):
    """
    When rows have the exact same timestamp (committed in the same batch),
    parent tables (customers, bills) must be ordered before child tables (bill_items, loyalty_ledger).
    """
    same_ts = "2026-09-11 12:00:00"
    rows_data = [
        ("bill_items", "insert", str(uuid.uuid4()), "{}", same_ts),
        ("bills", "insert", str(uuid.uuid4()), "{}", same_ts),
        ("customers", "insert", str(uuid.uuid4()), "{}", same_ts),
        ("bill_payments", "insert", str(uuid.uuid4()), "{}", same_ts),
        ("categories", "insert", str(uuid.uuid4()), "{}", same_ts),
        ("products", "insert", str(uuid.uuid4()), "{}", same_ts),
    ]

    for tbl, op, u, p, ts in rows_data:
        test_db.execute(
            "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (tbl, op, u, p, ts)
        )
    test_db.commit()

    rows = test_db.execute("SELECT * FROM sync_queue WHERE status = 'pending'").fetchall()
    items = [dict(r) for r in rows]
    items.sort(key=lambda r: (
        r.get('created_at') or '',
        sync_worker.TABLE_SYNC_PRIORITY.get(r.get('table_name'), 999),
        r.get('id') or 0
    ))

    sorted_tables = [item['table_name'] for item in items]
    assert sorted_tables == ['categories', 'products', 'customers', 'bills', 'bill_items', 'bill_payments']


def test_foreign_key_resolution_and_payload_sanitization(test_db):
    """
    Verify sanitize_payload_for_sync resolves local integer foreign keys
    (e.g., bill_id, product_id) to parent client_uuid values.
    """
    # Create parent category, product, and bill
    cat_uuid = str(uuid.uuid4())
    cat_name = f"Test Poultry {cat_uuid[:8]}"
    test_db.execute("INSERT INTO categories (name, client_uuid) VALUES (?, ?)", (cat_name, cat_uuid))
    cat_id = test_db.execute("SELECT id FROM categories WHERE client_uuid = ?", (cat_uuid,)).fetchone()['id']

    prod_uuid = str(uuid.uuid4())
    prod_code = f"T{cat_uuid[:4].upper()}"
    test_db.execute("INSERT INTO products (name, code, category_id, client_uuid) VALUES ('Chicken Curry Cut', ?, ?, ?)", (prod_code, cat_id, prod_uuid))
    prod_id = test_db.execute("SELECT id FROM products WHERE client_uuid = ?", (prod_uuid,)).fetchone()['id']

    bill_uuid = str(uuid.uuid4())
    bill_no = f"MPI-TEST-{bill_uuid[:8]}"
    test_db.execute("INSERT INTO bills (bill_no, client_uuid) VALUES (?, ?)", (bill_no, bill_uuid))
    bill_id = test_db.execute("SELECT id FROM bills WHERE client_uuid = ?", (bill_uuid,)).fetchone()['id']
    test_db.commit()

    # Product payload with integer category_id
    raw_prod_payload = {
        'id': prod_id,
        'name': 'Chicken Curry Cut',
        'code': 'CHIC1',
        'category_id': cat_id,
        'purchase_price': 150.0,
        'active': 1,
        'is_price_inclusive_of_tax': 1,
        'client_uuid': prod_uuid,
        'unknown_column': 'should_be_stripped'
    }

    sanitized_prod = sync_worker.sanitize_payload_for_sync('products', raw_prod_payload, test_db)
    assert 'id' not in sanitized_prod
    assert 'unknown_column' not in sanitized_prod
    assert sanitized_prod['category_id'] == cat_uuid
    assert sanitized_prod['active'] is True
    assert sanitized_prod['is_price_inclusive_of_tax'] is True
    assert 'tenant_id' in sanitized_prod
    assert sanitized_prod['tenant_id'] == sync_worker.get_tenant_id()

    # Bill item payload with integer bill_id and product_id
    raw_bi_payload = {
        'id': 101,
        'bill_id': bill_id,
        'product_id': prod_id,
        'product_name': 'Chicken Curry Cut',
        'quantity': 1.5,
        'unit_price': 200.0,
        'amount': 300.0,
        'client_uuid': str(uuid.uuid4())
    }

    sanitized_bi = sync_worker.sanitize_payload_for_sync('bill_items', raw_bi_payload, test_db)
    assert 'id' not in sanitized_bi
    assert sanitized_bi['bill_id'] == bill_uuid
    assert sanitized_bi['product_id'] == prod_uuid
    assert sanitized_bi['amount'] == 300.0
    assert 'tenant_id' in sanitized_bi


def test_build_upsert_and_delete_sql():
    """Verify PostgreSQL upsert and delete queries generation with tenant isolation."""
    cust_uuid = str(uuid.uuid4())
    payload = {
        'client_uuid': cust_uuid,
        'name': 'John Doe',
        'phone': '9876543210',
        'is_active': True,
        'tenant_id': 'TENANT_TEST_123'
    }

    sql, values = sync_worker.build_upsert_sql('customers', payload, cust_uuid)
    assert "INSERT INTO customers" in sql
    assert "ON CONFLICT (client_uuid) DO UPDATE SET" in sql
    assert "synced_at = now()" in sql
    assert values == [cust_uuid, 'John Doe', '9876543210', True, 'TENANT_TEST_123']

    del_sql, del_values = sync_worker.build_delete_sql('customers', cust_uuid, tenant_id='TENANT_TEST_123')
    assert del_sql.strip() == "DELETE FROM customers WHERE client_uuid = %s AND tenant_id = %s;"
    assert del_values == [cust_uuid, 'TENANT_TEST_123']


def test_tenant_isolation_payload_stamping(test_db):
    """Verify tenant_id environment override stamps distinct tenant IDs for multi-shop isolation."""
    raw_payload = {'name': 'Shop Item', 'code': 'ITEM01', 'client_uuid': str(uuid.uuid4())}

    with patch.dict('os.environ', {'TENANT_ID': 'OUTLET_KOCHI'}):
        res_kochi = sync_worker.sanitize_payload_for_sync('products', raw_payload, test_db)
        assert res_kochi['tenant_id'] == 'OUTLET_KOCHI'

    with patch.dict('os.environ', {'TENANT_ID': 'OUTLET_TRIVANDRUM'}):
        res_tvm = sync_worker.sanitize_payload_for_sync('products', raw_payload, test_db)
        assert res_tvm['tenant_id'] == 'OUTLET_TRIVANDRUM'

    assert res_kochi['tenant_id'] != res_tvm['tenant_id']


def test_sync_queue_tolerance_to_individual_row_failure(test_db):
    """
    When row 1 fails (e.g. database error), row 1 is marked 'failed' and attempts incremented,
    while row 2 still proceeds and is marked 'synced'. Subsequent rows are not blocked.
    """
    uuid_fail = str(uuid.uuid4())
    uuid_ok = str(uuid.uuid4())

    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, attempts, created_at) VALUES (?, ?, ?, ?, 'pending', 0, '2026-09-11 10:00:00')",
        ("customers", "insert", uuid_fail, json.dumps({"name": "Faulty Customer"}),)
    )
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, attempts, created_at) VALUES (?, ?, ?, ?, 'pending', 0, '2026-09-11 10:00:01')",
        ("customers", "insert", uuid_ok, json.dumps({"name": "Good Customer"}),)
    )
    test_db.commit()

    # Mock Supabase PG Connection
    mock_pg_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_pg_conn.cursor.return_value = mock_cursor

    def mock_execute(sql, values):
        if uuid_fail in values:
            raise sqlite3.DatabaseError("Remote syntax error on faulty customer")
        return None

    mock_cursor.execute.side_effect = mock_execute

    with patch('sync_worker.check_internet_connection', return_value=True):
        with patch('sync_worker.get_supabase_connection') as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = (mock_pg_conn, None)
            synced, failed = sync_worker.process_sync_queue()

    assert synced == 1
    assert failed == 1

    row_fail = test_db.execute("SELECT status, attempts, last_error FROM sync_queue WHERE row_client_uuid = ?", (uuid_fail,)).fetchone()
    assert row_fail['status'] == 'failed'
    assert row_fail['attempts'] == 1
    assert "Remote syntax error" in row_fail['last_error']

    row_ok = test_db.execute("SELECT status, attempts, synced_at, last_error FROM sync_queue WHERE row_client_uuid = ?", (uuid_ok,)).fetchone()
    assert row_ok['status'] == 'synced'
    assert row_ok['attempts'] == 0
    assert row_ok['synced_at'] is not None
    assert row_ok['last_error'] is None


def test_get_sync_status_telemetry(test_db):
    """Verify get_sync_status accurately computes pending, failed, and synced totals."""
    test_db.execute("INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status) VALUES ('customers', 'insert', 'u1', '{}', 'pending')")
    test_db.execute("INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, attempts, last_error) VALUES ('customers', 'insert', 'u2', '{}', 'failed', 2, 'Timeout')")
    test_db.execute("INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, synced_at) VALUES ('customers', 'insert', 'u3', '{}', 'synced', '2026-09-11 14:00:00')")
    test_db.commit()

    with patch('sync_worker.check_internet_connection', return_value=True):
        status = sync_worker.get_sync_status()

    assert status['pending_count'] == 1
    assert status['failed_count'] == 1
    assert status['total_synced'] == 1
    assert status['last_synced_at'] == '2026-09-11 14:00:00'
    assert status['is_online'] is True
    assert status['is_syncing'] is False


def test_api_sync_status_endpoint(test_db):
    """Verify /api/sync/status endpoint returns valid telemetry data."""
    client = app.test_client()

    with patch('sync_worker.check_internet_connection', return_value=True), \
         patch('license_manager.check_internet_connection', return_value=True), \
         patch('license_sync.sync_with_cloud_server', return_value=(True, "OK")):

        # 1. Unauthenticated should fail
        resp = client.get('/api/sync/status')
        assert resp.status_code in (401, 403)

        # 2. Authenticated as Admin
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role'] = 'admin'

        resp = client.get('/api/sync/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] in ('ok', 'success')
        assert 'pending_count' in data['data']
        assert 'failed_count' in data['data']
        assert 'total_synced' in data['data']
        assert 'is_online' in data['data']


def test_concurrency_lock_prevents_overlapping_runs():
    """Verify when _sync_lock is already held, a second invocation immediately returns (0, 0)."""
    assert not sync_worker._sync_lock.locked()
    sync_worker._sync_lock.acquire()
    try:
        synced, failed = sync_worker.process_sync_queue()
        assert synced == 0
        assert failed == 0
    finally:
        sync_worker._sync_lock.release()


def test_prune_synced_queue_older_than_30_days(test_db):
    """Pruning deletes rows with status='synced' older than retention_days, keeping younger or pending rows."""
    # 1. Old synced row (>30 days ago) -> should be deleted
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, synced_at) VALUES ('bills', 'insert', 'old_u', '{}', 'synced', datetime('now', '-35 days'))"
    )
    # 2. Recent synced row (<30 days ago) -> should be kept
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, synced_at) VALUES ('bills', 'insert', 'recent_u', '{}', 'synced', datetime('now', '-5 days'))"
    )
    # 3. Old failed row (>30 days ago) -> should be kept (never prune unsynced data!)
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, synced_at) VALUES ('bills', 'insert', 'failed_u', '{}', 'failed', datetime('now', '-35 days'))"
    )
    # 4. Old pending row (>30 days ago) -> should be kept
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status) VALUES ('bills', 'insert', 'pending_u', '{}', 'pending')"
    )
    test_db.commit()

    pruned = sync_worker.prune_synced_queue(retention_days=30)
    assert pruned == 1

    remaining = [r['row_client_uuid'] for r in test_db.execute("SELECT row_client_uuid FROM sync_queue ORDER BY row_client_uuid").fetchall()]
    assert 'old_u' not in remaining
    assert 'recent_u' in remaining
    assert 'failed_u' in remaining
    assert 'pending_u' in remaining


def test_retry_failed_sync_queue(test_db):
    """retry_failed_sync_queue resets status='failed' rows back to 'pending' with attempts=0 and clears last_error."""
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, attempts, last_error) VALUES ('products', 'update', 'u1', '{}', 'failed', 4, 'Network timeout')"
    )
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, attempts, last_error) VALUES ('products', 'update', 'u2', '{}', 'failed', 10, 'Remote constraint')"
    )
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, attempts, last_error) VALUES ('products', 'update', 'u3', '{}', 'synced', 0, NULL)"
    )
    test_db.commit()

    with patch('sync_worker.trigger_sync_async') as mock_trigger:
        reset_count = sync_worker.retry_failed_sync_queue()
        assert reset_count == 2
        mock_trigger.assert_called_once()

    rows = test_db.execute("SELECT row_client_uuid, status, attempts, last_error FROM sync_queue WHERE row_client_uuid IN ('u1', 'u2')").fetchall()
    for r in rows:
        assert r['status'] == 'pending'
        assert r['attempts'] == 0
        assert r['last_error'] is None


def test_api_sync_retry_failed_endpoint(test_db):
    """Verify POST /api/sync/retry-failed resets failed rows and returns updated status."""
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status, attempts, last_error) VALUES ('bills', 'insert', 'u_retry', '{}', 'failed', 3, 'Timeout')"
    )
    test_db.commit()

    client = app.test_client()

    with patch('sync_worker.trigger_sync_async') as mock_trigger, \
         patch('sync_worker.check_internet_connection', return_value=True), \
         patch('license_manager.check_internet_connection', return_value=True), \
         patch('license_sync.sync_with_cloud_server', return_value=(True, "OK")):

        # 1. Unauthenticated request
        resp_unauth = client.post('/api/sync/retry-failed')
        assert resp_unauth.status_code in (401, 403)

        # 2. Authenticated Admin request
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
            sess['role'] = 'admin'

        resp = client.post('/api/sync/retry-failed')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] in ('ok', 'success')
        assert data['data']['reset_count'] == 1
        assert data['data']['status']['failed_count'] == 0
        assert data['data']['status']['pending_count'] == 1


def test_sync_failure_logging_context(test_db):
    """Verify sync failure logs to app logger with table, client_uuid, error, and no plaintext customer payload."""
    test_uuid = str(uuid.uuid4())
    customer_payload = {
        'name': 'Private Customer Name',
        'phone': '9876543210',
        'address': 'Secret Address 123'
    }
    test_db.execute(
        "INSERT INTO sync_queue (table_name, operation, row_client_uuid, payload, status) VALUES ('customers', 'insert', ?, ?, 'pending')",
        (test_uuid, json.dumps(customer_payload))
    )
    test_db.commit()

    mock_pg_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_pg_conn.cursor.return_value = mock_cursor
    mock_cursor.execute.side_effect = Exception("DB Connection closed by remote host with password=secret123")

    with patch('sync_worker.logger.error') as mock_log_err:
        with patch('sync_worker.check_internet_connection', return_value=True):
            with patch('sync_worker.get_supabase_connection') as mock_conn:
                mock_conn.return_value.__enter__.return_value = (mock_pg_conn, None)
                sync_worker.process_sync_queue()

        mock_log_err.assert_called_once()
        log_msg = mock_log_err.call_args[0][0]
        log_args = mock_log_err.call_args[0][1:]
        full_log_str = log_msg % log_args

        # Context present
        assert "table='customers'" in full_log_str
        assert test_uuid in full_log_str
        assert "DB Connection closed" in full_log_str

        # Secrets and private customer data NOT exposed
        assert "password=secret123" not in full_log_str
        assert "password=***" in full_log_str
        assert "Private Customer Name" not in full_log_str
        assert "Secret Address" not in full_log_str

