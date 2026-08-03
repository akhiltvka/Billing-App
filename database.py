"""
database.py — SQLite Schema, Initialization, and Helper Functions
Meat Products of India — Billing & Inventory Management App
"""
from werkzeug.security import generate_password_hash

import sqlite3
import os
from datetime import datetime

import sys
if getattr(sys, 'frozen', False):
    _base_dir = os.path.dirname(sys.executable)
else:
    _base_dir = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.environ.get('DB_PATH') or os.path.join(_base_dir, 'data', 'meatshop.db')


def get_db():
    """Return a connected SQLite database with Row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """Initialize the database schema and seed default data."""
    conn = get_db()
    c = conn.cursor()

    c.executescript('''
        -- Shop-level key-value settings
        CREATE TABLE IF NOT EXISTS shop_settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        -- Product categories (Chicken, Mutton, Fish, Groceries, etc.)
        CREATE TABLE IF NOT EXISTS categories (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            name               TEXT NOT NULL UNIQUE,
            gst_rate           REAL DEFAULT 0,
            hsn_code           TEXT,
            description        TEXT,
            parent_category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            created_at         TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Product catalog
        CREATE TABLE IF NOT EXISTS products (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id        INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            name               TEXT NOT NULL,
            code               TEXT UNIQUE NOT NULL,
            hsn_code           TEXT,
            unit               TEXT DEFAULT 'kg',
            purchase_unit      TEXT DEFAULT 'kg',
            sale_unit          TEXT DEFAULT 'kg',
            conversion_factor  REAL DEFAULT 1.0,
            purchase_price     REAL DEFAULT 0,
            selling_price      REAL DEFAULT 0,
            gst_rate           REAL DEFAULT 0,
            min_stock          REAL DEFAULT 1,
            current_stock      REAL DEFAULT 0,
            barcode            TEXT,
            product_type       TEXT DEFAULT 'perishable' CHECK(product_type IN ('perishable', 'general')),
            mrp                REAL DEFAULT NULL,
            is_price_inclusive_of_tax INTEGER DEFAULT 1,
            brand              TEXT DEFAULT NULL,
            pack_size          TEXT DEFAULT NULL,
            reorder_lead_time_days INTEGER DEFAULT 1,
            active             INTEGER DEFAULT 1,
            created_at         TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at         TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Customer master
        CREATE TABLE IF NOT EXISTS customers (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            phone          TEXT,
            email          TEXT,
            address        TEXT,
            gstin          TEXT,
            state_code     TEXT,
            credit_balance REAL DEFAULT 0,
            is_active      INTEGER DEFAULT 1,
            created_at     TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Supplier master
        CREATE TABLE IF NOT EXISTS suppliers (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            name           TEXT NOT NULL,
            contact_person TEXT,
            phone          TEXT,
            email          TEXT,
            address        TEXT,
            gstin          TEXT,
            balance        REAL DEFAULT 0,
            created_at     TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- All stock movements (in / out / wastage / conversion_out / conversion_in)
        CREATE TABLE IF NOT EXISTS stock_transactions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
            type         TEXT NOT NULL CHECK(type IN ('in','out','wastage','adjustment','conversion_out','conversion_in')),
            quantity     REAL NOT NULL,
            unit_price   REAL DEFAULT 0,
            reference_id TEXT,
            supplier_id  INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
            expiry_date  TEXT,
            notes        TEXT,
            date         TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Sales bills / invoices
        CREATE TABLE IF NOT EXISTS bills (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_no          TEXT UNIQUE NOT NULL,
            customer_id      INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            customer_name    TEXT,
            customer_phone   TEXT,
            customer_gstin   TEXT,
            place_of_supply  TEXT,
            is_interstate    INTEGER DEFAULT 0,
            date             TEXT DEFAULT CURRENT_TIMESTAMP,
            subtotal         REAL DEFAULT 0,
            discount_percent REAL DEFAULT 0,
            discount_amount  REAL DEFAULT 0,
            cgst             REAL DEFAULT 0,
            sgst             REAL DEFAULT 0,
            igst             REAL DEFAULT 0,
            grand_total      REAL DEFAULT 0,
            amount_paid      REAL DEFAULT 0,
            amount_due       REAL DEFAULT 0,
            change_amount    REAL DEFAULT 0,
            payment_mode     TEXT DEFAULT 'cash',
            notes            TEXT,
            cancel_reason    TEXT,
            status           TEXT DEFAULT 'paid'
        );

        -- Line items in each bill
        CREATE TABLE IF NOT EXISTS bill_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id      INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name TEXT NOT NULL,
            hsn_code     TEXT,
            unit         TEXT,
            quantity     REAL NOT NULL,
            unit_price   REAL NOT NULL,
            gst_rate     REAL DEFAULT 0,
            discount     REAL DEFAULT 0,
            taxable_amt  REAL DEFAULT 0,
            cgst_amt     REAL DEFAULT 0,
            sgst_amt     REAL DEFAULT 0,
            igst_amt     REAL DEFAULT 0,
            amount       REAL NOT NULL,
            cost_price   REAL DEFAULT NULL
        );

        -- Payment history for credit / partial bills
        CREATE TABLE IF NOT EXISTS bill_payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id      INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            amount       REAL NOT NULL,
            payment_mode TEXT DEFAULT 'cash',
            paid_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            received_by  TEXT,
            notes        TEXT
        );

        -- Purchase / stock-in orders from suppliers
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            po_no        TEXT UNIQUE NOT NULL,
            supplier_id  INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
            supplier_name TEXT,
            date         TEXT DEFAULT CURRENT_TIMESTAMP,
            subtotal     REAL DEFAULT 0,
            gst_amount   REAL DEFAULT 0,
            total        REAL DEFAULT 0,
            amount_paid  REAL DEFAULT 0,
            amount_due   REAL DEFAULT 0,
            status       TEXT DEFAULT 'received',
            notes        TEXT
        );

        -- Line items in each purchase order
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
            product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name TEXT NOT NULL,
            quantity     REAL NOT NULL,
            unit_price   REAL NOT NULL,
            amount       REAL NOT NULL,
            expiry_date  TEXT
        );

        -- Payment history for purchase orders
        CREATE TABLE IF NOT EXISTS po_payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
            amount       REAL NOT NULL,
            payment_mode TEXT DEFAULT 'bank_transfer',
            paid_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            recorded_by  TEXT,
            notes        TEXT
        );

        -- Miscellaneous expenses & other income
        CREATE TABLE IF NOT EXISTS expenses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            category     TEXT NOT NULL,
            description  TEXT,
            amount       REAL NOT NULL,
            date         TEXT DEFAULT CURRENT_DATE,
            entry_type   TEXT DEFAULT 'expense',
            payment_mode TEXT DEFAULT 'cash',
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- User accounts for role-based access
        CREATE TABLE IF NOT EXISTS users (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            username              TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash         TEXT NOT NULL,
            full_name             TEXT NOT NULL,
            role                  TEXT NOT NULL CHECK(role IN ('admin','md','manager','accountant','counter_staff','tester')),
            role_id               INTEGER REFERENCES roles(id) ON DELETE SET NULL,
            outlet_code           TEXT,
            machine_id            TEXT,
            active                INTEGER DEFAULT 1,
            must_change_password  INTEGER DEFAULT 0,
            last_login            TEXT,
            created_at            TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Roles master table
        CREATE TABLE IF NOT EXISTS roles (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        -- Granular permissions table
        CREATE TABLE IF NOT EXISTS permissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL UNIQUE,
            description TEXT
        );

        -- Role-Permission mappings
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id       INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY(role_id, permission_id)
        );

        -- RBAC & Sensitive Action Audit Log
        CREATE TABLE IF NOT EXISTS audit_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
            username        TEXT,
            permission_code TEXT NOT NULL,
            route           TEXT NOT NULL,
            method          TEXT NOT NULL,
            allowed         INTEGER NOT NULL,
            timestamp       TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Audit & Notification logs (e.g., password changes by managers)
        CREATE TABLE IF NOT EXISTS notifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            target_role TEXT NOT NULL DEFAULT 'admin',
            title       TEXT NOT NULL,
            message     TEXT NOT NULL,
            read        INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Full activity audit trail — every important user action is logged
        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL,
            full_name   TEXT NOT NULL,
            role        TEXT NOT NULL,
            action      TEXT NOT NULL,
            description TEXT,
            table_name  TEXT,
            record_id   INTEGER,
            ip_address  TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Login rate limiting & lockout tracking
        CREATE TABLE IF NOT EXISTS login_attempts (
            username       TEXT PRIMARY KEY,
            failed_count   INTEGER DEFAULT 0,
            last_failed_at TEXT,
            locked_until   TEXT
        );

        -- Held bills queue (POS hold & recall feature)
        CREATE TABLE IF NOT EXISTS held_bills (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_code   TEXT,
            terminal_id      TEXT DEFAULT 'POS-1',
            cashier_user_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
            customer_id      INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            customer_name    TEXT,
            items_json       TEXT NOT NULL,
            discount_percent REAL DEFAULT 0,
            payment_mode     TEXT DEFAULT 'cash',
            total_amount     REAL DEFAULT 0,
            notes            TEXT,
            status           TEXT DEFAULT 'held' CHECK(status IN ('held', 'recalled')),
            created_at       TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Batch tracking for perishable stock (FEFO)
        CREATE TABLE IF NOT EXISTS stock_batches (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id           INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            batch_no             TEXT,
            quantity_remaining   REAL NOT NULL DEFAULT 0,
            unit_price           REAL DEFAULT 0,
            unit_cost            REAL DEFAULT NULL,
            expiry_date          TEXT,
            supplier_id          INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
            received_at          TEXT DEFAULT CURRENT_TIMESTAMP,
            stock_transaction_id INTEGER REFERENCES stock_transactions(id) ON DELETE SET NULL
        );

        -- Credit notes for partial returns / price adjustments
        CREATE TABLE IF NOT EXISTS credit_notes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            cn_no         TEXT UNIQUE NOT NULL,
            bill_id       INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
            customer_id   INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            customer_name TEXT,
            reason        TEXT,
            subtotal      REAL DEFAULT 0,
            cgst          REAL DEFAULT 0,
            sgst          REAL DEFAULT 0,
            igst          REAL DEFAULT 0,
            total         REAL DEFAULT 0,
            status        TEXT DEFAULT 'issued',
            created_by    TEXT,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Line items in each credit note
        CREATE TABLE IF NOT EXISTS credit_note_items (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            credit_note_id INTEGER NOT NULL REFERENCES credit_notes(id) ON DELETE CASCADE,
            bill_item_id   INTEGER REFERENCES bill_items(id) ON DELETE SET NULL,
            product_id     INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name   TEXT NOT NULL,
            hsn_code       TEXT,
            unit           TEXT,
            quantity       REAL NOT NULL,
            unit_price     REAL NOT NULL,
            gst_rate       REAL DEFAULT 0,
            taxable_amt    REAL DEFAULT 0,
            cgst_amt       REAL DEFAULT 0,
            sgst_amt       REAL DEFAULT 0,
            igst_amt       REAL DEFAULT 0,
            amount         REAL NOT NULL
        );

        -- Double-entry ledger accounts
        CREATE TABLE IF NOT EXISTS ledger_accounts (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            name                 TEXT UNIQUE NOT NULL,
            account_group        TEXT NOT NULL CHECK(account_group IN ('Asset', 'Liability', 'Income', 'Expense', 'Equity')),
            account_type         TEXT NOT NULL,
            opening_balance      REAL DEFAULT 0,
            opening_balance_type TEXT DEFAULT 'dr' CHECK(opening_balance_type IN ('dr', 'cr')),
            is_system            INTEGER DEFAULT 0,
            created_at           TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Double-entry ledger journal entries
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_type    TEXT NOT NULL CHECK(voucher_type IN ('sales', 'credit_note', 'purchase', 'payment_in', 'payment_out', 'expense', 'journal')),
            voucher_no      TEXT,
            voucher_date    TEXT,
            account_id      INTEGER NOT NULL REFERENCES ledger_accounts(id) ON DELETE RESTRICT,
            debit           REAL DEFAULT 0,
            credit          REAL DEFAULT 0,
            narration       TEXT,
            reference_table TEXT,
            reference_id    INTEGER,
            created_by      TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Stock conversion / processing journals (bulk items cut/processed into sellable products)
        CREATE TABLE IF NOT EXISTS stock_conversions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            conversion_no    TEXT UNIQUE NOT NULL,
            conversion_date  TEXT DEFAULT CURRENT_TIMESTAMP,
            input_product_id INTEGER NOT NULL REFERENCES products(id),
            input_quantity   REAL NOT NULL,
            yield_percent    REAL DEFAULT 0,
            loss_quantity    REAL DEFAULT 0,
            notes            TEXT,
            created_by       TEXT,
            created_at       TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS stock_conversion_outputs (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            conversion_id     INTEGER NOT NULL REFERENCES stock_conversions(id) ON DELETE CASCADE,
            output_product_id INTEGER NOT NULL REFERENCES products(id),
            output_quantity   REAL NOT NULL,
            allocated_unit_cost REAL DEFAULT NULL,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP
        );

        -- Standard reusable templates for stock conversions / butchery cuts
        CREATE TABLE IF NOT EXISTS conversion_templates (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT NOT NULL,
            input_product_id INTEGER NOT NULL REFERENCES products(id),
            is_active        INTEGER DEFAULT 1,
            created_at       TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversion_template_items (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id            INTEGER NOT NULL REFERENCES conversion_templates(id) ON DELETE CASCADE,
            output_product_id      INTEGER NOT NULL REFERENCES products(id),
            expected_yield_percent REAL DEFAULT 0,
            created_at             TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    # ── Migrations ───────────────────────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_batches (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id           INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            batch_no             TEXT,
            quantity_remaining   REAL NOT NULL DEFAULT 0,
            unit_price           REAL DEFAULT 0,
            expiry_date          TEXT,
            supplier_id          INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
            received_at          TEXT DEFAULT CURRENT_TIMESTAMP,
            stock_transaction_id INTEGER REFERENCES stock_transactions(id) ON DELETE SET NULL
        )
    ''')
    p_cols = [r[1] for r in c.execute("PRAGMA table_info(products)").fetchall()]
    if 'code' not in p_cols:
        try:
            c.execute('ALTER TABLE products ADD COLUMN code TEXT')
            conn.commit()
        except Exception:
            pass

    try:
        c.execute('ALTER TABLE stock_transactions ADD COLUMN status TEXT DEFAULT "approved"')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE stock_transactions ADD COLUMN created_by TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE stock_transactions ADD COLUMN approved_by TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE bills ADD COLUMN cancel_reason TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE bills ADD COLUMN is_test INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE customers ADD COLUMN state_code TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE customers ADD COLUMN is_active INTEGER DEFAULT 1')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_phone_unique ON customers(phone) WHERE phone IS NOT NULL AND phone != ""')
    except Exception:
        pass

    try:
        c.execute('ALTER TABLE bills ADD COLUMN place_of_supply TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE bills ADD COLUMN is_interstate INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE bills ADD COLUMN igst REAL DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE bill_items ADD COLUMN igst_amt REAL DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE products ADD COLUMN purchase_unit TEXT DEFAULT 'kg'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE products ADD COLUMN sale_unit TEXT DEFAULT 'kg'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE users ADD COLUMN outlet_code TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE users ADD COLUMN machine_id TEXT')
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE expenses ADD COLUMN entry_type TEXT DEFAULT 'expense'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE expenses ADD COLUMN payment_mode TEXT DEFAULT 'cash'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute('ALTER TABLE purchase_orders ADD COLUMN amount_due REAL DEFAULT 0')
    except sqlite3.OperationalError:
        pass

    # RBAC Users column migration & Seeding
    u_cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
    if 'role_id' not in u_cols:
        try:
            c.execute("ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES roles(id) ON DELETE SET NULL")
        except Exception:
            pass

    default_roles = [
        (1, 'Admin'),
        (2, 'Manager'),
        (3, 'Accountant'),
        (4, 'Billing Staff'),
        (5, 'Auditor')
    ]
    for r_id, r_name in default_roles:
        c.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (?, ?)", (r_id, r_name))

    all_permissions = [
        ('*', 'Superuser all permissions'),
        ('users.view', 'View user accounts'),
        ('users.manage', 'Create, update, delete user accounts'),
        ('settings.view', 'View shop settings'),
        ('settings.manage', 'Update shop settings'),
        ('settings.gst_toggle', 'Toggle GST system ON/OFF'),
        ('activity.view', 'View activity log'),
        ('notifications.view', 'View notifications'),
        ('inventory.view', 'View products, categories, stock'),
        ('inventory.create', 'Create products & categories'),
        ('inventory.edit', 'Update products & categories'),
        ('inventory.edit_price', 'Edit product selling or purchase price'),
        ('inventory.delete', 'Delete products & categories'),
        ('stock.in', 'Record incoming stock'),
        ('stock.verify', 'Verify & approve stock entries'),
        ('stock.wastage', 'Record stock wastage'),
        ('stock.adjustment', 'Manual stock adjustment'),
        ('stock.conversions', 'Manage stock conversions & butchery templates'),
        ('customers.view', 'View customer master'),
        ('customers.manage', 'Create, update, delete customers'),
        ('suppliers.view', 'View supplier master'),
        ('suppliers.manage', 'Create, update, delete suppliers'),
        ('billing.create', 'Create sales invoices'),
        ('billing.view', 'View sales invoices & history'),
        ('billing.hold', 'Hold and recall sales bills'),
        ('billing.delete_held', 'Delete held bills'),
        ('billing.give_discount', 'Apply discounts on sales bills'),
        ('billing.void_bill', 'Void / cancel sales invoices'),
        ('billing.payment', 'Record invoice payment'),
        ('billing.credit_note', 'Issue credit notes'),
        ('purchase.view', 'View purchase orders'),
        ('purchase.manage', 'Create purchase orders & payments'),
        ('expenses.view', 'View income & expenses'),
        ('expenses.manage', 'Create and delete expenses'),
        ('accounts.view_ledger', 'View ledger accounts, trial balance, P&L, balance sheet'),
        ('accounts.manage', 'Create and update ledger accounts'),
        ('reports.view', 'View dashboard & reports'),
        ('settings.view', 'View system settings'),
        ('settings.gst_toggle', 'Enable or disable GST calculations'),
        ('settings.manage', 'Update shop info, GST, invoice & backup settings'),
        ('users.view', 'View user accounts & activity logs'),
        ('users.manage', 'Create, update, reset password & manage user roles'),
        ('backup.manage', 'Manage database backup & cloud sync'),
        ('license.view', 'View license status'),
        ('license.manage', 'Manage system license & cloud activation'),
    ]

    for p_code, p_desc in all_permissions:
        c.execute("INSERT OR IGNORE INTO permissions (code, description) VALUES (?, ?)", (p_code, p_desc))

    perm_rows = c.execute("SELECT id, code FROM permissions").fetchall()
    perm_map = {p['code']: p['id'] for p in perm_rows}

    billing_staff_perms = [
        'billing.create', 'billing.view', 'billing.hold', 'billing.payment',
        'customers.view', 'customers.manage', 'inventory.view', 'reports.view'
    ]

    accountant_perms = list(set(billing_staff_perms + [
        'accounts.view_ledger', 'accounts.manage', 'expenses.view', 'expenses.manage',
        'reports.view', 'customers.view', 'suppliers.view', 'billing.view', 'purchase.view',
        'inventory.view', 'stock.in', 'stock.verify', 'billing.credit_note',
        'settings.view', 'settings.gst_toggle'
    ]))

    auditor_perms = [
        'inventory.view', 'billing.view', 'customers.view', 'suppliers.view',
        'purchase.view', 'expenses.view', 'reports.view', 'accounts.view_ledger',
        'settings.view', 'license.view', 'users.view', 'activity.view'
    ]

    manager_perms = list(set(accountant_perms + billing_staff_perms + auditor_perms + [
        'inventory.create', 'inventory.edit', 'inventory.edit_price', 'inventory.delete',
        'stock.wastage', 'stock.adjustment', 'stock.conversions', 'suppliers.manage',
        'purchase.manage', 'billing.delete_held', 'billing.give_discount', 'billing.void_bill',
        'settings.view', 'settings.gst_toggle', 'settings.manage', 'users.view', 'notifications.view'
    ]))

    role_mapping_defs = [
        (1, ['*']),
        (2, manager_perms),
        (3, accountant_perms),
        (4, billing_staff_perms),
        (5, auditor_perms)
    ]

    for role_id, p_codes in role_mapping_defs:
        for code in p_codes:
            p_id = perm_map.get(code)
            if p_id:
                c.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, p_id))

    legacy_map = {
        'admin': 1,
        'md': 1,
        'manager': 2,
        'accountant': 3,
        'counter_staff': 4,
        'tester': 4
    }
    for leg_role, r_id in legacy_map.items():
        c.execute("UPDATE users SET role_id = ? WHERE role = ? AND (role_id IS NULL OR role_id = 0)", (r_id, leg_role))

    c.execute("UPDATE users SET role_id = 4 WHERE role_id IS NULL OR role_id = 0")

    # Ensure role_id 4 (counter_staff / billing staff) always has customer creation & management permissions
    c.execute('''
        INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
        SELECT 4, id FROM permissions WHERE code IN ('customers.view', 'customers.manage', 'customers.create', 'billing.create', 'billing.view', 'billing.hold', 'billing.payment')
    ''')
    conn.commit()

    # Products & Categories multi-type and hierarchy migrations
    p_cols = [r[1] for r in c.execute("PRAGMA table_info(products)").fetchall()]
    if 'product_type' not in p_cols:
        try: c.execute("ALTER TABLE products ADD COLUMN product_type TEXT DEFAULT 'perishable'")
        except Exception: pass
    if 'mrp' not in p_cols:
        try: c.execute("ALTER TABLE products ADD COLUMN mrp REAL DEFAULT NULL")
        except Exception: pass
    if 'is_price_inclusive_of_tax' not in p_cols:
        try: c.execute("ALTER TABLE products ADD COLUMN is_price_inclusive_of_tax INTEGER DEFAULT 1")
        except Exception: pass
    if 'brand' not in p_cols:
        try: c.execute("ALTER TABLE products ADD COLUMN brand TEXT DEFAULT NULL")
        except Exception: pass
    if 'pack_size' not in p_cols:
        try: c.execute("ALTER TABLE products ADD COLUMN pack_size TEXT DEFAULT NULL")
        except Exception: pass
    if 'reorder_lead_time_days' not in p_cols:
        try: c.execute("ALTER TABLE products ADD COLUMN reorder_lead_time_days INTEGER DEFAULT 1")
        except Exception: pass

    # Backfill all existing products to product_type = 'perishable'
    c.execute("UPDATE products SET product_type = 'perishable' WHERE product_type IS NULL OR product_type = ''")
    c.execute("UPDATE products SET reorder_lead_time_days = 7 WHERE product_type = 'general' AND (reorder_lead_time_days IS NULL OR reorder_lead_time_days = 1)")

    # Users table: add outlet_code and machine_id for hardware-bound login
    u_cols = [r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()]
    if 'outlet_code' not in u_cols:
        try: c.execute("ALTER TABLE users ADD COLUMN outlet_code TEXT DEFAULT NULL")
        except Exception: pass
    if 'machine_id' not in u_cols:
        try: c.execute("ALTER TABLE users ADD COLUMN machine_id TEXT DEFAULT NULL")
        except Exception: pass
    if 'employee_id' not in u_cols:
        try: c.execute("ALTER TABLE users ADD COLUMN employee_id TEXT DEFAULT NULL")
        except Exception: pass

    # Clean up old pre-seeded default staff accounts to avoid confusion
    try:
        c.execute("DELETE FROM users WHERE username COLLATE NOCASE IN ('admin', 'md', 'manager', 'accountant', 'counter')")
        conn.commit()
    except Exception:
        pass

    cat_cols = [r[1] for r in c.execute("PRAGMA table_info(categories)").fetchall()]
    if 'parent_category_id' not in cat_cols:
        try: c.execute("ALTER TABLE categories ADD COLUMN parent_category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL")
        except Exception: pass

    sco_cols = [r[1] for r in c.execute("PRAGMA table_info(stock_conversion_outputs)").fetchall()]
    if 'allocated_unit_cost' not in sco_cols:
        try: c.execute("ALTER TABLE stock_conversion_outputs ADD COLUMN allocated_unit_cost REAL DEFAULT NULL")
        except Exception: pass

    sb_cols = [r[1] for r in c.execute("PRAGMA table_info(stock_batches)").fetchall()]
    if 'unit_cost' not in sb_cols:
        try: c.execute("ALTER TABLE stock_batches ADD COLUMN unit_cost REAL DEFAULT NULL")
        except Exception: pass

    bi_cols = [r[1] for r in c.execute("PRAGMA table_info(bill_items)").fetchall()]
    if 'cost_price' not in bi_cols:
        try: c.execute("ALTER TABLE bill_items ADD COLUMN cost_price REAL DEFAULT NULL")
        except Exception: pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS po_payments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
            amount       REAL NOT NULL,
            payment_mode TEXT DEFAULT 'bank_transfer',
            paid_at      TEXT DEFAULT CURRENT_TIMESTAMP,
            recorded_by  TEXT,
            notes        TEXT
        )
    ''')

    c.execute('''
        UPDATE purchase_orders
        SET amount_due = MAX(total - amount_paid, 0)
        WHERE amount_due IS NULL OR amount_due = 0
    ''')

    c.execute('''
        UPDATE products
        SET purchase_unit = COALESCE(unit, 'kg'),
            sale_unit = COALESCE(unit, 'kg'),
            conversion_factor = 1.0
        WHERE purchase_unit IS NULL OR purchase_unit = ''
    ''')

    # Ensure existing products with current_stock > 0 have an initial batch record
    prods_without_batches = c.execute('''
        SELECT p.id, p.current_stock, p.purchase_price
        FROM products p
        LEFT JOIN stock_batches sb ON p.id = sb.product_id
        WHERE p.current_stock > 0
        GROUP BY p.id
        HAVING COUNT(sb.id) = 0
    ''').fetchall()
    for p in prods_without_batches:
        pid, stock, price = p[0], p[1], p[2]
        c.execute('''
            INSERT INTO stock_batches (product_id, batch_no, quantity_remaining, unit_price)
            VALUES (?, ?, ?, ?)
        ''', (pid, f"INIT-P{pid:04d}", stock, price))

    conn.commit()

    # Assign 4-letter unique codes for any existing products missing a code
    rows_no_code = c.execute('SELECT id, name FROM products WHERE code IS NULL OR code = ""').fetchall()
    for row in rows_no_code:
        pid, pname = row[0], row[1]
        # Generate 4-letter code e.g. CHIC, MUTC, P001...
        clean = "".join([ch for ch in pname.upper() if ch.isalnum()])
        base_code = clean[:4].ljust(4, 'X')
        candidate = base_code
        seq = 1
        while c.execute('SELECT id FROM products WHERE code=? AND id != ?', (candidate, pid)).fetchone():
            candidate = f"{base_code[:3]}{seq}"
            seq += 1
        c.execute('UPDATE products SET code=? WHERE id=?', (candidate, pid))

    # Ensure users table CHECK constraint includes 'tester'
    try:
        table_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        if table_sql and "CHECK" in table_sql[0] and "'tester'" not in table_sql[0]:
            c.execute("CREATE TABLE users_tmp AS SELECT * FROM users")
            c.execute("DROP TABLE users")
            c.execute('''
                CREATE TABLE users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    full_name     TEXT NOT NULL,
                    role          TEXT NOT NULL CHECK(role IN ('admin','manager','accountant','counter_staff','tester')),
                    active        INTEGER DEFAULT 1,
                    last_login    TEXT,
                    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute("INSERT INTO users SELECT * FROM users_tmp")
    except Exception:
        pass

    # Ensure stock_transactions CHECK constraint includes 'conversion_out' and 'conversion_in'
    try:
        st_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='stock_transactions'").fetchone()
        if st_sql and "CHECK" in st_sql[0] and "'conversion_out'" not in st_sql[0]:
            c.execute("CREATE TABLE stock_transactions_tmp AS SELECT * FROM stock_transactions")
            c.execute("DROP TABLE stock_transactions")
            c.execute('''
                CREATE TABLE stock_transactions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
                    type         TEXT NOT NULL CHECK(type IN ('in','out','wastage','adjustment','conversion_out','conversion_in')),
                    quantity     REAL NOT NULL,
                    unit_price   REAL DEFAULT 0,
                    reference_id TEXT,
                    supplier_id  INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
                    expiry_date  TEXT,
                    notes        TEXT,
                    status       TEXT DEFAULT 'approved',
                    created_by   TEXT,
                    approved_by  TEXT,
                    date         TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute("INSERT INTO stock_transactions SELECT * FROM stock_transactions_tmp")
            c.execute("DROP TABLE stock_transactions_tmp")
    except Exception:
        pass

    # ── Default shop settings ────────────────────────────────────────────────
    defaults = {
        'shop_name':        'Meat Products of India',
        'shop_tagline':     'Fresh. Pure. Delicious.',
        'shop_address':     '123, Main Market Road, City, State – 000 000',
        'shop_phone':       '+91 98765 43210',
        'shop_email':       'info@meatproductsofindia.in',
        'shop_gstin':       '',
        'shop_fssai':       '',
        'shop_state_code':  '32',
        'currency_symbol':  '₹',
        'bill_prefix':      'MPI',
        'next_bill_no':     '1',
        'next_po_no':       '1',
        'next_cn_no':       '1',
        'next_test_no':     '1',
        'next_conversion_no': '1',
        'gst_enabled':      'true',
        'print_after_bill': 'true',
        'low_stock_alert':  'true',
        'decimal_places':   '2',
        'shop_logo':        '',
    }
    for k, v in defaults.items():
        c.execute('INSERT OR IGNORE INTO shop_settings (key, value) VALUES (?, ?)', (k, v))

    # ── Default meat product categories ─────────────────────────────────────
    categories = [
        ('Chicken',            5,  '0207', 'Fresh and frozen chicken products'),
        ('Mutton / Goat',     12,  '0204', 'Fresh and frozen mutton / goat'),
        ('Beef',              12,  '0202', 'Fresh and frozen beef products'),
        ('Pork',              12,  '0203', 'Fresh and frozen pork products'),
        ('Fish & Seafood',     5,  '0302', 'Fresh fish, prawns, crabs, lobsters'),
        ('Eggs',               0,  '0407', 'Chicken, duck and other eggs'),
        ('Processed Meats',   12,  '1601', 'Sausages, salamis, ham, bacon'),
        ('Marinated / RTC',    5,  '1602', 'Marinated and ready-to-cook items'),
        ('Bone & Offal',       0,  '0206', 'Liver, kidney, heart, bones'),
    ]
    for row in categories:
        c.execute(
            'INSERT OR IGNORE INTO categories (name, gst_rate, hsn_code, description) VALUES (?,?,?,?)',
            row
        )

    # ── Default user accounts ────────────────────────────────────────────────
    import secrets
    import string

    # Ensure must_change_password column exists on legacy databases
    try:
        c.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER DEFAULT 0")
    except Exception:
        pass

    # 1. Seed 'sudo' (admin) with a randomly generated 16-character password if not present
    existing_sudo = c.execute('SELECT id FROM users WHERE username=?', ('sudo',)).fetchone()
    if not existing_sudo:
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        raw_sudo_pw = ''.join(secrets.choice(alphabet) for _ in range(16))
        c.execute(
            '''INSERT INTO users (username, password_hash, full_name, role, employee_id, must_change_password)
               VALUES (?, ?, ?, ?, ?, 1)''',
            ('sudo', generate_password_hash(raw_sudo_pw), 'Developer Superuser', 'admin', 'DEV-001')
        )
        print("\n" + "=" * 75)
        print(" [SECURITY] Initial admin ('sudo') password (save this now, it will not be shown again):")
        print(f" >>> {raw_sudo_pw} <<<")
        print("=" * 75 + "\n")

    # 2. Seed 'tester' account if enabled via SEED_TESTER_ACCOUNT env var (default: enabled = 1)
    seed_tester = os.environ.get('SEED_TESTER_ACCOUNT', '1').strip().lower() not in ('0', 'false', 'no', 'off')
    if seed_tester:
        existing_tester = c.execute('SELECT id FROM users WHERE username=?', ('tester',)).fetchone()
        if not existing_tester:
            c.execute(
                '''INSERT INTO users (username, password_hash, full_name, role, employee_id, must_change_password)
                   VALUES (?, ?, ?, ?, ?, 1)''',
                ('tester', generate_password_hash('Tester@1234'), 'Tester Staff (Demo)', 'tester', 'TEST-999')
            )

    # ── Sample supplier ──────────────────────────────────────────────────────
    c.execute('''
        INSERT OR IGNORE INTO suppliers (id, name, contact_person, phone, address)
        VALUES (1, 'Fresh Farms Pvt. Ltd.', 'Ramesh Kumar', '+91 91234 56789',
                '45, Cold Storage Road, City')
    ''')

    # ── Starter Chart of Accounts ─────────────────────────────────────────────
    starter_accounts = [
        ('Cash',               'Asset',     'Cash',             0, 'dr', 1),
        ('Bank',               'Asset',     'Bank',             0, 'dr', 1),
        ('Sales Account',      'Income',    'Sales',            0, 'cr', 1),
        ('Purchase Account',   'Expense',   'Purchases',        0, 'dr', 1),
        ('Sundry Debtors',     'Asset',     'Sundry Debtors',   0, 'dr', 1),
        ('Sundry Creditors',   'Liability', 'Sundry Creditors', 0, 'cr', 1),
        ('CGST Payable',       'Liability', 'Duties & Taxes',   0, 'cr', 1),
        ('SGST Payable',       'Liability', 'Duties & Taxes',   0, 'cr', 1),
        ('IGST Payable',       'Liability', 'Duties & Taxes',   0, 'cr', 1),
        ('Direct Expenses',    'Expense',   'Direct Expense',   0, 'dr', 1),
        ('Indirect Expenses',  'Expense',   'Indirect Expense', 0, 'dr', 1),
        ('Capital Account',    'Equity',    'Capital',          0, 'cr', 1),
        ('Discount Allowed',   'Expense',   'Indirect Expense', 0, 'dr', 1),
        ('Round Off',          'Expense',   'Indirect Expense', 0, 'dr', 1),
    ]
    for acc_name, acc_grp, acc_type, op_bal, op_type, is_sys in starter_accounts:
        c.execute('''
            INSERT INTO ledger_accounts (name, account_group, account_type, opening_balance, opening_balance_type, is_system)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO NOTHING
        ''', (acc_name, acc_grp, acc_type, op_bal, op_type, is_sys))

    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at: {DB_PATH}")
    print("[DB] Initial user accounts configured.")


def dict_row(row):
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else None


def dict_rows(rows):
    """Convert a list of sqlite3.Row objects to plain dicts."""
    return [dict(r) for r in rows]


def post_ledger_entry(conn, voucher_type, voucher_no, voucher_date, entries, reference_table=None, reference_id=None, created_by=None):
    """
    Post a double-entry journal voucher to ledger_entries.
    `entries` is a list of dicts: [{'account_name': str, 'debit': float, 'credit': float, 'narration': str}]
    Validates sum(debit) == sum(credit) (within 0.01 tolerance) before saving.
    """
    if not entries or not isinstance(entries, list):
        raise ValueError("Ledger posting requires a non-empty list of entry dicts")

    valid_voucher_types = ('sales', 'credit_note', 'purchase', 'payment_in', 'payment_out', 'expense', 'journal')
    if voucher_type not in valid_voucher_types:
        raise ValueError(f"Invalid voucher_type '{voucher_type}'. Must be one of {valid_voucher_types}")

    total_debit = 0.0
    total_credit = 0.0
    processed_rows = []

    for idx, e in enumerate(entries):
        acc_name = e.get('account_name')
        if not acc_name:
            raise ValueError(f"Entry at index {idx} is missing 'account_name'")

        account = conn.execute('SELECT id FROM ledger_accounts WHERE name=?', (acc_name,)).fetchone()
        if not account:
            raise ValueError(f"Ledger account '{acc_name}' not found in ledger_accounts")

        try:
            dr = float(e.get('debit', 0) or 0)
        except (ValueError, TypeError):
            dr = 0.0

        try:
            cr = float(e.get('credit', 0) or 0)
        except (ValueError, TypeError):
            cr = 0.0

        if dr < 0 or cr < 0:
            raise ValueError(f"Debit and Credit amounts must be non-negative (account: '{acc_name}')")

        total_debit += dr
        total_credit += cr

        processed_rows.append((
            voucher_type,
            voucher_no,
            str(voucher_date) if voucher_date else None,
            account['id'],
            round(dr, 2),
            round(cr, 2),
            e.get('narration', ''),
            reference_table,
            reference_id,
            created_by
        ))

    if abs(total_debit - total_credit) > 0.01:
        raise ValueError(
            f"Unbalanced ledger entry for voucher '{voucher_no}': "
            f"Total Debit (₹{total_debit:.2f}) != Total Credit (₹{total_credit:.2f})"
        )

    inserted_ids = []
    for row in processed_rows:
        cur = conn.execute('''
            INSERT INTO ledger_entries
            (voucher_type, voucher_no, voucher_date, account_id, debit, credit, narration, reference_table, reference_id, created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        ''', row)
        inserted_ids.append(cur.lastrowid)

    return inserted_ids

