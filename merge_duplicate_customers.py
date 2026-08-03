#!/usr/bin/env python3
"""
merge_duplicate_customers.py — Cleanup & Merge Duplicate Customer Records
Meat Products of India — Billing & Inventory Management App

Finds duplicate customers with identical non-empty phone numbers, selects a
surviving customer record (preferring highest bill count, then oldest created_at),
reassigns all bills/credit notes/held bills/ledgers to the survivor, transfers credit balance,
and removes duplicate customer records.

Runs in --dry-run mode by default. Pass --apply to commit database changes.
"""

import sys
import os
import sqlite3
import argparse

# Base directory setup
_base_dir = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.environ.get('DB_PATH') or os.path.join(_base_dir, 'data', 'meatshop.db')

def get_db_connection(db_path):
    if not os.path.exists(db_path):
        print(f"[ERROR] Database file not found at '{db_path}'")
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def main():
    parser = argparse.ArgumentParser(description="Find and merge duplicate customer records by phone number.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help=f"Path to SQLite database file (default: {DEFAULT_DB_PATH})")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True, help="Preview actions without modifying the database (default)")
    group.add_argument("--apply", action="store_true", help="Execute merge operations and commit changes to database")

    args = parser.parse_args()
    is_dry_run = not args.apply

    print("=" * 80)
    print(" CUSTOMER DUPLICATE CLEANUP & MERGE TOOL")
    print(f" Database Path : {args.db_path}")
    print(f" Execution Mode: {'[DRY RUN] Preview only - no DB changes' if is_dry_run else '[APPLY] Modifying database'}")
    print("=" * 80)

    conn = get_db_connection(args.db_path)
    c = conn.cursor()

    # Find phone numbers associated with multiple customer records
    duplicate_groups = c.execute("""
        SELECT phone, COUNT(*) as cnt
        FROM customers
        WHERE phone IS NOT NULL AND phone != ''
        GROUP BY phone
        HAVING cnt > 1
        ORDER BY cnt DESC, phone ASC
    """).fetchall()

    if not duplicate_groups:
        print("\n[OK] No duplicate customers found. All registered phone numbers are unique!")
        conn.close()
        return

    print(f"\nFound {len(duplicate_groups)} duplicate phone number group(s):\n")

    total_duplicates_merged = 0
    total_bills_reassigned = 0

    for idx, group in enumerate(duplicate_groups, start=1):
        phone = group['phone']
        cust_rows = c.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchall()

        # Score customers to pick survivor:
        # Highest bill count first, then oldest created_at, then lowest ID
        scored_custs = []
        for cust in cust_rows:
            cid = cust['id']
            bill_cnt = c.execute("SELECT COUNT(*) FROM bills WHERE customer_id = ?", (cid,)).fetchone()[0]
            created_at = cust['created_at'] or ''
            scored_custs.append({
                'row': cust,
                'bill_cnt': bill_cnt,
                'created_at': created_at,
                'id': cid
            })

        # Sort: max bill_cnt descending, created_at ascending, id ascending
        scored_custs.sort(key=lambda x: (-x['bill_cnt'], x['created_at'], x['id']))

        survivor = scored_custs[0]['row']
        survivor_stats = scored_custs[0]
        duplicates = scored_custs[1:]

        dup_ids = [d['id'] for d in duplicates]
        total_duplicates_merged += len(dup_ids)

        # Calculate bills to reassign
        placeholders = ','.join('?' for _ in dup_ids)
        dup_bills = c.execute(f"SELECT COUNT(*) FROM bills WHERE customer_id IN ({placeholders})", dup_ids).fetchone()[0]
        total_bills_reassigned += dup_bills

        # Calculate credit balance transfer
        dup_credit_transfer = sum(float(d['row']['credit_balance'] or 0) for d in duplicates)

        print(f"Group #{idx}: Phone '{phone}' ({len(cust_rows)} records)")
        print(f"  [SURVIVOR] Customer #{survivor['id']} - \"{survivor['name']}\"")
        print(f"      Created: {survivor['created_at']} | Bills: {survivor_stats['bill_cnt']} | Credit Bal: Rs. {survivor['credit_balance'] or 0}")

        for dup in duplicates:
            d_row = dup['row']
            print(f"  [MERGE & DELETE] Customer #{d_row['id']} - \"{d_row['name']}\"")
            print(f"      Created: {d_row['created_at']} | Bills: {dup['bill_cnt']} | Credit Bal: Rs. {d_row['credit_balance'] or 0}")

        print(f"  -> Action: Reassign {dup_bills} bill(s), transfer Rs. {dup_credit_transfer:.2f} credit balance to Survivor #{survivor['id']}, and delete duplicate customer records {dup_ids}")
        print("-" * 75)

        if not is_dry_run:
            # Execute database updates inside transaction
            survivor_id = survivor['id']

            # Reassign bills
            c.execute(f"UPDATE bills SET customer_id = ? WHERE customer_id IN ({placeholders})", [survivor_id] + dup_ids)

            # Reassign credit notes
            try:
                c.execute(f"UPDATE credit_notes SET customer_id = ? WHERE customer_id IN ({placeholders})", [survivor_id] + dup_ids)
            except sqlite3.OperationalError:
                pass

            # Reassign held bills
            try:
                c.execute(f"UPDATE held_bills SET customer_id = ? WHERE customer_id IN ({placeholders})", [survivor_id] + dup_ids)
            except sqlite3.OperationalError:
                pass

            # Reassign ledger entries
            try:
                c.execute(f"UPDATE ledger_entries SET reference_id = ? WHERE reference_table = 'customers' AND reference_id IN ({placeholders})", [survivor_id] + dup_ids)
            except sqlite3.OperationalError:
                pass

            # Transfer credit balance
            if dup_credit_transfer > 0:
                c.execute("UPDATE customers SET credit_balance = credit_balance + ? WHERE id = ?", (dup_credit_transfer, survivor_id))

            # Delete duplicate customer records
            c.execute(f"DELETE FROM customers WHERE id IN ({placeholders})", dup_ids)

    if is_dry_run:
        print("\n" + "=" * 80)
        print(f" Summary (DRY RUN): {len(duplicate_groups)} group(s) processed.")
        print(f" {total_duplicates_merged} duplicate record(s) identified for deletion.")
        print(f" {total_bills_reassigned} bill(s) identified for reassignment.")
        print(" No changes were made to the database.")
        print(" To apply these merges to the database, run:")
        print(f"   python merge_duplicate_customers.py --apply")
        print("=" * 80)
    else:
        conn.commit()
        # Attempt to build unique index after cleanup
        try:
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_phone_unique ON customers(phone) WHERE phone IS NOT NULL AND phone != ""')
            conn.commit()
            index_status = "and created UNIQUE INDEX `idx_customers_phone_unique` successfully"
        except Exception as e:
            index_status = f"(unique index status: {e})"

        print("\n" + "=" * 80)
        print(f" SUCCESS: Merged {total_duplicates_merged} duplicate record(s) into surviving customers {index_status}.")
        print(f" {total_bills_reassigned} bill(s) reassigned.")
        print(" Database updated successfully!")
        print("=" * 80)

    conn.close()

if __name__ == "__main__":
    main()
