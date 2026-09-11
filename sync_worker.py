"""
sync_worker.py — Background Sync Worker for Supabase PostgreSQL Mirror
Meat Products of India — Billing & Inventory Management App

Performs non-blocking background synchronization of the local SQLite `sync_queue`
to the Supabase PostgreSQL mirror.
- Reuses license_manager.check_internet_connection() to detect online status.
- Preserves write order with timestamp + parent-before-child ordering.
- Resolves local integer foreign keys to authoritative client_uuid values.
- Executes conflict-safe upserts: INSERT ... ON CONFLICT (client_uuid) DO UPDATE SET ...
- Records telemetry accessible via /api/sync/status.
- Runs every 60 seconds in the background and triggers immediately on API mutations.
"""

import os
import sys
import json
import time
import uuid
import logging
import re
import threading
from contextlib import contextmanager
from datetime import datetime

from database import get_db, get_database_url
from license_manager import check_internet_connection, get_machine_id

logger = logging.getLogger("sync_worker")


def get_tenant_id() -> str:
    """
    Returns the authoritative tenant identifier for this installation.
    Prefers TENANT_ID environment variable (useful in test suites / custom overrides),
    falling back to the deterministic hardware machine ID.
    """
    return os.environ.get('TENANT_ID') or get_machine_id()


def _sanitize_error_message(err_str: str) -> str:
    """Masks database passwords or credentials from error strings."""
    if not err_str:
        return ""
    # Mask passwords in URLs e.g. postgresql://user:password@host:port/db
    sanitized = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', str(err_str))
    # Mask password parameters (quoted or unquoted)
    sanitized = re.sub(r'password\s*=\s*([\'"][^\'"]*[\'"]|[^\s;,]+)', 'password=***', sanitized, flags=re.IGNORECASE)
    return sanitized


# Sync interval default: 60 seconds
SYNC_INTERVAL_SECONDS = 60

# Concurrency locks and status state
_sync_lock = threading.Lock()
_is_syncing = False
_pg_pool = None
_pg_pool_lock = threading.Lock()

# Table dependency ordering (parent tables before child tables when timestamps tie)
TABLE_SYNC_PRIORITY = {
    'categories': 10,
    'products': 20,
    'customers': 30,
    'suppliers': 40,
    'bills': 50,
    'bill_items': 60,
    'bill_payments': 70,
    'loyalty_ledger': 80,
    'stock_transactions': 90,
    'ledger_vouchers': 100,
    'ledger_entries': 110,
}

# Mapping of local foreign key columns to target parent tables
FK_MAPPINGS = {
    'categories': {
        'parent_category_id': 'categories'
    },
    'products': {
        'category_id': 'categories'
    },
    'customers': {},
    'suppliers': {},
    'bills': {
        'customer_id': 'customers'
    },
    'bill_items': {
        'bill_id': 'bills',
        'product_id': 'products'
    },
    'bill_payments': {
        'bill_id': 'bills'
    },
    'loyalty_ledger': {
        'customer_id': 'customers',
        'bill_id': 'bills'
    },
    'stock_transactions': {
        'product_id': 'products',
        'supplier_id': 'suppliers'
    },
    'ledger_vouchers': {},
    'ledger_entries': {}
}

