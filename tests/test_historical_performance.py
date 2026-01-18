"""Tests for historical portfolio performance functionality."""

import pytest
from datetime import date, timedelta
from typing import Dict, List
from unittest.mock import Mock

from wpm.models import Asset, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio, get_historical_performance


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


class TestGetHistoricalPerformanceBrokerFilter:
    """Tests for broker filtering in get_historical_performance."""

    def test_get_historical_performance_with_broker_filter_single(self):
        """Test get_historical_performance with single broker filter."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="Schwab",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
            )
        )

        mock_price_service = Mock()
        mock_price_service.get_historical_prices.return_value = _create_price_dict(
            ["VOO"], 620.0, date(2024, 1, 31), date(2024, 1, 31)
        )

        history_points = get_historical_performance(
            portfolio, mock_price_service, date(2024, 1, 31), date(2024, 1, 31), brokers=["IBKR"]
        )

        assert len(history_points) == 1
        hp = history_points[0]
        # Should only include positions from IBKR (2.0 * 620 = 1240.0)
        assert hp.asset_positions["VOO"] == 1240.0
        assert hp.total_market_value == 1240.0

    def test_get_historical_performance_with_broker_filter_multiple(self):
        """Test get_historical_performance with multiple broker filter."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="Schwab",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 20),
                asset=asset,
                action="Buy",
                broker="Tiger",
                currency="USD",
                price=620.0,
                price_native=620.0,
                quantity=1.0,
            )
        )

        mock_price_service = Mock()
        mock_price_service.get_historical_prices.return_value = _create_price_dict(
            ["VOO"], 630.0, date(2024, 1, 31), date(2024, 1, 31)
        )

        history_points = get_historical_performance(
            portfolio,
            mock_price_service,
            date(2024, 1, 31),
            date(2024, 1, 31),
            brokers=["IBKR", "Schwab"],
        )

        assert len(history_points) == 1
        hp = history_points[0]
        # Should include positions from IBKR and Schwab (3.0 * 630 = 1890.0)
        assert hp.asset_positions["VOO"] == 1890.0

    def test_get_historical_performance_with_broker_filter_none(self):
        """Test get_historical_performance with None broker filter (all brokers)."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="Schwab",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
            )
        )

        mock_price_service = Mock()
        mock_price_service.get_historical_prices.return_value = _create_price_dict(
            ["VOO"], 620.0, date(2024, 1, 31), date(2024, 1, 31)
        )

        history_points = get_historical_performance(
            portfolio, mock_price_service, date(2024, 1, 31), date(2024, 1, 31), brokers=None
        )

        assert len(history_points) == 1
        hp = history_points[0]
        # Should include all positions (3.0 * 620 = 1860.0)
        assert hp.asset_positions["VOO"] == 1860.0

    def test_get_historical_performance_composite_with_broker_filter(self):
        """Test get_historical_performance with broker filter for composite portfolio."""
        sub1 = SimplePortfolio(name="Sub1", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        sub1.add_trade(
            Trade(
                date=date(2024, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2", is_historical=True)
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="Schwab",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
            )
        )

        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        mock_price_service = Mock()
        mock_price_service.get_historical_prices.return_value = _create_price_dict(
            ["VOO"], 620.0, date(2024, 1, 31), date(2024, 1, 31)
        )

        history_points = get_historical_performance(
            composite, mock_price_service, date(2024, 1, 31), date(2024, 1, 31), brokers=["IBKR"]
        )

        assert len(history_points) == 1
        hp = history_points[0]
        # Should only include positions from IBKR (2.0 * 620 = 1240.0)
        assert hp.asset_positions["VOO"] == 1240.0
