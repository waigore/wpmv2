"""Tests for price retrieval module with caching and rate limiting."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import pytz
import pandas as pd

from wpm.pricing import (
    PriceRetriever,
    YahooFinanceRetriever,
    CoinGeckoRetriever,
    RateLimiter,
    PriceCache,
    PriceService,
)
from wpm.models import Asset


class TestPriceRetriever:
    """Tests for PriceRetriever abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that PriceRetriever ABC cannot be instantiated."""
        with pytest.raises(TypeError):
            PriceRetriever()


class TestYahooFinanceRetriever:
    """Tests for YahooFinanceRetriever."""

    @patch("wpm.pricing.yf")
    def test_get_price_success(self, mock_yf):
        """Test successful price retrieval from Yahoo Finance."""
        mock_ticker = Mock()
        mock_data = pd.DataFrame(
            {"Close": [150.0, 151.0, 152.0]},
            index=pd.date_range("2024-01-15", periods=3, freq="1min"),
        )
        mock_ticker.history.return_value = mock_data
        mock_yf.Ticker.return_value = mock_ticker

        retriever = YahooFinanceRetriever()
        price = retriever.get_price("GOOG", "Stock")

        assert price == 152.0
        mock_ticker.history.assert_called_once_with(period="1d", interval="1m")

    @patch("wpm.pricing.yf")
    def test_get_price_empty_data(self, mock_yf):
        """Test price retrieval with empty data."""
        mock_ticker = Mock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        retriever = YahooFinanceRetriever()
        with pytest.raises(ValueError, match="No price data available"):
            retriever.get_price("GOOG", "Stock")

    @patch("wpm.pricing.yf")
    def test_get_price_invalid_data(self, mock_yf):
        """Test price retrieval with invalid price data."""
        mock_ticker = Mock()
        mock_data = pd.DataFrame(
            {"Close": [None]},
            index=pd.date_range("2024-01-15", periods=1, freq="1min"),
        )
        mock_ticker.history.return_value = mock_data
        mock_yf.Ticker.return_value = mock_ticker

        retriever = YahooFinanceRetriever()
        with pytest.raises(ValueError, match="Invalid price data"):
            retriever.get_price("GOOG", "Stock")


class TestCoinGeckoRetriever:
    """Tests for CoinGeckoRetriever."""

    def test_get_coin_id(self):
        """Test coin ID conversion."""
        retriever = CoinGeckoRetriever()

        assert retriever._get_coin_id("BTC-USD") == "bitcoin"
        assert retriever._get_coin_id("ETH-USD") == "ethereum"
        assert retriever._get_coin_id("unknown") == "unknown"

    @patch("wpm.pricing.CoinGeckoAPI")
    def test_get_price_success(self, mock_api_class):
        """Test successful price retrieval from CoinGecko."""
        mock_client = Mock()
        mock_client.get_price.return_value = {"bitcoin": {"usd": 50000.0}}
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        price = retriever.get_price("BTC-USD", "Crypto")

        assert price == 50000.0
        mock_client.get_price.assert_called_once()

    @patch("wpm.pricing.CoinGeckoAPI")
    def test_get_price_no_data(self, mock_api_class):
        """Test price retrieval with no data."""
        mock_client = Mock()
        mock_client.get_price.return_value = {}
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        with pytest.raises(ValueError, match="No price data available"):
            retriever.get_price("BTC-USD", "Crypto")


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_calls_per_minute=10)
        assert limiter.max_calls_per_minute == 10

    @patch("time.sleep")
    @patch("wpm.pricing.datetime")
    def test_rate_limit_wait(self, mock_datetime, mock_sleep):
        """Test rate limiter waits when limit exceeded."""
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        limiter = RateLimiter(max_calls_per_minute=2)

        # Make 2 calls (at limit)
        limiter.wait_if_needed()
        limiter.wait_if_needed()

        # Third call should wait
        limiter.wait_if_needed()
        mock_sleep.assert_called_once()


class TestPriceCache:
    """Tests for PriceCache."""

    def test_cache_initialization(self):
        """Test cache initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)
            assert cache.cache_file == cache_file

    def test_get_cached_price_no_cache(self):
        """Test getting cached price when cache doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            price = cache.get_cached_price("GOOG", "Stock")
            assert price is None

    def test_set_and_get_cached_price(self):
        """Test setting and getting cached price."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            cache.set_cached_price("GOOG", "Stock", 150.0)
            price = cache.get_cached_price("GOOG", "Stock")

            assert price == 150.0

    @patch("wpm.pricing.is_within_trading_hours")
    @patch("wpm.pricing.datetime")
    def test_cache_validity_stock_outside_hours(self, mock_datetime, mock_within_hours):
        """Test cache validity for stock outside trading hours."""
        mock_now = datetime(2024, 1, 15, 20, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now
        mock_within_hours.return_value = False

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with old timestamp (outside hours)
            old_timestamp = datetime(2024, 1, 15, 18, 0, 0, tzinfo=pytz.UTC)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=old_timestamp)

            # Cache should be valid if both are outside hours
            price = cache.get_cached_price("GOOG", "Stock")
            assert price == 150.0

    @patch("wpm.pricing.is_within_trading_hours")
    @patch("wpm.pricing.datetime")
    def test_cache_validity_stock_within_hours_recent(self, mock_datetime, mock_within_hours):
        """Test cache validity for stock within trading hours with recent cache."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now
        mock_within_hours.return_value = True

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with recent timestamp (5 minutes ago)
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=recent_timestamp)

            # Cache should be valid (< 10 minutes old)
            price = cache.get_cached_price("GOOG", "Stock")
            assert price == 150.0

    @patch("wpm.pricing.is_within_trading_hours")
    @patch("wpm.pricing.datetime")
    def test_cache_validity_stock_within_hours_stale(self, mock_datetime, mock_within_hours):
        """Test cache validity for stock within trading hours with stale cache."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now
        mock_within_hours.return_value = True

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with old timestamp (15 minutes ago)
            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=old_timestamp)

            # Cache should be invalid (> 10 minutes old)
            price = cache.get_cached_price("GOOG", "Stock")
            assert price is None

    @patch("wpm.pricing.datetime")
    def test_cache_validity_crypto_recent(self, mock_datetime):
        """Test cache validity for crypto with recent cache."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with recent timestamp (5 minutes ago)
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("BTC-USD", "Crypto", 50000.0, timestamp=recent_timestamp)

            # Cache should be valid (< 10 minutes old)
            price = cache.get_cached_price("BTC-USD", "Crypto")
            assert price == 50000.0

    @patch("wpm.pricing.datetime")
    def test_cache_validity_crypto_stale(self, mock_datetime):
        """Test cache validity for crypto with stale cache."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with old timestamp (15 minutes ago)
            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("BTC-USD", "Crypto", 50000.0, timestamp=old_timestamp)

            # Cache should be invalid (> 10 minutes old)
            price = cache.get_cached_price("BTC-USD", "Crypto")
            assert price is None