# Exact valid columns allowed in Supabase PostgreSQL mirror
TABLE_COLUMNS = {
    'categories': {
        'client_uuid', 'name', 'gst_rate', 'hsn_code', 'description',
        'parent_category_id', 'created_at'
    },
    'products': {
        'client_uuid', 'category_id', 'name', 'code', 'hsn_code', 'unit',
        'purchase_unit', 'sale_unit', 'conversion_factor', 'purchase_price',
        'selling_price', 'gst_rate', 'min_stock', 'current_stock', 'barcode',
        'product_type', 'mrp', 'is_price_inclusive_of_tax', 'brand', 'pack_size',
        'reorder_lead_time_days', 'shelf_life_days', 'active', 'created_at', 'updated_at'
    },
    'customers': {
        'client_uuid', 'name', 'phone', 'email', 'address', 'gstin', 'state_code',
        'credit_balance', 'loyalty_points', 'is_active', 'created_at'
    },
    'suppliers': {
        'client_uuid', 'name', 'contact_person', 'phone', 'email', 'address',
        'gstin', 'balance', 'created_at'
    },
    'bills': {
        'client_uuid', 'bill_no', 'customer_id', 'customer_name', 'customer_phone',
        'customer_gstin', 'place_of_supply', 'is_interstate', 'date', 'subtotal',
        'discount_percent', 'discount_amount', 'cgst', 'sgst', 'igst', 'grand_total',
        'amount_paid', 'amount_due', 'change_amount', 'payment_mode', 'notes',
        'cancel_reason', 'status', 'is_test'
    },
    'bill_items': {
        'client_uuid', 'bill_id', 'product_id', 'product_name', 'hsn_code', 'unit',
        'quantity', 'unit_price', 'gst_rate', 'discount', 'taxable_amt', 'cgst_amt',
        'sgst_amt', 'igst_amt', 'amount', 'cost_price'
    },
    'bill_payments': {
        'client_uuid', 'bill_id', 'amount', 'payment_mode', 'paid_at', 'received_by', 'notes'
    },
    'loyalty_ledger': {
        'client_uuid', 'customer_id', 'bill_id', 'points_change', 'reason', 'created_at'
    },
    'stock_transactions': {
        'client_uuid', 'product_id', 'type', 'quantity', 'unit_price', 'reference_id',
        'supplier_id', 'expiry_date', 'notes', 'date', 'status', 'created_by',
        'approved_by', 'purchase_date'
    },
    'ledger_vouchers': {
        'client_uuid', 'voucher_type', 'voucher_no', 'voucher_date', 'reference_table',
        'reference_id', 'created_by', 'created_at'
    },
    'ledger_entries': {
        'client_uuid', 'voucher_type', 'voucher_no', 'voucher_date', 'account_id',
        'debit', 'credit', 'narration', 'reference_table', 'reference_id', 'created_by', 'created_at'
    }
}

# Whitelist tenant_id across all mirrored tables
for _tbl in TABLE_COLUMNS:
    TABLE_COLUMNS[_tbl].add('tenant_id')

BOOLEAN_COLUMNS = {
    'products': {'is_price_inclusive_of_tax', 'active'},
    'customers': {'is_active'},
    'bills': {'is_interstate', 'is_test'}
}

DATE_COLUMNS = {
    'stock_transactions': {'expiry_date', 'purchase_date'},
    'ledger_vouchers': {'voucher_date'},
    'ledger_entries': {'voucher_date'}
}


def is_uuid_str(val) -> bool:
    """Return True if val is a valid UUID string format."""
    if not isinstance(val, str):
        return False
    try:
        uuid.UUID(val)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def get_pg_pool():
    """
    Initializes and returns the thread-safe psycopg2 connection pool.
    Enforces sslmode=require. Returns None if connection string is missing or invalid.
    """
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool

    with _pg_pool_lock:
        if _pg_pool is not None:
            return _pg_pool

        db_url = get_database_url()
        if not db_url:
            return None

        connect_kwargs = {'connect_timeout': 10}
        if 'sslmode=' not in db_url:
            connect_kwargs['sslmode'] = 'require'

        try:
            from psycopg2 import pool
            _pg_pool = pool.ThreadedConnectionPool(minconn=1, maxconn=5, dsn=db_url, **connect_kwargs)
            return _pg_pool
        except Exception as exc:
            print(f"[Sync Worker] Connection pool initialization notice: {exc}")
            return None


def close_pg_pool():
    """Closes the connection pool (used during app shutdown or tests)."""
    global _pg_pool
    with _pg_pool_lock:
        if _pg_pool is not None:
            try:
                _pg_pool.closeall()
            except Exception:
                pass
            _pg_pool = None


@contextmanager
def get_supabase_connection():
    """
    Context manager that leases a pooled connection to Supabase PostgreSQL.
    Yields (conn, None) or (None, error_str).
    """
    pool = get_pg_pool()
    if pool is None:
        yield None, "PostgreSQL connection pool is not available."
        return

    conn = None
    try:
        conn = pool.getconn()
        conn.autocommit = False
        yield conn, None
    except Exception as exc:
        yield None, f"Failed to acquire database connection: {exc}"
    finally:
        if conn is not None and pool is not None:
            try:
                pool.putconn(conn)
            except Exception:
                pass


