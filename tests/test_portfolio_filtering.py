"""Tests for portfolio position filtering functionality."""

from datetime import date
from decimal import Decimal

from wpm.models import Asset, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio


class TestGetPositionsFiltering:
    """Tests for get_positions filtering functionality."""

    def test_filter_by_asset_type_stock(self):
        """Test filtering positions by asset type (Stock)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        
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
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.5,
            )
        )
        
        positions = portfolio.get_positions(asset_type="Stock")
        
        assert len(positions) == 1
        assert stock_asset in positions
        assert crypto_asset not in positions

    def test_filter_by_asset_type_etf(self):
        """Test filtering positions by asset type (ETF)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        
        etf_asset = Asset(ticker="SPY", asset_type="ETF")
        stock_asset = Asset(ticker="GOOG", asset_type="Stock")
        
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=etf_asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=400.0,
                price_native=400.0,
                quantity=5.0,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=stock_asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        
        positions = portfolio.get_positions(asset_type="ETF")
        
        assert len(positions) == 1
        assert etf_asset in positions
        assert stock_asset not in positions

    def test_filter_by_asset_type_crypto(self):
        """Test filtering positions by asset type (Crypto)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        
        crypto_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        stock_asset = Asset(ticker="GOOG", asset_type="Stock")
        
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=crypto_asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.5,
            )
        )
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=stock_asset,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        
        positions = portfolio.get_positions(asset_type="Crypto")
        
        assert len(positions) == 1
        assert crypto_asset in positions
        assert stock_asset not in positions

    def test_filter_by_single_ticker(self):
        """Test filtering positions by single ticker."""
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
        
        positions = portfolio.get_positions(tickers=["GOOG"])
        
        assert len(positions) == 1
        assert asset1 in positions
        assert asset2 not in positions

    def test_filter_by_multiple_tickers(self):
        """Test filtering positions by multiple tickers."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        asset3 = Asset(ticker="MSFT", asset_type="Stock")
        
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
                price=300.0,
                price_native=300.0,
                quantity=3.0,
            )
        )
        
        positions = portfolio.get_positions(tickers=["GOOG", "AAPL"])
        
        assert len(positions) == 2
        assert asset1 in positions
        assert asset2 in positions
        assert asset3 not in positions

    def test_filter_by_both_asset_type_and_tickers(self):
        """Test filtering by both asset_type and tickers (AND logic)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        
        stock1 = Asset(ticker="GOOG", asset_type="Stock")
        stock2 = Asset(ticker="AAPL", asset_type="Stock")
        crypto1 = Asset(ticker="BTC-USD", asset_type="Crypto")
        
        portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=stock1,
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
                asset=stock2,
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
                asset=crypto1,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.5,
            )
        )
        
        # Filter for Stock type AND ticker GOOG
        positions = portfolio.get_positions(asset_type="Stock", tickers=["GOOG"])
        
        assert len(positions) == 1
        assert stock1 in positions
        assert stock2 not in positions  # Stock but wrong ticker
        assert crypto1 not in positions  # Wrong asset type

    def test_filter_empty_results_when_no_match(self):
        """Test filtering returns empty dict when no positions match."""
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
        
        # Filter for asset type that doesn't exist
        positions = portfolio.get_positions(asset_type="Crypto")
        assert positions == {}
        
        # Filter for ticker that doesn't exist
        positions = portfolio.get_positions(tickers=["AAPL"])
        assert positions == {}

    def test_filter_empty_portfolio(self):
        """Test filtering on empty portfolio returns empty dict."""
        portfolio = SimplePortfolio(name="Empty Portfolio")
        
        positions = portfolio.get_positions(asset_type="Stock")
        assert positions == {}
        
        positions = portfolio.get_positions(tickers=["GOOG"])
        assert positions == {}
        
        positions = portfolio.get_positions(asset_type="Stock", tickers=["GOOG"])
        assert positions == {}

    def test_filter_composite_portfolio(self):
        """Test filtering in composite portfolios."""
        composite = CompositePortfolio(name="Composite")
        
        sub1 = SimplePortfolio(name="Sub1")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="BTC-USD", asset_type="Crypto")
        
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
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.5,
            )
        )
        
        sub2 = SimplePortfolio(name="Sub2")
        asset3 = Asset(ticker="AAPL", asset_type="Stock")
        sub2.add_trade(
            Trade(
                date=date(2024, 1, 17),
                asset=asset3,
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
        
        # Filter for Stock type only
        positions = composite.get_positions(asset_type="Stock")
        assert len(positions) == 2
        assert asset1 in positions
        assert asset3 in positions
        assert asset2 not in positions

    def test_filter_nested_composite_portfolio(self):
        """Test filtering in nested composite portfolios."""
        outer = CompositePortfolio(name="Outer")
        inner = CompositePortfolio(name="Inner")
        
        sub = SimplePortfolio(name="Sub")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="BTC-USD", asset_type="Crypto")
        
        sub.add_trade(
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
        sub.add_trade(
            Trade(
                date=date(2024, 1, 16),
                asset=asset2,
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.5,
            )
        )
        
        inner.add_sub_portfolio(sub)
        outer.add_sub_portfolio(inner)
        
        # Filter for Crypto only
        positions = outer.get_positions(asset_type="Crypto")
        assert len(positions) == 1
        assert asset2 in positions
        assert asset1 not in positions

    def test_filter_ticker_not_in_portfolio(self):
        """Test filtering with ticker that doesn't exist in portfolio."""
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
        
        # Filter for ticker that doesn't exist
        positions = portfolio.get_positions(tickers=["NONEXISTENT"])
        assert positions == {}

    def test_filter_asset_type_not_in_portfolio(self):
        """Test filtering with asset_type that doesn't exist in portfolio."""
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
        
        # Filter for asset type that doesn't exist
        positions = portfolio.get_positions(asset_type="ETF")
        assert positions == {}

    def test_filter_case_sensitive_ticker(self):
        """Test that ticker filtering is case-sensitive."""
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
        
        # Case mismatch should not match
        positions = portfolio.get_positions(tickers=["goog"])
        assert positions == {}
        
        # Exact case should match
        positions = portfolio.get_positions(tickers=["GOOG"])
        assert len(positions) == 1
        assert asset in positions

    def test_filter_aggregation_with_same_asset_in_composite(self):
        """Test filtering works correctly when same asset exists in multiple sub-portfolios."""
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
        
        # Filter for this specific ticker
        positions = composite.get_positions(tickers=["GOOG"])
        assert len(positions) == 1
        assert asset in positions
        # Quantity should be aggregated
        assert positions[asset].quantity == Decimal('15.0')

    def test_no_filter_returns_all_positions(self):
        """Test that calling get_positions() without filters returns all positions."""
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
                quantity=0.5,
            )
        )
        
        # No filters - should return all positions
        positions = portfolio.get_positions()
        assert len(positions) == 2
        assert asset1 in positions
        assert asset2 in positions

    def test_filter_asset_type_case_insensitive(self):
        """Test that asset_type filter is case-insensitive (normalized)."""
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
        
        # Test lowercase
        positions = portfolio.get_positions(asset_type="stock")
        assert len(positions) == 1
        assert asset in positions
        
        # Test uppercase
        positions = portfolio.get_positions(asset_type="STOCK")
        assert len(positions) == 1
        assert asset in positions
        
        # Test mixed case
        positions = portfolio.get_positions(asset_type="StOcK")
        assert len(positions) == 1
        assert asset in positions

    def test_filter_invalid_asset_type(self):
        """Test filtering with invalid asset_type returns empty results."""
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
        
        # Invalid asset type should return empty dict
        positions = portfolio.get_positions(asset_type="InvalidType")
        assert positions == {}

