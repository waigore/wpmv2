"""Tests for portfolio allocation calculation methods."""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from wpm.models import Asset, Trade
from wpm.portfolio import (
    CompositePortfolio,
    SimplePortfolio,
    get_historical_allocations,
    get_historical_positions_with_allocations,
    get_positions_with_allocations,
)


class TestSimplePortfolioAllocations:
    """Tests for allocation methods in SimplePortfolio."""

    def test_get_asset_allocation_single_asset(self):
        """Test allocation for single asset portfolio (should be 100%)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)

        prices = {asset: 160.0}
        allocation = portfolio.get_asset_allocation(asset, prices)

        assert allocation == Decimal('100.00')

    def test_get_asset_allocation_multiple_assets(self):
        """Test allocation calculation for multiple assets."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        # GOOG: 10 shares @ $150 = $1500 cost, $160 current = $1600 market value
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        # AAPL: 5 shares @ $200 = $1000 cost, $220 current = $1100 market value
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0}
        # Total market value: $1600 + $1100 = $2700
        # GOOG allocation: $1600 / $2700 * 100 = 59.26%
        # AAPL allocation: $1100 / $2700 * 100 = 40.74%

        allocation1 = portfolio.get_asset_allocation(asset1, prices)
        allocation2 = portfolio.get_asset_allocation(asset2, prices)

        assert allocation1 == Decimal('59.26')
        assert allocation2 == Decimal('40.74')

    def test_get_asset_allocation_asset_not_in_portfolio(self):
        """Test allocation for asset not in portfolio returns 0.00."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        other_asset = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        prices = {asset: 160.0, other_asset: 200.0}
        allocation = portfolio.get_asset_allocation(other_asset, prices)

        assert allocation == Decimal('0.00')

    def test_get_asset_allocation_missing_price(self):
        """Test allocation for asset with missing price returns 0.00."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        prices = {}
        allocation = portfolio.get_asset_allocation(asset, prices)

        assert allocation == Decimal('0.00')

    def test_get_asset_allocation_zero_total_market_value(self):
        """Test allocation when total market value is zero."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        # All prices are None or 0, so total market value is 0
        prices = {asset: None}
        allocation = portfolio.get_asset_allocation(asset, prices)

        assert allocation == Decimal('0.00')

    def test_get_all_allocations_single_asset(self):
        """Test all allocations for single asset portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        prices = {asset: 160.0}
        allocations = portfolio.get_all_allocations(prices)

        assert len(allocations) == 1
        assert allocations[asset] == Decimal('100.00')

    def test_get_all_allocations_multiple_assets_sums_to_100(self):
        """Test that all allocations sum to 100.00."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0}
        allocations = portfolio.get_all_allocations(prices)

        total = sum(allocations.values())
        assert total == Decimal('100.00')

    def test_get_all_allocations_empty_portfolio(self):
        """Test all allocations for empty portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        prices = {}
        allocations = portfolio.get_all_allocations(prices)

        assert allocations == {}

    def test_get_all_allocations_decimal_precision(self):
        """Test that allocations use Decimal precision correctly."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        # Create scenario where allocations don't divide evenly
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=100.0,
                price_native=100.0,
                quantity=1.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=100.0,
                price_native=100.0,
                quantity=3.0,
            )
        )

        prices = {asset1: 100.0, asset2: 100.0}
        # Total: $400, so each should be 25% and 75%
        allocations = portfolio.get_all_allocations(prices)

        assert allocations[asset1] == Decimal('25.00')
        assert allocations[asset2] == Decimal('75.00')
        assert sum(allocations.values()) == Decimal('100.00')


class TestCompositePortfolioAllocations:
    """Tests for allocation methods in CompositePortfolio."""

    def test_get_asset_allocation_composite(self):
        """Test allocation calculation for composite portfolio."""
        # Create sub-portfolios
        sub1 = SimplePortfolio(name="Sub1")
        sub2 = SimplePortfolio(name="Sub2")

        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        # Sub1: GOOG 10 shares
        sub1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        # Sub2: AAPL 5 shares
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        prices = {asset1: 160.0, asset2: 220.0}
        # Total: $1600 + $1100 = $2700
        allocation1 = composite.get_asset_allocation(asset1, prices)
        allocation2 = composite.get_asset_allocation(asset2, prices)

        assert allocation1 == Decimal('59.26')
        assert allocation2 == Decimal('40.74')

    def test_get_all_allocations_composite_sums_to_100(self):
        """Test that composite portfolio allocations sum to 100.00."""
        sub1 = SimplePortfolio(name="Sub1")
        sub2 = SimplePortfolio(name="Sub2")

        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        sub1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        prices = {asset1: 160.0, asset2: 220.0}
        allocations = composite.get_all_allocations(prices)

        total = sum(allocations.values())
        assert total == Decimal('100.00')


class TestPositionsWithAllocations:
    """Tests for get_positions_with_allocations utility function."""

    def test_get_positions_with_allocations_simple(self):
        """Test combining positions and allocations for simple portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0}
        result = get_positions_with_allocations(portfolio, prices)

        assert len(result) == 2
        assert asset1 in result
        assert asset2 in result

        position1, allocation1 = result[asset1]
        assert position1.quantity == Decimal('10.0')
        assert allocation1 == Decimal('59.26')

        position2, allocation2 = result[asset2]
        assert position2.quantity == Decimal('5.0')
        assert allocation2 == Decimal('40.74')

    def test_get_positions_with_allocations_empty(self):
        """Test positions with allocations for empty portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        prices = {}
        result = get_positions_with_allocations(portfolio, prices)

        assert result == {}


class TestHistoricalAllocations:
    """Tests for historical allocation functions."""

    def _create_price_dict(
        self, tickers: list, price_value: float, start_date: date, end_date: date
    ) -> dict:
        """Helper to create price dictionary."""
        result = {}
        current = start_date
        while current <= end_date:
            for ticker in tickers:
                if ticker not in result:
                    result[ticker] = {}
                result[ticker][current] = price_value
            current += timedelta(days=1)
        return result

    @patch('wpm.portfolio.get_historical_performance')
    def test_get_historical_allocations(self, mock_get_perf):
        """Test historical allocations calculation."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        from wpm.models import PortfolioHistoryPoint

        # Mock historical performance
        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 17)
        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),
                total_market_value=1500.0,  # Only GOOG
                asset_positions={"GOOG": 1500.0, "AAPL": 0.0},
                prices={"GOOG": 150.0},
                quantities={"GOOG": 10.0, "AAPL": 0.0},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 16),
                total_market_value=2500.0,  # GOOG + AAPL
                asset_positions={"GOOG": 1500.0, "AAPL": 1000.0},
                prices={"GOOG": 150.0, "AAPL": 200.0},
                quantities={"GOOG": 10.0, "AAPL": 5.0},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 17),
                total_market_value=2700.0,  # GOOG + AAPL with new prices
                asset_positions={"GOOG": 1600.0, "AAPL": 1100.0},
                prices={"GOOG": 160.0, "AAPL": 220.0},
                quantities={"GOOG": 10.0, "AAPL": 5.0},
                percentage_return=0.0,
            ),
        ]
        mock_get_perf.return_value = history_points

        price_service = MagicMock()
        allocations_list = get_historical_allocations(
            portfolio, price_service, start_date, end_date
        )

        assert len(allocations_list) == 3

        # Day 1: Only GOOG, should be 100%
        assert allocations_list[0][asset1] == Decimal('100.00')
        assert allocations_list[0][asset2] == Decimal('0.00')

        # Day 2: GOOG 60%, AAPL 40%
        assert allocations_list[1][asset1] == Decimal('60.00')
        assert allocations_list[1][asset2] == Decimal('40.00')

        # Day 3: GOOG 59.26%, AAPL 40.74%
        assert allocations_list[2][asset1] == Decimal('59.26')
        assert allocations_list[2][asset2] == Decimal('40.74')

        # Verify allocations sum to 100% for each day
        for allocations in allocations_list:
            total = sum(allocations.values())
            assert total == Decimal('100.00')

    @patch('wpm.portfolio.get_historical_performance')
    @patch('wpm.portfolio.get_historical_allocations')
    def test_get_historical_positions_with_allocations(self, mock_get_alloc, mock_get_perf):
        """Test combining historical positions and allocations."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        from wpm.models import PortfolioHistoryPoint

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 16)

        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),
                total_market_value=1500.0,
                asset_positions={"GOOG": 1500.0, "AAPL": 0.0},
                prices={"GOOG": 150.0},
                quantities={"GOOG": 10.0, "AAPL": 0.0},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 16),
                total_market_value=1500.0,
                asset_positions={"GOOG": 1600.0, "AAPL": 0.0},
                prices={"GOOG": 160.0},
                quantities={"GOOG": 10.0, "AAPL": 0.0},
                percentage_return=0.0,
            ),
        ]
        mock_get_perf.return_value = history_points

        allocations_list = [
            {asset1: Decimal('100.00'), asset2: Decimal('0.00')},
            {asset1: Decimal('100.00'), asset2: Decimal('0.00')},
        ]
        mock_get_alloc.return_value = allocations_list

        price_service = MagicMock()
        result = get_historical_positions_with_allocations(
            portfolio, price_service, start_date, end_date
        )

        assert len(result) == 2
        assert asset1 in result[0]
        # asset2 has 0.0 position value, so it's not included in result
        # (only assets with non-zero position values are included)

        position_value, allocation = result[0][asset1]
        assert position_value == 1500.0
        assert allocation == Decimal('100.00')


class TestGetAllAllocationsFiltering:
    """Tests for get_all_allocations filtering functionality."""

    def test_get_all_allocations_backward_compatible(self):
        """Test that get_all_allocations works without filters (backward compatible)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0}
        allocations = portfolio.get_all_allocations(prices)

        # Should work exactly as before - all assets included
        assert len(allocations) == 2
        assert asset1 in allocations
        assert asset2 in allocations
        total = sum(allocations.values())
        assert total == Decimal('100.00')

    def test_get_all_allocations_filter_by_asset_types(self):
        """Test filtering by asset types only."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="BTC-USD", asset_type="Crypto")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.1,
            )
        )

        prices = {asset1: 160.0, asset2: 55000.0}
        allocations = portfolio.get_all_allocations(prices, asset_types=["Stock"])

        # Only Stock assets should be included
        assert len(allocations) == 1
        assert asset1 in allocations
        assert asset2 not in allocations
        # Allocation should sum to 100% of filtered assets
        assert allocations[asset1] == Decimal('100.00')

    def test_get_all_allocations_filter_by_tickers(self):
        """Test filtering by tickers only."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0}
        allocations = portfolio.get_all_allocations(prices, asset_tickers=["GOOG"])

        # Only GOOG should be included
        assert len(allocations) == 1
        assert asset1 in allocations
        assert asset2 not in allocations
        assert allocations[asset1] == Decimal('100.00')

    def test_get_all_allocations_filter_by_both_or(self):
        """Test filtering by both asset_types and tickers with OR logic."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        asset3 = Asset(ticker="BTC-USD", asset_type="Crypto")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 17),
                asset=asset3,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.1,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0, asset3: 55000.0}
        # Filter: Crypto OR GOOG (should include asset3 and asset1, but not asset2)
        allocations = portfolio.get_all_allocations(
            prices, asset_types=["Crypto"], asset_tickers=["GOOG"]
        )

        # Should include Crypto (asset3) OR GOOG (asset1) - OR logic
        assert len(allocations) == 2
        assert asset1 in allocations  # Matches ticker
        assert asset2 not in allocations  # Doesn't match either
        assert asset3 in allocations  # Matches asset_type
        # Allocations should sum to 100% of filtered assets
        total = sum(allocations.values())
        assert total == Decimal('100.00')

    def test_get_all_allocations_filter_empty_result(self):
        """Test filtering when all assets are filtered out."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        prices = {asset1: 160.0}
        allocations = portfolio.get_all_allocations(prices, asset_types=["Crypto"])

        # No Crypto assets, so should return empty dict
        assert allocations == {}

    def test_get_all_allocations_filter_asset_type_normalization(self):
        """Test that asset type normalization works in filters."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        prices = {asset1: 160.0}
        # Use lowercase "stock" - should be normalized
        allocations = portfolio.get_all_allocations(prices, asset_types=["stock"])

        assert len(allocations) == 1
        assert asset1 in allocations


class TestPositionsWithAllocationsFiltering:
    """Tests for get_positions_with_allocations filtering functionality."""

    def test_get_positions_with_allocations_filter_by_asset_types(self):
        """Test filtering by asset types only."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="BTC-USD", asset_type="Crypto")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.1,
            )
        )

        prices = {asset1: 160.0, asset2: 55000.0}
        result = get_positions_with_allocations(portfolio, prices, asset_types=["Stock"])

        assert len(result) == 1
        assert asset1 in result
        assert asset2 not in result
        position, allocation = result[asset1]
        assert position.quantity == Decimal('10.0')
        assert allocation == Decimal('100.00')  # Only one asset, so 100%

    def test_get_positions_with_allocations_filter_by_tickers(self):
        """Test filtering by tickers only."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0}
        result = get_positions_with_allocations(portfolio, prices, asset_tickers=["GOOG"])

        assert len(result) == 1
        assert asset1 in result
        assert asset2 not in result
        assert result[asset1][1] == Decimal('100.00')

    def test_get_positions_with_allocations_filter_by_both_or(self):
        """Test filtering by both asset_types and tickers with OR logic."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        asset3 = Asset(ticker="BTC-USD", asset_type="Crypto")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 17),
                asset=asset3,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.1,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0, asset3: 55000.0}
        # Filter: Crypto OR GOOG
        result = get_positions_with_allocations(
            portfolio, prices, asset_types=["Crypto"], asset_tickers=["GOOG"]
        )

        # Should include Crypto (asset3) OR GOOG (asset1)
        assert len(result) == 2
        assert asset1 in result
        assert asset2 not in result
        assert asset3 in result
        # Allocations should sum to 100% of filtered assets
        total_allocation = sum(allocation for _, allocation in result.values())
        assert total_allocation == Decimal('100.00')

    def test_get_positions_with_allocations_filter_none(self):
        """Test that no filters works as before (backward compatible)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=200.0,
                price_native=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 220.0}
        result = get_positions_with_allocations(portfolio, prices)

        # Should work exactly as before
        assert len(result) == 2
        assert asset1 in result
        assert asset2 in result


class TestHistoricalPositionsWithAllocationsFiltering:
    """Tests for get_historical_positions_with_allocations filtering functionality."""

    @patch('wpm.portfolio.get_historical_performance')
    def test_get_historical_positions_with_allocations_filter_by_asset_types(
        self, mock_get_perf
    ):
        """Test filtering by asset types."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="BTC-USD", asset_type="Crypto")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        from wpm.models import PortfolioHistoryPoint

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 16)

        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),
                total_market_value=1500.0,
                asset_positions={"GOOG": 1500.0, "BTC-USD": 5000.0},
                prices={"GOOG": 150.0, "BTC-USD": 50000.0},
                quantities={"GOOG": 10.0, "BTC-USD": 0.1},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 16),
                total_market_value=1600.0,
                asset_positions={"GOOG": 1600.0, "BTC-USD": 5500.0},
                prices={"GOOG": 160.0, "BTC-USD": 55000.0},
                quantities={"GOOG": 10.0, "BTC-USD": 0.1},
                percentage_return=0.0,
            ),
        ]
        mock_get_perf.return_value = history_points

        price_service = MagicMock()
        result = get_historical_positions_with_allocations(
            portfolio, price_service, start_date, end_date, asset_types=["Stock"]
        )

        assert len(result) == 2
        # Only Stock assets should be included
        assert asset1 in result[0]
        assert asset2 not in result[0]
        # Allocations should sum to 100% of filtered assets for each date
        for day_result in result:
            total_allocation = sum(allocation for _, allocation in day_result.values())
            assert total_allocation == Decimal('100.00')

    @patch('wpm.portfolio.get_historical_performance')
    def test_get_historical_positions_with_allocations_filter_by_tickers(
        self, mock_get_perf
    ):
        """Test filtering by tickers."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        from wpm.models import PortfolioHistoryPoint

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 16)

        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),
                total_market_value=1500.0,
                asset_positions={"GOOG": 1500.0, "AAPL": 1000.0},
                prices={"GOOG": 150.0, "AAPL": 200.0},
                quantities={"GOOG": 10.0, "AAPL": 5.0},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 16),
                total_market_value=2700.0,
                asset_positions={"GOOG": 1600.0, "AAPL": 1100.0},
                prices={"GOOG": 160.0, "AAPL": 220.0},
                quantities={"GOOG": 10.0, "AAPL": 5.0},
                percentage_return=0.0,
            ),
        ]
        mock_get_perf.return_value = history_points

        price_service = MagicMock()
        result = get_historical_positions_with_allocations(
            portfolio, price_service, start_date, end_date, asset_tickers=["GOOG"]
        )

        assert len(result) == 2
        # Only GOOG should be included
        assert asset1 in result[0]
        assert asset2 not in result[0]
        # Allocations should sum to 100% for each date
        for day_result in result:
            total_allocation = sum(allocation for _, allocation in day_result.values())
            assert total_allocation == Decimal('100.00')

    @patch('wpm.portfolio.get_historical_performance')
    def test_get_historical_positions_with_allocations_filter_by_both_or(
        self, mock_get_perf
    ):
        """Test filtering by both asset_types and tickers with OR logic."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        asset3 = Asset(ticker="BTC-USD", asset_type="Crypto")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        # Add BTC-USD trade so it's in portfolio assets (even if sold later)
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset3,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.1,
            )
        )

        from wpm.models import PortfolioHistoryPoint

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 16)

        history_points = [
            PortfolioHistoryPoint(
                date=date(2024, 1, 15),
                total_market_value=1500.0,
                asset_positions={"GOOG": 1500.0, "AAPL": 1000.0, "BTC-USD": 5000.0},
                prices={"GOOG": 150.0, "AAPL": 200.0, "BTC-USD": 50000.0},
                quantities={"GOOG": 10.0, "AAPL": 5.0, "BTC-USD": 0.1},
                percentage_return=0.0,
            ),
            PortfolioHistoryPoint(
                date=date(2024, 1, 16),
                total_market_value=2700.0,
                asset_positions={"GOOG": 1600.0, "AAPL": 1100.0, "BTC-USD": 5500.0},
                prices={"GOOG": 160.0, "AAPL": 220.0, "BTC-USD": 55000.0},
                quantities={"GOOG": 10.0, "AAPL": 5.0, "BTC-USD": 0.1},
                percentage_return=0.0,
            ),
        ]
        mock_get_perf.return_value = history_points

        price_service = MagicMock()
        # Filter: Crypto OR GOOG
        result = get_historical_positions_with_allocations(
            portfolio,
            price_service,
            start_date,
            end_date,
            asset_types=["Crypto"],
            asset_tickers=["GOOG"],
        )

        assert len(result) == 2
        # Should include Crypto (asset3) OR GOOG (asset1), but not AAPL (asset2)
        assert asset1 in result[0]  # Matches ticker
        assert asset2 not in result[0]  # Doesn't match either
        assert asset3 in result[0]  # Matches asset_type
        # Allocations should sum to 100% of filtered assets for each date
        for day_result in result:
            total_allocation = sum(allocation for _, allocation in day_result.values())
            assert total_allocation == Decimal('100.00')
