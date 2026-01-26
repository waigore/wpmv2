"""Tests for reference portfolio creation."""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

from wpm.models import Asset, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.reference import (
    BuyAndHoldStrategy,
    DefaultHistoricalPriceFetcher,
    HistoricalPriceFetcher,
    ReferenceStrategy,
    create_reference_portfolio,
)
from wpm.currency import CurrencyService


class TestBuyAndHoldStrategy:
    """Tests for BuyAndHoldStrategy class."""

    def test_init_valid_asset(self):
        """Test initializing strategy with valid asset."""
        reference_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset)
        assert strategy.reference_asset == reference_asset

    def test_init_invalid_asset(self):
        """Test initializing strategy with invalid asset raises error."""
        with pytest.raises(ValueError, match="reference_asset must be an Asset object"):
            BuyAndHoldStrategy("not an asset")

    def test_generate_trades_buy(self):
        """Test generating reference trade from Buy trade."""
        reference_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset)

        original_trade = Trade(
            date=date(2024, 1, 15),
            asset=Asset(ticker="GOOG", asset_type="Stock"),
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )

        # Mock price service
        price_service = MagicMock()
        price_service.get_historical_price.return_value = 400.0  # SPY at $400

        currency_service = MagicMock()

        # Generate reference trades
        reference_trades = strategy.generate_trades(
            original_trade=original_trade,
            price_service=price_service,
            currency_service=currency_service,
        )

        # Verify result
        assert len(reference_trades) == 1
        reference_trade = reference_trades[0]

        assert reference_trade.date == original_trade.date
        assert reference_trade.asset == reference_asset
        assert reference_trade.action == "Buy"
        assert reference_trade.broker == original_trade.broker
        assert reference_trade.price == 400.0
        assert reference_trade.currency == "USD"
        # Cost basis: 150.0 * 10.0 = 1500.0
        # Quantity: 1500.0 / 400.0 = 3.75
        assert reference_trade.quantity == Decimal('3.75')
        assert reference_trade.total_value == 1500.0

        # Verify price service was called correctly
        price_service.get_historical_price.assert_called_once_with(
            ticker="SPY",
            asset_type="ETF",
            target_date=date(2024, 1, 15),
            in_native_currency=False,
        )

    def test_generate_trades_sell(self):
        """Test generating reference trade from Sell trade."""
        reference_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset)

        original_trade = Trade(
            date=date(2024, 2, 15),
            asset=Asset(ticker="GOOG", asset_type="Stock"),
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=160.0,
            price_native=160.0,
            quantity=5.0,
        )

        # Mock price service
        price_service = MagicMock()
        price_service.get_historical_price.return_value = 410.0  # SPY at $410

        currency_service = MagicMock()

        # Generate reference trades
        reference_trades = strategy.generate_trades(
            original_trade=original_trade,
            price_service=price_service,
            currency_service=currency_service,
        )

        # Verify result
        assert len(reference_trades) == 1
        reference_trade = reference_trades[0]

        assert reference_trade.action == "Sell"
        # Cost basis: 160.0 * 5.0 = 800.0
        # Quantity: 800.0 / 410.0 ≈ 1.9512...
        expected_quantity = Decimal('800.0') / Decimal('410.0')
        assert abs(float(reference_trade.quantity) - float(expected_quantity)) < 0.0001
        assert abs(reference_trade.total_value - 800.0) < 0.01

    def test_generate_trades_preserves_metadata(self):
        """Test that reference trade preserves original trade metadata."""
        reference_asset = Asset(ticker="VOO", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset)

        original_trade = Trade(
            date=date(2024, 1, 15),
            asset=Asset(ticker="AAPL", asset_type="Stock"),
            action="Buy",
            broker="Fidelity",
            order_instruction="Limit",
            trade_type="Recurring buy",
            currency="USD",
            price=180.0,
            price_native=180.0,
            quantity=5.0,
        )

        price_service = MagicMock()
        price_service.get_historical_price.return_value = 350.0

        currency_service = MagicMock()

        reference_trades = strategy.generate_trades(
            original_trade=original_trade,
            price_service=price_service,
            currency_service=currency_service,
        )

        reference_trade = reference_trades[0]
        assert reference_trade.broker == "Fidelity"
        assert reference_trade.order_instruction == "Limit"
        assert reference_trade.trade_type == "Recurring buy"

    def test_generate_trades_missing_price(self):
        """Test that missing historical price raises ValueError."""
        reference_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset)

        original_trade = Trade(
            date=date(2024, 1, 15),
            asset=Asset(ticker="GOOG", asset_type="Stock"),
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )

        price_service = MagicMock()
        price_service.get_historical_price.side_effect = ValueError(
            "No historical price data available"
        )

        currency_service = MagicMock()

        with pytest.raises(ValueError, match="Cannot create reference trade"):
            strategy.generate_trades(
                original_trade=original_trade,
                price_service=price_service,
                currency_service=currency_service,
            )

    def test_generate_trades_invalid_cost_basis(self):
        """Test that invalid cost basis raises ValueError."""
        reference_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset)

        # Create a valid trade
        original_trade = Trade(
            date=date(2024, 1, 15),
            asset=Asset(ticker="GOOG", asset_type="Stock"),
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )

        # Mock total_value property to return 0 to test invalid cost basis scenario
        # Note: In practice, this can't happen with a valid Trade, but we test the validation
        price_service = MagicMock()
        currency_service = MagicMock()
        
        with patch.object(type(original_trade), 'total_value', PropertyMock(return_value=0.0)):
            with pytest.raises(ValueError, match="invalid cost basis"):
                strategy.generate_trades(
                    original_trade=original_trade,
                    price_service=price_service,
                    currency_service=currency_service,
                )

    def test_generate_trades_different_asset_types(self):
        """Test strategy works with different reference asset types."""
        # Test with Stock
        stock_asset = Asset(ticker="AAPL", asset_type="Stock")
        strategy = BuyAndHoldStrategy(stock_asset)

        original_trade = Trade(
            date=date(2024, 1, 15),
            asset=Asset(ticker="GOOG", asset_type="Stock"),
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )

        price_service = MagicMock()
        price_service.get_historical_price.return_value = 180.0

        currency_service = MagicMock()

        reference_trades = strategy.generate_trades(
            original_trade=original_trade,
            price_service=price_service,
            currency_service=currency_service,
        )

        assert len(reference_trades) == 1
        assert reference_trades[0].asset == stock_asset

        # Test with Crypto
        crypto_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        strategy = BuyAndHoldStrategy(crypto_asset)

        price_service.get_historical_price.return_value = 45000.0

        reference_trades = strategy.generate_trades(
            original_trade=original_trade,
            price_service=price_service,
            currency_service=currency_service,
        )

        assert len(reference_trades) == 1
        assert reference_trades[0].asset == crypto_asset


