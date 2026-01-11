"""Tests for historical portfolio performance functionality."""

from datetime import date, timedelta
from typing import Dict, List


def _create_price_dict(
    tickers: List[str], price_value: float, start_date: date, end_date: date
) -> Dict[str, Dict[date, float]]:
    """Helper to create price dictionary in new format.

    Args:
        tickers: List of ticker symbols
        price_value: Price value to use for all dates
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        Dictionary mapping ticker to dictionary mapping date to price
    """
    result: Dict[str, Dict[date, float]] = {}
    current = start_date
    while current <= end_date:
        for ticker in tickers:
            if ticker not in result:
                result[ticker] = {}
            result[ticker][current] = price_value
        current += timedelta(days=1)
    return result


# Tests for get_historical_performance have been removed as part of refactoring
# The v1 implementation and all tests comparing v1 vs v2 have been removed
# The function now uses the optimized implementation (formerly v2)
