"""Tests for portfolio trade retrieval and price map functionality."""

from datetime import date
from unittest.mock import Mock

from wpm.models import Asset, Trade
from wpm.portfolio import CompositePortfolio, fetch_price_map, SimplePortfolio


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
            currency="USD",
            price=150.0,
            price_native=150.0,
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
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(stock_trade)
        
        crypto_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        crypto_trade = Trade(
            date=date(2024, 1, 15),
            asset=crypto_asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=50000.0,
            price_native=50000.0,
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
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade1)
        
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
            currency="USD",
            price=150.0,
            price_native=150.0,
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
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(stock_trade)
        
        crypto_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        crypto_trade = Trade(
            date=date(2024, 1, 15),
            asset=crypto_asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=50000.0,
            price_native=50000.0,
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
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade1)
        
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
        portfolio.add_trade(trade2)
        
        price_service = Mock()
        # Only return price for one ticker
        price_service.get_prices.return_value = {"GOOG": 160.0}
        
        price_map = fetch_price_map(portfolio, price_service)
        
        assert len(price_map) == 2
        assert price_map[asset1] == 160.0
        assert price_map[asset2] is None  # Missing ticker results in None


class TestGetAssetTrades:
    """Tests for get_asset_trades method."""

    def test_get_asset_trades_simple_portfolio_by_ticker_only(self):
        """Test filtering trades by ticker only in SimplePortfolio."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")

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
        trade3 = Trade(
            date=date(2024, 1, 17),
            asset=asset1,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=160.0,
            price_native=160.0,
            quantity=3.0,
        )

        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)
        portfolio.add_trade(trade3)

        trades = portfolio.get_asset_trades("GOOG")
        assert len(trades) == 2
        assert trade1 in trades
        assert trade3 in trades
        assert trade2 not in trades

    def test_get_asset_trades_simple_portfolio_with_start_date(self):
        """Test filtering trades by ticker and start_date in SimplePortfolio."""
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
        trade3 = Trade(
            date=date(2024, 3, 15),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=170.0,
            price_native=170.0,
            quantity=3.0,
        )

        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)
        portfolio.add_trade(trade3)

        trades = portfolio.get_asset_trades("GOOG", start_date=date(2024, 2, 1))
        assert len(trades) == 2
        assert trade1 not in trades
        assert trade2 in trades
        assert trade3 in trades

    def test_get_asset_trades_simple_portfolio_with_end_date(self):
        """Test filtering trades by ticker and end_date in SimplePortfolio."""
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
        trade3 = Trade(
            date=date(2024, 3, 15),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=170.0,
            price_native=170.0,
            quantity=3.0,
        )

        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)
        portfolio.add_trade(trade3)

        trades = portfolio.get_asset_trades("GOOG", end_date=date(2024, 2, 28))
        assert len(trades) == 2
        assert trade1 in trades
        assert trade2 in trades
        assert trade3 not in trades

    def test_get_asset_trades_simple_portfolio_with_both_dates(self):
        """Test filtering trades by ticker and both dates in SimplePortfolio."""
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
        trade3 = Trade(
            date=date(2024, 3, 15),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=170.0,
            price_native=170.0,
            quantity=3.0,
        )

        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)
        portfolio.add_trade(trade3)

        trades = portfolio.get_asset_trades(
            "GOOG", start_date=date(2024, 2, 1), end_date=date(2024, 2, 28)
        )
        assert len(trades) == 1
        assert trade1 not in trades
        assert trade2 in trades
        assert trade3 not in trades

    def test_get_asset_trades_simple_portfolio_empty_result(self):
        """Test get_asset_trades returns empty list when ticker doesn't exist."""
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

        trades = portfolio.get_asset_trades("AAPL")
        assert trades == []

    def test_get_asset_trades_simple_portfolio_returns_both_buy_and_sell(self):
        """Test get_asset_trades returns both Buy and Sell trades."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")

        buy_trade = Trade(
            date=date(2024, 1, 15),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        sell_trade = Trade(
            date=date(2024, 2, 15),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=160.0,
            price_native=160.0,
            quantity=5.0,
        )

        portfolio.add_trade(buy_trade)
        portfolio.add_trade(sell_trade)

        trades = portfolio.get_asset_trades("GOOG")
        assert len(trades) == 2
        assert buy_trade in trades
        assert sell_trade in trades

    def test_get_asset_trades_simple_portfolio_date_filtering_inclusive(self):
        """Test that date filtering is inclusive (boundary dates are included)."""
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
        trade3 = Trade(
            date=date(2024, 3, 15),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=170.0,
            price_native=170.0,
            quantity=3.0,
        )

        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)
        portfolio.add_trade(trade3)

        # Test start_date inclusive
        trades = portfolio.get_asset_trades("GOOG", start_date=date(2024, 1, 15))
        assert len(trades) == 3
        assert trade1 in trades

        # Test end_date inclusive
        trades = portfolio.get_asset_trades("GOOG", end_date=date(2024, 3, 15))
        assert len(trades) == 3
        assert trade3 in trades

        # Test both dates inclusive
        trades = portfolio.get_asset_trades(
            "GOOG", start_date=date(2024, 1, 15), end_date=date(2024, 3, 15)
        )
        assert len(trades) == 3

    def test_get_asset_trades_simple_portfolio_empty_portfolio(self):
        """Test get_asset_trades on empty portfolio returns empty list."""
        portfolio = SimplePortfolio(name="Empty Portfolio")

        trades = portfolio.get_asset_trades("GOOG")
        assert trades == []

    def test_get_asset_trades_composite_portfolio_aggregates_from_sub_portfolios(self):
        """Test get_asset_trades aggregates trades from multiple sub-portfolios."""
        composite = CompositePortfolio(name="Composite")

        sub1 = SimplePortfolio(name="Sub1")
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
        sub1.add_trade(trade1)

        sub2 = SimplePortfolio(name="Sub2")
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
        sub2.add_trade(trade2)

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)

        trades = composite.get_asset_trades("GOOG")
        assert len(trades) == 2
        assert trade1 in trades
        assert trade2 in trades

    def test_get_asset_trades_composite_portfolio_respects_date_filtering(self):
        """Test get_asset_trades respects date filtering across sub-portfolios."""
        composite = CompositePortfolio(name="Composite")

        sub1 = SimplePortfolio(name="Sub1")
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
        sub1.add_trade(trade1)

        sub2 = SimplePortfolio(name="Sub2")
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
        sub2.add_trade(trade2)

        sub3 = SimplePortfolio(name="Sub3")
        trade3 = Trade(
            date=date(2024, 3, 15),
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=170.0,
            price_native=170.0,
            quantity=3.0,
        )
        sub3.add_trade(trade3)

        composite.add_sub_portfolio(sub1)
        composite.add_sub_portfolio(sub2)
        composite.add_sub_portfolio(sub3)

        trades = composite.get_asset_trades(
            "GOOG", start_date=date(2024, 2, 1), end_date=date(2024, 2, 28)
        )
        assert len(trades) == 1
        assert trade1 not in trades
        assert trade2 in trades
        assert trade3 not in trades

    def test_get_asset_trades_composite_portfolio_nested(self):
        """Test get_asset_trades handles nested composite portfolios."""
        outer = CompositePortfolio(name="Outer")
        inner = CompositePortfolio(name="Inner")

        sub = SimplePortfolio(name="Sub")
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
        sub.add_trade(trade1)

        inner.add_sub_portfolio(sub)
        outer.add_sub_portfolio(inner)

        trades = outer.get_asset_trades("GOOG")
        assert len(trades) == 1
        assert trade1 in trades

    def test_get_asset_trades_composite_portfolio_no_matching_trades(self):
        """Test get_asset_trades returns empty list when no trades match."""
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
            date=date(2024, 2, 15),
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

        trades = composite.get_asset_trades("MSFT")
        assert trades == []

    def test_get_asset_trades_composite_portfolio_empty(self):
        """Test get_asset_trades on empty composite portfolio returns empty list."""
        composite = CompositePortfolio(name="Empty Composite")

        trades = composite.get_asset_trades("GOOG")
        assert trades == []

    def test_get_asset_trades_simple_portfolio_date_boundary_cases(self):
        """Test date boundary cases for date filtering."""
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

        # Test trade before start_date is excluded
        trades = portfolio.get_asset_trades("GOOG", start_date=date(2024, 1, 16))
        assert len(trades) == 1
        assert trade1 not in trades
        assert trade2 in trades

        # Test trade after end_date is excluded
        trades = portfolio.get_asset_trades("GOOG", end_date=date(2024, 1, 14))
        assert trades == []

    def test_get_asset_trades_composite_portfolio_mixed_assets(self):
        """Test get_asset_trades filters correctly when sub-portfolios have different assets."""
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
            date=date(2024, 2, 15),
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

        # Get trades for GOOG only
        trades = composite.get_asset_trades("GOOG")
        assert len(trades) == 1
        assert trade1 in trades
        assert trade2 not in trades

        # Get trades for AAPL only
        trades = composite.get_asset_trades("AAPL")
        assert len(trades) == 1
        assert trade1 not in trades
        assert trade2 in trades

