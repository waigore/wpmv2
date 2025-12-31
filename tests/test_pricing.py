"""Tests for price retrieval module with caching and rate limiting."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import pytz
import pandas as pd

from wpm.pricing import (
    CacheValidity,
    CacheValidityStatus,
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

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_price_success(self, mock_yf, mock_within_hours):
        """Test successful price retrieval from Yahoo Finance."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
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

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_price_empty_data(self, mock_yf, mock_within_hours):
        """Test price retrieval with empty data."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
        mock_ticker = Mock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        retriever = YahooFinanceRetriever()
        with pytest.raises(ValueError, match="No price data available"):
            retriever.get_price("GOOG", "Stock")

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_price_invalid_data(self, mock_yf, mock_within_hours):
        """Test price retrieval with invalid price data."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
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

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_price_exception(self, mock_yf, mock_within_hours):
        """Test price retrieval with exception."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
        mock_yf.Ticker.side_effect = Exception("Network error")

        retriever = YahooFinanceRetriever()
        with pytest.raises(ValueError, match="Error fetching price"):
            retriever.get_price("GOOG", "Stock")

    def test_extract_price_from_ticker_data_success(self):
        """Test extracting price from ticker data successfully."""
        retriever = YahooFinanceRetriever()
        ticker_data = pd.DataFrame({"Close": [150.0, 151.0, 152.0]})
        price = retriever._extract_price_from_ticker_data(ticker_data, "GOOG")
        assert price == 152.0

    def test_extract_price_from_ticker_data_no_close(self):
        """Test extracting price when Close column is missing."""
        retriever = YahooFinanceRetriever()
        ticker_data = pd.DataFrame({"Open": [150.0]})
        price = retriever._extract_price_from_ticker_data(ticker_data, "GOOG")
        assert price is None

    def test_extract_price_from_ticker_data_empty(self):
        """Test extracting price from empty DataFrame."""
        retriever = YahooFinanceRetriever()
        ticker_data = pd.DataFrame()
        price = retriever._extract_price_from_ticker_data(ticker_data, "GOOG")
        assert price is None

    def test_extract_price_from_ticker_data_invalid(self):
        """Test extracting price with invalid data."""
        retriever = YahooFinanceRetriever()
        ticker_data = pd.DataFrame({"Close": [None]})
        price = retriever._extract_price_from_ticker_data(ticker_data, "GOOG")
        assert price is None

    def test_extract_price_from_ticker_data_zero(self):
        """Test extracting price with zero price."""
        retriever = YahooFinanceRetriever()
        ticker_data = pd.DataFrame({"Close": [0.0]})
        price = retriever._extract_price_from_ticker_data(ticker_data, "GOOG")
        assert price is None

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_empty_list(self, mock_yf, mock_within_hours):
        """Test batch retrieval with empty ticker list."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices([], "Stock")
        assert prices == {}
        mock_yf.download.assert_not_called()

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_empty_data(self, mock_yf, mock_within_hours):
        """Test batch retrieval with empty data from API."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
        mock_yf.download.return_value = pd.DataFrame()
        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices(["GOOG"], "Stock")
        assert prices == {}

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_single_ticker(self, mock_yf, mock_within_hours):
        """Test batch retrieval with single ticker (MultiIndex columns)."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
        # yf.download always returns MultiIndex columns, even for single ticker
        arrays = [["GOOG", "GOOG"], ["Close", "Open"]]
        tuples = list(zip(*arrays))
        mock_data = pd.DataFrame(
            {
                ("GOOG", "Close"): [150.0, 151.0, 152.0],
                ("GOOG", "Open"): [149.0, 150.0, 151.0],
            },
            index=pd.date_range("2024-01-15", periods=3, freq="1min"),
        )
        mock_data.columns = pd.MultiIndex.from_tuples(tuples, names=["Ticker", "Price"])
        mock_yf.download.return_value = mock_data
        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices(["GOOG"], "Stock")
        assert prices == {"GOOG": 152.0}

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_multiple_tickers(self, mock_yf, mock_within_hours):
        """Test batch retrieval with multiple tickers (MultiIndex)."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
        # Create MultiIndex DataFrame
        arrays = [["GOOG", "GOOG", "AAPL", "AAPL"], ["Close", "Open", "Close", "Open"]]
        tuples = list(zip(*arrays))
        index = pd.MultiIndex.from_tuples(tuples, names=["ticker", "column"])
        mock_data = pd.DataFrame(
            {
                ("GOOG", "Close"): [150.0, 151.0],
                ("GOOG", "Open"): [149.0, 150.0],
                ("AAPL", "Close"): [200.0, 201.0],
                ("AAPL", "Open"): [199.0, 200.0],
            },
            index=pd.date_range("2024-01-15", periods=2, freq="1min"),
        )
        mock_data.columns = pd.MultiIndex.from_tuples(tuples)
        mock_yf.download.return_value = mock_data
        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices(["GOOG", "AAPL"], "Stock")
        assert "GOOG" in prices
        assert "AAPL" in prices

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_price_during_trading_hours_realtime(self, mock_yf, mock_within_hours):
        """Test get_price during trading hours uses real-time prices."""
        mock_within_hours.return_value = True
        mock_ticker = Mock()
        mock_ticker.info = {"currentPrice": 155.0}
        mock_yf.Ticker.return_value = mock_ticker

        retriever = YahooFinanceRetriever()
        price = retriever.get_price("GOOG", "Stock")

        assert price == 155.0
        mock_ticker.history.assert_not_called()

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_price_during_trading_hours_fallback_to_close(self, mock_yf, mock_within_hours):
        """Test get_price during trading hours falls back to Close when real-time prices unavailable."""
        mock_within_hours.return_value = True
        mock_ticker = Mock()
        mock_ticker.info = {}  # No real-time prices available
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

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_price_during_trading_hours_regular_market_price(self, mock_yf, mock_within_hours):
        """Test get_price during trading hours uses regularMarketPrice when currentPrice unavailable."""
        mock_within_hours.return_value = True
        mock_ticker = Mock()
        mock_ticker.info = {"regularMarketPrice": 154.0}  # No currentPrice, but has regularMarketPrice
        mock_yf.Ticker.return_value = mock_ticker

        retriever = YahooFinanceRetriever()
        price = retriever.get_price("GOOG", "Stock")

        assert price == 154.0
        mock_ticker.history.assert_not_called()

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_price_outside_trading_hours(self, mock_yf, mock_within_hours):
        """Test get_price outside trading hours uses Close."""
        mock_within_hours.return_value = False
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

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_during_trading_hours_realtime(self, mock_yf, mock_within_hours):
        """Test get_prices during trading hours uses real-time prices."""
        mock_within_hours.return_value = True
        mock_ticker1 = Mock()
        mock_ticker1.info = {"currentPrice": 155.0}
        mock_ticker2 = Mock()
        mock_ticker2.info = {"regularMarketPrice": 200.0}
        mock_yf.Ticker.side_effect = [mock_ticker1, mock_ticker2]

        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices(["GOOG", "AAPL"], "Stock")

        assert prices["GOOG"] == 155.0
        assert prices["AAPL"] == 200.0
        mock_yf.download.assert_not_called()

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_during_trading_hours_partial_fallback(self, mock_yf, mock_within_hours):
        """Test get_prices during trading hours with partial fallback to Close."""
        mock_within_hours.return_value = True
        mock_ticker1 = Mock()
        mock_ticker1.info = {"currentPrice": 155.0}  # GOOG has real-time price
        mock_ticker2 = Mock()
        mock_ticker2.info = {}  # AAPL has no real-time price, will use Close
        mock_yf.Ticker.side_effect = [mock_ticker1, mock_ticker2]

        # Mock batch download for Close prices
        arrays = [["AAPL", "AAPL"], ["Close", "Open"]]
        tuples = list(zip(*arrays))
        mock_data = pd.DataFrame(
            {
                ("AAPL", "Close"): [200.0, 201.0],
                ("AAPL", "Open"): [199.0, 200.0],
            },
            index=pd.date_range("2024-01-15", periods=2, freq="1min"),
        )
        mock_data.columns = pd.MultiIndex.from_tuples(tuples)
        mock_yf.download.return_value = mock_data

        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices(["GOOG", "AAPL"], "Stock")

        assert prices["GOOG"] == 155.0
        assert prices["AAPL"] == 201.0
        mock_yf.download.assert_called_once_with(["AAPL"], period="1d", interval="1m", group_by="ticker", progress=False)

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_outside_trading_hours(self, mock_yf, mock_within_hours):
        """Test get_prices outside trading hours uses Close."""
        mock_within_hours.return_value = False
        arrays = [["GOOG", "GOOG", "AAPL", "AAPL"], ["Close", "Open", "Close", "Open"]]
        tuples = list(zip(*arrays))
        mock_data = pd.DataFrame(
            {
                ("GOOG", "Close"): [150.0, 151.0],
                ("GOOG", "Open"): [149.0, 150.0],
                ("AAPL", "Close"): [200.0, 201.0],
                ("AAPL", "Open"): [199.0, 200.0],
            },
            index=pd.date_range("2024-01-15", periods=2, freq="1min"),
        )
        mock_data.columns = pd.MultiIndex.from_tuples(tuples)
        mock_yf.download.return_value = mock_data

        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices(["GOOG", "AAPL"], "Stock")

        assert prices["GOOG"] == 151.0
        assert prices["AAPL"] == 201.0
        mock_yf.download.assert_called_once_with(["GOOG", "AAPL"], period="1d", interval="1m", group_by="ticker", progress=False)
        assert prices["GOOG"] == 151.0
        assert prices["AAPL"] == 201.0

    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_partial_failure(self, mock_yf):
        """Test batch retrieval with partial failure (some tickers missing)."""
        # Note: This test doesn't patch is_within_trading_hours because it tests
        # the behavior when outside trading hours, which will use Close prices anyway
        # Create MultiIndex DataFrame with only one ticker
        arrays = [["GOOG", "GOOG"], ["Close", "Open"]]
        tuples = list(zip(*arrays))
        mock_data = pd.DataFrame(
            {
                ("GOOG", "Close"): [150.0, 151.0],
                ("GOOG", "Open"): [149.0, 150.0],
            },
            index=pd.date_range("2024-01-15", periods=2, freq="1min"),
        )
        mock_data.columns = pd.MultiIndex.from_tuples(tuples)
        mock_yf.download.return_value = mock_data
        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices(["GOOG", "AAPL"], "Stock")
        assert "GOOG" in prices
        assert "AAPL" not in prices

    @patch("wpm.pricing.yahoo.is_within_trading_hours")
    @patch("wpm.pricing.yahoo.yf")
    def test_get_prices_exception(self, mock_yf, mock_within_hours):
        """Test batch retrieval with exception."""
        mock_within_hours.return_value = False  # Outside trading hours, uses Close
        mock_yf.download.side_effect = Exception("Network error")
        retriever = YahooFinanceRetriever()
        prices = retriever.get_prices(["GOOG"], "Stock")
        assert prices == {}



class TestCoinGeckoRetriever:
    """Tests for CoinGeckoRetriever."""

    def test_get_coin_id(self):
        """Test coin ID conversion."""
        retriever = CoinGeckoRetriever()

        assert retriever._get_coin_id("BTC-USD") == "bitcoin"
        assert retriever._get_coin_id("ETH-USD") == "ethereum"
        assert retriever._get_coin_id("unknown") == "unknown"

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_price_success(self, mock_api_class):
        """Test successful price retrieval from CoinGecko."""
        mock_client = Mock()
        mock_client.get_price.return_value = {"bitcoin": {"usd": 50000.0}}
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        price = retriever.get_price("BTC-USD", "Crypto")

        assert price == 50000.0
        mock_client.get_price.assert_called_once()

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_price_no_data(self, mock_api_class):
        """Test price retrieval with no data."""
        mock_client = Mock()
        mock_client.get_price.return_value = {}
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        with pytest.raises(ValueError, match="No price data available"):
            retriever.get_price("BTC-USD", "Crypto")

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_price_invalid_price(self, mock_api_class):
        """Test price retrieval with invalid price (zero or negative)."""
        mock_client = Mock()
        mock_client.get_price.return_value = {"bitcoin": {"usd": 0}}
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        with pytest.raises(ValueError, match="Invalid price data"):
            retriever.get_price("BTC-USD", "Crypto")

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_price_exception(self, mock_api_class):
        """Test price retrieval with exception."""
        mock_client = Mock()
        mock_client.get_price.side_effect = Exception("Network error")
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        with pytest.raises(ValueError, match="Error fetching price"):
            retriever.get_price("BTC-USD", "Crypto")

    @patch("wpm.pricing.coingecko.Config")
    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_init_with_api_key(self, mock_api_class, mock_config):
        """Test CoinGeckoRetriever initialization with API key."""
        mock_config.COINGECKO_API_KEY = "test_key"
        mock_config.COINGECKO_API_IS_DEMO = False
        retriever = CoinGeckoRetriever()
        mock_api_class.assert_called_once_with(api_key="test_key")

    @patch("wpm.pricing.coingecko.Config")
    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_init_without_api_key(self, mock_api_class, mock_config):
        """Test CoinGeckoRetriever initialization without API key."""
        mock_config.COINGECKO_API_KEY = None
        retriever = CoinGeckoRetriever()
        mock_api_class.assert_called_once_with()

    def test_extract_price_from_coin_data_success(self):
        """Test extracting price from coin data successfully."""
        retriever = CoinGeckoRetriever()
        coin_data = {"usd": 50000.0}
        price = retriever._extract_price_from_coin_data(coin_data, "BTC-USD")
        assert price == 50000.0

    def test_extract_price_from_coin_data_no_price(self):
        """Test extracting price when price is missing."""
        retriever = CoinGeckoRetriever()
        coin_data = {}
        price = retriever._extract_price_from_coin_data(coin_data, "BTC-USD")
        assert price is None

    def test_extract_price_from_coin_data_zero(self):
        """Test extracting price with zero price."""
        retriever = CoinGeckoRetriever()
        coin_data = {"usd": 0}
        price = retriever._extract_price_from_coin_data(coin_data, "BTC-USD")
        assert price is None

    def test_extract_price_from_coin_data_negative(self):
        """Test extracting price with negative price."""
        retriever = CoinGeckoRetriever()
        coin_data = {"usd": -100}
        price = retriever._extract_price_from_coin_data(coin_data, "BTC-USD")
        assert price is None

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_prices_empty_list(self, mock_api_class):
        """Test batch retrieval with empty ticker list."""
        retriever = CoinGeckoRetriever()
        prices = retriever.get_prices([], "Crypto")
        assert prices == {}

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_prices_success(self, mock_api_class):
        """Test batch retrieval with multiple tickers."""
        mock_client = Mock()
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 50000.0},
            "ethereum": {"usd": 3000.0},
        }
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        prices = retriever.get_prices(["BTC-USD", "ETH-USD"], "Crypto")
        assert prices["BTC-USD"] == 50000.0
        assert prices["ETH-USD"] == 3000.0

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_prices_empty_data(self, mock_api_class):
        """Test batch retrieval with empty data from API."""
        mock_client = Mock()
        mock_client.get_price.return_value = {}
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        prices = retriever.get_prices(["BTC-USD"], "Crypto")
        assert prices == {}

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_prices_partial_failure(self, mock_api_class):
        """Test batch retrieval with partial failure."""
        mock_client = Mock()
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 50000.0},
            # ethereum missing
        }
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        prices = retriever.get_prices(["BTC-USD", "ETH-USD"], "Crypto")
        assert "BTC-USD" in prices
        assert "ETH-USD" not in prices

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_prices_invalid_price(self, mock_api_class):
        """Test batch retrieval with invalid price in response."""
        mock_client = Mock()
        mock_client.get_price.return_value = {
            "bitcoin": {"usd": 0},  # Invalid price
        }
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        prices = retriever.get_prices(["BTC-USD"], "Crypto")
        assert "BTC-USD" not in prices

    @patch("wpm.pricing.coingecko.CoinGeckoAPI")
    def test_get_prices_exception(self, mock_api_class):
        """Test batch retrieval with exception."""
        mock_client = Mock()
        mock_client.get_price.side_effect = Exception("Network error")
        mock_api_class.return_value = mock_client

        retriever = CoinGeckoRetriever()
        prices = retriever.get_prices(["BTC-USD"], "Crypto")
        assert prices == {}


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_calls_per_minute=10)
        assert limiter.max_calls_per_minute == 10

    @patch("time.sleep")
    @patch("wpm.pricing.rate_limiter.datetime")
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

    @patch("wpm.pricing.rate_limiter.datetime")
    def test_rate_limit_no_wait(self, mock_datetime):
        """Test rate limiter doesn't wait when under limit."""
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        limiter = RateLimiter(max_calls_per_minute=10)

        # Make calls under limit
        limiter.wait_if_needed()
        limiter.wait_if_needed()
        # Should not raise any exceptions


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

    @patch("wpm.pricing.cache.datetime")
    def test_cache_validity_stock_outside_hours(self, mock_datetime):
        """Test cache validity for stock (age-based only)."""
        mock_now = datetime(2024, 1, 15, 20, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with recent timestamp (5 minutes ago - should be valid)
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=recent_timestamp)

            # Cache should be valid (< 10 minutes old)
            price = cache.get_cached_price("GOOG", "Stock")
            assert price == 150.0

    @patch("wpm.pricing.cache.datetime")
    def test_cache_validity_stock_within_hours_recent(self, mock_datetime):
        """Test cache validity for stock with recent cache (age-based only)."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with recent timestamp (5 minutes ago)
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=recent_timestamp)

            # Cache should be valid (< 10 minutes old)
            price = cache.get_cached_price("GOOG", "Stock")
            assert price == 150.0

    @patch("wpm.pricing.cache.datetime")
    def test_cache_validity_stock_within_hours_stale(self, mock_datetime):
        """Test cache validity for stock with stale cache (age-based only)."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with old timestamp (15 minutes ago)
            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=old_timestamp)

            # Cache should be invalid (> 10 minutes old)
            price = cache.get_cached_price("GOOG", "Stock")
            assert price is None

    @patch("wpm.pricing.cache.datetime")
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

    @patch("wpm.pricing.cache.datetime")
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

    def test_get_stale_cached_price_exists(self):
        """Test getting stale cached price when entry exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cached price (even if stale)
            old_timestamp = datetime(2024, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=old_timestamp)

            # Should return stale price
            price = cache.get_stale_cached_price("GOOG", "Stock")
            assert price == 150.0

    def test_get_stale_cached_price_not_exists(self):
        """Test getting stale cached price when entry doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            price = cache.get_stale_cached_price("GOOG", "Stock")
            assert price is None

    def test_is_stock_cache_valid_recent(self):
        """Test stock cache validity with recent cache (age-based only)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            cache.set_cached_price("GOOG", "Stock", 150.0)

            cache_entry = cache._load_cache().iloc[0]
            # Recent cache (age < 10 minutes) should be valid
            is_valid = cache._is_stock_cache_valid(cache_entry, 5.0)
            assert is_valid is True

    def test_is_stock_cache_valid_stale(self):
        """Test stock cache validity with stale cache (age-based only)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            cache.set_cached_price("GOOG", "Stock", 150.0)

            cache_entry = cache._load_cache().iloc[0]
            # Stale cache (age >= 10 minutes) should be invalid
            is_valid = cache._is_stock_cache_valid(cache_entry, 15.0)
            assert is_valid is False

    def test_is_stock_cache_valid_exactly_at_threshold(self):
        """Test stock cache validity at the 10-minute threshold."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            cache.set_cached_price("GOOG", "Stock", 150.0)

            cache_entry = cache._load_cache().iloc[0]
            # Exactly 10 minutes should be invalid (age must be < 10)
            is_valid = cache._is_stock_cache_valid(cache_entry, 10.0)
            assert is_valid is False

    @patch("wpm.pricing.cache.datetime")
    def test_is_crypto_cache_valid_recent(self, mock_datetime):
        """Test crypto cache validity with recent cache."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("BTC-USD", "Crypto", 50000.0, timestamp=recent_timestamp)

            cache_entry = cache._load_cache().iloc[0]
            is_valid = cache._is_crypto_cache_valid(cache_entry, 5.0)
            assert is_valid is True

    @patch("wpm.pricing.cache.datetime")
    def test_is_crypto_cache_valid_stale(self, mock_datetime):
        """Test crypto cache validity with stale cache."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("BTC-USD", "Crypto", 50000.0, timestamp=old_timestamp)

            cache_entry = cache._load_cache().iloc[0]
            is_valid = cache._is_crypto_cache_valid(cache_entry, 15.0)
            assert is_valid is False

    @patch("wpm.pricing.cache.datetime")
    def test_is_cache_valid_string_timestamp(self, mock_datetime):
        """Test cache validity with string timestamp."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with string timestamp by directly modifying the cache DataFrame
            cache.set_cached_price("GOOG", "Stock", 150.0)
            cache_df = cache._load_cache()
            # Modify timestamp to be a string using .loc to avoid SettingWithCopyWarning
            cache_df.loc[cache_df.index[0], "timestamp"] = "2024-01-15 14:00:00"
            cache_entry = cache_df.iloc[0]

            # Should handle string timestamp conversion
            is_valid = cache._is_cache_valid(cache_entry, "Stock")
            # Result depends on current time, but should not raise exception
            assert isinstance(is_valid, bool)

    @patch("wpm.pricing.cache.datetime")
    def test_is_cache_valid_pandas_timestamp(self, mock_datetime):
        """Test cache validity with pandas Timestamp."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set cache with pandas Timestamp
            pd_timestamp = pd.Timestamp("2024-01-15 14:00:00", tz="UTC")
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=pd_timestamp.to_pydatetime())
            cache_df = cache._load_cache()
            # Modify to pandas Timestamp using .loc to avoid SettingWithCopyWarning
            cache_df.loc[cache_df.index[0], "timestamp"] = pd_timestamp
            cache_entry = cache_df.iloc[0]

            is_valid = cache._is_cache_valid(cache_entry, "Stock")
            assert isinstance(is_valid, bool)

    @patch("wpm.pricing.cache.datetime")
    def test_is_cache_valid_invalid_timestamp(self, mock_datetime):
        """Test cache validity with invalid timestamp."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            cache.set_cached_price("GOOG", "Stock", 150.0)
            cache_df = cache._load_cache()
            # Convert timestamp column to object type first to allow string
            cache_df["timestamp"] = cache_df["timestamp"].astype(object)
            # Set invalid timestamp using .loc to avoid SettingWithCopyWarning
            cache_df.loc[cache_df.index[0], "timestamp"] = "invalid"
            cache_entry = cache_df.iloc[0]

            is_valid = cache._is_cache_valid(cache_entry, "Stock")
            assert is_valid is False

    @patch("wpm.pricing.cache.datetime")
    def test_is_cache_valid_na_timestamp(self, mock_datetime):
        """Test cache validity with NaN timestamp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            cache.set_cached_price("GOOG", "Stock", 150.0)
            cache_df = cache._load_cache()
            # Convert timestamp column to object type first to allow NaT
            cache_df["timestamp"] = cache_df["timestamp"].astype(object)
            # Set NaN timestamp using .loc to avoid SettingWithCopyWarning
            cache_df.loc[cache_df.index[0], "timestamp"] = pd.NaT
            cache_entry = cache_df.iloc[0]

            is_valid = cache._is_cache_valid(cache_entry, "Stock")
            assert is_valid is False

    @patch("wpm.pricing.cache.datetime")
    def test_is_cache_valid_unsupported_asset_type(self, mock_datetime):
        """Test cache validity with unsupported asset type."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            cache.set_cached_price("GOOG", "Stock", 150.0)
            cache_entry = cache._load_cache().iloc[0]

            is_valid = cache._is_cache_valid(cache_entry, "Invalid")
            assert is_valid is False

    def test_get_cache_validity_empty_cache(self):
        """Test get_cache_validity with empty cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            validity = cache.get_cache_validity()
            assert validity.status == CacheValidityStatus.STALE
            assert validity.stale_entries == []

    @patch("wpm.pricing.cache.datetime")
    def test_get_cache_validity_all_valid(self, mock_datetime):
        """Test get_cache_validity when all entries are valid."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set recent cache entries (5 minutes ago)
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=recent_timestamp)
            cache.set_cached_price("AAPL", "Stock", 200.0, timestamp=recent_timestamp)
            cache.set_cached_price("BTC-USD", "Crypto", 50000.0, timestamp=recent_timestamp)

            validity = cache.get_cache_validity()
            assert validity.status == CacheValidityStatus.VALID
            assert len(validity.stale_entries) == 0

    @patch("wpm.pricing.cache.datetime")
    def test_get_cache_validity_all_stale(self, mock_datetime):
        """Test get_cache_validity when all entries are stale."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set old cache entries (15 minutes ago)
            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=old_timestamp)
            cache.set_cached_price("AAPL", "Stock", 200.0, timestamp=old_timestamp)
            cache.set_cached_price("BTC-USD", "Crypto", 50000.0, timestamp=old_timestamp)

            validity = cache.get_cache_validity()
            assert validity.status == CacheValidityStatus.STALE
            assert len(validity.stale_entries) == 3
            assert all(entry["ticker"] in ["GOOG", "AAPL", "BTC-USD"] for entry in validity.stale_entries)

    @patch("wpm.pricing.cache.datetime")
    def test_get_cache_validity_partial(self, mock_datetime):
        """Test get_cache_validity when some entries are valid and some are stale."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set recent cache entry (5 minutes ago) - valid
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=recent_timestamp)

            # Set old cache entries (15 minutes ago) - stale
            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("AAPL", "Stock", 200.0, timestamp=old_timestamp)
            cache.set_cached_price("BTC-USD", "Crypto", 50000.0, timestamp=old_timestamp)

            validity = cache.get_cache_validity()
            assert validity.status == CacheValidityStatus.PARTIAL
            assert len(validity.stale_entries) == 2
            assert all(entry["ticker"] in ["AAPL", "BTC-USD"] for entry in validity.stale_entries)
            assert all(entry["ticker"] != "GOOG" for entry in validity.stale_entries)

    @patch("wpm.pricing.cache.datetime")
    def test_get_cache_validity_with_tickers_filter(self, mock_datetime):
        """Test get_cache_validity with specific tickers filter."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set recent cache entry (5 minutes ago) - valid
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=recent_timestamp)

            # Set old cache entry (15 minutes ago) - stale
            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("AAPL", "Stock", 200.0, timestamp=old_timestamp)

            # Check only GOOG (should be valid)
            validity = cache.get_cache_validity(tickers=["GOOG"])
            assert validity.status == CacheValidityStatus.VALID
            assert len(validity.stale_entries) == 0

            # Check only AAPL (should be stale)
            validity = cache.get_cache_validity(tickers=["AAPL"])
            assert validity.status == CacheValidityStatus.STALE
            assert len(validity.stale_entries) == 1
            assert validity.stale_entries[0]["ticker"] == "AAPL"

            # Check both (should be partial)
            validity = cache.get_cache_validity(tickers=["GOOG", "AAPL"])
            assert validity.status == CacheValidityStatus.PARTIAL
            assert len(validity.stale_entries) == 1
            assert validity.stale_entries[0]["ticker"] == "AAPL"

    @patch("wpm.pricing.cache.datetime")
    def test_get_cache_validity_with_nonexistent_tickers(self, mock_datetime):
        """Test get_cache_validity with tickers that don't exist in cache."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set one cache entry
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=recent_timestamp)

            # Check for tickers that don't exist
            validity = cache.get_cache_validity(tickers=["NONEXISTENT"])
            assert validity.status == CacheValidityStatus.STALE
            assert len(validity.stale_entries) == 0

    @patch("wpm.pricing.cache.datetime")
    def test_get_cache_validity_stale_entries_structure(self, mock_datetime):
        """Test that stale entries have the correct structure."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set old cache entry (15 minutes ago)
            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=old_timestamp)

            validity = cache.get_cache_validity()
            assert len(validity.stale_entries) == 1
            stale_entry = validity.stale_entries[0]
            assert "ticker" in stale_entry
            assert "asset_type" in stale_entry
            assert "price" in stale_entry
            assert "timestamp" in stale_entry
            assert stale_entry["ticker"] == "GOOG"
            assert stale_entry["asset_type"] == "Stock"
            assert stale_entry["price"] == 150.0
            assert isinstance(stale_entry["timestamp"], datetime)

    @patch("wpm.pricing.cache.datetime")
    def test_get_cache_validity_mixed_asset_types(self, mock_datetime):
        """Test get_cache_validity with mixed asset types (Stock, ETF, Crypto)."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = PriceCache(cache_file=cache_file)

            # Set recent entries (5 minutes ago) - valid
            recent_timestamp = mock_now - timedelta(minutes=5)
            cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=recent_timestamp)
            cache.set_cached_price("SPY", "ETF", 400.0, timestamp=recent_timestamp)
            cache.set_cached_price("BTC-USD", "Crypto", 50000.0, timestamp=recent_timestamp)

            # Set old entries (15 minutes ago) - stale
            old_timestamp = mock_now - timedelta(minutes=15)
            cache.set_cached_price("AAPL", "Stock", 200.0, timestamp=old_timestamp)
            cache.set_cached_price("ETH-USD", "Crypto", 3000.0, timestamp=old_timestamp)

            validity = cache.get_cache_validity()
            assert validity.status == CacheValidityStatus.PARTIAL
            assert len(validity.stale_entries) == 2
            stale_tickers = {entry["ticker"] for entry in validity.stale_entries}
            assert stale_tickers == {"AAPL", "ETH-USD"}


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

    @patch("wpm.pricing.service.YahooFinanceRetriever")
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

    @patch("wpm.pricing.service.YahooFinanceRetriever")
    def test_get_prices_all_cached(self, mock_retriever_class):
        """Test batch retrieval when all prices are cached."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            # Cache all prices
            service.cache.set_cached_price("GOOG", "Stock", 150.0)
            service.cache.set_cached_price("AAPL", "Stock", 200.0)

            prices = service.get_prices(["GOOG", "AAPL"], "Stock")
            assert prices["GOOG"] == 150.0
            assert prices["AAPL"] == 200.0
            # Should not call retriever since all prices are cached
            # YahooFinanceRetriever is instantiated in __init__, so it's called once
            mock_retriever_class.assert_called_once()

    @patch.object(YahooFinanceRetriever, "get_prices")
    def test_get_prices_all_uncached(self, mock_get_prices):
        """Test batch retrieval when no prices are cached."""
        mock_get_prices.return_value = {"GOOG": 150.0, "AAPL": 200.0}

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            prices = service.get_prices(["GOOG", "AAPL"], "Stock")
            assert prices["GOOG"] == 150.0
            assert prices["AAPL"] == 200.0
            mock_get_prices.assert_called_once_with(["GOOG", "AAPL"], "Stock")

    @patch.object(YahooFinanceRetriever, "get_prices")
    def test_get_prices_mixed_cache(self, mock_get_prices):
        """Test batch retrieval with mixed cached and uncached prices."""
        mock_get_prices.return_value = {"AAPL": 200.0}  # Only AAPL from API

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            # Cache GOOG
            service.cache.set_cached_price("GOOG", "Stock", 150.0)

            prices = service.get_prices(["GOOG", "AAPL"], "Stock")
            assert prices["GOOG"] == 150.0  # From cache
            assert prices["AAPL"] == 200.0  # From API
            mock_get_prices.assert_called_once_with(["AAPL"], "Stock")

    @patch.object(YahooFinanceRetriever, "get_prices")
    def test_get_prices_partial_failure_with_stale_cache(self, mock_get_prices):
        """Test batch retrieval with partial failure and stale cache fallback."""
        mock_get_prices.return_value = {"AAPL": 200.0}  # GOOG failed

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            # Set stale cache for GOOG
            old_timestamp = datetime(2024, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
            service.cache.set_cached_price("GOOG", "Stock", 150.0, timestamp=old_timestamp)

            prices = service.get_prices(["GOOG", "AAPL"], "Stock")
            assert prices["GOOG"] == 150.0  # From stale cache
            assert prices["AAPL"] == 200.0  # From API

    @patch.object(YahooFinanceRetriever, "get_prices")
    def test_get_prices_partial_failure_no_cache(self, mock_get_prices):
        """Test batch retrieval with partial failure and no cache (should raise error)."""
        mock_get_prices.return_value = {"AAPL": 200.0}  # GOOG failed

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            with pytest.raises(ValueError, match="No price data available for GOOG"):
                service.get_prices(["GOOG", "AAPL"], "Stock")

    @patch.object(YahooFinanceRetriever, "get_prices")
    def test_get_prices_empty_list(self, mock_get_prices):
        """Test batch retrieval with empty ticker list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = PriceService(cache_file=cache_file)

            prices = service.get_prices([], "Stock")
            assert prices == {}
            mock_get_prices.assert_not_called()

    def test_get_retriever_stock(self):
        """Test getting stock retriever."""
        service = PriceService()
        retriever = service._get_retriever("Stock")
        assert isinstance(retriever, YahooFinanceRetriever)

    def test_get_retriever_etf(self):
        """Test getting ETF retriever."""
        service = PriceService()
        retriever = service._get_retriever("ETF")
        assert isinstance(retriever, YahooFinanceRetriever)

    def test_get_retriever_crypto(self):
        """Test getting crypto retriever."""
        service = PriceService()
        retriever = service._get_retriever("Crypto")
        assert isinstance(retriever, CoinGeckoRetriever)

    def test_get_retriever_invalid(self):
        """Test getting retriever for invalid asset type."""
        service = PriceService()
        with pytest.raises(ValueError, match="Unsupported asset type"):
            service._get_retriever("Invalid")

