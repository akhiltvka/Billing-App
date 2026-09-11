-- =============================================================================
-- Supabase PostgreSQL Schema: Multi-Tenant Synced Mirror
-- =============================================================================
-- This schema represents the multi-tenant cloud PostgreSQL mirror of the local
-- SQLite database across all registered outlets / terminals.
--
-- Key Multi-Tenant Architecture Rules:
-- 1. Tenant Partitioning: Every core transactional and master table includes
--    `tenant_id TEXT NOT NULL`, derived from the registered hardware machine ID.
-- 2. Primary Key: `client_uuid UUID PRIMARY KEY DEFAULT gen_random_uuid()`
--    (Authoritative across both local SQLite and remote PostgreSQL).
-- 3. Tenant-Scoped Uniqueness: Uniqueness constraints (such as bill_no,
--    product code, category name) are scoped per tenant:
--    `UNIQUE (tenant_id, bill_no)`, `UNIQUE (tenant_id, code)`.
--    Outlets will never clash or overwrite each other's data.
-- 4. Foreign Keys: Reference parent tables' client_uuid (UUID).
-- 5. Numeric Precision:
--    - Currency / Money columns: NUMERIC(12, 2)
--    - Quantities / Weights / Ratios: NUMERIC(12, 3)
-- 6. Booleans: Stored as native PostgreSQL BOOLEAN (converted from SQLite 0/1).
-- 7. Auditability: Every table contains `synced_at TIMESTAMPTZ DEFAULT now()`.
-- =============================================================================

-- Enable pgcrypto / uuid-ossp if needed (built-in gen_random_uuid() in PG 13+)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- 0. TENANTS (Registered Outlets & Multi-Tenant Directory)
-- =============================================================================
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id       TEXT PRIMARY KEY,
    shop_name       TEXT NOT NULL DEFAULT 'Meat Products of India',
    shop_tagline    TEXT,
    currency_symbol TEXT DEFAULT '₹',
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_synced_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenants_last_synced ON tenants(last_synced_at);

-- =============================================================================
-- 1. CATEGORIES (Self-referencing hierarchy)
-- =============================================================================
CREATE TABLE IF NOT EXISTS categories (
    client_uuid        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    name               TEXT NOT NULL,
    gst_rate           NUMERIC(12, 2) DEFAULT 0.00,
    hsn_code           TEXT,
    description        TEXT,
    parent_category_id UUID REFERENCES categories(client_uuid) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    synced_at          TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_categories_tenant_name UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_categories_tenant_id ON categories(tenant_id);
CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_category_id);

-- =============================================================================
-- 2. PRODUCTS (Product catalog and inventory master)
-- =============================================================================
CREATE TABLE IF NOT EXISTS products (
    client_uuid               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                 TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    category_id               UUID REFERENCES categories(client_uuid) ON DELETE SET NULL,
    name                      TEXT NOT NULL,
    code                      TEXT NOT NULL,
    hsn_code                  TEXT,
    unit                      TEXT DEFAULT 'kg',
    purchase_unit             TEXT DEFAULT 'kg',
    sale_unit                 TEXT DEFAULT 'kg',
    conversion_factor         NUMERIC(12, 3) DEFAULT 1.000,
    purchase_price            NUMERIC(12, 2) DEFAULT 0.00,
    selling_price             NUMERIC(12, 2) DEFAULT 0.00,
    gst_rate                  NUMERIC(12, 2) DEFAULT 0.00,
    min_stock                 NUMERIC(12, 3) DEFAULT 1.000,
    current_stock             NUMERIC(12, 3) DEFAULT 0.000,
    barcode                   TEXT,
    product_type              TEXT DEFAULT 'perishable' CHECK (product_type IN ('perishable', 'general')),
    mrp                       NUMERIC(12, 2) DEFAULT NULL,
    is_price_inclusive_of_tax BOOLEAN DEFAULT TRUE,
    brand                     TEXT DEFAULT NULL,
    pack_size                 TEXT DEFAULT NULL,
    reorder_lead_time_days    INTEGER DEFAULT 1,
    shelf_life_days           INTEGER DEFAULT NULL,
    active                    BOOLEAN DEFAULT TRUE,
    created_at                TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at                TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    synced_at                 TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_products_tenant_code UNIQUE (tenant_id, code)
);

