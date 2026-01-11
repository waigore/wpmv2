"""Tests for historical portfolio performance functionality."""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from wpm.models import Asset, PortfolioError, PortfolioHistoryPoint, Trade
from wpm.portfolio import (
    CompositePortfolio,
    SimplePortfolio,
    get_historical_performance,
)
from wpm.pricing import PriceService


class TestGetHistoricalPerformanceSimplePortfolio:
    """Tests for get_historical_performance with SimplePortfolio."""

    def test_basic_historical_performance(self):
        """Test basic historical performance calculation."""
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

        # Mock price service
        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_prices.return_value = {"GOOG": 155.0}

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 17)

        history_points = get_historical_performance(
            portfolio, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 3  # 15th, 16th, 17th
        assert all(isinstance(point, PortfolioHistoryPoint) for point in history_points)
        assert history_points[0].date == date(2024, 1, 15)
        assert history_points[1].date == date(2024, 1, 16)
        assert history_points[2].date == date(2024, 1, 17)

        # Check that price service was called for each date
        assert mock_price_service.get_historical_prices.call_count == 3

        # Check first day (trade date)
        assert "GOOG" in history_points[0].asset_positions
        assert history_points[0].asset_positions["GOOG"] == 10.0 * 155.0
        assert history_points[0].total_market_value == 10.0 * 155.0

    def test_asset_purchased_after_start_date(self):
        """Test asset purchased after start_date shows 0.0 position before purchase."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="AAPL", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 20),  # Purchased on 20th
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=180.0,
            price_native=180.0,
            quantity=5.0,
        )
        portfolio.add_trade(trade)

        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_prices.return_value = {"AAPL": 185.0}

        start_date = date(2024, 1, 15)  # Start before purchase
        end_date = date(2024, 1, 22)

        history_points = get_historical_performance(
            portfolio, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 8  # 15th-22nd inclusive

        # Days before purchase (15th-19th) should have 0.0 position
        for i in range(5):  # First 5 days
            assert history_points[i].asset_positions["AAPL"] == 0.0
            assert history_points[i].total_market_value == 0.0

        # Days on and after purchase (20th-22nd) should have position
        for i in range(5, 8):  # Last 3 days
            assert history_points[i].asset_positions["AAPL"] == 5.0 * 185.0
            assert history_points[i].total_market_value == 5.0 * 185.0

    def test_asset_sold_before_end_date(self):
        """Test asset sold before end_date shows 0.0 position after sale."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="MSFT", asset_type="Stock")
        buy_trade = Trade(
            date=date(2024, 1, 10),
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=300.0,
            price_native=300.0,
            quantity=10.0,
        )
        sell_trade = Trade(
            date=date(2024, 1, 20),  # Sold on 20th
            asset=asset,
            action="Sell",
            broker="IBKR",
            currency="USD",
            price=320.0,
            price_native=320.0,
            quantity=10.0,
        )
        portfolio.add_trade(buy_trade)
        portfolio.add_trade(sell_trade)

        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_prices.return_value = {"MSFT": 310.0}

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 25)

        history_points = get_historical_performance(
            portfolio, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 11  # 15th-25th inclusive

        # Days before sale (15th-19th) should have position
        for i in range(5):  # First 5 days (15th-19th)
            assert history_points[i].asset_positions["MSFT"] > 0.0
            assert history_points[i].total_market_value > 0.0

        # On sell date (20th), the sell trade is included in the clone, so position should be 0
        assert history_points[5].date == date(2024, 1, 20)
        assert history_points[5].asset_positions["MSFT"] == 0.0
        assert history_points[5].total_market_value == 0.0

        # Days after sale (21st-25th) should have 0.0 position
        for i in range(6, 11):  # Last 5 days
            assert history_points[i].asset_positions["MSFT"] == 0.0
            assert history_points[i].total_market_value == 0.0

    def test_multiple_assets_different_purchase_dates(self):
        """Test multiple assets with different purchase dates."""
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
            date=date(2024, 1, 20),  # Purchased later
            asset=asset2,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=180.0,
            price_native=180.0,
            quantity=5.0,
        )
        portfolio.add_trade(trade1)
        portfolio.add_trade(trade2)

        mock_price_service = Mock(spec=PriceService)

        def mock_get_historical_prices(tickers, asset_type, start_date, end_date):
            prices = {}
            if "GOOG" in tickers:
                prices["GOOG"] = 155.0
            if "AAPL" in tickers:
                prices["AAPL"] = 185.0
            return prices

        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 22)

        history_points = get_historical_performance(
            portfolio, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 8

        # All history points should have both assets in asset_positions
        for point in history_points:
            assert "GOOG" in point.asset_positions
            assert "AAPL" in point.asset_positions

        # Days before AAPL purchase (15th-19th)
        for i in range(5):
            assert history_points[i].asset_positions["GOOG"] == 10.0 * 155.0
            assert history_points[i].asset_positions["AAPL"] == 0.0
            assert history_points[i].total_market_value == 10.0 * 155.0

        # Days after AAPL purchase (20th-22nd)
        for i in range(5, 8):
            assert history_points[i].asset_positions["GOOG"] == 10.0 * 155.0
            assert history_points[i].asset_positions["AAPL"] == 5.0 * 185.0
            assert history_points[i].total_market_value == (10.0 * 155.0) + (5.0 * 185.0)

    def test_missing_prices_raises_error(self):
        """Test that missing prices raise ValueError."""
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

        mock_price_service = Mock(spec=PriceService)
        # Return empty dict (no prices)
        mock_price_service.get_historical_prices.return_value = {}

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 16)

        with pytest.raises(ValueError, match="Historical prices unavailable for tickers"):
            get_historical_performance(
                portfolio, mock_price_service, start_date, end_date
            )

    def test_invalid_date_range_raises_error(self):
        """Test that invalid date range raises PortfolioError."""
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

        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_prices.return_value = {"GOOG": 155.0}

        # Start date after end date - should still raise error
        with pytest.raises(PortfolioError, match="start_date.*is after end_date"):
            get_historical_performance(
                portfolio, mock_price_service, date(2024, 1, 20), date(2024, 1, 15)
            )

        # Note: We no longer validate start_date before portfolio_start or
        # end_date after portfolio_end, as these are allowed for calculating
        # performance across any date range (assets will show 0 positions
        # before purchase or after portfolio end_date)

    def test_empty_portfolio(self):
        """Test empty portfolio returns history points with zero values."""
        portfolio = SimplePortfolio(name="Empty Portfolio")

        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_prices.return_value = {}

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 17)

        history_points = get_historical_performance(
            portfolio, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 3
        for point in history_points:
            assert point.total_market_value == 0.0
            assert point.asset_positions == {}

    def test_single_day_range(self):
        """Test single day range (start_date == end_date)."""
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

        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_prices.return_value = {"GOOG": 155.0}

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 15)

        history_points = get_historical_performance(
            portfolio, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 1
        assert history_points[0].date == date(2024, 1, 15)
        assert history_points[0].asset_positions["GOOG"] == 10.0 * 155.0
        assert history_points[0].total_market_value == 10.0 * 155.0

    def test_weekend_dates(self):
        """Test weekend dates (markets closed but portfolio state valid)."""
        portfolio = SimplePortfolio(name="Test Portfolio")
        asset = Asset(ticker="GOOG", asset_type="Stock")
        trade = Trade(
            date=date(2024, 1, 12),  # Friday
            asset=asset,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio.add_trade(trade)

        mock_price_service = Mock(spec=PriceService)
        # Should still return prices for weekends (using last available price)
        mock_price_service.get_historical_prices.return_value = {"GOOG": 155.0}

        start_date = date(2024, 1, 13)  # Saturday
        end_date = date(2024, 1, 14)  # Sunday

        history_points = get_historical_performance(
            portfolio, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 2
        assert history_points[0].date == date(2024, 1, 13)  # Saturday
        assert history_points[1].date == date(2024, 1, 14)  # Sunday
        # Portfolio state should be valid even on weekends
        assert history_points[0].asset_positions["GOOG"] == 10.0 * 155.0
        assert history_points[1].asset_positions["GOOG"] == 10.0 * 155.0


class TestGetHistoricalPerformanceCompositePortfolio:
    """Tests for get_historical_performance with CompositePortfolio."""

    def test_asset_position_merging(self):
        """Test asset positions from sub-portfolios are merged."""
        # Create sub-portfolio 1 with BTC-USD
        portfolio1 = SimplePortfolio(name="P1")
        asset1 = Asset(ticker="BTC-USD", asset_type="Crypto")
        trade1 = Trade(
            date=date(2024, 1, 15),
            asset=asset1,
            action="Buy",
            broker="Coinbase",
            currency="USD",
            price=40000.0,
            price_native=40000.0,
            quantity=0.5,
        )
        portfolio1.add_trade(trade1)

        # Create sub-portfolio 2 with same ticker BTC-USD
        portfolio2 = SimplePortfolio(name="P2")
        asset2 = Asset(ticker="BTC-USD", asset_type="Crypto")
        trade2 = Trade(
            date=date(2024, 1, 15),
            asset=asset2,
            action="Buy",
            broker="Binance",
            currency="USD",
            price=40000.0,
            price_native=40000.0,
            quantity=0.3,
        )
        portfolio2.add_trade(trade2)

        # Create composite portfolio
        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio1)
        composite.add_sub_portfolio(portfolio2)

        mock_price_service = Mock(spec=PriceService)
        mock_price_service.get_historical_prices.return_value = {"BTC-USD": 45000.0}

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 17)

        history_points = get_historical_performance(
            composite, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 3

        # Positions should be merged (0.5 + 0.3 = 0.8)
        for point in history_points:
            assert "BTC-USD" in point.asset_positions
            # Total position value should be (0.5 + 0.3) * 45000.0 = 36000.0
            assert point.asset_positions["BTC-USD"] == 0.8 * 45000.0
            assert point.total_market_value == 0.8 * 45000.0

    def test_different_assets_in_sub_portfolios(self):
        """Test different assets in sub-portfolios are tracked separately."""
        portfolio1 = SimplePortfolio(name="P1")
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
        portfolio1.add_trade(trade1)

        portfolio2 = SimplePortfolio(name="P2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        trade2 = Trade(
            date=date(2024, 1, 15),
            asset=asset2,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=180.0,
            price_native=180.0,
            quantity=5.0,
        )
        portfolio2.add_trade(trade2)

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio1)
        composite.add_sub_portfolio(portfolio2)

        mock_price_service = Mock(spec=PriceService)

        def mock_get_historical_prices(tickers, asset_type, start_date, end_date):
            prices = {}
            if "GOOG" in tickers:
                prices["GOOG"] = 155.0
            if "AAPL" in tickers:
                prices["AAPL"] = 185.0
            return prices

        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 17)

        history_points = get_historical_performance(
            composite, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 3

        # Both assets should be present in all history points
        for point in history_points:
            assert "GOOG" in point.asset_positions
            assert "AAPL" in point.asset_positions
            assert point.asset_positions["GOOG"] == 10.0 * 155.0
            assert point.asset_positions["AAPL"] == 5.0 * 185.0
            assert point.total_market_value == (10.0 * 155.0) + (5.0 * 185.0)

    def test_sub_portfolios_with_different_date_ranges(self):
        """Test sub-portfolios with different date ranges."""
        portfolio1 = SimplePortfolio(name="P1")
        asset1 = Asset(ticker="GOOG", asset_type="Stock")
        trade1 = Trade(
            date=date(2024, 1, 10),  # Earlier start
            asset=asset1,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=150.0,
            price_native=150.0,
            quantity=10.0,
        )
        portfolio1.add_trade(trade1)

        portfolio2 = SimplePortfolio(name="P2")
        asset2 = Asset(ticker="AAPL", asset_type="Stock")
        trade2 = Trade(
            date=date(2024, 1, 20),  # Later start
            asset=asset2,
            action="Buy",
            broker="IBKR",
            currency="USD",
            price=180.0,
            price_native=180.0,
            quantity=5.0,
        )
        portfolio2.add_trade(trade2)

        composite = CompositePortfolio(name="Composite")
        composite.add_sub_portfolio(portfolio1)
        composite.add_sub_portfolio(portfolio2)

        mock_price_service = Mock(spec=PriceService)

        def mock_get_historical_prices(tickers, asset_type, start_date, end_date):
            prices = {}
            if "GOOG" in tickers:
                prices["GOOG"] = 155.0
            if "AAPL" in tickers:
                prices["AAPL"] = 185.0
            return prices

        mock_price_service.get_historical_prices.side_effect = mock_get_historical_prices

        start_date = date(2024, 1, 15)
        end_date = date(2024, 1, 25)

        history_points = get_historical_performance(
            composite, mock_price_service, start_date, end_date
        )

        assert len(history_points) == 11

        # Days before AAPL purchase (15th-19th) - only GOOG should have position
        for i in range(5):
            assert history_points[i].asset_positions["GOOG"] == 10.0 * 155.0
            assert history_points[i].asset_positions["AAPL"] == 0.0

        # Days after AAPL purchase (20th-25th) - both should have positions
        for i in range(5, 11):
            assert history_points[i].asset_positions["GOOG"] == 10.0 * 155.0
            assert history_points[i].asset_positions["AAPL"] == 5.0 * 185.0
