"""Regression tests for deterministic monetary arithmetic."""

import unittest
from decimal import Decimal

from money import db_money, money, to_decimal


class TestMoney(unittest.TestCase):
    def test_half_up_rounding_does_not_use_binary_float_behavior(self):
        self.assertEqual(money('2.675'), Decimal('2.68'))
        self.assertEqual(money('10.005'), Decimal('10.01'))

    def test_database_boundary_returns_two_decimal_float(self):
        self.assertEqual(db_money('19.999'), 20.0)

    def test_invalid_value_is_rejected(self):
        with self.assertRaises(ValueError):
            to_decimal('not-a-number')


if __name__ == '__main__':
    unittest.main()