CREATE INDEX IF NOT EXISTS idx_products_tenant_id ON products(tenant_id);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(active);

-- =============================================================================
-- 3. CUSTOMERS (Customer master)
-- =============================================================================
CREATE TABLE IF NOT EXISTS customers (
    client_uuid    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    name           TEXT NOT NULL,
    phone          TEXT,
    email          TEXT,
    address        TEXT,
    gstin          TEXT,
    state_code     TEXT,
    credit_balance NUMERIC(12, 2) DEFAULT 0.00,
    loyalty_points NUMERIC(12, 2) DEFAULT 0.00,
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    synced_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_customers_tenant_id ON customers(tenant_id);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

-- =============================================================================
-- 4. SUPPLIERS (Supplier master)
-- =============================================================================
CREATE TABLE IF NOT EXISTS suppliers (
    client_uuid    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    name           TEXT NOT NULL,
    contact_person TEXT,
    phone          TEXT,
    email          TEXT,
    address        TEXT,
    gstin          TEXT,
    balance        NUMERIC(12, 2) DEFAULT 0.00,
    created_at     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    synced_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_suppliers_tenant_id ON suppliers(tenant_id);
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
CREATE INDEX IF NOT EXISTS idx_suppliers_phone ON suppliers(phone);

-- =============================================================================
-- 5. BILLS (Sales invoices / receipts)
-- =============================================================================
CREATE TABLE IF NOT EXISTS bills (
    client_uuid      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    bill_no          TEXT NOT NULL,
    customer_id      UUID REFERENCES customers(client_uuid) ON DELETE SET NULL,
    customer_name    TEXT,
    customer_phone   TEXT,
    customer_gstin   TEXT,
    place_of_supply  TEXT,
    is_interstate    BOOLEAN DEFAULT FALSE,
    date             TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    subtotal         NUMERIC(12, 2) DEFAULT 0.00,
    discount_percent NUMERIC(12, 2) DEFAULT 0.00,
    discount_amount  NUMERIC(12, 2) DEFAULT 0.00,
    cgst             NUMERIC(12, 2) DEFAULT 0.00,
    sgst             NUMERIC(12, 2) DEFAULT 0.00,
    igst             NUMERIC(12, 2) DEFAULT 0.00,
    grand_total      NUMERIC(12, 2) DEFAULT 0.00,
    amount_paid      NUMERIC(12, 2) DEFAULT 0.00,
    amount_due       NUMERIC(12, 2) DEFAULT 0.00,
    change_amount    NUMERIC(12, 2) DEFAULT 0.00,
    payment_mode     TEXT DEFAULT 'cash',
    notes            TEXT,
    cancel_reason    TEXT,
    status           TEXT DEFAULT 'paid',
    is_test          BOOLEAN DEFAULT FALSE,
    synced_at        TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_bills_tenant_bill_no UNIQUE (tenant_id, bill_no)
);

CREATE INDEX IF NOT EXISTS idx_bills_tenant_id ON bills(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bills_customer_id ON bills(customer_id);
CREATE INDEX IF NOT EXISTS idx_bills_date ON bills(date);
CREATE INDEX IF NOT EXISTS idx_bills_status ON bills(status);

-- =============================================================================
-- 6. BILL_ITEMS (Line items in each bill)
-- =============================================================================
CREATE TABLE IF NOT EXISTS bill_items (
    client_uuid  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    bill_id      UUID NOT NULL REFERENCES bills(client_uuid) ON DELETE CASCADE,
    product_id   UUID REFERENCES products(client_uuid) ON DELETE SET NULL,
    product_name TEXT NOT NULL,
    hsn_code     TEXT,
    unit         TEXT,
    quantity     NUMERIC(12, 3) NOT NULL,
    unit_price   NUMERIC(12, 2) NOT NULL,
    gst_rate     NUMERIC(12, 2) DEFAULT 0.00,
    discount     NUMERIC(12, 2) DEFAULT 0.00,
    taxable_amt  NUMERIC(12, 2) DEFAULT 0.00,
    cgst_amt     NUMERIC(12, 2) DEFAULT 0.00,
    sgst_amt     NUMERIC(12, 2) DEFAULT 0.00,
    igst_amt     NUMERIC(12, 2) DEFAULT 0.00,
    amount       NUMERIC(12, 2) NOT NULL,
    cost_price   NUMERIC(12, 2) DEFAULT NULL,
    synced_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bill_items_tenant_id ON bill_items(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bill_items_bill_id ON bill_items(bill_id);
CREATE INDEX IF NOT EXISTS idx_bill_items_product_id ON bill_items(product_id);

-- =============================================================================
-- 7. BILL_PAYMENTS (Payment installments / settlements for bills)
-- =============================================================================
CREATE TABLE IF NOT EXISTS bill_payments (
    client_uuid  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    bill_id      UUID NOT NULL REFERENCES bills(client_uuid) ON DELETE CASCADE,
    amount       NUMERIC(12, 2) NOT NULL,
    payment_mode TEXT DEFAULT 'cash',
    paid_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    received_by  TEXT,
    notes        TEXT,
    synced_at    TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bill_payments_tenant_id ON bill_payments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bill_payments_bill_id ON bill_payments(bill_id);
CREATE INDEX IF NOT EXISTS idx_bill_payments_paid_at ON bill_payments(paid_at);

-- =============================================================================
-- 8. LOYALTY_LEDGER (Loyalty points earn / burn audit ledger)
-- =============================================================================
CREATE TABLE IF NOT EXISTS loyalty_ledger (
    client_uuid   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    customer_id   UUID NOT NULL REFERENCES customers(client_uuid) ON DELETE CASCADE,
    bill_id       UUID REFERENCES bills(client_uuid) ON DELETE SET NULL,
    points_change NUMERIC(12, 2) NOT NULL,
    reason        TEXT,
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    synced_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_tenant_id ON loyalty_ledger(tenant_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_customer_id ON loyalty_ledger(customer_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_bill_id ON loyalty_ledger(bill_id);

-- =============================================================================
-- 9. STOCK_TRANSACTIONS (Inventory movement ledger)
-- =============================================================================
CREATE TABLE IF NOT EXISTS stock_transactions (
    client_uuid   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    product_id    UUID REFERENCES products(client_uuid) ON DELETE SET NULL,
    type          TEXT NOT NULL CHECK (type IN ('in','out','wastage','adjustment','conversion_out','conversion_in')),
    quantity      NUMERIC(12, 3) NOT NULL,
    unit_price    NUMERIC(12, 2) DEFAULT 0.00,
    reference_id  TEXT,
    supplier_id   UUID REFERENCES suppliers(client_uuid) ON DELETE SET NULL,
    expiry_date   DATE,
    notes         TEXT,
    date          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    status        TEXT DEFAULT 'approved',
    created_by    TEXT,
    approved_by   TEXT,
    purchase_date DATE,
    synced_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stock_transactions_tenant_id ON stock_transactions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_stock_transactions_product_id ON stock_transactions(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_transactions_supplier_id ON stock_transactions(supplier_id);
CREATE INDEX IF NOT EXISTS idx_stock_transactions_date ON stock_transactions(date);
CREATE INDEX IF NOT EXISTS idx_stock_transactions_type ON stock_transactions(type);

-- =============================================================================
-- 10. LEDGER_VOUCHERS (Double-entry voucher header / idempotency protection)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ledger_vouchers (
    client_uuid     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    voucher_type    TEXT NOT NULL,
    voucher_no      TEXT NOT NULL,
    voucher_date    DATE,
    reference_table TEXT,
    reference_id    TEXT,
    created_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    synced_at       TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_ledger_vouchers_tenant_type_no UNIQUE (tenant_id, voucher_type, voucher_no)
);

CREATE INDEX IF NOT EXISTS idx_ledger_vouchers_tenant_id ON ledger_vouchers(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ledger_vouchers_date ON ledger_vouchers(voucher_date);
CREATE INDEX IF NOT EXISTS idx_ledger_vouchers_ref ON ledger_vouchers(reference_table, reference_id);

-- =============================================================================
-- 11. LEDGER_ENTRIES (Double-entry journal lines)
-- =============================================================================
CREATE TABLE IF NOT EXISTS ledger_entries (
    client_uuid     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL DEFAULT 'DEFAULT_TENANT',
    voucher_type    TEXT NOT NULL CHECK (voucher_type IN ('sales', 'credit_note', 'purchase', 'payment_in', 'payment_out', 'expense', 'journal')),
    voucher_no      TEXT,
    voucher_date    DATE,
    account_id      INTEGER NOT NULL,
    debit           NUMERIC(12, 2) DEFAULT 0.00,
    credit          NUMERIC(12, 2) DEFAULT 0.00,
    narration       TEXT,
    reference_table TEXT,
    reference_id    TEXT,
    created_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    synced_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ledger_entries_tenant_id ON ledger_entries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_voucher ON ledger_entries(voucher_type, voucher_no);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_account ON ledger_entries(account_id);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_date ON ledger_entries(voucher_date);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_ref ON ledger_entries(reference_table, reference_id);

-- =============================================================================
-- 12. LICENSES (Application Licensing & Razorpay Payment Tracking)
-- =============================================================================
CREATE TABLE IF NOT EXISTS licenses (
    id                    BIGSERIAL PRIMARY KEY,
    machine_id            VARCHAR(64) UNIQUE NOT NULL,
    outlet_code           VARCHAR(16),
    outlet_name           TEXT,
    status                VARCHAR(32) NOT NULL DEFAULT 'trial',
    activated_at          TIMESTAMPTZ,
    expires_at            TIMESTAMPTZ,
    grace_expires_at      TIMESTAMPTZ,
    razorpay_payment_link TEXT DEFAULT 'https://rzp.io/rzp/gVl69f0',
    amount                NUMERIC(12, 2) DEFAULT 8000.00,
    payment_id            TEXT,
    last_synced_at        TIMESTAMPTZ DEFAULT now(),
    created_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_licenses_machine_id ON licenses(machine_id);
CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);

-- =============================================================================
-- IDEMPOTENT MULTI-TENANCY MIGRATION FOR EXISTING SUPABASE DATABASES
-- =============================================================================
DO $$
BEGIN
    -- 1. categories
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='categories' AND column_name='tenant_id') THEN
        ALTER TABLE categories ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
        ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_name_key;
        ALTER TABLE categories ADD CONSTRAINT uq_categories_tenant_name UNIQUE (tenant_id, name);
    END IF;

    -- 2. products
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='products' AND column_name='tenant_id') THEN
        ALTER TABLE products ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
        ALTER TABLE products DROP CONSTRAINT IF EXISTS products_code_key;
        ALTER TABLE products ADD CONSTRAINT uq_products_tenant_code UNIQUE (tenant_id, code);
    END IF;

    -- 3. customers
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='customers' AND column_name='tenant_id') THEN
        ALTER TABLE customers ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
    END IF;

    -- 4. suppliers
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='suppliers' AND column_name='tenant_id') THEN
        ALTER TABLE suppliers ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
    END IF;

    -- 5. bills
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bills' AND column_name='tenant_id') THEN
        ALTER TABLE bills ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
        ALTER TABLE bills DROP CONSTRAINT IF EXISTS bills_bill_no_key;
        ALTER TABLE bills ADD CONSTRAINT uq_bills_tenant_bill_no UNIQUE (tenant_id, bill_no);
    END IF;

    -- 6. bill_items
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bill_items' AND column_name='tenant_id') THEN
        ALTER TABLE bill_items ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
    END IF;

    -- 7. bill_payments
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bill_payments' AND column_name='tenant_id') THEN
        ALTER TABLE bill_payments ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
    END IF;

    -- 8. loyalty_ledger
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='loyalty_ledger' AND column_name='tenant_id') THEN
        ALTER TABLE loyalty_ledger ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
    END IF;

    -- 9. stock_transactions
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stock_transactions' AND column_name='tenant_id') THEN
        ALTER TABLE stock_transactions ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
    END IF;

    -- 10. ledger_vouchers
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ledger_vouchers' AND column_name='tenant_id') THEN
        ALTER TABLE ledger_vouchers ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
        ALTER TABLE ledger_vouchers DROP CONSTRAINT IF EXISTS uq_ledger_vouchers_type_no;
        ALTER TABLE ledger_vouchers ADD CONSTRAINT uq_ledger_vouchers_tenant_type_no UNIQUE (tenant_id, voucher_type, voucher_no);
    END IF;

    -- 11. ledger_entries
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ledger_entries' AND column_name='tenant_id') THEN
        ALTER TABLE ledger_entries ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'DEFAULT_TENANT';
    END IF;
END $$;
