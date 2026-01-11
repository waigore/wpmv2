"""Tests for historical price retrieval and caching."""

import pytest
from datetime import date
from pathlib import Path
import tempfile
import pandas as pd
from unittest.mock import Mock, patch

from wpm.pricing.historical_cache import HistoricalPriceCache
from wpm.pricing.service import PriceService


class TestHistoricalPriceCache:
    """Tests for HistoricalPriceCache class."""

    def test_create_cache(self):
        """Test creating historical price cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = HistoricalPriceCache(cache_file)
            assert cache.cache_file == cache_file

    def test_get_cached_price_no_cache(self):
        """Test getting cached price when cache is empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = HistoricalPriceCache(cache_file)
            
            price = cache.get_cached_price("GOOG", "Stock", date(2024, 1, 15))
            assert price is None

    def test_set_and_get_cached_prices(self):
        """Test setting and getting cached prices."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = HistoricalPriceCache(cache_file)
            
            # Create price DataFrame
            dates = pd.date_range(start=date(2024, 1, 15), end=date(2024, 1, 20), freq="D")
            prices_df = pd.DataFrame({"price": [150.0, 151.0, 152.0, 153.0, 154.0, 155.0]}, index=dates)
            prices_df.index.name = "date"
            
            cache.set_cached_prices("GOOG", "Stock", prices_df, native_prices_df=prices_df, native_currency="USD")
            
            # Get price for specific date
            price = cache.get_cached_price("GOOG", "Stock", date(2024, 1, 17))
            assert price == 152.0
            
            # Get price for date after range (should get most recent)
            price = cache.get_cached_price("GOOG", "Stock", date(2024, 1, 25))
            assert price == 155.0

    def test_get_cached_prices_range(self):
        """Test getting cached prices for a date range."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = HistoricalPriceCache(cache_file)
            
            # Create price DataFrame
            dates = pd.date_range(start=date(2024, 1, 15), end=date(2024, 1, 20), freq="D")
            prices_df = pd.DataFrame({"price": [150.0, 151.0, 152.0, 153.0, 154.0, 155.0]}, index=dates)
            prices_df.index.name = "date"
            
            cache.set_cached_prices("GOOG", "Stock", prices_df, native_prices_df=prices_df, native_currency="USD")
            
            # Get prices for date range
            result_df = cache.get_cached_prices("GOOG", "Stock", date(2024, 1, 16), date(2024, 1, 18))
            assert result_df is not None
            assert len(result_df) > 0

    def test_clear_asset(self):
        """Test clearing prices for a specific asset."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = HistoricalPriceCache(cache_file)
            
            # Add prices for two assets
            dates = pd.date_range(start=date(2024, 1, 15), end=date(2024, 1, 17), freq="D")
            prices_df = pd.DataFrame({"price": [150.0, 151.0, 152.0]}, index=dates)
            prices_df.index.name = "date"
            
            cache.set_cached_prices("GOOG", "Stock", prices_df, native_prices_df=prices_df, native_currency="USD")
            cache.set_cached_prices("AAPL", "Stock", prices_df, native_prices_df=prices_df, native_currency="USD")
            
            # Clear one asset
            cache.clear_asset("GOOG", "Stock")
            
            # GOOG should be gone
            assert cache.get_cached_price("GOOG", "Stock", date(2024, 1, 16)) is None
            # AAPL should still be there
            assert cache.get_cached_price("AAPL", "Stock", date(2024, 1, 16)) == 151.0

    def test_clear_all(self):
        """Test clearing entire cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = HistoricalPriceCache(cache_file)
            
            # Add prices
            dates = pd.date_range(start=date(2024, 1, 15), end=date(2024, 1, 17), freq="D")
            prices_df = pd.DataFrame({"price": [150.0, 151.0, 152.0]}, index=dates)
            prices_df.index.name = "date"
            
            cache.set_cached_prices("GOOG", "Stock", prices_df, native_prices_df=prices_df, native_currency="USD")
            
            # Clear all
            cache.clear_all()
            
            # Should be empty
            assert cache.get_cached_price("GOOG", "Stock", date(2024, 1, 16)) is None


class TestPriceServiceHistorical:
    """Tests for PriceService historical price methods."""

    @patch("wpm.pricing.service.CurrencyService")
    def test_get_historical_price(self, mock_currency_service_class):
        """Test getting historical price for a single asset."""
        mock_currency_service = Mock()
        mock_currency_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_currency_service
        
        # Create service first
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            historical_cache_file = Path(temp_dir) / "test_historical_cache.parquet"
            service = PriceService(
                cache_file=cache_file,
                historical_cache_file=historical_cache_file,
                currency_service=mock_currency_service
            )
            
            # Mock the retriever's get_historical_prices method
            mock_stock_retriever = Mock()
            dates = pd.date_range(start=date(2024, 1, 15), end=date(2024, 1, 15), freq="D")
            prices_df = pd.DataFrame({"price": [150.0]}, index=dates)
            prices_df.index.name = "date"
            # Service calls retriever with a list, so retriever returns Dict[str, pd.DataFrame]
            mock_stock_retriever.get_historical_prices.return_value = {"GOOG": prices_df}
            mock_stock_retriever._detect_currency.return_value = "USD"
            service._stock_retriever = mock_stock_retriever
            
            # Get historical price (calls get_historical_prices with [ticker])
            price = service.get_historical_price("GOOG", "Stock", date(2024, 1, 15))
            assert price == 150.0
            # get_historical_price calls get_historical_prices with a list
            mock_stock_retriever.get_historical_prices.assert_called_once()

    @patch("wpm.pricing.service.CurrencyService")
    def test_get_historical_prices(self, mock_currency_service_class):
        """Test getting historical prices for multiple assets."""
        mock_currency_service = Mock()
        mock_currency_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_currency_service
        
        # Create service first
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            historical_cache_file = Path(temp_dir) / "test_historical_cache.parquet"
            service = PriceService(
                cache_file=cache_file,
                historical_cache_file=historical_cache_file,
                currency_service=mock_currency_service
            )
            
            # Mock the retriever's get_historical_prices method
            mock_stock_retriever = Mock()
            dates = pd.date_range(start=date(2024, 1, 15), end=date(2024, 1, 20), freq="D")
            prices_df_goog = pd.DataFrame({"price": [150.0] * 6}, index=dates)
            prices_df_goog.index.name = "date"
            prices_df_aapl = pd.DataFrame({"price": [175.0] * 6}, index=dates)
            prices_df_aapl.index.name = "date"
            # For multiple tickers, retriever returns Dict[str, pd.DataFrame]
            mock_stock_retriever.get_historical_prices.return_value = {
                "GOOG": prices_df_goog,
                "AAPL": prices_df_aapl
            }
            mock_stock_retriever._detect_currency.return_value = "USD"
            service._stock_retriever = mock_stock_retriever
            
            # Get historical prices
            prices = service.get_historical_prices(
                ["GOOG", "AAPL"], "Stock", date(2024, 1, 15), date(2024, 1, 20)
            )
            
            # Should have called retriever once with both tickers (batch)
            assert mock_stock_retriever.get_historical_prices.call_count == 1
            assert "GOOG" in prices
            assert "AAPL" in prices
            # Prices should be Dict[date, float] for each ticker
            assert isinstance(prices["GOOG"], dict)
            assert isinstance(prices["AAPL"], dict)