class TestCreateReferencePortfolio:
    """Tests for create_reference_portfolio function."""

    def test_create_reference_simple_portfolio(self):
        """Test creating reference portfolio from SimplePortfolio."""
        # Create original portfolio
        original_portfolio = SimplePortfolio(name="My Portfolio")
        original_portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=Asset(ticker="GOOG", asset_type="Stock"),
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        # Create strategy
        reference_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset)

        # Mock price service
        price_service = MagicMock()
        price_service.get_historical_price.return_value = 400.0

        # Create currency service
        currency_service = CurrencyService()

        # Create reference portfolio
        reference_portfolio = create_reference_portfolio(
            original_portfolio=original_portfolio,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
        )

        # Verify result
        assert isinstance(reference_portfolio, SimplePortfolio)
        assert reference_portfolio.name == "My Portfolio (Reference)"
        assert reference_portfolio.is_historical == original_portfolio.is_historical

        reference_trades = reference_portfolio.get_all_trades()
        assert len(reference_trades) == 1
        assert reference_trades[0].asset == reference_asset
        assert reference_trades[0].total_value == 1500.0

    def test_create_reference_simple_portfolio_custom_name(self):
        """Test creating reference portfolio with custom name."""
        original_portfolio = SimplePortfolio(name="Original")
        strategy = BuyAndHoldStrategy(Asset(ticker="SPY", asset_type="ETF"))
        price_service = MagicMock()
        price_service.get_historical_price.return_value = 400.0
        currency_service = CurrencyService()

        reference_portfolio = create_reference_portfolio(
            original_portfolio=original_portfolio,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
            name="Custom Reference Name",
        )

        assert reference_portfolio.name == "Custom Reference Name"

    def test_create_reference_simple_portfolio_multiple_trades(self):
        """Test creating reference portfolio with multiple trades."""
        original_portfolio = SimplePortfolio(name="Multi Trade Portfolio")
        original_portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=Asset(ticker="GOOG", asset_type="Stock"),
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        original_portfolio.add_trade(
            Trade(
                date=date(2024, 2, 15),
                asset=Asset(ticker="AAPL", asset_type="Stock"),
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=180.0,
                price_native=180.0,
                quantity=5.0,
            )
        )

        strategy = BuyAndHoldStrategy(Asset(ticker="SPY", asset_type="ETF"))
        price_service = MagicMock()
        price_service.get_historical_price.return_value = 400.0
        currency_service = CurrencyService()

        reference_portfolio = create_reference_portfolio(
            original_portfolio=original_portfolio,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
        )

        reference_trades = reference_portfolio.get_all_trades()
        assert len(reference_trades) == 2
        # First trade: 1500.0 / 400.0 = 3.75 shares
        assert reference_trades[0].quantity == Decimal('3.75')
        # Second trade: 900.0 / 400.0 = 2.25 shares
        assert reference_trades[1].quantity == Decimal('2.25')

    def test_create_reference_simple_portfolio_historical(self):
        """Test creating reference portfolio preserves is_historical flag."""
        original_portfolio = SimplePortfolio(name="Historical", is_historical=True)
        original_portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=Asset(ticker="GOOG", asset_type="Stock"),
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        strategy = BuyAndHoldStrategy(Asset(ticker="SPY", asset_type="ETF"))
        price_service = MagicMock()
        price_service.get_historical_price.return_value = 400.0
        currency_service = CurrencyService()

        reference_portfolio = create_reference_portfolio(
            original_portfolio=original_portfolio,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
        )

        assert reference_portfolio.is_historical is True

    def test_create_reference_composite_portfolio(self):
        """Test creating reference portfolio from CompositePortfolio."""
        # Create original composite portfolio
        original_composite = CompositePortfolio(name="Composite Portfolio")
        
        sub_portfolio1 = SimplePortfolio(name="Sub Portfolio 1")
        sub_portfolio1.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=Asset(ticker="GOOG", asset_type="Stock"),
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )
        original_composite.add_sub_portfolio(sub_portfolio1)

        sub_portfolio2 = SimplePortfolio(name="Sub Portfolio 2")
        sub_portfolio2.add_trade(
            Trade(
                date=date(2024, 2, 15),
                asset=Asset(ticker="AAPL", asset_type="Stock"),
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=180.0,
                price_native=180.0,
                quantity=5.0,
            )
        )
        original_composite.add_sub_portfolio(sub_portfolio2)

        strategy = BuyAndHoldStrategy(Asset(ticker="SPY", asset_type="ETF"))
        price_service = MagicMock()
        price_service.get_historical_price.return_value = 400.0
        currency_service = CurrencyService()

        reference_portfolio = create_reference_portfolio(
            original_portfolio=original_composite,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
        )

        assert isinstance(reference_portfolio, CompositePortfolio)
        assert reference_portfolio.name == "Composite Portfolio (Reference)"
        
        reference_sub_portfolios = reference_portfolio.get_sub_portfolios()
        assert len(reference_sub_portfolios) == 2
        assert "Sub Portfolio 1 (Reference)" in reference_sub_portfolios
        assert "Sub Portfolio 2 (Reference)" in reference_sub_portfolios

    def test_create_reference_portfolio_empty(self):
        """Test creating reference portfolio from empty portfolio."""
        original_portfolio = SimplePortfolio(name="Empty Portfolio")
        
        strategy = BuyAndHoldStrategy(Asset(ticker="SPY", asset_type="ETF"))
        price_service = MagicMock()
        currency_service = CurrencyService()

        reference_portfolio = create_reference_portfolio(
            original_portfolio=original_portfolio,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
        )

        assert len(reference_portfolio.get_all_trades()) == 0

    def test_create_reference_portfolio_error_handling(self):
        """Test error handling when price service fails."""
        original_portfolio = SimplePortfolio(name="Test Portfolio")
        original_portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=Asset(ticker="GOOG", asset_type="Stock"),
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        strategy = BuyAndHoldStrategy(Asset(ticker="SPY", asset_type="ETF"))
        price_service = MagicMock()
        price_service.get_historical_price.side_effect = ValueError(
            "No historical price data available"
        )
        currency_service = CurrencyService()

        with pytest.raises(ValueError, match="Cannot create reference portfolio"):
            create_reference_portfolio(
                original_portfolio=original_portfolio,
                strategy=strategy,
                price_service=price_service,
                currency_service=currency_service,
            )

    def test_create_reference_portfolio_with_get_historical_performance(self):
        """Test that reference portfolio works with get_historical_performance()."""
        from wpm.portfolio import get_historical_performance

        # Create original portfolio
        original_portfolio = SimplePortfolio(name="Test", is_historical=True)
        original_portfolio.add_trade(
            Trade(
                date=date(2024, 1, 15),
                asset=Asset(ticker="GOOG", asset_type="Stock"),
                action="Buy",
                broker="IBKR",
                currency="USD",
                price=150.0,
                price_native=150.0,
                quantity=10.0,
            )
        )

        # Create reference portfolio
        strategy = BuyAndHoldStrategy(Asset(ticker="SPY", asset_type="ETF"))
        price_service = MagicMock()
        currency_service = CurrencyService()
        
        # Mock historical prices for different dates
        def mock_get_historical_price(ticker, asset_type, target_date, in_native_currency):
            if ticker == "SPY" and target_date == date(2024, 1, 15):
                return 400.0
            elif ticker == "SPY" and target_date == date(2024, 1, 16):
                return 401.0
            elif ticker == "SPY" and target_date == date(2024, 1, 17):
                return 402.0
            raise ValueError(f"No price for {ticker} on {target_date}")
        
        price_service.get_historical_price.side_effect = mock_get_historical_price
        
        # Mock get_historical_prices for get_historical_performance and prefetch
        def mock_get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False, cached_prices_only=False):
            if "SPY" in tickers:
                return {
                    "SPY": {
                        date(2024, 1, 15): 400.0,
                        date(2024, 1, 16): 401.0,
                        date(2024, 1, 17): 402.0,
                    }
                }
            return {}
        
        price_service.get_historical_prices.side_effect = mock_get_historical_prices

        reference_portfolio = create_reference_portfolio(
            original_portfolio=original_portfolio,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
        )

        # Verify reference portfolio can be used with get_historical_performance
        # This should not raise an error
        history_points = get_historical_performance(
            portfolio=reference_portfolio,
            price_service=price_service,
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 17),
        )

        assert len(history_points) == 3
        # First day: 3.75 shares * $400 = $1500
        assert abs(history_points[0].total_market_value - 1500.0) < 0.01
        # Second day: 3.75 shares * $401 = $1503.75
        assert abs(history_points[1].total_market_value - 1503.75) < 0.01
        # Third day: 3.75 shares * $402 = $1507.50
        assert abs(history_points[2].total_market_value - 1507.50) < 0.01