class TestPriceService:
    """Tests for PriceService."""

    def test_get_price_cache_hit(self):
        """Test price retrieval with cache hit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            # Set cached price
            service.cache.set_cached_price("GOOG", "Stock", 150.0)

            # Mock the retriever's get_price method
            with patch.object(service._stock_retriever, 'get_price') as mock_get_price:
                price = service.get_price("GOOG", "Stock")
                assert price == 150.0
                # Should not call retriever since cache hit
                mock_get_price.assert_not_called()

    @patch("wpm.pricing.YahooFinanceRetriever")
    def test_get_price_cache_miss(self, mock_retriever_class):
        """Test price retrieval with cache miss."""
        mock_retriever = Mock()
        mock_retriever.get_price.return_value = 150.0
        mock_retriever_class.return_value = mock_retriever

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            price = service.get_price("GOOG", "Stock")
            assert price == 150.0
            mock_retriever.get_price.assert_called_once_with("GOOG", "Stock")

    def test_get_prices_batch(self):
        """Test batch price retrieval."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            # Cache some prices
            service.cache.set_cached_price("GOOG", "Stock", 150.0)
            service.cache.set_cached_price("AAPL", "Stock", 200.0)

            prices = service.get_prices(["GOOG", "AAPL"], "Stock")
            assert prices["GOOG"] == 150.0
            assert prices["AAPL"] == 200.0

    def test_get_price_unsupported_asset_type(self):
        """Test price retrieval with unsupported asset type."""
        service = PriceService()
        with pytest.raises(ValueError, match="Unsupported asset type"):
            service.get_price("GOOG", "Invalid")

