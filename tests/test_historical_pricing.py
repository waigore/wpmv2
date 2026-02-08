"""Tests for historical price retrieval and caching."""

import pytest
from datetime import date
from pathlib import Path
import tempfile
import pandas as pd
from unittest.mock import Mock, patch

from wpm.pricing.historical_cache import HistoricalPriceCache
from wpm.pricing.service import PriceService
from wpm.pricing.splits import SplitService


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
            service._retrievers["Stock"] = service._retrievers["ETF"] = mock_stock_retriever

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
            service._retrievers["Stock"] = service._retrievers["ETF"] = mock_stock_retriever

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

    @patch("wpm.pricing.service.CurrencyService")
    def test_get_historical_prices_cached_prices_only_false(self, mock_currency_service_class):
        """Test get_historical_prices with cached_prices_only=False (default behavior)."""
        mock_currency_service = Mock()
        mock_currency_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_currency_service
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            historical_cache_file = Path(temp_dir) / "test_historical_cache.parquet"
            service = PriceService(
                cache_file=cache_file,
                historical_cache_file=historical_cache_file,
                currency_service=mock_currency_service
            )
            
            mock_stock_retriever = Mock()
            dates = pd.date_range(start=date(2024, 1, 15), end=date(2024, 1, 20), freq="D")
            prices_df = pd.DataFrame({"price": [150.0] * 6}, index=dates)
            prices_df.index.name = "date"
            mock_stock_retriever.get_historical_prices.return_value = {"GOOG": prices_df}
            mock_stock_retriever._detect_currency.return_value = "USD"
            service._stock_retriever = mock_stock_retriever
            service._retrievers["Stock"] = service._retrievers["ETF"] = mock_stock_retriever

            # Call with cached_prices_only=False (default)
            prices = service.get_historical_prices(
                ["GOOG"], "Stock", date(2024, 1, 15), date(2024, 1, 20),
                cached_prices_only=False
            )
            
            # Should call retriever (normal behavior)
            assert mock_stock_retriever.get_historical_prices.call_count == 1
            assert "GOOG" in prices

    @patch("wpm.pricing.service.CurrencyService")
    def test_get_historical_prices_cached_prices_only_true_with_cache(self, mock_currency_service_class):
        """Test get_historical_prices with cached_prices_only=True when cache exists."""
        mock_currency_service = Mock()
        mock_currency_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_currency_service
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            historical_cache_file = Path(temp_dir) / "test_historical_cache.parquet"
            service = PriceService(
                cache_file=cache_file,
                historical_cache_file=historical_cache_file,
                currency_service=mock_currency_service
            )
            
            # Pre-populate cache
            dates = pd.date_range(start=date(2024, 1, 15), end=date(2024, 1, 20), freq="D")
            prices_df = pd.DataFrame({"price": [150.0] * 6}, index=dates)
            prices_df.index.name = "date"
            service.historical_cache.set_cached_prices(
                "GOOG", "Stock", prices_df, native_prices_df=prices_df, native_currency="USD"
            )
            
            mock_stock_retriever = Mock()
            service._stock_retriever = mock_stock_retriever
            
            # Call with cached_prices_only=True
            prices = service.get_historical_prices(
                ["GOOG"], "Stock", date(2024, 1, 15), date(2024, 1, 20),
                cached_prices_only=True
            )
            
            # Should NOT call retriever when cache exists
            mock_stock_retriever.get_historical_prices.assert_not_called()
            assert "GOOG" in prices
            assert len(prices["GOOG"]) == 6

    @patch("wpm.pricing.service.CurrencyService")
    def test_get_historical_prices_cached_prices_only_true_without_cache(self, mock_currency_service_class):
        """Test get_historical_prices with cached_prices_only=True when cache miss raises error."""
        mock_currency_service = Mock()
        mock_currency_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_currency_service
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            historical_cache_file = Path(temp_dir) / "test_historical_cache.parquet"
            service = PriceService(
                cache_file=cache_file,
                historical_cache_file=historical_cache_file,
                currency_service=mock_currency_service
            )
            
            mock_stock_retriever = Mock()
            service._stock_retriever = mock_stock_retriever
            
            # Call with cached_prices_only=True but no cache
            with pytest.raises(ValueError, match="No cached prices available"):
                service.get_historical_prices(
                    ["GOOG"], "Stock", date(2024, 1, 15), date(2024, 1, 20),
                    cached_prices_only=True
                )
            
            # Should NOT call retriever when cached_prices_only=True
            mock_stock_retriever.get_historical_prices.assert_not_called()

    @patch("wpm.pricing.service.CurrencyService")
    def test_cache_invalidation_with_splits(self, mock_currency_service_class):
        """Test that cache is invalidated when splits occur in the date range."""
        mock_currency_service = Mock()
        mock_currency_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_currency_service
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            historical_cache_file = Path(temp_dir) / "test_historical_cache.parquet"
            service = PriceService(
                cache_file=cache_file,
                historical_cache_file=historical_cache_file,
                currency_service=mock_currency_service
            )
            
            # Pre-populate cache with prices INCLUDING dates after split (pre-split prices)
            # This simulates the scenario where prices were cached before the split occurred
            dates_full_range = pd.date_range(start=date(2024, 1, 1), end=date(2024, 1, 10), freq="D")
            # All prices are pre-split (100-109) - these will become stale after split
            prices_pre_split = pd.DataFrame(
                {"price": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0]},
                index=dates_full_range
            )
            prices_pre_split.index.name = "date"
            service.historical_cache.set_cached_prices(
                "GOOG", "Stock", prices_pre_split, 
                native_prices_df=prices_pre_split, native_currency="USD"
            )
            
            # Verify cache has prices for full range
            cached_prices = service.historical_cache.get_cached_prices(
                "GOOG", "Stock", date(2024, 1, 1), date(2024, 1, 10)
            )
            assert cached_prices is not None
            assert len(cached_prices) == 10
            # Verify cache has pre-split prices (105.0 for 2024-01-06)
            assert cached_prices.loc[pd.Timestamp('2024-01-06'), 'price'] == 105.0
            
            # Mock split service to return a split on 2024-01-06
            with patch('wpm.pricing.service.SplitService') as mock_split_service_class:
                mock_split_service = Mock(spec=SplitService)
                # Create mock split data (2:1 split on 2024-01-06)
                split_data = pd.Series(
                    [2.0],
                    index=[pd.Timestamp('2024-01-06')]
                )
                mock_split_service.get_splits.return_value = {"GOOG": split_data}
                mock_split_service_class.return_value = mock_split_service
                # Service was created before the patch; use the mock so get_historical_prices calls it
                service._split_service = mock_split_service

                # Mock retriever to return post-split prices for the full range
                # Post-split prices should be halved (50-54.5)
                prices_post_split = pd.DataFrame(
                    {"price": [100.0, 101.0, 102.0, 103.0, 104.0, 50.0, 51.0, 52.0, 53.0, 54.0]},
                    index=dates_full_range
                )
                prices_post_split.index.name = "date"
                mock_stock_retriever = Mock()
                mock_stock_retriever.get_historical_prices.return_value = {
                    "GOOG": prices_post_split
                }
                service._stock_retriever = mock_stock_retriever
                service._retrievers["Stock"] = service._retrievers["ETF"] = mock_stock_retriever

                # Mock detect_currency to return USD (so no conversion happens)
                with patch.object(service, 'detect_currency', return_value='USD'):
                    # Request prices including split date (2024-01-06)
                    # Cache should be invalidated for dates >= split date
                    prices = service.get_historical_prices(
                        ["GOOG"], "Stock", date(2024, 1, 1), date(2024, 1, 10)
                    )
                
                    # Verify split service was called with batch
                    mock_split_service.get_splits.assert_called_once_with(
                        ["GOOG"],
                        start_date=date(2024, 1, 1),
                        end_date=date(2024, 1, 10),
                    )
                    
                    # Verify retriever was called (cache was invalidated, so fetch was needed)
                    mock_stock_retriever.get_historical_prices.assert_called_once()
                    
                    # Verify cache was invalidated and repopulated with fresh prices
                    # Cache should still have prices for dates before split
                    cached_before_split = service.historical_cache.get_cached_prices(
                        "GOOG", "Stock", date(2024, 1, 1), date(2024, 1, 5)
                    )
                    assert cached_before_split is not None
                    assert len(cached_before_split) == 5
                    
                    # After fetching, cache should have NEW prices for dates >= split date
                    # Verify the cache was updated with post-split prices
                    cached_after_split = service.historical_cache.get_cached_prices(
                        "GOOG", "Stock", date(2024, 1, 6), date(2024, 1, 10)
                    )
                    assert cached_after_split is not None
                    # Verify the cached prices are the post-split prices (50.0, not 105.0)
                    assert cached_after_split.loc[pd.Timestamp('2024-01-06'), 'price'] == 50.0
                    assert cached_after_split.loc[pd.Timestamp('2024-01-10'), 'price'] == 54.0
                    
                    # Verify the returned prices include post-split prices
                    assert "GOOG" in prices
                    goog_prices = prices["GOOG"]
                    # Pre-split prices should be from cache (100-104)
                    assert goog_prices[date(2024, 1, 1)] == 100.0
                    assert goog_prices[date(2024, 1, 5)] == 104.0
                    # Post-split prices should be from fresh fetch (50-54)
                    assert goog_prices[date(2024, 1, 6)] == 50.0
                    assert goog_prices[date(2024, 1, 10)] == 54.0
                
                # Verify retriever was called to fetch fresh prices for invalidated dates
                mock_stock_retriever.get_historical_prices.assert_called_once()
                
                # Verify returned prices include both cached (pre-split) and fresh (post-split) prices
                assert "GOOG" in prices
                goog_prices = prices["GOOG"]
                # Should have prices for all dates
                assert date(2024, 1, 1) in goog_prices  # Cached pre-split
                assert date(2024, 1, 5) in goog_prices  # Cached pre-split
                assert date(2024, 1, 6) in goog_prices  # Fresh post-split
                assert date(2024, 1, 10) in goog_prices  # Fresh post-split
