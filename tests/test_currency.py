"""Tests for currency conversion module."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import pytz
import pandas as pd

from wpm.currency import CurrencyService, CurrencyCache
from wpm.config import Config


class TestCurrencyCache:
    """Tests for CurrencyCache."""

    def test_cache_initialization(self):
        """Test cache initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_currency_cache.parquet"
            cache = CurrencyCache(cache_file=cache_file)
            assert cache.cache_file == cache_file

    def test_get_cached_rate_no_cache(self):
        """Test getting cached rate when cache doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_currency_cache.parquet"
            cache = CurrencyCache(cache_file=cache_file)

            rate = cache.get_cached_rate("HKD", "USD")
            assert rate is None

    def test_set_and_get_cached_rate(self):
        """Test setting and getting cached rate."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_currency_cache.parquet"
            cache = CurrencyCache(cache_file=cache_file)

            cache.set_cached_rate("HKD", "USD", 0.128)
            rate = cache.get_cached_rate("HKD", "USD")

            assert rate == 0.128

    @patch("wpm.currency.datetime")
    def test_cache_validity_recent(self, mock_datetime):
        """Test cache validity with recent cache (24-hour validity)."""
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_currency_cache.parquet"
            cache = CurrencyCache(cache_file=cache_file)

            # Set cache with recent timestamp (1 hour ago - should be valid)
            recent_timestamp = mock_now - timedelta(hours=1)
            cache.set_cached_rate("HKD", "USD", 0.128, timestamp=recent_timestamp)

            # Cache should be valid (< 24 hours old)
            rate = cache.get_cached_rate("HKD", "USD")
            assert rate == 0.128

    @patch("wpm.currency.datetime")
    def test_cache_validity_stale(self, mock_datetime):
        """Test cache validity with stale cache (24-hour validity)."""
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_currency_cache.parquet"
            cache = CurrencyCache(cache_file=cache_file)

            # Set cache with old timestamp (25 hours ago)
            old_timestamp = mock_now - timedelta(hours=25)
            cache.set_cached_rate("HKD", "USD", 0.128, timestamp=old_timestamp)

            # Cache should be invalid (> 24 hours old)
            rate = cache.get_cached_rate("HKD", "USD")
            assert rate is None

    def test_get_cached_rate_different_counter_currency(self):
        """Test getting cached rate with different counter currency."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_currency_cache.parquet"
            cache = CurrencyCache(cache_file=cache_file)

            cache.set_cached_rate("HKD", "USD", 0.128)
            cache.set_cached_rate("HKD", "EUR", 0.118)

            assert cache.get_cached_rate("HKD", "USD") == 0.128
            assert cache.get_cached_rate("HKD", "EUR") == 0.118

    def test_set_cached_rate_updates_existing(self):
        """Test setting cached rate updates existing entry."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_currency_cache.parquet"
            cache = CurrencyCache(cache_file=cache_file)

            cache.set_cached_rate("HKD", "USD", 0.128)
            assert cache.get_cached_rate("HKD", "USD") == 0.128

            cache.set_cached_rate("HKD", "USD", 0.129)
            assert cache.get_cached_rate("HKD", "USD") == 0.129


