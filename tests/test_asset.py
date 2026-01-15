"""Tests for asset metadata module."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import pytz

from wpm.asset import AssetMetadataCache, AssetService
from wpm.pricing import PriceService, YahooFinanceRetriever


class TestAssetMetadataCache:
    """Tests for AssetMetadataCache."""

    def test_cache_initialization(self):
        """Test cache initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = AssetMetadataCache(cache_file=cache_file)
            assert cache.cache_file == cache_file

    def test_get_cached_metadata_no_cache(self):
        """Test getting cached metadata when cache doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = AssetMetadataCache(cache_file=cache_file)

            metadata = cache.get_cached_metadata("GOOG", "Stock")
            assert metadata is None

    def test_set_and_get_cached_metadata(self):
        """Test setting and getting cached metadata."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = AssetMetadataCache(cache_file=cache_file)

            metadata = {
                "name": "Alphabet Inc.",
                "sector": "Technology",
                "industry": "Internet Content & Information",
                "country": "United States",
                "market_cap": 1_500_000_000_000,
                "category": "unknown",
            }
            cache.set_cached_metadata("GOOG", "Stock", metadata)

            retrieved = cache.get_cached_metadata("GOOG", "Stock")
            assert retrieved is not None
            assert retrieved["name"] == "Alphabet Inc."
            assert retrieved["sector"] == "Technology"
            assert retrieved["market_cap"] == 1_500_000_000_000

    @patch("wpm.asset.datetime")
    def test_cache_validity_recent(self, mock_datetime):
        """Test cache validity with recent cache."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = AssetMetadataCache(cache_file=cache_file)

            recent_timestamp = mock_now - timedelta(hours=12)
            metadata = {
                "name": "Alphabet Inc.",
                "sector": "Technology",
                "industry": "Internet Content & Information",
                "country": "United States",
                "market_cap": 1_500_000_000_000,
                "category": "unknown",
            }
            cache.set_cached_metadata("GOOG", "Stock", metadata, timestamp=recent_timestamp)

            retrieved = cache.get_cached_metadata("GOOG", "Stock")
            assert retrieved is not None

    @patch("wpm.asset.datetime")
    def test_cache_validity_stale(self, mock_datetime):
        """Test cache validity with stale cache (older than 24 hours)."""
        mock_now = datetime(2024, 1, 15, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = AssetMetadataCache(cache_file=cache_file)

            stale_timestamp = mock_now - timedelta(hours=25)
            metadata = {
                "name": "Alphabet Inc.",
                "sector": "Technology",
                "industry": "Internet Content & Information",
                "country": "United States",
                "market_cap": 1_500_000_000_000,
                "category": "unknown",
            }
            cache.set_cached_metadata("GOOG", "Stock", metadata, timestamp=stale_timestamp)

            retrieved = cache.get_cached_metadata("GOOG", "Stock")
            assert retrieved is None  # Stale cache should return None

    def test_get_cached_metadata_batch(self):
        """Test batch cache retrieval."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = AssetMetadataCache(cache_file=cache_file)

            metadata1 = {
                "name": "Alphabet Inc.",
                "sector": "Technology",
                "industry": "Internet Content & Information",
                "country": "United States",
                "market_cap": 1_500_000_000_000,
                "category": "unknown",
            }
            metadata2 = {
                "name": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "country": "United States",
                "market_cap": 2_000_000_000_000,
                "category": "unknown",
            }

            cache.set_cached_metadata("GOOG", "Stock", metadata1)
            cache.set_cached_metadata("AAPL", "Stock", metadata2)

            results = cache.get_cached_metadata_batch(["GOOG", "AAPL", "MSFT"], "Stock")
            assert results["GOOG"] is not None
            assert results["AAPL"] is not None
            assert results["MSFT"] is None  # Not in cache

    def test_set_cached_metadata_batch(self):
        """Test batch cache storage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            cache = AssetMetadataCache(cache_file=cache_file)

            metadata_list = [
                {
                    "ticker": "GOOG",
                    "asset_type": "Stock",
                    "metadata": {
                        "name": "Alphabet Inc.",
                        "sector": "Technology",
                        "industry": "Internet Content & Information",
                        "country": "United States",
                        "market_cap": 1_500_000_000_000,
                        "category": "unknown",
                    },
                },
                {
                    "ticker": "AAPL",
                    "asset_type": "Stock",
                    "metadata": {
                        "name": "Apple Inc.",
                        "sector": "Technology",
                        "industry": "Consumer Electronics",
                        "country": "United States",
                        "market_cap": 2_000_000_000_000,
                        "category": "unknown",
                    },
                },
            ]

            cache.set_cached_metadata_batch(metadata_list)

            assert cache.get_cached_metadata("GOOG", "Stock") is not None
            assert cache.get_cached_metadata("AAPL", "Stock") is not None


class TestAssetService:
    """Tests for AssetService."""

    @patch("wpm.pricing.yahoo.yf")
    def test_get_metadata_success(self, mock_yf):
        """Test successful metadata retrieval via retriever."""
        mock_ticker = Mock()
        mock_info = {
            "longName": "Alphabet Inc.",
            "sector": "Technology",
            "industry": "Internet Content & Information",
            "country": "United States",
            "marketCap": 1_500_000_000_000,
            "category": "Technology",
        }
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            price_service = PriceService()
            service = AssetService(cache_file=cache_file, price_service=price_service)

            metadata = service.get_metadata("GOOG", "Stock")

            assert metadata is not None
            assert metadata["name"] == "Alphabet Inc."
            assert metadata["sector"] == "Technology"
            assert metadata["industry"] == "Internet Content & Information"
            assert metadata["country"] == "United States"
            assert metadata["market_cap"] == 1_500_000_000_000
            assert metadata["category"] == "Technology"

    @patch("wpm.pricing.yahoo.yf")
    def test_get_metadata_fallback_name(self, mock_yf):
        """Test metadata retrieval with name fallback."""
        mock_ticker = Mock()
        mock_info = {
            "shortName": "Alphabet",
            "marketCap": 1_500_000_000_000,
        }
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            price_service = PriceService()
            service = AssetService(cache_file=cache_file, price_service=price_service)

            metadata = service.get_metadata("GOOG", "Stock")

            assert metadata is not None
            assert metadata["name"] == "Alphabet"  # Uses shortName

    @patch("wpm.pricing.yahoo.yf")
    def test_get_metadata_crypto(self, mock_yf):
        """Test metadata retrieval for crypto (no sector/industry/country)."""
        mock_ticker = Mock()
        mock_info = {
            "longName": "Bitcoin USD",
            "marketCap": 500_000_000_000,
            "category": "Crypto",
        }
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            price_service = PriceService()
            service = AssetService(cache_file=cache_file, price_service=price_service)

            metadata = service.get_metadata("BTC-USD", "Crypto")

            assert metadata is not None
            assert metadata["name"] == "Bitcoin USD"
            assert metadata["sector"] == "N/A"  # Crypto doesn't have sector
            assert metadata["industry"] == "N/A"
            assert metadata["country"] == "N/A"
            assert metadata["market_cap"] == 500_000_000_000

    @patch("wpm.pricing.yahoo.yf")
    def test_get_metadata_batch_mixed_cache(self, mock_yf):
        """Test batch metadata retrieval with mixed cache states."""
        mock_ticker = Mock()
        mock_info = {
            "longName": "Microsoft Corporation",
            "sector": "Technology",
            "industry": "Software",
            "country": "United States",
            "marketCap": 2_500_000_000_000,
            "category": "Technology",
        }
        mock_ticker.info = mock_info
        mock_yf.Ticker.return_value = mock_ticker

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            price_service = PriceService()
            service = AssetService(cache_file=cache_file, price_service=price_service)

            # Pre-populate cache for GOOG
            cached_metadata = {
                "name": "Alphabet Inc.",
                "sector": "Technology",
                "industry": "Internet Content & Information",
                "country": "United States",
                "market_cap": 1_500_000_000_000,
                "category": "unknown",
            }
            service.cache.set_cached_metadata("GOOG", "Stock", cached_metadata)

            # Batch retrieve: GOOG (cached), MSFT (not cached)
            results = service.get_metadata_batch(["GOOG", "MSFT"], "Stock")

            assert results["GOOG"] is not None
            assert results["GOOG"]["name"] == "Alphabet Inc."  # From cache
            assert results["MSFT"] is not None
            assert results["MSFT"]["name"] == "Microsoft Corporation"  # From API

            # Verify MSFT was cached
            assert service.cache.get_cached_metadata("MSFT", "Stock") is not None

    @patch("wpm.pricing.yahoo.yf")
    def test_get_metadata_empty_info(self, mock_yf):
        """Test metadata retrieval with empty info dict."""
        mock_ticker = Mock()
        mock_ticker.info = {}
        mock_yf.Ticker.return_value = mock_ticker

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            price_service = PriceService()
            service = AssetService(cache_file=cache_file, price_service=price_service)

            metadata = service.get_metadata("INVALID", "Stock")
            assert metadata is None

    @patch("wpm.pricing.yahoo.yf")
    def test_get_metadata_exception(self, mock_yf):
        """Test metadata retrieval with exception."""
        mock_yf.Ticker.side_effect = Exception("Network error")

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            price_service = PriceService()
            service = AssetService(cache_file=cache_file, price_service=price_service)

            metadata = service.get_metadata("GOOG", "Stock")
            assert metadata is None

    def test_get_metadata_no_price_service(self):
        """Test metadata retrieval without PriceService."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = AssetService(cache_file=cache_file)

            metadata = service.get_metadata("GOOG", "Stock")
            assert metadata is None

    def test_get_metadata_unsupported_retriever(self):
        """Test metadata retrieval with unsupported retriever."""
        # Create a mock PriceService with a retriever that doesn't support metadata
        mock_retriever = Mock()
        mock_retriever.metadata_supported = False
        
        mock_price_service = Mock()
        mock_price_service.get_retriever.return_value = mock_retriever
        
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = AssetService(cache_file=cache_file, price_service=mock_price_service)

            # Should return None when retriever doesn't support metadata
            metadata = service.get_metadata("TEST", "Stock")
            assert metadata is None

    def test_update_metadata(self):
        """Test updating metadata from info dict."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = AssetService(cache_file=cache_file)

            info_dict = {
                "longName": "Alphabet Inc.",
                "sector": "Technology",
                "industry": "Internet Content & Information",
                "country": "United States",
                "marketCap": 1_500_000_000_000,
                "category": "Technology",
            }

            service.update_metadata("GOOG", "Stock", info_dict)

            cached = service.cache.get_cached_metadata("GOOG", "Stock")
            assert cached is not None
            assert cached["name"] == "Alphabet Inc."

    def test_update_metadata_batch(self):
        """Test batch metadata update."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = AssetService(cache_file=cache_file)

            metadata_dict = {
                ("GOOG", "Stock"): {
                    "longName": "Alphabet Inc.",
                    "sector": "Technology",
                    "industry": "Internet Content & Information",
                    "country": "United States",
                    "marketCap": 1_500_000_000_000,
                    "category": "Technology",
                },
                ("AAPL", "Stock"): {
                    "longName": "Apple Inc.",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "country": "United States",
                    "marketCap": 2_000_000_000_000,
                    "category": "Technology",
                },
            }

            service.update_metadata_batch(metadata_dict)

            assert service.cache.get_cached_metadata("GOOG", "Stock") is not None
            assert service.cache.get_cached_metadata("AAPL", "Stock") is not None

    def test_extract_metadata_market_cap_fallback(self):
        """Test metadata extraction with market cap fallback to totalAssets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = AssetService(cache_file=cache_file)

            info_dict = {
                "longName": "ETF Name",
                "totalAssets": 10_000_000_000,  # No marketCap, use totalAssets
                "category": "ETF",
            }

            metadata = service._extract_metadata_from_info(info_dict, "ETF-TICKER", "ETF")
            assert metadata["market_cap"] == 10_000_000_000

    def test_extract_metadata_name_fallback(self):
        """Test metadata extraction with name fallback chain."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "test_cache.parquet"
            service = AssetService(cache_file=cache_file)

            # Test fallback to ticker
            info_dict = {}
            metadata = service._extract_metadata_from_info(info_dict, "TICKER", "Stock")
            assert metadata["name"] == "TICKER"  # Falls back to ticker

            # Test shortName fallback
            info_dict = {"shortName": "Short Name"}
            metadata = service._extract_metadata_from_info(info_dict, "TICKER", "Stock")
            assert metadata["name"] == "Short Name"