def sanitize_payload_for_sync(table_name: str, payload_dict: dict, sqlite_conn) -> dict:
    """
    Prepares a row payload for Supabase insertion:
    1. Removes local SQLite `id`.
    2. Resolves integer foreign keys to corresponding parent `client_uuid`s.
    3. Handles polymorphic reference_id in ledger tables.
    4. Converts 0/1 integer flags to native booleans.
    5. Converts empty date strings to None.
    6. Filters only columns valid in the target Supabase table.
    """
    sanitized = dict(payload_dict)

    # 1. Remove local SQLite autoincrement id
    sanitized.pop('id', None)

    # 2. Resolve Foreign Keys
    table_fk_rules = FK_MAPPINGS.get(table_name, {})
    for fk_col, parent_table in table_fk_rules.items():
        val = sanitized.get(fk_col)
        if val is not None and val != '':
            if not is_uuid_str(str(val)):
                # Query local SQLite for parent's client_uuid
                try:
                    p_row = sqlite_conn.execute(
                        f"SELECT client_uuid FROM {parent_table} WHERE id = ?", (val,)
                    ).fetchone()
                    if p_row and p_row['client_uuid']:
                        sanitized[fk_col] = p_row['client_uuid']
                    else:
                        sanitized[fk_col] = None
                except Exception:
                    sanitized[fk_col] = None

    # 3. Handle Polymorphic reference_id for ledger_vouchers & ledger_entries
    if table_name in ('ledger_vouchers', 'ledger_entries'):
        ref_tbl = sanitized.get('reference_table')
        ref_id = sanitized.get('reference_id')
        if ref_tbl in ('bills', 'bill_payments', 'products', 'customers', 'suppliers') and ref_id:
            if not is_uuid_str(str(ref_id)):
                try:
                    p_row = sqlite_conn.execute(
                        f"SELECT client_uuid FROM {ref_tbl} WHERE id = ?", (ref_id,)
                    ).fetchone()
                    if p_row and p_row['client_uuid']:
                        sanitized['reference_id'] = p_row['client_uuid']
                except Exception:
                    pass

    # 4. Convert Booleans
    bool_cols = BOOLEAN_COLUMNS.get(table_name, set())
    for b_col in bool_cols:
        if b_col in sanitized:
            v = sanitized[b_col]
            sanitized[b_col] = bool(v) if v is not None else False

    # 5. Convert Empty Date Strings to None
    date_cols = DATE_COLUMNS.get(table_name, set())
    for d_col in date_cols:
        if d_col in sanitized:
            v = sanitized[d_col]
            if v == "" or v is None or str(v).lower() == 'none' or str(v).lower() == 'null':
                sanitized[d_col] = None
            elif isinstance(v, str):
                # Clean timestamp to calendar date if needed
                sanitized[d_col] = v[:10]

    # 6. Stamp tenant_id if not explicitly provided or empty
    if 'tenant_id' not in sanitized or not sanitized['tenant_id']:
        sanitized['tenant_id'] = get_tenant_id()

    # 7. Filter strictly allowed columns
    allowed_cols = TABLE_COLUMNS.get(table_name, set())
    return {k: v for k, v in sanitized.items() if k in allowed_cols}


def build_upsert_sql(table_name: str, payload: dict, row_client_uuid: str):
    """
    Builds the PostgreSQL parameterized upsert query:
    INSERT INTO <table> (...) VALUES (...)
    ON CONFLICT (client_uuid) DO UPDATE SET ... , synced_at = now()
    """
    cols = list(payload.keys())
    if 'client_uuid' not in cols:
        cols.append('client_uuid')
        payload['client_uuid'] = row_client_uuid

    col_names = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))

    update_cols = [c for c in cols if c != 'client_uuid']
    if update_cols:
        update_assignments = ", ".join([f"{c} = EXCLUDED.{c}" for c in update_cols])
        update_clause = f"DO UPDATE SET {update_assignments}, synced_at = now()"
    else:
        update_clause = "DO NOTHING"

    sql = f"""
        INSERT INTO {table_name} ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (client_uuid) {update_clause};
    """
    values = [payload[c] for c in cols]
    return sql, values