class TestReferenceStrategyPrepare:
    """Tests for ReferenceStrategy.prepare() method."""

    def test_default_implementation_does_nothing(self):
        """Test that default prepare() implementation does nothing."""
        # Create a concrete strategy that doesn't override prepare()
        class TestStrategy(ReferenceStrategy):
            def generate_trades(self, original_trade, price_service, currency_service, price_fetcher=None):
                return []
        
        strategy = TestStrategy()
        portfolio = SimplePortfolio(name="Test")
        mock_fetcher = MagicMock()
        
        # Should not raise and should not call fetcher
        strategy.prepare(portfolio, mock_fetcher)
        mock_fetcher.prefetch_prices.assert_not_called()

    def test_buy_and_hold_strategy_prepare_calls_fetcher(self):
        """Test that BuyAndHoldStrategy.prepare() calls fetcher.prefetch_prices()."""
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
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
        
        mock_fetcher = MagicMock()
        
        strategy.prepare(portfolio, mock_fetcher)
        
        # Verify prefetch_prices was called with correct arguments
        mock_fetcher.prefetch_prices.assert_called_once()
        call_args = mock_fetcher.prefetch_prices.call_args
        assert call_args[0][0] == spy_asset  # asset
        assert call_args[0][1] == date(2024, 1, 8)  # start_date - 7 days
        assert call_args[0][2] == date(2024, 1, 15)  # end_date

    def test_buy_and_hold_strategy_prepare_with_end_date_none(self):
        """Test BuyAndHoldStrategy.prepare() when portfolio.end_date is None."""
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        portfolio = SimplePortfolio(name="Test")
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
            date=date(2024, 1, 20),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=151.0,
            price_native=151.0,
            quantity=5.0,
        )
        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)
        
        mock_fetcher = MagicMock()
        
        strategy.prepare(portfolio, mock_fetcher)
        
        # Verify prefetch_prices was called with max trade date as end_date
        call_args = mock_fetcher.prefetch_prices.call_args
        assert call_args[0][2] == date(2024, 1, 20)  # max trade date

    def test_buy_and_hold_strategy_prepare_with_no_start_date(self):
        """Test BuyAndHoldStrategy.prepare() when portfolio has no start_date."""
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        portfolio = SimplePortfolio(name="Test")  # Empty portfolio
        
        mock_fetcher = MagicMock()
        
        strategy.prepare(portfolio, mock_fetcher)
        
        # Should not call prefetch_prices when no start_date
        mock_fetcher.prefetch_prices.assert_not_called()

    def test_buy_and_hold_strategy_prepare_with_empty_portfolio(self):
        """Test BuyAndHoldStrategy.prepare() with empty portfolio."""
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        portfolio = SimplePortfolio(name="Test")
        # Add and then remove trade to create portfolio with no trades
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
        # Remove the trade
        portfolio._trades = []
        
        mock_fetcher = MagicMock()
        
        strategy.prepare(portfolio, mock_fetcher)
        
        # Should not call prefetch_prices when no trades
        mock_fetcher.prefetch_prices.assert_not_called()


