"""Tests for portfolio metrics (market value and unrealized P/L)."""

from datetime import date

from wpm.models import Asset, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio


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
                currency="USD",
                price=150.0,
                price_native=150.0,
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
                currency="USD",
                price=150.0,
                price_native=150.0,
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
                currency="USD",
                price=150.0,
                price_native=150.0,
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

