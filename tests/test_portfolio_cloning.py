"""Tests for portfolio cloning functionality."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from wpm.models import Asset, PortfolioError, Trade
from wpm.portfolio import (
    CompositePortfolio,
    SimplePortfolio,
    generate_historical_snapshots,
)


class TestSimplePortfolioCloning:
    """Tests for SimplePortfolio cloning."""

    def test_clone_without_date_filtering(self):
        """Test cloning simple portfolio without date filtering."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        trade2 = Trade(
            date=date(2024, 2, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=160.0,
            price_native=160.0,
            quantity=5.0,
        )

        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)

        cloned = portfolio.clone()

        # Verify cloned portfolio has same name and is_historical flag
        assert cloned.name == portfolio.name
        assert cloned.is_historical == portfolio.is_historical

        # Verify all trades are cloned
        cloned_trades = cloned.get_all_trades()
        assert len(cloned_trades) == 2

        # Verify trades are deep copied (different objects)
        original_trades = portfolio.get_all_trades()
        assert cloned_trades[0] is not original_trades[0]
        assert cloned_trades[1] is not original_trades[1]

        # Verify trade data is identical
        assert cloned_trades[0].date == trade1.date
        assert cloned_trades[0].asset == trade1.asset
        assert cloned_trades[0].price == trade1.price
        assert cloned_trades[1].date == trade2.date
        assert cloned_trades[1].price == trade2.price

    def test_clone_with_start_date(self):
        """Test cloning simple portfolio with start_date filtering."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        trade2 = Trade(
            date=date(2024, 2, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=160.0,
            price_native=160.0,
            quantity=5.0,
        )

        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)

        cloned = portfolio.clone(start_date=date(2024, 2, 1))

        # Should only include trade2
        cloned_trades = cloned.get_all_trades()
        assert len(cloned_trades) == 1
        assert cloned_trades[0].date == date(2024, 2, 15)

    def test_clone_with_end_date(self):
        """Test cloning simple portfolio with end_date filtering."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        trade2 = Trade(
            date=date(2024, 2, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=160.0,
            price_native=160.0,
            quantity=5.0,
        )

        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)

        cloned = portfolio.clone(end_date=date(2024, 1, 31))

        # Should only include trade1
        cloned_trades = cloned.get_all_trades()
        assert len(cloned_trades) == 1
        assert cloned_trades[0].date == date(2024, 1, 15)

    def test_clone_with_date_range(self):
        """Test cloning simple portfolio with both start_date and end_date."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=5.0,
            ),
            Trade(
                date=date(2024, 3, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=170.0,
                price_native=170.0,
                quantity=3.0,
            ),
        ]

        for trade in trades:
            portfolio.add_trade(trade)

        cloned = portfolio.clone(
            start_date=date(2024, 2, 1), end_date=date(2024, 2, 28)
        )

        # Should only include trade2
        cloned_trades = cloned.get_all_trades()
        assert len(cloned_trades) == 1
        assert cloned_trades[0].date == date(2024, 2, 15)

    def test_clone_deep_copy_independence(self):
        """Test that cloned trades are independent (deep copy)."""
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
        cloned = portfolio.clone()

        # Modify original trade (if possible - Trade is a dataclass, so we can't modify it directly)
        # But we can verify they are different objects
        original_trades = portfolio.get_all_trades()
        cloned_trades = cloned.get_all_trades()

        assert original_trades[0] is not cloned_trades[0]
        assert original_trades[0].date == cloned_trades[0].date
        assert original_trades[0].price == cloned_trades[0].price

    def test_clone_empty_portfolio(self):
        """Test cloning empty portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        cloned = portfolio.clone()

        assert cloned.name == portfolio.name
        assert cloned.is_historical == portfolio.is_historical
        assert len(cloned.get_all_trades()) == 0

    def test_clone_date_range_validation_start_before(self):
        """Test that cloning with start_date before portfolio start raises error."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 2, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )

        portfolio.add_trade(trade)

        with pytest.raises(PortfolioError, match="start_date.*before portfolio's start_date"):
            portfolio.clone(start_date=date(2024, 1, 15))

    def test_clone_date_range_validation_end_after(self):
        """Test that cloning with end_date after portfolio end raises error."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 2, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )

        portfolio.add_trade(trade)

        with pytest.raises(PortfolioError, match="end_date.*after portfolio's end_date"):
            portfolio.clone(end_date=date(2024, 3, 15))

    def test_clone_date_range_validation_start_after_end(self):
        """Test that cloning with start_date after end_date raises error."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 2, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )

        portfolio.add_trade(trade)

        with pytest.raises(PortfolioError, match="start_date.*after end_date"):
            portfolio.clone(start_date=date(2024, 3, 15), end_date=date(2024, 2, 15))

    def test_clone_historical_portfolio(self):
        """Test cloning historical portfolio preserves is_historical flag."""
        portfolio = SimplePortfolio(name="Test Portfolio", is_historical=True)
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
        cloned = portfolio.clone()

        assert cloned.is_historical is True


class TestCompositePortfolioCloning:
    """Tests for CompositePortfolio cloning."""

    def test_clone_without_date_filtering(self):
        """Test cloning composite portfolio without date filtering."""
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
                date=date(2024, 2, 15),
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

        cloned = composite.clone()

        # Verify cloned portfolio has same name and is_historical flag
        assert cloned.name == composite.name
        assert cloned.is_historical == composite.is_historical

        # Verify sub-portfolios are cloned
        assert len(cloned._sub_portfolios) == 2
        assert "Sub1" in cloned._sub_portfolios
        assert "Sub2" in cloned._sub_portfolios

        # Verify sub-portfolios are deep copied (different objects)
        assert cloned._sub_portfolios["Sub1"] is not sub1
        assert cloned._sub_portfolios["Sub2"] is not sub2

        # Verify sub-portfolio data is correct
        cloned_sub1_trades = cloned._sub_portfolios["Sub1"].get_all_trades()
        assert len(cloned_sub1_trades) == 1
        assert cloned_sub1_trades[0].asset.ticker == "GOOG"

    def test_clone_with_date_filtering(self):
        """Test cloning composite portfolio with date filtering."""
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
                date=date(2024, 1, 20),
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

        cloned = composite.clone(end_date=date(2024, 1, 18))

        # Should only include trades from sub1 (sub2 trade is after end_date)
        cloned_trades = cloned.get_all_trades()
        assert len(cloned_trades) == 1
        assert cloned_trades[0].asset.ticker == "GOOG"

    def test_clone_nested_composite_portfolios(self):
        """Test cloning nested composite portfolios."""
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

        cloned = outer.clone()

        # Verify nested structure is cloned
        assert len(cloned._sub_portfolios) == 1
        assert "Inner" in cloned._sub_portfolios
        cloned_inner = cloned._sub_portfolios["Inner"]
        assert len(cloned_inner._sub_portfolios) == 1
        assert "Sub" in cloned_inner._sub_portfolios

        # Verify trades are accessible
        positions = cloned.get_positions()
        assert asset in positions

    def test_clone_historical_portfolio(self):
        """Test cloning historical composite portfolio preserves is_historical flag."""
        composite = CompositePortfolio(name="Composite", is_historical=True)
        sub = SimplePortfolio(name="Sub", is_historical=True)
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

        composite.add_sub_portfolio(sub)
        cloned = composite.clone()

        assert cloned.is_historical is True
        assert cloned._sub_portfolios["Sub"].is_historical is True

    def test_clone_date_range_validation(self):
        """Test that cloning composite portfolio validates date range."""
        composite = CompositePortfolio(name="Composite")
        sub = SimplePortfolio(name="Sub")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        sub.add_trade(
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        composite.add_sub_portfolio(sub)

        with pytest.raises(PortfolioError, match="start_date.*before portfolio's start_date"):
            composite.clone(start_date=date(2024, 1, 15))


class TestHistoricalSnapshots:
    """Tests for generate_historical_snapshots helper function."""

    def test_generate_snapshots_simple_portfolio(self):
        """Test generating snapshots for simple portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2024, 1, 20),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=5.0,
            ),
            Trade(
                date=date(2024, 1, 25),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=170.0,
                price_native=170.0,
                quantity=3.0,
            ),
        ]

        for trade in trades:
            portfolio.add_trade(trade)

        snapshots = generate_historical_snapshots(
            portfolio, start_date=date(2024, 1, 18), end_date=date(2024, 1, 22)
        )

        # Should have 5 snapshots (18, 19, 20, 21, 22)
        assert len(snapshots) == 5

        # Verify each snapshot has correct end_date
        assert len(snapshots[0].get_all_trades()) == 1  # Only first trade
        assert len(snapshots[1].get_all_trades()) == 1  # Only first trade
        assert len(snapshots[2].get_all_trades()) == 2  # First two trades
        assert len(snapshots[3].get_all_trades()) == 2  # First two trades
        assert len(snapshots[4].get_all_trades()) == 2  # First two trades

    def test_generate_snapshots_composite_portfolio(self):
        """Test generating snapshots for composite portfolio."""
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
                date=date(2024, 1, 20),
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

        # Use date range within composite portfolio's range
        snapshots = generate_historical_snapshots(
            composite, start_date=date(2024, 1, 15), end_date=date(2024, 1, 20)
        )

        # Should have 6 snapshots (15, 16, 17, 18, 19, 20)
        assert len(snapshots) == 6

        # Verify first snapshot only has sub1 trade
        assert len(snapshots[0].get_all_trades()) == 1
        assert snapshots[0].get_all_trades()[0].asset.ticker == "GOOG"

        # Verify last snapshot has both trades
        assert len(snapshots[5].get_all_trades()) == 2

    def test_generate_snapshots_single_date(self):
        """Test generating snapshots for single date."""
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

        snapshots = generate_historical_snapshots(
            portfolio, start_date=date(2024, 1, 15), end_date=date(2024, 1, 15)
        )

        assert len(snapshots) == 1
        assert len(snapshots[0].get_all_trades()) == 1

    def test_generate_snapshots_date_validation(self):
        """Test that generating snapshots validates date range."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        # Test start_date before portfolio start
        with pytest.raises(PortfolioError, match="start_date.*before portfolio's start_date"):
            generate_historical_snapshots(
                portfolio, start_date=date(2024, 1, 15), end_date=date(2024, 2, 20)
            )

        # Test end_date after portfolio end
        with pytest.raises(PortfolioError, match="end_date.*after portfolio's end_date"):
            generate_historical_snapshots(
                portfolio, start_date=date(2024, 2, 15), end_date=date(2024, 3, 15)
            )

        # Test start_date after end_date
        with pytest.raises(PortfolioError, match="start_date.*after end_date"):
            generate_historical_snapshots(
                portfolio, start_date=date(2024, 2, 20), end_date=date(2024, 2, 15)
            )

    def test_generate_snapshots_empty_portfolio(self):
        """Test generating snapshots for empty portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")

        snapshots = generate_historical_snapshots(
            portfolio, start_date=date(2024, 1, 15), end_date=date(2024, 1, 20)
        )

        # Should still generate snapshots, but all will be empty
        assert len(snapshots) == 6  # 15, 16, 17, 18, 19, 20
        for snapshot in snapshots:
            assert len(snapshot.get_all_trades()) == 0