def build_delete_sql(table_name: str, row_client_uuid: str, tenant_id: str = None):
    """Builds the PostgreSQL delete query scoped to tenant."""
    if tenant_id is None:
        tenant_id = get_tenant_id()
    sql = f"DELETE FROM {table_name} WHERE client_uuid = %s AND tenant_id = %s;"
    values = [row_client_uuid, tenant_id]
    return sql, values


def sync_single_queue_row(sqlite_conn, pg_cursor, queue_row: dict) -> tuple:
    """
    Syncs a single row from sync_queue to Supabase PostgreSQL.
    Returns (True, None) on success or (False, error_message) on failure.
    """
    row_id = queue_row['id']
    table_name = queue_row['table_name']
    operation = queue_row['operation']
    row_client_uuid = queue_row['row_client_uuid']

    if table_name not in TABLE_COLUMNS:
        return False, f"Unknown or unsynced table '{table_name}'"

    try:
        if operation in ('insert', 'update'):
            raw_payload = json.loads(queue_row['payload']) if queue_row['payload'] else {}
            sanitized = sanitize_payload_for_sync(table_name, raw_payload, sqlite_conn)
            sql, values = build_upsert_sql(table_name, sanitized, row_client_uuid)
            pg_cursor.execute(sql, values)
        elif operation == 'delete':
            raw_payload = json.loads(queue_row['payload']) if queue_row.get('payload') else {}
            tenant_id = raw_payload.get('tenant_id') or get_tenant_id()
            sql, values = build_delete_sql(table_name, row_client_uuid, tenant_id=tenant_id)
            pg_cursor.execute(sql, values)
        else:
            return False, f"Unsupported operation '{operation}'"

        return True, None
    except Exception as exc:
        return False, str(exc)


def sync_tenant_metadata(pg_cursor, sqlite_conn):
    """
    Registers/updates this installation's metadata in the Supabase `tenants` table.
    Ensures the central dashboard always has an active, up-to-date registry
    of all shops and their last sync timestamps.
    """
    try:
        tenant_id = get_tenant_id()
        shop_name = "Meat Products of India"
        shop_tagline = ""
        currency_symbol = "₹"
        try:
            rows = sqlite_conn.execute(
                "SELECT key, value FROM settings WHERE key IN ('shop_name', 'tagline', 'currency_symbol')"
            ).fetchall()
            for r in rows:
                k = r['key'] if isinstance(r, dict) or hasattr(r, '__getitem__') else r[0]
                v = r['value'] if isinstance(r, dict) or hasattr(r, '__getitem__') else r[1]
                if k == 'shop_name' and v:
                    shop_name = str(v)
                elif k == 'tagline' and v:
                    shop_tagline = str(v)
                elif k == 'currency_symbol' and v:
                    currency_symbol = str(v)
        except Exception:
            pass

        sql = """
            INSERT INTO tenants (tenant_id, shop_name, shop_tagline, currency_symbol, last_synced_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (tenant_id) DO UPDATE SET
                shop_name = EXCLUDED.shop_name,
                shop_tagline = EXCLUDED.shop_tagline,
                currency_symbol = EXCLUDED.currency_symbol,
                last_synced_at = now();
        """
        pg_cursor.execute(sql, (tenant_id, shop_name, shop_tagline, currency_symbol))
    except Exception as exc:
        logger.warning("Could not sync tenant metadata to Supabase: %s", _sanitize_error_message(str(exc)))


