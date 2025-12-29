"""Tests for portfolio implementations."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock, MagicMock

from wpm.models import Asset, PortfolioError, Trade
from wpm.portfolio import CompositePortfolio, fetch_price_map, SimplePortfolio


class TestSimplePortfolio:
    """Tests for SimplePortfolio class."""

    def test_create_portfolio(self):
        """Test creating a simple portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        assert portfolio.name == "Test Portfolio"
        assert portfolio.cost_basis_method == "fifo"

    def test_create_portfolio_with_method(self):
        """Test creating portfolio with specific cost basis method."""
        portfolio = SimplePortfolio(name="Test", cost_basis_method="average")
        assert portfolio.cost_basis_method == "average"

    def test_invalid_cost_basis_method(self):
        """Test portfolio creation with invalid cost basis method."""
        with pytest.raises(PortfolioError):
            SimplePortfolio(name="Test", cost_basis_method="invalid")

    def test_add_trade(self):
        """Test adding a trade to portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )

        portfolio.add_trade(trade)
        trades = portfolio.get_all_trades()
        assert len(trades) == 1
        assert trades[0] == trade

    def test_add_invalid_trade(self):
        """Test adding invalid trade raises error."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        with pytest.raises(PortfolioError):
            portfolio.add_trade("not a trade")

    def test_get_positions_empty(self):
        """Test getting positions from empty portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        positions = portfolio.get_positions()
        assert positions == {}

    def test_get_positions_single_buy(self):
        """Test getting positions with a single buy."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )

        portfolio.add_trade(trade)
        positions = portfolio.get_positions()

        assert asset in positions
        position = positions[asset]
        assert position.quantity == Decimal('10.0')
        assert position.cost_basis == 1500.0

    def test_get_total_cost_basis(self):
        """Test getting total cost basis."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        total = portfolio.get_total_cost_basis()
        assert total == 2500.0

    def test_get_position_for_asset(self):
        """Test getting position for specific asset."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )

        portfolio.add_trade(trade)
        position = portfolio.get_position(asset)

        assert position is not None
        assert position.quantity == Decimal('10.0')

    def test_get_position_for_nonexistent_asset(self):
        """Test getting position for asset not in portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        position = portfolio.get_position(asset)
        assert position is None

    def test_average_cost_method(self):
        """Test portfolio with average cost basis method."""
        portfolio = SimplePortfolio(name="Test", cost_basis_method="average")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            )
        )

        positions = portfolio.get_positions()
        position = positions[asset]
        assert position.cost_basis_method == "average"
        assert position.cost_basis == 2300.0


class TestCompositePortfolio:
    """Tests for CompositePortfolio class."""

    def test_create_composite_portfolio(self):
        """Test creating a composite portfolio."""
        portfolio = CompositePortfolio(name="Composite")
        assert portfolio.name == "Composite"

    def test_add_sub_portfolio(self):
        """Test adding a sub-portfolio."""
        composite = CompositePortfolio(name="Composite")
        sub_portfolio = SimplePortfolio(name="Sub")

        composite.add_sub_portfolio(sub_portfolio)
        positions = composite.get_positions()
        assert positions == {}  # Empty sub-portfolio

    def test_add_duplicate_sub_portfolio(self):
        """Test adding duplicate sub-portfolio raises error."""
        composite = CompositePortfolio(name="Composite")
        sub_portfolio = SimplePortfolio(name="Sub")

        composite.add_sub_portfolio(sub_portfolio)

        with pytest.raises(PortfolioError):
            composite.add_sub_portfolio(sub_portfolio)

    def test_add_invalid_sub_portfolio(self):
        """Test adding invalid sub-portfolio raises error."""
        composite = CompositePortfolio(name="Composite")
        with pytest.raises(PortfolioError):
            composite.add_sub_portfolio("not a portfolio")

    def test_get_positions_from_sub_portfolios(self):
        """Test aggregating positions from sub-portfolios."""
        composite = CompositePortfolio(name="Composite")

        sub1 = SimplePortfolio(name="Sub1")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        sub1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        positions = composite.get_positions()
        assert len(positions) == 2
        assert positions[asset1].quantity == Decimal('10.0')
        assert positions[asset2].quantity == Decimal('5.0')

    def test_aggregate_same_asset_from_multiple_sub_portfolios(self):
        """Test aggregating same asset from multiple sub-portfolios."""
        composite = CompositePortfolio(name="Composite")

        sub1 = SimplePortfolio(name="Sub1")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        sub1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2")
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=160.0,
                quantity=5.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        positions = composite.get_positions()
        assert len(positions) == 1
        position = positions[asset]
        assert position.quantity == Decimal('15.0')
        assert position.cost_basis == 2300.0  # 10*150 + 5*160

    def test_get_total_cost_basis_composite(self):
        """Test getting total cost basis from composite portfolio."""
        composite = CompositePortfolio(name="Composite")

        sub1 = SimplePortfolio(name="Sub1")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        sub1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        total = composite.get_total_cost_basis()
        assert total == 2500.0

    def test_get_all_trades_from_composite(self):
        """Test getting all trades from composite portfolio."""
        composite = CompositePortfolio(name="Composite")

        sub1 = SimplePortfolio(name="Sub1")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset1,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        sub1.add_trade(trade1)

        sub2 = SimplePortfolio(name="Sub2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        trade2 = Trade(
            date=date(2024, 1, 16),
            asset=asset2,
            action="Buy",
            broker="IBKR",
            price=200.0,
            quantity=5.0,
        )
        sub2.add_trade(trade2)

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        all_trades = composite.get_all_trades()
        assert len(all_trades) == 2
        assert trade1 in all_trades
        assert trade2 in all_trades

    def test_nested_composite_portfolios(self):
        """Test nested composite portfolios."""
        outer = CompositePortfolio(name="Outer")
        inner = CompositePortfolio(name="Inner")

        sub = SimplePortfolio(name="Sub")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        sub.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        inner.add_sub_portfolio(sub)
        outer.add_sub_portfolio(inner)

        positions = outer.get_positions()
        assert asset in positions
        assert positions[asset].quantity == 10.0


class TestTotalMarketValue:
    """Tests for get_total_market_value method."""

    def test_total_market_value_simple_portfolio(self):
        """Test total market value for simple portfolio with multiple assets."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 210.0}
        market_value = portfolio.get_total_market_value(prices)

        # 10 * 160 + 5 * 210 = 1600 + 1050 = 2650
        assert market_value == 2650.0

    def test_total_market_value_simple_portfolio_missing_price(self):
        """Test total market value with missing prices (should exclude those assets)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        # Only price for asset1
        prices = {asset1: 160.0}
        market_value = portfolio.get_total_market_value(prices)

        # Only asset1 should be included: 10 * 160 = 1600
        assert market_value == 1600.0

    def test_total_market_value_simple_portfolio_none_price(self):
        """Test total market value with None prices (should exclude those assets)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        # asset2 has None price
        prices = {asset1: 160.0, asset2: None}
        market_value = portfolio.get_total_market_value(prices)

        # Only asset1 should be included: 10 * 160 = 1600
        assert market_value == 1600.0

    def test_total_market_value_composite_portfolio(self):
        """Test total market value for composite portfolio (sums from sub-portfolios)."""
        composite = CompositePortfolio(name="Composite")

        sub1 = SimplePortfolio(name="Sub1")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        sub1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        prices = {asset1: 160.0, asset2: 210.0}
        market_value = composite.get_total_market_value(prices)

        # Sum of sub-portfolios: 10 * 160 + 5 * 210 = 2650
        assert market_value == 2650.0

    def test_total_market_value_nested_composite(self):
        """Test total market value with nested composite portfolios."""
        outer = CompositePortfolio(name="Outer")
        inner = CompositePortfolio(name="Inner")

        sub = SimplePortfolio(name="Sub")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        sub.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        inner.add_sub_portfolio(sub)
        outer.add_sub_portfolio(inner)

        prices = {asset: 160.0}
        market_value = outer.get_total_market_value(prices)

        # Should recursively sum: 10 * 160 = 1600
        assert market_value == 1600.0

    def test_total_market_value_empty_portfolio(self):
        """Test total market value for empty portfolio."""
        portfolio = SimplePortfolio(name="Empty")
        prices = {}
        market_value = portfolio.get_total_market_value(prices)
        assert market_value == 0.0


