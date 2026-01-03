"""Tests for basic portfolio operations."""

import pytest
from datetime import date
from decimal import Decimal

from wpm.models import Asset, PortfolioError, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio


class TestSimplePortfolio:
    """Tests for SimplePortfolio class."""

    def test_create_portfolio(self):
        """Test creating a simple portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        assert portfolio.name == "Test Portfolio"

    def test_add_trade(self):
        """Test adding a trade to portfolio."""
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
            currency="USD",
            price=150.0,
            price_native=150.0,
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
            currency="USD",
            price=150.0,
            price_native=150.0,
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
                currency="USD",
                price=150.0,
                price_native=150.0,
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
                currency="USD",
                price=200.0,
                price_native=200.0,
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
                currency="USD",
                price=150.0,
                price_native=150.0,
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
                currency="USD",
                price=160.0,
                price_native=160.0,
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
                currency="USD",
                price=150.0,
                price_native=150.0,
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
                currency="USD",
                price=200.0,
                price_native=200.0,
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
            currency="USD",
            price=150.0,
            price_native=150.0,
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
            currency="USD",
            price=200.0,
            price_native=200.0,
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
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        inner.add_sub_portfolio(sub)
        outer.add_sub_portfolio(inner)

        positions = outer.get_positions()
        assert asset in positions
        assert positions[asset].quantity == 10.0

