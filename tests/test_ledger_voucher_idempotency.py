"""Regression tests for duplicate ledger voucher protection."""

import unittest

from database import get_db, init_db, post_ledger_entry


class TestLedgerVoucherIdempotency(unittest.TestCase):
    voucher_no = 'TEST-IDEMPOTENT-001'

    @classmethod
    def setUpClass(cls):
        init_db()

    def tearDown(self):
        conn = get_db()
        conn.execute('DELETE FROM ledger_entries WHERE voucher_no=?', (self.voucher_no,))
        conn.execute('DELETE FROM ledger_vouchers WHERE voucher_no=?', (self.voucher_no,))
        conn.commit()
        conn.close()

    def test_multi_line_voucher_is_allowed(self):
        conn = get_db()
        ids = post_ledger_entry(
            conn, 'journal', self.voucher_no, '2026-01-01',
            [
                {'account_name': 'Cash', 'debit': 100, 'credit': 0},
                {'account_name': 'Sales Account', 'debit': 0, 'credit': 100},
            ],
        )
        conn.commit()
        conn.close()
        self.assertEqual(len(ids), 2)

    def test_duplicate_voucher_is_rejected(self):
        conn = get_db()
        entries = [
            {'account_name': 'Cash', 'debit': 50, 'credit': 0},
            {'account_name': 'Sales Account', 'debit': 0, 'credit': 50},
        ]
        post_ledger_entry(conn, 'journal', self.voucher_no, '2026-01-01', entries)
        with self.assertRaisesRegex(ValueError, 'already been posted'):
            post_ledger_entry(conn, 'journal', self.voucher_no, '2026-01-01', entries)
        conn.rollback()
        conn.close()

    def test_unbalanced_voucher_does_not_register_header(self):
        conn = get_db()
        with self.assertRaisesRegex(ValueError, 'Unbalanced ledger entry'):
            post_ledger_entry(
                conn, 'journal', self.voucher_no, '2026-01-01',
                [{'account_name': 'Cash', 'debit': 10, 'credit': 0}],
            )
        self.assertIsNone(conn.execute(
            'SELECT 1 FROM ledger_vouchers WHERE voucher_no=?', (self.voucher_no,)
        ).fetchone())
        conn.close()


if __name__ == '__main__':
    unittest.main()