def process_sync_queue() -> tuple:
    """
    Processes pending and failed (attempts < 10) rows from sync_queue:
    1. Checks internet connectivity. If offline, exits silently.
    2. Acquires non-blocking lock to prevent overlapping sync passes.
    3. Fetches queue rows ordered by created_at ASC and parent-table priority.
    4. Syncs each row. On success: status='synced', synced_at=now. On failure:
       status='failed', attempts=attempts+1, last_error=error (subsequent rows continue).
    Returns (synced_count, failed_count).
    """
    global _is_syncing

    # Non-blocking lock to guarantee only one sync pass runs at a time
    if not _sync_lock.acquire(blocking=False):
        return 0, 0

    _is_syncing = True
    synced_count = 0
    failed_count = 0

    try:
        # Step 1: Check internet connectivity
        if not check_internet_connection():
            return 0, 0

        # Step 2: Acquire Supabase connection
        with get_supabase_connection() as (pg_conn, pg_err):
            if pg_conn is None:
                return 0, 0

            sqlite_conn = get_db()
            try:
                # Step 3: Fetch pending/failed queue rows
                rows = sqlite_conn.execute("""
                    SELECT id, table_name, operation, row_client_uuid, payload, attempts, created_at
                    FROM sync_queue
                    WHERE (status = 'pending' OR (status = 'failed' AND attempts < 10))
                    ORDER BY created_at ASC, id ASC
                """).fetchall()

                if not rows:
                    return 0, 0

                # Sort by (created_at, table_dependency_priority, id) to preserve parent-before-child ordering
                queue_items = [dict(r) for r in rows]
                queue_items.sort(key=lambda r: (
                    r.get('created_at') or '',
                    TABLE_SYNC_PRIORITY.get(r.get('table_name'), 999),
                    r.get('id') or 0
                ))

                pg_cur = pg_conn.cursor()
                sync_tenant_metadata(pg_cur, sqlite_conn)
                try:
                    pg_conn.commit()
                except Exception:
                    pass

                for item in queue_items:
                    success, error_msg = sync_single_queue_row(sqlite_conn, pg_cur, item)

                    if success:
                        try:
                            pg_conn.commit()
                            sqlite_conn.execute("""
                                UPDATE sync_queue
                                SET status = 'synced',
                                    synced_at = CURRENT_TIMESTAMP,
                                    last_error = NULL
                                WHERE id = ?
                            """, (item['id'],))
                            sqlite_conn.commit()
                            synced_count += 1
                        except Exception as commit_exc:
                            pg_conn.rollback()
                            clean_err = _sanitize_error_message(f"Commit error: {commit_exc}")
                            logger.error(
                                "Supabase sync commit failure for table='%s' client_uuid='%s' (attempt %d): %s",
                                item['table_name'],
                                item['row_client_uuid'],
                                (item.get('attempts', 0) + 1),
                                clean_err
                            )
                            sqlite_conn.execute("""
                                UPDATE sync_queue
                                SET attempts = attempts + 1,
                                    status = 'failed',
                                    last_error = ?
                                WHERE id = ?
                            """, (clean_err[:500], item['id']))
                            sqlite_conn.commit()
                            failed_count += 1
                    else:
                        pg_conn.rollback()
                        clean_err = _sanitize_error_message(str(error_msg))
                        logger.error(
                            "Supabase sync failure for table='%s' client_uuid='%s' (attempt %d): %s",
                            item['table_name'],
                            item['row_client_uuid'],
                            (item.get('attempts', 0) + 1),
                            clean_err
                        )
                        sqlite_conn.execute("""
                            UPDATE sync_queue
                            SET attempts = attempts + 1,
                                status = 'failed',
                                last_error = ?
                            WHERE id = ?
                        """, (clean_err[:500], item['id']))
                        sqlite_conn.commit()
                        failed_count += 1

                pg_cur.close()

                # Periodic pruning of rows older than 30 days with status='synced'
                global _last_prune_time
                now = time.time()
                if (now - _last_prune_time) >= 3600:
                    prune_synced_queue(retention_days=30)
                    _last_prune_time = now

            finally:
                sqlite_conn.close()

    except Exception as exc:
        logger.warning("Sync worker process notice: %s", _sanitize_error_message(str(exc)))
    finally:
        _is_syncing = False
        _sync_lock.release()

    return synced_count, failed_count


_last_prune_time = 0


