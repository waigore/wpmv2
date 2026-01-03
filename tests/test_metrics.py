"""Tests for portfolio metrics and breakdown generation."""

import pytest
from datetime import date
from decimal import Decimal

from wpm.metrics import (
    breakdown_by_asset_type,
    breakdown_by_broker,
    breakdown_by_purchase_period,
    breakdown_by_ticker,
    calculate_market_value,
    calculate_portfolio_metrics,
)
from wpm.models import Asset, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio


class TestCalculatePortfolioMetrics:
    """Tests for calculate_portfolio_metrics function."""

    def test_calculate_metrics_simple_portfolio(self):
        """Test metrics calculation for simple portfolio."""
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

        metrics = calculate_portfolio_metrics(portfolio)

        assert metrics["portfolio_name"] == "Test Portfolio"
        assert metrics["cost_basis_method"] == "fifo"
        assert metrics["total_cost_basis"] == 1500.0
        assert metrics["position_count"] == 1
        assert asset in metrics["positions"]


class TestBreakdownByAssetType:
    """Tests for breakdown_by_asset_type function."""

    def test_breakdown_single_asset_type(self):
        """Test breakdown with single asset type."""
        portfolio = SimplePortfolio(name="Test")
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

        breakdown = breakdown_by_asset_type(portfolio)

        assert "Stock" in breakdown
        assert breakdown["Stock"]["total_quantity"] == Decimal('10.0')
        assert breakdown["Stock"]["total_cost_basis"] == 1500.0
        assert len(breakdown["Stock"]["positions"]) == 1

    def test_breakdown_multiple_asset_types(self):
        """Test breakdown with multiple asset types."""
        portfolio = SimplePortfolio(name="Test")
        stock_asset = Asset(ticker="GOOG", asset_type="Stock")
        crypto_asset = Asset(ticker="BTC-USD", asset_type="Crypto")

        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=stock_asset,
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
                asset=crypto_asset,
                action="Buy",
            broker="Coinbase",
            currency="USD",
            price=50000.0,
            price_native=50000.0,
            quantity=0.1,
            )
        )

        breakdown = breakdown_by_asset_type(portfolio)

        assert "Stock" in breakdown
        assert "Crypto" in breakdown
        assert breakdown["Stock"]["total_quantity"] == Decimal('10.0')
        assert breakdown["Crypto"]["total_quantity"] == Decimal('0.1')


class TestBreakdownByTicker:
    """Tests for breakdown_by_ticker function."""

    def test_breakdown_by_ticker(self):
        """Test breakdown by ticker."""
        portfolio = SimplePortfolio(name="Test")
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

        breakdown = breakdown_by_ticker(portfolio)

        assert "GOOG" in breakdown
        assert "AAPL" in breakdown
        assert breakdown["GOOG"].quantity == Decimal('10.0')
        assert breakdown["AAPL"].quantity == Decimal('5.0')


class TestBreakdownByPurchasePeriod:
    """Tests for breakdown_by_purchase_period function."""

    def test_breakdown_by_month(self):
        """Test breakdown by month."""
        portfolio = SimplePortfolio(name="Test")
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
        portfolio.add_trade(
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=5.0,
            )
        )

        breakdown = breakdown_by_purchase_period(portfolio, period="month")

        assert "2024-01" in breakdown
        assert "2024-02" in breakdown
        assert breakdown["2024-01"]["total_quantity"] == Decimal('10.0')
        assert breakdown["2024-02"]["total_quantity"] == Decimal('5.0')

    def test_breakdown_by_quarter(self):
        """Test breakdown by quarter."""
        portfolio = SimplePortfolio(name="Test")
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
        portfolio.add_trade(
            Trade(
                date=date(2024, 2, 15),
                asset=asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=5.0,
            )
        )

        breakdown = breakdown_by_purchase_period(portfolio, period="quarter")

        assert "2024-Q1" in breakdown
        assert breakdown["2024-Q1"]["total_quantity"] == Decimal('15.0')

    def test_breakdown_by_year(self):
        """Test breakdown by year."""
        portfolio = SimplePortfolio(name="Test")
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

        breakdown = breakdown_by_purchase_period(portfolio, period="year")

        assert "2024" in breakdown
        assert breakdown["2024"]["total_quantity"] == Decimal('10.0')

    def test_breakdown_invalid_period(self):
        """Test breakdown with invalid period."""
        portfolio = SimplePortfolio(name="Test")
        with pytest.raises(ValueError, match="Period must be"):
            breakdown_by_purchase_period(portfolio, period="invalid")


class TestBreakdownByBroker:
    """Tests for breakdown_by_broker function."""

    def test_breakdown_by_broker(self):
        """Test breakdown by broker."""
        portfolio = SimplePortfolio(name="Test")
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
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset,
                action="Buy",
                broker="Fidelity",
                currency="USD",
                price=160.0,
                price_native=160.0,
                quantity=5.0,
            )
        )

        breakdown = breakdown_by_broker(portfolio)

        assert "IBKR" in breakdown
        assert "Fidelity" in breakdown
        assert breakdown["IBKR"]["total_cost_basis"] == 1500.0
        assert breakdown["Fidelity"]["total_cost_basis"] == 800.0


class TestCalculateMarketValue:
    """Tests for calculate_market_value function."""

    def test_calculate_market_value(self):
        """Test market value calculation."""
        portfolio = SimplePortfolio(name="Test")
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
        market_value = calculate_market_value(portfolio, prices)

        # 10 * 160 + 5 * 210 = 1600 + 1050 = 2650
        assert market_value == 2650.0

    def test_calculate_market_value_missing_price(self):
        """Test market value calculation with missing price."""
        portfolio = SimplePortfolio(name="Test")
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

        prices = {}  # No price for asset
        market_value = calculate_market_value(portfolio, prices)

        assert market_value == 0.0

    def test_calculate_market_value_composite_portfolio(self):
        """Test market value calculation for composite portfolio."""
        composite = CompositePortfolio(name="Composite")

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

        composite.add_sub_portfolio(sub)

        prices = {asset: 160.0}
        market_value = calculate_market_value(composite, prices)

        assert market_value == 1600.0