class TestCurrencyService:
    """Tests for CurrencyService."""

    @patch("wpm.currency.yf")
    @patch("wpm.currency.CurrencyCache")
    def test_get_forex_rate_success(self, mock_cache_class, mock_yf):
        """Test successful forex rate retrieval."""
        mock_cache = Mock()
        mock_cache.get_cached_rate.return_value = None  # Cache miss
        mock_cache_class.return_value = mock_cache

        mock_data = pd.DataFrame(
            {"Close": [0.128]},
            index=pd.date_range("2024-01-15", periods=1, freq="1d"),
        )
        mock_yf.download.return_value = mock_data

        service = CurrencyService(cache=mock_cache)
        rate = service.get_forex_rate("HKD", "USD")

        assert rate == 0.128
        mock_yf.download.assert_called_once_with("HKDUSD=X", period="1d", progress=False)

    @patch("wpm.currency.yf")
    @patch("wpm.currency.CurrencyCache")
    def test_get_forex_rate_empty_data(self, mock_cache_class, mock_yf):
        """Test forex rate retrieval with empty data."""
        mock_cache = Mock()
        mock_cache.get_cached_rate.return_value = None  # Cache miss
        mock_cache_class.return_value = mock_cache

        mock_yf.download.return_value = pd.DataFrame()

        service = CurrencyService(cache=mock_cache)
        with pytest.raises(ValueError, match="No forex rate data available"):
            service.get_forex_rate("HKD", "USD")

    @patch("wpm.currency.yf")
    @patch("wpm.currency.CurrencyCache")
    def test_get_forex_rate_invalid_data(self, mock_cache_class, mock_yf):
        """Test forex rate retrieval with invalid data."""
        mock_cache = Mock()
        mock_cache.get_cached_rate.return_value = None  # Cache miss
        mock_cache_class.return_value = mock_cache

        mock_data = pd.DataFrame(
            {"Close": [None]},
            index=pd.date_range("2024-01-15", periods=1, freq="1d"),
        )
        mock_yf.download.return_value = mock_data

        service = CurrencyService(cache=mock_cache)
        with pytest.raises(ValueError, match="Invalid forex rate data"):
            service.get_forex_rate("HKD", "USD")

    @patch("wpm.currency.yf")
    @patch("wpm.currency.CurrencyCache")
    def test_get_forex_rate_exception(self, mock_cache_class, mock_yf):
        """Test forex rate retrieval with exception."""
        mock_cache = Mock()
        mock_cache.get_cached_rate.return_value = None  # Cache miss
        mock_cache_class.return_value = mock_cache

        mock_yf.download.side_effect = Exception("Network error")

        service = CurrencyService(cache=mock_cache)
        with pytest.raises(ValueError, match="Error fetching forex rate"):
            service.get_forex_rate("HKD", "USD")

    def test_get_forex_rate_same_currency(self):
        """Test forex rate for same currency returns 1.0."""
        service = CurrencyService()
        rate = service.get_forex_rate("USD", "USD")
        assert rate == 1.0

    @patch("wpm.currency.CurrencyCache")
    def test_get_forex_rate_uses_cache(self, mock_cache_class):
        """Test forex rate retrieval uses cache."""
        mock_cache = Mock()
        mock_cache.get_cached_rate.return_value = 0.128
        mock_cache_class.return_value = mock_cache

        service = CurrencyService(cache=mock_cache)
        rate = service.get_forex_rate("HKD", "USD")

        assert rate == 0.128
        mock_cache.get_cached_rate.assert_called_once_with("HKD", "USD")

    @patch("wpm.currency.yf")
    @patch("wpm.currency.CurrencyCache")
    def test_get_forex_rate_caches_result(self, mock_cache_class, mock_yf):
        """Test forex rate retrieval caches result."""
        mock_cache = Mock()
        mock_cache.get_cached_rate.return_value = None  # Cache miss
        mock_cache_class.return_value = mock_cache

        mock_data = pd.DataFrame(
            {"Close": [0.128]},
            index=pd.date_range("2024-01-15", periods=1, freq="1d"),
        )
        mock_yf.download.return_value = mock_data

        service = CurrencyService(cache=mock_cache)
        rate = service.get_forex_rate("HKD", "USD")

        assert rate == 0.128
        mock_cache.set_cached_rate.assert_called_once()
        call_args = mock_cache.set_cached_rate.call_args
        assert call_args[0][0] == "HKD"
        assert call_args[0][1] == "USD"
        assert call_args[0][2] == 0.128

    def test_convert_to_usd_same_currency(self):
        """Test converting USD to USD returns unchanged."""
        service = CurrencyService()
        result = service.convert_to_usd(100.0, "USD")
        assert result == 100.0

    @patch("wpm.currency.yf")
    def test_convert_to_usd_different_currency(self, mock_yf):
        """Test converting non-USD currency to USD."""
        mock_data = pd.DataFrame(
            {"Close": [0.128]},
            index=pd.date_range("2024-01-15", periods=1, freq="1d"),
        )
        mock_yf.download.return_value = mock_data

        service = CurrencyService()
        result = service.convert_to_usd(100.0, "HKD")

        # 100 HKD * 0.128 = 12.8 USD
        assert result == 12.8

    @patch("wpm.currency.CurrencyCache")
    def test_convert_to_usd_uses_cache(self, mock_cache_class):
        """Test convert_to_usd uses cached rate."""
        mock_cache = Mock()
        mock_cache.get_cached_rate.return_value = 0.128
        mock_cache_class.return_value = mock_cache

        service = CurrencyService(cache=mock_cache)
        result = service.convert_to_usd(100.0, "HKD")

        assert result == 12.8
        mock_cache.get_cached_rate.assert_called_once_with("HKD", "USD")

