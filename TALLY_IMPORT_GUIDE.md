# Tally Prime XML Data Import Guide

This guide details the two-step workflow for exporting accounting data from the Billing & Inventory App and importing it directly into **Tally Prime** or **Tally.ERP 9**.

---

## Step 1: Export & Import Ledger Masters (One-Time Setup)

Before importing vouchers for the first time, you must import the Chart of Accounts (Ledger Masters) into your Tally company.

1. **Download Master XML**:
   - Access `GET /api/ledger/accounts/export-tally-masters` (via app menu or direct link).
   - This downloads `tally_masters.xml`.

2. **Import into Tally**:
   - Open **Tally Prime** and select your company.
   - Go to **Alt + O** (Import) → **Masters** (or **Gateway of Tally** → **Import Data** → **Masters**).
   - In **File Path / File Name**, specify the path to `tally_masters.xml`.
   - Select **Behavior on import**: *Combine Amounts / Modify with new data* (or *Ignore Duplicate*).
   - Press **Enter** to complete the import.

---

## Step 2: Export & Import Financial Vouchers (Periodic)

Export sales, purchases, payments, receipts, credit notes, and expenses for any given accounting period.

1. **Download Voucher XML**:
   - Access `GET /api/ledger/export-tally-vouchers?from=YYYY-MM-DD&to=YYYY-MM-DD` (e.g., `from=2026-08-01&to=2026-08-31`).
   - Optional filter: Add `&voucher_type=sales` (or `purchase`, `payment_in`, `payment_out`, `expense`, `credit_note`, `journal`).
   - This downloads `tally_vouchers_2026-08-01_2026-08-31.xml`.

2. **Import into Tally**:
   - In **Tally Prime**, go to **Alt + O** (Import) → **Transactions** (or **Gateway of Tally** → **Import Data** → **Vouchers**).
   - Enter the full filepath to `tally_vouchers_...xml`.
   - Press **Enter** to execute the import.

---

## Step 3: Verification & Reconciliation

After importing both masters and vouchers into Tally Prime:

1. In **Tally Prime**, open **Gateway of Tally** → **Display More Reports** → **Trial Balance**.
2. Press **Alt + F2** to set the date range matching your exported period.
3. Compare Tally's Trial Balance total debits and credits against the web application's Trial Balance report at `GET /api/reports/trial-balance?as_of=YYYY-MM-DD`.
4. The **Total Debits**, **Total Credits**, **Sales Account**, and **Sundry Debtors** balances in Tally should match the web app's financial reports to the exact rupee.
