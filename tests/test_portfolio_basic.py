"""Tests for basic portfolio operations."""

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

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

    def test_get_asset_lots_simple_portfolio(self):
        """Test get_asset_lots for simple portfolio."""
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
                date=date(2025, 11, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
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

        lots = portfolio.get_asset_lots("VOO")
        assert len(lots) == 2
        assert lots[0].purchase_date == date(2025, 10, 1)
        assert lots[0].remaining_quantity == Decimal('1')
        assert lots[1].purchase_date == date(2025, 11, 1)
        assert lots[1].remaining_quantity == Decimal('1')

    def test_get_total_realized_pnl_simple_portfolio(self):
        """Test get_total_realized_pnl for simple portfolio."""
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

        prices = {asset: 630.0}
        realized_pnl = portfolio.get_total_realized_pnl(prices)
        # 1 * (620 - 600) = 20
        assert realized_pnl == 20.0

    def test_get_total_realized_pnl_empty_portfolio(self):
        """Test get_total_realized_pnl for empty portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        prices = {}
        realized_pnl = portfolio.get_total_realized_pnl(prices)
        assert realized_pnl == 0.0

    def test_get_assets_empty(self):
        """Test getting assets from empty portfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        assets = portfolio.get_assets()
        assert assets == {}

    def test_get_assets_after_adding_trades(self):
        """Test that get_assets() returns correct assets after adding trades."""
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
                broker="Coinbase",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.1,
            )
        )

        assets = portfolio.get_assets()
        assert len(assets) == 3
        assert "GOOG" in assets
        assert assets["GOOG"] == asset1
        assert "AAPL" in assets
        assert assets["AAPL"] == asset2
        assert "BTC-USD" in assets
        assert assets["BTC-USD"] == asset3

    def test_add_trade_updates_assets(self):
        """Test that adding a trade updates the asset cache."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        # Initially empty
        assets = portfolio.get_assets()
        assert assets == {}

        # Add trade
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

        # Asset should now be in cache
        assets = portfolio.get_assets()
        assert "GOOG" in assets
        assert assets["GOOG"] == asset

    def test_get_assets_no_calculations(self):
        """Test that get_assets() doesn't trigger FIFO calculations."""
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

        # Mock get_positions to verify it's not called
        with patch.object(portfolio, "get_positions") as mock_get_positions:
            assets = portfolio.get_assets()
            # Verify get_assets() worked
            assert "GOOG" in assets
            # Verify get_positions() was NOT called
            mock_get_positions.assert_not_called()

    def test_get_assets_duplicate_ticker(self):
        """Test that get_assets() handles multiple trades for same ticker correctly."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        # Add multiple trades for same asset
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
        portfolio.add_trade(
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

        # Should only have one entry for GOOG
        assets = portfolio.get_assets()
        assert len(assets) == 1
        assert "GOOG" in assets
        assert assets["GOOG"] == asset


class TestCompositePortfolio:
    """Tests for CompositePortfolio class."""

    def test_get_assets_empty_composite(self):
        """Test getting assets from empty composite portfolio."""
        composite = CompositePortfolio(name="Composite")
        assets = composite.get_assets()
        assert assets == {}

    def test_get_assets_composite_aggregates(self):
        """Test that composite portfolio aggregates assets from sub-portfolios."""
        portfolio1 = SimplePortfolio(name="Portfolio1")
        portfolio2 = SimplePortfolio(name="Portfolio2")

        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        asset3 = Asset(ticker="BTC-USD", asset_type="Crypto")

        portfolio1.add_trade(
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
        portfolio2.add_trade(
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
        portfolio2.add_trade(
            Trade(
                date=date(2024, 1, 17),
                asset=asset3,
                action="Buy",
                broker="Coinbase",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.1,
            )
        )

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio1)
        composite.add_sub_portfolio(portfolio2)

        assets = composite.get_assets()
        assert len(assets) == 3
        assert "GOOG" in assets
        assert assets["GOOG"] == asset1
        assert "AAPL" in assets
        assert assets["AAPL"] == asset2
        assert "BTC-USD" in assets
        assert assets["BTC-USD"] == asset3

    def test_get_assets_composite_duplicate_tickers(self):
        """Test that composite handles duplicate tickers across sub-portfolios."""
        portfolio1 = SimplePortfolio(name="Portfolio1")
        portfolio2 = SimplePortfolio(name="Portfolio2")

        asset = Asset(ticker="GOOG", asset_type="Stock")

        portfolio1.add_trade(
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
        portfolio2.add_trade(
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

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio1)
        composite.add_sub_portfolio(portfolio2)

        assets = composite.get_assets()
        # Should only have one entry for GOOG (keeps first one)
        assert len(assets) == 1
        assert "GOOG" in assets
        assert assets["GOOG"] == asset

    def test_get_assets_composite_no_calculations(self):
        """Test that composite get_assets() doesn't trigger calculations."""
        portfolio = SimplePortfolio(name="SubPortfolio")
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

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio)

        # Mock get_positions to verify it's not called
        with patch.object(composite, "get_positions") as mock_get_positions:
            with patch.object(portfolio, "get_positions") as mock_sub_get_positions:
                assets = composite.get_assets()
                # Verify get_assets() worked
                assert "GOOG" in assets
                # Verify get_positions() was NOT called on either portfolio
                mock_get_positions.assert_not_called()
                mock_sub_get_positions.assert_not_called()

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

    def test_get_sub_portfolios(self):
        """Test getting sub-portfolios via public method."""
        composite = CompositePortfolio(name="Composite")
        sub_portfolio1 = SimplePortfolio(name="Sub1")
        sub_portfolio2 = SimplePortfolio(name="Sub2")
        
        composite.add_sub_portfolio(sub_portfolio1)
        composite.add_sub_portfolio(sub_portfolio2)
        
        sub_portfolios = composite.get_sub_portfolios()
        assert isinstance(sub_portfolios, dict)
        assert len(sub_portfolios) == 2
        assert "Sub1" in sub_portfolios
        assert "Sub2" in sub_portfolios
        assert sub_portfolios["Sub1"] is sub_portfolio1
        assert sub_portfolios["Sub2"] is sub_portfolio2
        # Verify it returns a copy (modifying the copy shouldn't affect the original)
        sub_portfolios["Sub3"] = SimplePortfolio(name="Sub3")
        assert "Sub3" not in composite.get_sub_portfolios()

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

    def test_get_asset_lots_composite_portfolio(self):
        """Test get_asset_lots for composite portfolio."""
        composite = CompositePortfolio(name="Composite")
        sub1 = SimplePortfolio(name="Sub1")
        asset = Asset(ticker="VOO", asset_type="ETF")
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

        sub2 = SimplePortfolio(name="Sub2")
        sub2.add_trade(
            Trade(
                date=date(2025, 11, 1),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=610.0,
                price_native=610.0,
                quantity=1.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        lots = composite.get_asset_lots("VOO")
        assert len(lots) == 2

    def test_get_total_realized_pnl_composite_portfolio(self):
        """Test get_total_realized_pnl for composite portfolio."""
        composite = CompositePortfolio(name="Composite")
        sub1 = SimplePortfolio(name="Sub1")
        asset1 = Asset(ticker="VOO", asset_type="ETF")
        sub1.add_trade(
            Trade(
                date=date(2025, 10, 1),
                asset=asset1,
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
                asset=asset1,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=620.0,
                price_native=620.0,
                quantity=1.0,
            )
        )

        sub2 = SimplePortfolio(name="Sub2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        sub2.add_trade(
            Trade(
                date=date(2025, 10, 1),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        prices = {asset1: 630.0, asset2: 160.0}
        realized_pnl = composite.get_total_realized_pnl(prices)
        # From sub1: 1 * (620 - 600) = 20
        # From sub2: 0 (no sells)
        assert realized_pnl == 20.0


class TestPortfolioHistoricalProperties:
    """Tests for historical portfolio properties."""

    def test_simple_portfolio_is_historical(self):
        """Test is_historical flag for simple portfolio."""
        portfolio = SimplePortfolio(name="Test", is_historical=False)
        assert not portfolio.is_historical

        historical_portfolio = SimplePortfolio(name="Test", is_historical=True)
        assert historical_portfolio.is_historical

    def test_composite_portfolio_is_historical(self):
        """Test is_historical flag for composite portfolio."""
        portfolio = CompositePortfolio(name="Test", is_historical=False)
        assert not portfolio.is_historical

        historical_portfolio = CompositePortfolio(name="Test", is_historical=True)
        assert historical_portfolio.is_historical

    def test_simple_portfolio_start_date_end_date(self):
        """Test start_date and end_date properties for simple portfolio."""
        portfolio = SimplePortfolio(name="Test")
        
        # Empty portfolio
        assert portfolio.start_date is None
        assert portfolio.end_date is None

        # Add trades
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
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=140.0,
                price_native=140.0,
                quantity=5.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 3, 15),
                asset=asset,
                action="Sell",
                broker="IBKR",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=3.0,
            )
        )

        # start_date should be earliest trade
        assert portfolio.start_date == date(2024, 1, 15)
        # end_date should be most recent trade
        assert portfolio.end_date == date(2024, 3, 15)

    def test_composite_portfolio_start_date_end_date(self):
        """Test start_date and end_date properties for composite portfolio."""
        composite = CompositePortfolio(name="Test")
        
        # Empty composite
        assert composite.start_date is None
        assert composite.end_date is None

        # Add sub-portfolios
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
        sub1.add_trade(
            Trade(
                date=date(2024, 3, 15),
                asset=asset1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=5.0,
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
        sub2.add_trade(
            Trade(
                date=date(2024, 4, 15),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=210.0,
                price_native=210.0,
                quantity=3.0,
            )
        )

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        # start_date should be earliest of all sub-portfolios
        assert composite.start_date == date(2024, 1, 15)
        # end_date should be most recent of all sub-portfolios
        assert composite.end_date == date(2024, 4, 15)

    def test_composite_portfolio_is_historical_validation(self):
        """Test that composite portfolio validates is_historical flags match."""
        composite = CompositePortfolio(name="Test", is_historical=True)
        
        sub1 = SimplePortfolio(name="Sub1", is_historical=True)
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
        composite.add_sub_portfolio(sub1)  # Should work

        # Try to add portfolio with different is_historical flag
        sub2 = SimplePortfolio(name="Sub2", is_historical=False)
        sub2.add_trade(
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
        with pytest.raises(PortfolioError, match="is_historical"):
            composite.add_sub_portfolio(sub2)