class TestTotalUnrealizedPnl:
    """Tests for get_total_unrealized_pnl method."""

    def test_total_unrealized_pnl_simple_portfolio(self):
        """Test total unrealized P/L for simple portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        prices = {asset1: 160.0, asset2: 210.0}
        unrealized_pnl = portfolio.get_total_unrealized_pnl(prices)

        # Market value: 10 * 160 + 5 * 210 = 2650
        # Cost basis: 10 * 150 + 5 * 200 = 2500
        # P/L: 2650 - 2500 = 150
        assert unrealized_pnl == 150.0

    def test_total_unrealized_pnl_simple_portfolio_loss(self):
        """Test total unrealized P/L showing a loss."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        prices = {asset: 140.0}
        unrealized_pnl = portfolio.get_total_unrealized_pnl(prices)

        # Market value: 10 * 140 = 1400
        # Cost basis: 10 * 150 = 1500
        # P/L: 1400 - 1500 = -100
        assert unrealized_pnl == -100.0

    def test_total_unrealized_pnl_composite_portfolio(self):
        """Test total unrealized P/L for composite portfolio."""
        composite = CompositePortfolio(name="Composite")

        sub1 = SimplePortfolio(name="Sub1")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        sub1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        prices = {asset1: 160.0, asset2: 210.0}
        unrealized_pnl = composite.get_total_unrealized_pnl(prices)

        # Sum of sub-portfolio P/L:
        # Sub1: (10 * 160) - (10 * 150) = 100
        # Sub2: (5 * 210) - (5 * 200) = 50
        # Total: 100 + 50 = 150
        assert unrealized_pnl == 150.0

    def test_total_unrealized_pnl_nested_composite(self):
        """Test total unrealized P/L with nested composite portfolios."""
        outer = CompositePortfolio(name="Outer")
        inner = CompositePortfolio(name="Inner")

        sub = SimplePortfolio(name="Sub")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        sub.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )

        inner.add_sub_portfolio(sub)
        outer.add_sub_portfolio(inner)

        prices = {asset: 160.0}
        unrealized_pnl = outer.get_total_unrealized_pnl(prices)

        # Should recursively sum: (10 * 160) - (10 * 150) = 100
        assert unrealized_pnl == 100.0

    def test_total_unrealized_pnl_missing_price(self):
        """Test total unrealized P/L with missing prices."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )

        # Only price for asset1
        prices = {asset1: 160.0}
        unrealized_pnl = portfolio.get_total_unrealized_pnl(prices)

        # Market value: 10 * 160 = 1600 (only asset1)
        # Cost basis: 10 * 150 + 5 * 200 = 2500 (all assets)
        # P/L: 1600 - 2500 = -900
        assert unrealized_pnl == -900.0

    def test_total_unrealized_pnl_empty_portfolio(self):
        """Test total unrealized P/L for empty portfolio."""
        portfolio = SimplePortfolio(name="Empty")
        prices = {}
        unrealized_pnl = portfolio.get_total_unrealized_pnl(prices)
        # Market value: 0, Cost basis: 0, P/L: 0
        assert unrealized_pnl == 0.0


class TestFetchPriceMap:
    """Tests for fetch_price_map helper function."""

    def test_fetch_price_map_empty_portfolio(self):
        """Test fetch_price_map with empty portfolio."""
        portfolio = SimplePortfolio(name="Empty")
        price_service = Mock()
        
        price_map = fetch_price_map(portfolio, price_service)
        
        assert price_map == {}
        price_service.get_prices.assert_not_called()

    def test_fetch_price_map_single_asset_type(self):
        """Test fetch_price_map with single asset type (Stock)."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)
        
        price_service = Mock()
        price_service.get_prices.return_value = {"GOOG": 160.0}
        
        price_map = fetch_price_map(portfolio, price_service)
        
        assert len(price_map) == 1
        assert price_map[asset] == 160.0
        price_service.get_prices.assert_called_once_with(["GOOG"], "Stock")

    def test_fetch_price_map_multiple_asset_types(self):
        """Test fetch_price_map with multiple asset types (Stock, Crypto)."""
        portfolio = SimplePortfolio(name="Test")
        
        stock_asset = Asset(ticker="GOOG", asset_type="Stock")
        stock_trade = Trade(
            date=date(2024, 1, 15),
            asset=stock_asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(stock_trade)
        
        crypto_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        crypto_trade = Trade(
            date=date(2024, 1, 15),
            asset=crypto_asset,
            action="Buy",
            broker="IBKR",
            price=50000.0,
            quantity=0.5,
        )
        portfolio.add_trade(crypto_trade)
        
        price_service = Mock()
        price_service.get_prices.side_effect = [
            {"GOOG": 160.0},  # First call for Stock
            {"BTC-USD": 51000.0},  # Second call for Crypto
        ]
        
        price_map = fetch_price_map(portfolio, price_service)
        
        assert len(price_map) == 2
        assert price_map[stock_asset] == 160.0
        assert price_map[crypto_asset] == 51000.0
        assert price_service.get_prices.call_count == 2
        price_service.get_prices.assert_any_call(["GOOG"], "Stock")
        price_service.get_prices.assert_any_call(["BTC-USD"], "Crypto")

    def test_fetch_price_map_partial_failure(self):
        """Test fetch_price_map with partial price retrieval failures."""
        portfolio = SimplePortfolio(name="Test")
        
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset1,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade1)
        
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        trade2 = Trade(
            date=date(2024, 1, 16),
            asset=asset2,
            action="Buy",
            broker="IBKR",
            price=200.0,
            quantity=5.0,
        )
        portfolio.add_trade(trade2)
        
        price_service = Mock()
        # First asset type succeeds, second fails
        price_service.get_prices.side_effect = [
            {"GOOG": 160.0, "AAPL": 210.0},  # Both succeed
            Exception("API error"),  # This shouldn't happen with current grouping
        ]
        
        price_map = fetch_price_map(portfolio, price_service)
        
        # Both assets are in the same asset type, so both should be fetched together
        assert len(price_map) == 2
        assert price_map[asset1] == 160.0
        assert price_map[asset2] == 210.0

    def test_fetch_price_map_complete_failure(self):
        """Test fetch_price_map when all price retrieval fails."""
        portfolio = SimplePortfolio(name="Test")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)
        
        price_service = Mock()
        price_service.get_prices.side_effect = Exception("API error")
        
        price_map = fetch_price_map(portfolio, price_service)
        
        assert len(price_map) == 1
        assert price_map[asset] is None

    def test_fetch_price_map_mixed_success_failure(self):
        """Test fetch_price_map with mixed success and failure across asset types."""
        portfolio = SimplePortfolio(name="Test")
        
        stock_asset = Asset(ticker="GOOG", asset_type="Stock")
        stock_trade = Trade(
            date=date(2024, 1, 15),
            asset=stock_asset,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(stock_trade)
        
        crypto_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        crypto_trade = Trade(
            date=date(2024, 1, 15),
            asset=crypto_asset,
            action="Buy",
            broker="IBKR",
            price=50000.0,
            quantity=0.5,
        )
        portfolio.add_trade(crypto_trade)
        
        price_service = Mock()
        price_service.get_prices.side_effect = [
            {"GOOG": 160.0},  # Stock succeeds
            Exception("Crypto API error"),  # Crypto fails
        ]
        
        price_map = fetch_price_map(portfolio, price_service)
        
        assert len(price_map) == 2
        assert price_map[stock_asset] == 160.0
        assert price_map[crypto_asset] is None

    def test_fetch_price_map_composite_portfolio(self):
        """Test fetch_price_map with CompositePortfolio."""
        composite = CompositePortfolio(name="Composite")
        
        sub1 = SimplePortfolio(name="Sub1")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        sub1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                price=150.0,
                quantity=10.0,
            )
        )
        
        sub2 = SimplePortfolio(name="Sub2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                price=200.0,
                quantity=5.0,
            )
        )
        
        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)
        
        price_service = Mock()
        price_service.get_prices.return_value = {"GOOG": 160.0, "AAPL": 210.0}
        
        price_map = fetch_price_map(composite, price_service)
        
        assert len(price_map) == 2
        assert price_map[asset1] == 160.0
        assert price_map[asset2] == 210.0
        price_service.get_prices.assert_called_once_with(["GOOG", "AAPL"], "Stock")

    def test_fetch_price_map_missing_ticker_in_response(self):
        """Test fetch_price_map when a ticker is missing from price service response."""
        portfolio = SimplePortfolio(name="Test")
        
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset1,
            action="Buy",
            broker="IBKR",
            price=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade1)
        
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        trade2 = Trade(
            date=date(2024, 1, 16),
            asset=asset2,
            action="Buy",
            broker="IBKR",
            price=200.0,
            quantity=5.0,
        )
        portfolio.add_trade(trade2)
        
        price_service = Mock()
        # Only return price for one ticker
        price_service.get_prices.return_value = {"GOOG": 160.0}
        
        price_map = fetch_price_map(portfolio, price_service)
        
        assert len(price_map) == 2
        assert price_map[asset1] == 160.0
        assert price_map[asset2] is None  # Missing ticker results in None