def prune_synced_queue(retention_days: int = 30) -> int:
    """
    Deletes sync_queue rows with status='synced' older than retention_days (default 30 days),
    preventing the local queue table from growing unbounded.
    Returns the number of pruned rows.
    """
    conn = get_db()
    try:
        cur = conn.execute("""
            DELETE FROM sync_queue
            WHERE status = 'synced'
              AND synced_at IS NOT NULL
              AND datetime(synced_at) < datetime('now', '-' || ? || ' days')
        """, (str(retention_days),))
        pruned = cur.rowcount
        conn.commit()
        if pruned > 0:
            logger.info("Pruned %d synced records older than %d days from sync_queue", pruned, retention_days)
        return pruned
    except Exception as exc:
        logger.warning("Failed to prune old synced queue records: %s", exc)
        return 0
    finally:
        conn.close()


def retry_failed_sync_queue() -> int:
    """
    Resets all rows with status='failed' back to 'pending' with attempts=0 and clears last_error,
    enabling manual retry after persistent failures are investigated.
    Immediately triggers a sync pass in the background.
    Returns the number of rows reset.
    """
    conn = get_db()
    try:
        cur = conn.execute("""
            UPDATE sync_queue
            SET status = 'pending',
                attempts = 0,
                last_error = NULL
            WHERE status = 'failed'
        """)
        reset_count = cur.rowcount
        conn.commit()
        if reset_count > 0:
            logger.info("Reset %d failed sync_queue records to 'pending' for retry", reset_count)
    finally:
        conn.close()

    if reset_count > 0:
        trigger_sync_async()

    return reset_count


def trigger_sync_async():
    """
    Spawns a background daemon thread to run a sync pass immediately.
    Non-blocking. Skips if already syncing or offline.
    """
    if os.environ.get('PYTEST_CURRENT_TEST') and not os.environ.get('TEST_RUN_SYNC_WORKER'):
        return None
    t = threading.Thread(target=process_sync_queue, daemon=True, name="SyncWorkerAsync")
    t.start()
    return t


def _sync_loop():
    """Background loop that invokes process_sync_queue and periodically prunes old synced rows."""
    global _last_prune_time
    while True:
        try:
            process_sync_queue()

            # Prune synced records older than 30 days once every hour
            now = time.time()
            if (now - _last_prune_time) >= 3600:
                prune_synced_queue(retention_days=30)
                _last_prune_time = now
        except Exception as exc:
            logger.warning("Sync worker loop notice: %s", exc)
        time.sleep(SYNC_INTERVAL_SECONDS)


def start_sync_scheduler():
    """
    Starts the background sync scheduler daemon thread and runs one initial pass immediately.
    Non-blocking so the app UI opens instantly.
    """
    # Trigger immediate sync pass (non-blocking)
    trigger_sync_async()

    # Launch periodic daemon loop
    t = threading.Thread(target=_sync_loop, daemon=True, name="SyncWorkerScheduler")
    t.start()
    return t


def get_sync_status() -> dict:
    """
    Returns sync telemetry for UI / API:
    - last_synced_at: timestamp of the most recent successfully synced queue record
    - pending_count: count of rows waiting for first sync attempt
    - failed_count: count of rows that failed recent sync attempts
    - total_synced: lifetime count of synced rows in local queue
    - is_syncing: whether a sync pass is currently executing
    - is_online: whether the client has internet connectivity
    """
    conn = get_db()
    try:
        last_row = conn.execute(
            "SELECT MAX(synced_at) AS last_synced FROM sync_queue WHERE status = 'synced'"
        ).fetchone()
        last_synced_at = last_row['last_synced'] if last_row and last_row['last_synced'] else None

        pending_count = conn.execute(
            "SELECT COUNT(*) AS c FROM sync_queue WHERE status = 'pending'"
        ).fetchone()['c']

        failed_count = conn.execute(
            "SELECT COUNT(*) AS c FROM sync_queue WHERE status = 'failed' AND attempts < 10"
        ).fetchone()['c']

        total_synced = conn.execute(
            "SELECT COUNT(*) AS c FROM sync_queue WHERE status = 'synced'"
        ).fetchone()['c']

    except Exception:
        last_synced_at = None
        pending_count = 0
        failed_count = 0
        total_synced = 0
    finally:
        conn.close()

    return {
        'last_synced_at': last_synced_at,
        'pending_count': pending_count,
        'failed_count': failed_count,
        'total_synced': total_synced,
        'is_syncing': _is_syncing,
        'is_online': check_internet_connection()
    }