class TestHistoricalPriceFetcher:
    """Tests for HistoricalPriceFetcher interface."""

    def test_abstract_class_cannot_be_instantiated(self):
        """Test that HistoricalPriceFetcher abstract class cannot be instantiated."""
        with pytest.raises(TypeError):
            HistoricalPriceFetcher()

    def test_concrete_implementation_must_implement_get_historical_price(self):
        """Test that concrete implementations must implement get_historical_price."""
        
        class IncompleteFetcher(HistoricalPriceFetcher):
            pass
        
        with pytest.raises(TypeError):
            IncompleteFetcher()

    def test_concrete_implementation_must_implement_prefetch_prices(self):
        """Test that concrete implementations must implement prefetch_prices."""
        
        class IncompleteFetcher(HistoricalPriceFetcher):
            def get_historical_price(self, asset, target_date):
                return 100.0
        
        with pytest.raises(TypeError):
            IncompleteFetcher()


class TestDefaultHistoricalPriceFetcher:
    """Tests for DefaultHistoricalPriceFetcher implementation."""

    def test_init_with_default_lookback(self):
        """Test initializing fetcher with default lookback_days."""
        mock_price_service = MagicMock()
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service)
        assert fetcher.price_service == mock_price_service
        assert fetcher.lookback_days == 7
        assert fetcher._price_cache == {}
        assert fetcher._cache_asset is None

    def test_init_with_custom_lookback(self):
        """Test initializing fetcher with custom lookback_days."""
        mock_price_service = MagicMock()
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service, lookback_days=14)
        assert fetcher.lookback_days == 14

    def test_prefetch_prices_success(self):
        """Test successful prefetch populates cache."""
        mock_price_service = MagicMock()
        mock_price_service.get_historical_prices.return_value = {
            "SPY": {
                date(2024, 1, 8): 400.0,
                date(2024, 1, 9): 401.0,
                date(2024, 1, 10): 402.0,
                date(2024, 1, 11): 403.0,
                date(2024, 1, 12): 404.0,
                date(2024, 1, 15): 405.0,
            }
        }
        
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service)
        asset = Asset(ticker="SPY", asset_type="ETF")
        
        fetcher.prefetch_prices(asset, date(2024, 1, 8), date(2024, 1, 15))
        
        # Verify cache was populated
        assert fetcher._cache_asset == asset
        assert len(fetcher._price_cache) == 6
        assert fetcher._price_cache[date(2024, 1, 15)] == 405.0
        
        # Verify get_historical_prices was called with cached_prices_only=False
        mock_price_service.get_historical_prices.assert_called_once_with(
            ["SPY"], "ETF", date(2024, 1, 8), date(2024, 1, 15),
            cached_prices_only=False
        )

    def test_prefetch_prices_handles_error(self):
        """Test prefetch handles errors gracefully."""
        mock_price_service = MagicMock()
        mock_price_service.get_historical_prices.side_effect = ValueError("No prices available")
        
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service)
        asset = Asset(ticker="SPY", asset_type="ETF")
        
        # Should not raise, just log warning
        fetcher.prefetch_prices(asset, date(2024, 1, 8), date(2024, 1, 15))
        
        # Cache should remain empty
        assert fetcher._price_cache == {}
        assert fetcher._cache_asset is None

    def test_prefetch_prices_clears_cache_for_different_asset(self):
        """Test prefetch clears cache when prefetching different asset."""
        mock_price_service = MagicMock()
        mock_price_service.get_historical_prices.return_value = {
            "SPY": {date(2024, 1, 15): 400.0},
        }
        
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service)
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        qqq_asset = Asset(ticker="QQQ", asset_type="ETF")
        
        # Prefetch SPY
        fetcher.prefetch_prices(spy_asset, date(2024, 1, 15), date(2024, 1, 15))
        assert fetcher._cache_asset == spy_asset
        assert date(2024, 1, 15) in fetcher._price_cache
        assert fetcher._price_cache[date(2024, 1, 15)] == 400.0
        
        # Prefetch QQQ - should replace cache
        mock_price_service.get_historical_prices.return_value = {
            "QQQ": {date(2024, 1, 15): 300.0}
        }
        fetcher.prefetch_prices(qqq_asset, date(2024, 1, 15), date(2024, 1, 15))
        assert fetcher._cache_asset == qqq_asset
        assert fetcher._price_cache[date(2024, 1, 15)] == 300.0

    def test_get_historical_price_from_cache(self):
        """Test getting price from internal cache."""
        mock_price_service = MagicMock()
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service)
        asset = Asset(ticker="SPY", asset_type="ETF")
        
        # Pre-populate cache
        fetcher._price_cache = {
            date(2024, 1, 15): 400.0,
            date(2024, 1, 16): 401.0,
        }
        fetcher._cache_asset = asset
        
        price = fetcher.get_historical_price(asset, date(2024, 1, 15))
        
        assert price == 400.0
        # Should not call price service when cache hit
        mock_price_service.get_historical_price.assert_not_called()

    def test_get_historical_price_from_cache_weekend_fallback(self):
        """Test getting price from cache for weekend date (finds previous trading day)."""
        mock_price_service = MagicMock()
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service)
        asset = Asset(ticker="SPY", asset_type="ETF")
        
        # Pre-populate cache with Friday price
        fetcher._price_cache = {
            date(2024, 1, 12): 400.0,  # Friday
            date(2024, 1, 15): 401.0,  # Monday
        }
        fetcher._cache_asset = asset
        
        # Request Saturday - should return Friday's price
        price = fetcher.get_historical_price(asset, date(2024, 1, 13))  # Saturday
        
        assert price == 400.0  # Friday's price
        mock_price_service.get_historical_price.assert_not_called()

    def test_get_historical_price_exact_date_success(self):
        """Test getting price for exact date when cache miss."""
        mock_price_service = MagicMock()
        mock_price_service.get_historical_price.return_value = 400.0
        
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service)
        asset = Asset(ticker="SPY", asset_type="ETF")
        target_date = date(2024, 1, 15)  # Monday
        
        price = fetcher.get_historical_price(asset, target_date)
        
        assert price == 400.0
        mock_price_service.get_historical_price.assert_called_once_with(
            ticker="SPY",
            asset_type="ETF",
            target_date=target_date,
            in_native_currency=False,
        )
        mock_price_service.get_historical_prices.assert_not_called()

    def test_get_historical_price_weekend_with_lookback(self):
        """Test getting price for weekend date using lookback (finds Friday's price)."""
        mock_price_service = MagicMock()
        # Exact date fails (weekend)
        mock_price_service.get_historical_price.side_effect = ValueError("No price available")
        # Lookback succeeds with Friday's price
        mock_price_service.get_historical_prices.return_value = {
            "SPY": {
                date(2024, 1, 12): 395.0,  # Friday
                date(2024, 1, 13): 395.0,  # Saturday (NaN in real data)
                date(2024, 1, 14): 395.0,  # Sunday (NaN in real data)
            }
        }
        
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service, lookback_days=7)
        asset = Asset(ticker="SPY", asset_type="ETF")
        target_date = date(2024, 1, 13)  # Saturday
        
        price = fetcher.get_historical_price(asset, target_date)
        
        # Should return Friday's price (most recent <= Saturday)
        assert price == 395.0
        mock_price_service.get_historical_price.assert_called_once()
        mock_price_service.get_historical_prices.assert_called_once_with(
            ["SPY"],
            "ETF",
            date(2024, 1, 6),  # 7 days before Saturday
            date(2024, 1, 13),  # Saturday
            cached_prices_only=True,  # Should use cached_prices_only=True
        )

    def test_get_historical_price_sunday_with_lookback(self):
        """Test getting price for Sunday date using lookback (finds Friday's price)."""
        mock_price_service = MagicMock()
        mock_price_service.get_historical_price.side_effect = ValueError("No price available")
        mock_price_service.get_historical_prices.return_value = {
            "SPY": {
                date(2024, 1, 12): 395.0,  # Friday
            }
        }
        
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service, lookback_days=7)
        asset = Asset(ticker="SPY", asset_type="ETF")
        target_date = date(2024, 1, 14)  # Sunday
        
        price = fetcher.get_historical_price(asset, target_date)
        
        assert price == 395.0

    def test_get_historical_price_no_price_within_lookback(self):
        """Test failure when no price found within lookback period."""
        mock_price_service = MagicMock()
        mock_price_service.get_historical_price.side_effect = ValueError("No price available")
        mock_price_service.get_historical_prices.return_value = {}  # No prices
        
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service, lookback_days=7)
        asset = Asset(ticker="SPY", asset_type="ETF")
        target_date = date(2024, 1, 13)  # Saturday
        
        with pytest.raises(ValueError, match="No historical price data available for SPY"):
            fetcher.get_historical_price(asset, target_date)

    def test_get_historical_price_no_available_dates_before_target(self):
        """Test failure when lookback returns prices but none before target_date."""
        mock_price_service = MagicMock()
        mock_price_service.get_historical_price.side_effect = ValueError("No price available")
        # Prices exist but all after target_date
        mock_price_service.get_historical_prices.return_value = {
            "SPY": {
                date(2024, 1, 20): 400.0,  # After target_date
            }
        }
        
        fetcher = DefaultHistoricalPriceFetcher(price_service=mock_price_service, lookback_days=7)
        asset = Asset(ticker="SPY", asset_type="ETF")
        target_date = date(2024, 1, 13)  # Saturday
        
        with pytest.raises(ValueError, match="No historical price data available for SPY.*on or before"):
            fetcher.get_historical_price(asset, target_date)


