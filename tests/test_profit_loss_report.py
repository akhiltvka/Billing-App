"""
Regression Test Suite for Profit & Loss Report Opening Balance Period Exclusion
"""

import unittest
import json
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, get_db


class TestProfitLossReport(unittest.TestCase):

    def _cleanup_test_data(self):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ledger_entries WHERE account_id IN (SELECT id FROM ledger_accounts WHERE name IN ('Test Sales Revenue PNL', 'Test Rent Expense PNL'))")
        cursor.execute("DELETE FROM ledger_accounts WHERE name IN ('Test Sales Revenue PNL', 'Test Rent Expense PNL')")
        cursor.execute("DELETE FROM users WHERE username='test_pnl_admin'")
        conn.commit()
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_pnl_secret_key'

        self._cleanup_test_data()

        conn = get_db()
        cursor = conn.cursor()

        # Seed admin user
        cursor.execute("""
            INSERT INTO users (username, password_hash, full_name, role, role_id, active)
            VALUES ('test_pnl_admin', 'dummy_hash', 'PNL Admin', 'admin', 1, 1)
        """)
        self.user_id = cursor.lastrowid

        # Seed test Income Account with opening balance = 5000.0 Cr
        cursor.execute("""
            INSERT INTO ledger_accounts (name, account_group, account_type, opening_balance, opening_balance_type, is_system)
            VALUES ('Test Sales Revenue PNL', 'Income', 'Direct Income', 5000.0, 'cr', 0)
        """)
        self.inc_acc_id = cursor.lastrowid

        # Seed test Expense Account with opening balance = 2000.0 Dr
        cursor.execute("""
            INSERT INTO ledger_accounts (name, account_group, account_type, opening_balance, opening_balance_type, is_system)
            VALUES ('Test Rent Expense PNL', 'Expense', 'Indirect Expense', 2000.0, 'dr', 0)
        """)
        self.exp_acc_id = cursor.lastrowid

        # Post transaction in July 2026 (last month)
        cursor.execute("""
            INSERT INTO ledger_entries (voucher_type, voucher_no, voucher_date, account_id, debit, credit, narration)
            VALUES ('sales', 'V-JUL-01', '2026-07-15', ?, 0, 1000.0, 'July Sale')
        """, (self.inc_acc_id,))
        cursor.execute("""
            INSERT INTO ledger_entries (voucher_type, voucher_no, voucher_date, account_id, debit, credit, narration)
            VALUES ('payment_out', 'V-JUL-02', '2026-07-15', ?, 400.0, 0, 'July Rent')
        """, (self.exp_acc_id,))

        # Post transaction in August 2026 (this month)
        cursor.execute("""
            INSERT INTO ledger_entries (voucher_type, voucher_no, voucher_date, account_id, debit, credit, narration)
            VALUES ('sales', 'V-AUG-01', '2026-08-10', ?, 0, 3000.0, 'August Sale')
        """, (self.inc_acc_id,))
        cursor.execute("""
            INSERT INTO ledger_entries (voucher_type, voucher_no, voucher_date, account_id, debit, credit, narration)
            VALUES ('payment_out', 'V-AUG-02', '2026-08-10', ?, 1200.0, 0, 'August Rent')
        """, (self.exp_acc_id,))

        conn.commit()
        conn.close()

    def tearDown(self):
        self._cleanup_test_data()

    def test_period_filtered_profit_loss_excludes_opening_balance(self):
        """Period-filtered P&L must only sum entries within the date range, excluding opening balance."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_pnl_admin'
            sess['user_role'] = 'admin'

        response = self.client.get('/api/reports/profit-loss?from=2026-08-01&to=2026-08-31')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')

        pnl = data.get('data', {})
        inc_rows = {r['account_name']: r['amount'] for r in pnl.get('income_accounts', [])}
        exp_rows = {r['account_name']: r['amount'] for r in pnl.get('expense_accounts', [])}

        # In August only: Test Sales Revenue should be 3000.0 (NOT 3000 + 5000 = 8000)
        self.assertEqual(inc_rows.get('Test Sales Revenue PNL'), 3000.0)
        # In August only: Test Rent Expense should be 1200.0 (NOT 1200 + 2000 = 3200)
        self.assertEqual(exp_rows.get('Test Rent Expense PNL'), 1200.0)

    def test_all_time_profit_loss_includes_opening_balance(self):
        """All-time P&L (without from/to parameters) must include opening balances in totals."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            sess['username'] = 'test_pnl_admin'
            sess['user_role'] = 'admin'

        response = self.client.get('/api/reports/profit-loss')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertEqual(data.get('status'), 'ok')

        pnl = data.get('data', {})
        inc_rows = {r['account_name']: r['amount'] for r in pnl.get('income_accounts', [])}
        exp_rows = {r['account_name']: r['amount'] for r in pnl.get('expense_accounts', [])}

        # All-time: 3000 (Aug) + 1000 (Jul) + 5000 (Op Bal) = 9000.0
        self.assertEqual(inc_rows.get('Test Sales Revenue PNL'), 9000.0)
        # All-time: 1200 (Aug) + 400 (Jul) + 2000 (Op Bal) = 3600.0
        self.assertEqual(exp_rows.get('Test Rent Expense PNL'), 3600.0)


if __name__ == '__main__':
    unittest.main()
