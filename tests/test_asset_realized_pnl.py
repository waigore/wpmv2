"""Tests for asset realized P/L calculation methods."""

import pytest
from datetime import date
from decimal import Decimal

from wpm.models import Asset, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio


class TestSimplePortfolioAssetRealizedPnl:
    """Tests for get_asset_realized_pnl method in SimplePortfolio."""

    def test_get_asset_realized_pnl_no_lots(self):
        """Test realized P/L for asset with no lots returns 0.0."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        realized_pnl = portfolio.get_asset_realized_pnl("AAPL")
        assert realized_pnl == 0.0

    def test_get_asset_realized_pnl_no_sells(self):
        """Test realized P/L for asset with buys but no sells returns 0.0."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="AAPL", asset_type="Stock")
        portfolio.add_trade(
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        realized_pnl = portfolio.get_asset_realized_pnl("AAPL")
        assert realized_pnl == 0.0

    def test_get_asset_realized_pnl_with_sells(self):
        """Test realized P/L for asset with sells calculates correctly."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="VOO", asset_type="ETF")
        trades = [
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            ),
            Trade(
                date=date(2025, 12, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=620.0,
                price_native=620.0,
                quantity=1.0,
            ),
        ]
        for trade in trades:
            portfolio.add_trade(trade)

        realized_pnl = portfolio.get_asset_realized_pnl("VOO")
        # 1 * (620 - 600) = 20
        assert realized_pnl == 20.0

    def test_get_asset_realized_pnl_broker_filter(self):
        """Test broker filtering works correctly."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="AAPL", asset_type="Stock")
        # Use different dates to ensure FIFO matching works correctly with broker filtering
        trades = [
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2025, 10, 2),
                asset=asset,
                action="Buy",
                broker="Fidelity",
                currency="USD",
                price=152.0,
                price_native=152.0,
                quantity=5.0,
            ),
            Trade(
                date=date(2025, 11, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=5.0,
            ),
            Trade(
                date=date(2025, 11, 2),
                asset=asset,
                action="Sell",
                broker="Fidelity",
                currency="USD",
                price=162.0,
                price_native=162.0,
                quantity=3.0,
            ),
        ]
        for trade in trades:
            portfolio.add_trade(trade)

        # Test with IBKR filter
        realized_pnl_ibkr = portfolio.get_asset_realized_pnl("AAPL", brokers=["IBKR"])
        # 5 * (160 - 150) = 50
        assert realized_pnl_ibkr == 50.0

        # Test with Fidelity filter
        realized_pnl_fidelity = portfolio.get_asset_realized_pnl("AAPL", brokers=["Fidelity"])
        # 3 * (162 - 152) = 30
        assert realized_pnl_fidelity == 30.0

        # Test with no filter (all brokers)
        # FIFO matching: IBKR sell (5 @ 160) matches IBKR lot -> 5 * (160 - 150) = 50
        # FIFO matching: Fidelity sell (3 @ 162) matches Fidelity lot -> 3 * (162 - 152) = 30
        # Total: 50 + 30 = 80 (FIFO matches by broker)
        realized_pnl_all = portfolio.get_asset_realized_pnl("AAPL")
        assert realized_pnl_all == 80.0

    def test_get_asset_realized_pnl_multiple_lots(self):
        """Test realized P/L with multiple lots from different purchases."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trades = [
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=100.0,
                price_native=100.0,
                quantity=10.0,
            ),
            Trade(
                date=date(2025, 11, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=110.0,
                price_native=110.0,
                quantity=5.0,
            ),
            Trade(
                date=date(2025, 12, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=120.0,
                price_native=120.0,
                quantity=8.0,
            ),
        ]
        for trade in trades:
            portfolio.add_trade(trade)

        realized_pnl = portfolio.get_asset_realized_pnl("GOOG")
        # From first lot (10 @ 100): 8 * (120 - 100) = 160
        assert realized_pnl == 160.0


class TestCompositePortfolioAssetRealizedPnl:
    """Tests for get_asset_realized_pnl method in CompositePortfolio."""

    def test_get_asset_realized_pnl_aggregates(self):
        """Test that composite portfolio aggregates realized P/L from sub-portfolios."""
        composite = CompositePortfolio(name="Composite")
        sub1 = SimplePortfolio(name="Sub1")
        asset = Asset(ticker="VOO", asset_type="ETF")
        
        # Sub1: Buy and sell
        sub1.add_trade(
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=600.0,
                price_native=600.0,
                quantity=2.0,
            )
        )
        sub1.add_trade(
            Trade(
                date=date(2025, 12, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=620.0,
                price_native=620.0,
                quantity=1.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2")
        # Sub2: Buy and sell
        sub2.add_trade(
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=2.0,
            )
        )
        sub2.add_trade(
            Trade(
                date=date(2025, 12, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=630.0,
                price_native=630.0,
                quantity=1.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        realized_pnl = composite.get_asset_realized_pnl("VOO")
        # From sub1: 1 * (620 - 600) = 20
        # From sub2: 1 * (630 - 610) = 20
        # Total: 40
        assert realized_pnl == 40.0

    def test_get_asset_realized_pnl_broker_filter_composite(self):
        """Test broker filtering works across sub-portfolios."""
        composite = CompositePortfolio(name="Composite")
        sub1 = SimplePortfolio(name="Sub1")
        asset = Asset(ticker="AAPL", asset_type="Stock")
        
        # Sub1 with IBKR
        sub1.add_trade(
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        sub1.add_trade(
            Trade(
                date=date(2025, 11, 1),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=5.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2")
        # Sub2 with Fidelity
        sub2.add_trade(
            Trade(
                date=date(2025, 10, 1),
                asset=asset,
                action="Buy",
                broker="Fidelity",
                currency="USD",
                price=152.0,
                price_native=152.0,
                quantity=5.0,
            )
        )
        sub2.add_trade(
            Trade(
                date=date(2025, 11, 1),
                asset=asset,
                action="Sell",
                broker="Fidelity",
                currency="USD",
                price=162.0,
                price_native=162.0,
                quantity=3.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        # Test with IBKR filter
        realized_pnl_ibkr = composite.get_asset_realized_pnl("AAPL", brokers=["IBKR"])
        # From sub1: 5 * (160 - 150) = 50
        assert realized_pnl_ibkr == 50.0

        # Test with Fidelity filter
        realized_pnl_fidelity = composite.get_asset_realized_pnl("AAPL", brokers=["Fidelity"])
        # From sub2: 3 * (162 - 152) = 30
        assert realized_pnl_fidelity == 30.0

        # Test with no filter (all brokers)
        realized_pnl_all = composite.get_asset_realized_pnl("AAPL")
        # 50 + 30 = 80
        assert realized_pnl_all == 80.0
