"""Deterministic monetary arithmetic helpers for billing and accounting."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


MONEY_QUANTUM = Decimal('0.01')


def to_decimal(value, default='0'):
    """Convert an API/database value without introducing binary float error."""
    if value is None or value == '':
        value = default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f'Invalid monetary value: {value!r}') from exc


def money(value, default='0'):
    """Return a monetary Decimal rounded to two places using half-up rounding."""
    return to_decimal(value, default).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def db_money(value, default='0'):
    """Return a two-decimal float for compatibility with existing SQLite REAL columns."""
    return float(money(value, default))
