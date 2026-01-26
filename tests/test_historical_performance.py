"""Tests for historical portfolio performance functionality."""

import pytest
from datetime import date, timedelta
from typing import Dict, List
from unittest.mock import Mock

from wpm.models import Asset, Trade
from wpm.portfolio import (
    CompositePortfolio,
    SimplePortfolio,
    _calculate_percentage_return_from_lots,
    get_historical_performance,
)


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


class TestPercentageReturn:
    """Tests for percentage return calculation in get_historical_performance."""

    def test_percentage_return_positive(self):
        """Test percentage return calculation for positive returns."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        # Buy 1 share at $400 on 2025-01-01
        portfolio.add_trade(
            Trade(
                date=date(2025, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            )
        )

        mock_price_service = Mock()
        # Price on 01-01: $400, 01-02: $410, 01-03: $420
        prices = {
            "VOO": {
                date(2025, 1, 1): 400.0,
                date(2025, 1, 2): 410.0,
                date(2025, 1, 3): 420.0,
            }
        }
        mock_price_service.get_historical_prices.return_value = prices

        history_points = get_historical_performance(
            portfolio, mock_price_service, date(2025, 1, 1), date(2025, 1, 3)
        )

        assert len(history_points) == 3

        # Day 1 (start_date): $400, unrealized P/L = 0, cost basis = 400, return = 0%
        hp1 = history_points[0]
        assert hp1.date == date(2025, 1, 1)
        assert hp1.total_market_value == 400.0
        assert hp1.percentage_return == 0.0

        # Day 2: $410, unrealized P/L = (410-400)*1 = 10, cost basis = 400, return = 10/400*100 = 2.5%
        hp2 = history_points[1]
        assert hp2.date == date(2025, 1, 2)
        assert hp2.total_market_value == 410.0
        assert abs(hp2.percentage_return - 2.5) < 0.01

        # Day 3: $420, unrealized P/L = (420-400)*1 = 20, cost basis = 400, return = 20/400*100 = 5.0%
        hp3 = history_points[2]
        assert hp3.date == date(2025, 1, 3)
        assert hp3.total_market_value == 420.0
        assert abs(hp3.percentage_return - 5.0) < 0.01

    def test_percentage_return_negative(self):
        """Test percentage return calculation for negative returns."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2025, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            )
        )

        mock_price_service = Mock()
        # Price on 01-01: $400, 01-02: $380
        prices = {
            "VOO": {
                date(2025, 1, 1): 400.0,
                date(2025, 1, 2): 380.0,
            }
        }
        mock_price_service.get_historical_prices.return_value = prices

        history_points = get_historical_performance(
            portfolio, mock_price_service, date(2025, 1, 1), date(2025, 1, 2)
        )

        assert len(history_points) == 2

        # Day 1: $400, unrealized P/L = 0, cost basis = 400, return = 0%
        hp1 = history_points[0]
        assert hp1.percentage_return == 0.0

        # Day 2: $380, unrealized P/L = (380-400)*1 = -20, cost basis = 400, return = -20/400*100 = -5.0%
        hp2 = history_points[1]
        assert hp2.total_market_value == 380.0
        assert abs(hp2.percentage_return - (-5.0)) < 0.01

    def test_percentage_return_zero_start_value(self):
        """Test percentage return calculation when portfolio starts with no positions."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        # Buy on 01-02, so 01-01 will have 0 value
        portfolio.add_trade(
            Trade(
                date=date(2025, 1, 2),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            )
        )

        mock_price_service = Mock()
        prices = {
            "VOO": {
                date(2025, 1, 1): 400.0,
                date(2025, 1, 2): 400.0,
                date(2025, 1, 3): 410.0,
            }
        }
        mock_price_service.get_historical_prices.return_value = prices

        history_points = get_historical_performance(
            portfolio, mock_price_service, date(2025, 1, 1), date(2025, 1, 3)
        )

        assert len(history_points) == 3

        # Day 1: $0 (no position yet), no lots, cost basis = 0, return = 0% (edge case)
        hp1 = history_points[0]
        assert hp1.total_market_value == 0.0
        assert hp1.percentage_return == 0.0

        # Day 2: $400 (first day with position), unrealized P/L = 0, cost basis = 400, return = 0%
        hp2 = history_points[1]
        assert hp2.total_market_value == 400.0
        assert hp2.percentage_return == 0.0

        # Day 3: $410, unrealized P/L = (410-400)*1 = 10, cost basis = 400, return = 10/400*100 = 2.5%
        hp3 = history_points[2]
        assert hp3.total_market_value == 410.0
        assert abs(hp3.percentage_return - 2.5) < 0.01

    def test_percentage_return_composite_portfolio(self):
        """Test percentage return calculation for composite portfolio."""
        sub1 = SimplePortfolio(name="Sub1", is_historical=True)
        asset1 = Asset(ticker="VOO", asset_type="ETF")
        sub1.add_trade(
            Trade(
                date=date(2025, 1, 1),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2", is_historical=True)
        asset2 = Asset(ticker="GOOG", asset_type="Stock")
        sub2.add_trade(
            Trade(
                date=date(2025, 1, 1),
                asset=asset2,
                action="Buy",
                broker="Schwab",
                currency="USD",
                price=100.0,
                price_native=100.0,
                quantity=1.0,
            )
        )

        composite = CompositePortfolio(name="Composite", is_historical=True)
        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        mock_price_service = Mock()
        # Start: VOO=$400, GOOG=$100, total=$500
        # Day 2: VOO=$410, GOOG=$105, total=$515
        prices = {
            "VOO": {
                date(2025, 1, 1): 400.0,
                date(2025, 1, 2): 410.0,
            },
            "GOOG": {
                date(2025, 1, 1): 100.0,
                date(2025, 1, 2): 105.0,
            },
        }
        mock_price_service.get_historical_prices.return_value = prices

        history_points = get_historical_performance(
            composite, mock_price_service, date(2025, 1, 1), date(2025, 1, 2)
        )

        assert len(history_points) == 2

        # Day 1: VOO=$400 (unrealized P/L=0, cost basis=400), GOOG=$100 (unrealized P/L=0, cost basis=100)
        # Total unrealized P/L = 0, total cost basis = 500, return = 0%
        hp1 = history_points[0]
        assert hp1.total_market_value == 500.0
        assert hp1.percentage_return == 0.0

        # Day 2: VOO=$410 (unrealized P/L=10, cost basis=400), GOOG=$105 (unrealized P/L=5, cost basis=100)
        # Total unrealized P/L = 15, total cost basis = 500, return = 15/500*100 = 3.0%
        hp2 = history_points[1]
        assert hp2.total_market_value == 515.0
        assert abs(hp2.percentage_return - 3.0) < 0.01

    def test_percentage_return_zero_return(self):
        """Test percentage return calculation when return is zero."""
        portfolio = SimplePortfolio(name="Test", is_historical=True)
        asset = Asset(ticker="VOO", asset_type="ETF")
        portfolio.add_trade(
            Trade(
                date=date(2025, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            )
        )

        mock_price_service = Mock()
        # Price stays at $400
        prices = {
            "VOO": {
                date(2025, 1, 1): 400.0,
                date(2025, 1, 2): 400.0,
            }
        }
        mock_price_service.get_historical_prices.return_value = prices

        history_points = get_historical_performance(
            portfolio, mock_price_service, date(2025, 1, 1), date(2025, 1, 2)
        )

        assert len(history_points) == 2

        # Day 1: $400, return = 0%
        hp1 = history_points[0]
        assert hp1.percentage_return == 0.0

        # Day 2: $400, return = 0%
        hp2 = history_points[1]
        assert hp2.percentage_return == 0.0


class TestCalculatePercentageReturnFromLots:
    """Tests for _calculate_percentage_return_from_lots helper function."""

    def test_portfolio_level_calculation(self):
        """Test portfolio-level calculation (ticker_filter=None)."""
        asset1 = Asset(ticker="VOO", asset_type="ETF")
        asset2 = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2025, 1, 1),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            ),
            Trade(
                date=date(2025, 1, 1),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=100.0,
                price_native=100.0,
                quantity=1.0,
            ),
        ]

        # Prices: VOO=$410, GOOG=$105
        prices_by_ticker = {"VOO": 410.0, "GOOG": 105.0}

        # VOO: unrealized P/L = (410-400)*1 = 10, cost basis = 400, return = 10/400 = 2.5%
        # GOOG: unrealized P/L = (105-100)*1 = 5, cost basis = 100, return = 5/100 = 5.0%
        # Total: unrealized P/L = 15, cost basis = 500, return = 15/500 = 3.0%
        percentage_return = _calculate_percentage_return_from_lots(
            trades, prices_by_ticker, ticker_filter=None
        )
        assert abs(percentage_return - 3.0) < 0.01

    def test_asset_level_calculation(self):
        """Test asset-level calculation (ticker_filter provided)."""
        asset1 = Asset(ticker="VOO", asset_type="ETF")
        asset2 = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2025, 1, 1),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            ),
            Trade(
                date=date(2025, 1, 1),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=100.0,
                price_native=100.0,
                quantity=1.0,
            ),
        ]

        # Prices: VOO=$410, GOOG=$105
        prices_by_ticker = {"VOO": 410.0, "GOOG": 105.0}

        # Filter by VOO only: unrealized P/L = (410-400)*1 = 10, cost basis = 400, return = 10/400 = 2.5%
        percentage_return = _calculate_percentage_return_from_lots(
            trades, prices_by_ticker, ticker_filter="VOO"
        )
        assert abs(percentage_return - 2.5) < 0.01

    def test_zero_cost_basis(self):
        """Test calculation when cost basis is zero."""
        trades = []  # No trades
        prices_by_ticker = {}

        percentage_return = _calculate_percentage_return_from_lots(
            trades, prices_by_ticker, ticker_filter=None
        )
        assert percentage_return == 0.0

    def test_missing_price(self):
        """Test calculation when price is missing (should skip that asset)."""
        asset1 = Asset(ticker="VOO", asset_type="ETF")
        asset2 = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2025, 1, 1),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            ),
            Trade(
                date=date(2025, 1, 1),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=100.0,
                price_native=100.0,
                quantity=1.0,
            ),
        ]

        # Only VOO price available, GOOG missing
        prices_by_ticker = {"VOO": 410.0}

        # Should only calculate for VOO: unrealized P/L = 10, cost basis = 400, return = 2.5%
        percentage_return = _calculate_percentage_return_from_lots(
            trades, prices_by_ticker, ticker_filter=None
        )
        assert abs(percentage_return - 2.5) < 0.01

    def test_negative_return(self):
        """Test calculation for negative returns."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        trades = [
            Trade(
                date=date(2025, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            )
        ]

        # Price dropped to $380
        prices_by_ticker = {"VOO": 380.0}

        # Unrealized P/L = (380-400)*1 = -20, cost basis = 400, return = -20/400 = -5.0%
        percentage_return = _calculate_percentage_return_from_lots(
            trades, prices_by_ticker, ticker_filter=None
        )
        assert abs(percentage_return - (-5.0)) < 0.01

    def test_multiple_lots_same_asset(self):
        """Test calculation with multiple lots of the same asset."""
        asset = Asset(ticker="VOO", asset_type="ETF")
        trades = [
            Trade(
                date=date(2025, 1, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=1.0,
            ),
            Trade(
                date=date(2025, 1, 2),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=410.0,
                price_native=410.0,
                quantity=1.0,
            ),
        ]

        # Current price: $420
        prices_by_ticker = {"VOO": 420.0}

        # Lot 1: unrealized P/L = (420-400)*1 = 20, cost basis = 400
        # Lot 2: unrealized P/L = (420-410)*1 = 10, cost basis = 410
        # Total: unrealized P/L = 30, cost basis = 810, return = 30/810 ≈ 3.70%
        percentage_return = _calculate_percentage_return_from_lots(
            trades, prices_by_ticker, ticker_filter=None
        )
        expected_return = (30.0 / 810.0) * 100
        assert abs(percentage_return - expected_return) < 0.01