class TestReferencePortfolioStrategyPrepare:
    """Tests for strategy prepare phase in reference portfolio creation."""

    def test_strategy_prepare_called_before_trade_processing(self):
        """Test that strategy.prepare() is called before processing trades."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 15),  # Monday
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)

        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        mock_price_service = MagicMock()
        mock_price_service.get_historical_price.return_value = 400.0
        mock_price_service.get_historical_prices.return_value = {
            "SPY": {
                date(2024, 1, 8): 395.0,
                date(2024, 1, 9): 396.0,
                date(2024, 1, 10): 397.0,
                date(2024, 1, 11): 398.0,
                date(2024, 1, 12): 399.0,
                date(2024, 1, 15): 400.0,
            }
        }
        
        currency_service = CurrencyService()
        
        create_reference_portfolio(
            original_portfolio=portfolio,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
        )
        
        # Verify get_historical_prices was called for prefetch (entire portfolio range)
        prefill_calls = [
            call for call in mock_price_service.get_historical_prices.call_args_list
            if call[0][0] == ["SPY"] and call[0][1] == "ETF"
        ]
        assert len(prefill_calls) > 0
        # Check that prefetch range covers entire portfolio (start_date - 7 to end_date)
        prefill_call = prefill_calls[0]
        prefill_start = prefill_call[0][2]
        prefill_end = prefill_call[0][3]
        assert prefill_start == date(2024, 1, 8)  # start_date - 7 days
        assert prefill_end == date(2024, 1, 15)  # end_date (same as start_date for single trade)
        # Verify cached_prices_only=False for prefetch
        assert prefill_call[1].get("cached_prices_only", False) is False

    def test_strategy_prepare_handles_empty_portfolio(self):
        """Test that strategy.prepare() handles empty portfolios gracefully."""
        portfolio = SimplePortfolio(name="Empty Portfolio")
        
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        mock_price_service = MagicMock()
        currency_service = CurrencyService()
        
        # Should not raise error
        result = create_reference_portfolio(
            original_portfolio=portfolio,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
        )
        
        assert result is not None
        # Prefetch should not be called for empty portfolio
        mock_price_service.get_historical_prices.assert_not_called()


class TestCryptoWeekendReferenceTrade:
    """Integration tests for crypto trade on weekend -> SPY reference trade scenario."""

    def test_crypto_trade_on_saturday_creates_spy_reference_trade(self):
        """Test that crypto trade on Saturday successfully creates SPY reference trade."""
        portfolio = SimplePortfolio(name="Crypto Portfolio")
        # Saturday, May 17, 2025
        crypto_trade = Trade(
            date=date(2025, 5, 17),  # Saturday
            asset=Asset(ticker="BTC-USD", asset_type="Crypto"),
            action="Buy",
            broker="Coinbase",
            currency="USD",
            price=50000.0,
            price_native=50000.0,
            quantity=0.1,
        )
        portfolio.add_trade(crypto_trade)

        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        mock_price_service = MagicMock()
        # Prefetch call (from strategy.prepare()) - should succeed
        # Exact date (Saturday) fails - market closed
        mock_price_service.get_historical_price.side_effect = ValueError("No price available")
        # Prefetch and lookback succeed with Friday's price
        prefetch_prices = {
            "SPY": {
                date(2025, 5, 10): 580.0,
                date(2025, 5, 11): 581.0,
                date(2025, 5, 12): 582.0,
                date(2025, 5, 13): 583.0,
                date(2025, 5, 14): 584.0,
                date(2025, 5, 15): 585.0,
                date(2025, 5, 16): 586.0,  # Friday
                date(2025, 5, 17): 586.0,  # Saturday (NaN in real data, but we'll have Friday's)
            }
        }
        mock_price_service.get_historical_prices.return_value = prefetch_prices
        
        currency_service = CurrencyService()
        
        reference_portfolio = create_reference_portfolio(
            original_portfolio=portfolio,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
        )
        
        # Verify reference portfolio was created
        assert reference_portfolio is not None
        reference_trades = reference_portfolio.get_all_trades()
        assert len(reference_trades) == 1
        
        reference_trade = reference_trades[0]
        assert reference_trade.date == date(2025, 5, 17)  # Same date as original
        assert reference_trade.asset == spy_asset
        assert reference_trade.action == "Buy"
        # Cost basis: 50000.0 * 0.1 = 5000.0
        # Price: 586.0 (Friday's price via cache lookup)
        # Quantity: 5000.0 / 586.0 ≈ 8.532
        expected_quantity = Decimal("5000.0") / Decimal("586.0")
        assert abs(float(reference_trade.quantity) - float(expected_quantity)) < 0.01
        
        # Verify prefetch was called (from strategy.prepare())
        prefetch_calls = [
            call for call in mock_price_service.get_historical_prices.call_args_list
            if call[0][0] == ["SPY"] and call[0][1] == "ETF" and call[1].get("cached_prices_only", False) is False
        ]
        assert len(prefetch_calls) > 0

    def test_crypto_trade_on_sunday_creates_spy_reference_trade(self):
        """Test that crypto trade on Sunday successfully creates SPY reference trade."""
        portfolio = SimplePortfolio(name="Crypto Portfolio")
        # Sunday, May 18, 2025
        crypto_trade = Trade(
            date=date(2025, 5, 18),  # Sunday
            asset=Asset(ticker="ETH-USD", asset_type="Crypto"),
            action="Buy",
            broker="Coinbase",
            currency="USD",
            price=3000.0,
            price_native=3000.0,
            quantity=1.0,
        )
        portfolio.add_trade(crypto_trade)

        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        mock_price_service = MagicMock()
        mock_price_service.get_historical_price.side_effect = ValueError("No price available")
        # Prefetch prices (from strategy.prepare())
        mock_price_service.get_historical_prices.return_value = {
            "SPY": {
                date(2025, 5, 11): 580.0,
                date(2025, 5, 12): 581.0,
                date(2025, 5, 13): 582.0,
                date(2025, 5, 14): 583.0,
                date(2025, 5, 15): 584.0,
                date(2025, 5, 16): 586.0,  # Friday (most recent before Sunday)
                date(2025, 5, 17): 586.0,  # Saturday
                date(2025, 5, 18): 586.0,  # Sunday
            }
        }
        
        currency_service = CurrencyService()
        
        reference_portfolio = create_reference_portfolio(
            original_portfolio=portfolio,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
        )
        
        # Verify reference portfolio was created
        assert reference_portfolio is not None
        reference_trades = reference_portfolio.get_all_trades()
        assert len(reference_trades) == 1
        
        reference_trade = reference_trades[0]
        assert reference_trade.date == date(2025, 5, 18)  # Same date as original
        assert reference_trade.asset == spy_asset
        # Cost basis: 3000.0 * 1.0 = 3000.0
        # Price: 586.0 (Friday's price via cache lookup)
        # Quantity: 3000.0 / 586.0 ≈ 5.119
        expected_quantity = Decimal("3000.0") / Decimal("586.0")
        assert abs(float(reference_trade.quantity) - float(expected_quantity)) < 0.01

    def test_multiple_trades_with_weekends(self):
        """Test multiple trades including weekends all succeed."""
        portfolio = SimplePortfolio(name="Mixed Portfolio")
        
        # Add trades on different days including weekends
        trades = [
            Trade(
                date=date(2025, 5, 15),  # Thursday
                asset=Asset(ticker="BTC-USD", asset_type="Crypto"),
                action="Buy",
                broker="Coinbase",
                currency="USD",
                price=50000.0,
                price_native=50000.0,
                quantity=0.1,
            ),
            Trade(
                date=date(2025, 5, 17),  # Saturday
                asset=Asset(ticker="ETH-USD", asset_type="Crypto"),
                action="Buy",
                broker="Coinbase",
                currency="USD",
                price=3000.0,
                price_native=3000.0,
                quantity=1.0,
            ),
            Trade(
                date=date(2025, 5, 18),  # Sunday
                asset=Asset(ticker="BTC-USD", asset_type="Crypto"),
                action="Buy",
                broker="Coinbase",
                currency="USD",
                price=51000.0,
                price_native=51000.0,
                quantity=0.05,
            ),
        ]
        
        for trade in trades:
            portfolio.add_trade(trade)

        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        
        mock_price_service = MagicMock()
        # Exact date calls - Thursday succeeds, weekends fail
        def mock_get_historical_price(ticker, asset_type, target_date, in_native_currency):
            if target_date == date(2025, 5, 15):
                return 585.0  # Thursday - market open
            raise ValueError("No price available")  # Weekends fail
        
        mock_price_service.get_historical_price.side_effect = mock_get_historical_price
        # Prefetch prices (from strategy.prepare()) - covers entire range
        mock_price_service.get_historical_prices.return_value = {
            "SPY": {
                date(2025, 5, 8): 580.0,
                date(2025, 5, 9): 581.0,
                date(2025, 5, 10): 582.0,
                date(2025, 5, 11): 583.0,
                date(2025, 5, 12): 584.0,
                date(2025, 5, 13): 585.0,
                date(2025, 5, 14): 586.0,
                date(2025, 5, 15): 585.0,
                date(2025, 5, 16): 586.0,  # Friday
                date(2025, 5, 17): 586.0,  # Saturday (NaN in real data)
                date(2025, 5, 18): 586.0,  # Sunday (NaN in real data)
            }
        }
        
        currency_service = CurrencyService()
        
        reference_portfolio = create_reference_portfolio(
            original_portfolio=portfolio,
            strategy=strategy,
            price_service=mock_price_service,
            currency_service=currency_service,
        )
        
        # Verify all reference trades were created
        assert reference_portfolio is not None
        reference_trades = reference_portfolio.get_all_trades()
        assert len(reference_trades) == 3
        
        # Verify each trade was created successfully
        for i, ref_trade in enumerate(reference_trades):
            assert ref_trade.date == trades[i].date
            assert ref_trade.asset == spy_asset
            assert ref_trade.action == "Buy"
