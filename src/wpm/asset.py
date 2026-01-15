"""Manages asset metadata retrieval and caching."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytz
from typing import TYPE_CHECKING

from wpm.config import Config
from wpm.utils import concat_dataframes

if TYPE_CHECKING:
    from wpm.pricing.service import PriceService

logger = logging.getLogger(__name__)


class AssetMetadataCache:
    """Manages persistent Parquet-based asset metadata cache."""

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize asset metadata cache.

        Args:
            cache_file: Path to cache file (default: Config.ASSET_METADATA_CACHE_FILE)
        """
        self.cache_file = cache_file or Config.ASSET_METADATA_CACHE_FILE
        self._cache: Optional[pd.DataFrame] = None
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        cache_dir = self.cache_file.parent
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created cache directory: {cache_dir}")

    def _load_cache(self) -> pd.DataFrame:
        """Load metadata cache from Parquet file.

        Returns:
            DataFrame with columns: ticker, asset_type, name, sector, industry, country, market_cap, category, timestamp
        """
        if self._cache is not None:
            return self._cache

        expected_columns = [
            "ticker",
            "asset_type",
            "name",
            "sector",
            "industry",
            "country",
            "market_cap",
            "category",
            "timestamp",
        ]

        if not self.cache_file.exists():
            logger.debug("Cache file does not exist, starting with empty cache")
            self._cache = pd.DataFrame(columns=expected_columns)
            return self._cache

        try:
            self._cache = pd.read_parquet(self.cache_file)
            logger.info(
                f"Loaded asset metadata cache from {self.cache_file} with {len(self._cache)} entries"
            )
        except Exception as e:
            logger.warning(f"Error loading cache file: {e}. Starting with empty cache")
            self._cache = pd.DataFrame(columns=expected_columns)

        return self._cache

    def _save_cache(self) -> None:
        """Save metadata cache to Parquet file."""
        if self._cache is None:
            return

        try:
            self._cache.to_parquet(self.cache_file, index=False)
            logger.debug(f"Saved asset metadata cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Error saving cache file: {e}")

    def _normalize_timestamp(self, cache_timestamp: Any) -> Optional[datetime]:
        """Normalize cache timestamp to timezone-aware datetime.

        Args:
            cache_timestamp: Timestamp value from cache (can be various types)

        Returns:
            Normalized datetime in UTC, or None if timestamp is invalid
        """
        if cache_timestamp is None:
            return None

        try:
            if pd.isna(cache_timestamp):
                return None
        except (ValueError, TypeError):
            return None

        if isinstance(cache_timestamp, str):
            try:
                cache_timestamp = pd.to_datetime(cache_timestamp)
            except (ValueError, TypeError):
                return None

        try:
            if isinstance(cache_timestamp, pd.Timestamp):
                cache_timestamp = cache_timestamp.to_pydatetime()
            elif isinstance(cache_timestamp, datetime):
                pass
            else:
                cache_timestamp = pd.to_datetime(cache_timestamp).to_pydatetime()
        except (ValueError, TypeError, AttributeError):
            return None

        if cache_timestamp.tzinfo is None:
            cache_timestamp = pytz.UTC.localize(cache_timestamp)
        else:
            cache_timestamp = cache_timestamp.astimezone(pytz.UTC)

        return cache_timestamp

    def _is_cache_valid(self, cache_entry: pd.Series) -> bool:
        """Check if cached metadata is valid (24-hour expiry).

        Args:
            cache_entry: Cache entry (row from DataFrame)

        Returns:
            True if cache is valid, False otherwise
        """
        cache_timestamp = cache_entry["timestamp"]
        normalized_timestamp = self._normalize_timestamp(cache_timestamp)

        if normalized_timestamp is None:
            return False

        now = datetime.now(pytz.UTC)
        age_minutes = (now - normalized_timestamp).total_seconds() / 60

        # 24-hour expiry (1440 minutes)
        is_valid = age_minutes < 1440
        logger.debug(
            f"Cache validity for {cache_entry['ticker']}: "
            f"{is_valid} (age: {age_minutes:.1f} min)"
        )
        return is_valid

    def get_cached_metadata(
        self, ticker: str, asset_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached metadata if valid.

        Args:
            ticker: Asset ticker
            asset_type: Asset type

        Returns:
            Cached metadata dict if valid, None otherwise
        """
        cache = self._load_cache()

        if cache.empty:
            return None

        matches = cache[
            (cache["ticker"] == ticker) & (cache["asset_type"] == asset_type)
        ]

        if matches.empty:
            logger.debug(f"No cache entry found for {ticker} ({asset_type})")
            return None

        cache_entry = matches.iloc[0]

        if self._is_cache_valid(cache_entry):
            metadata = {
                "name": cache_entry["name"],
                "sector": cache_entry["sector"],
                "industry": cache_entry["industry"],
                "country": cache_entry["country"],
                "market_cap": cache_entry["market_cap"] if pd.notna(cache_entry["market_cap"]) else None,
                "category": cache_entry["category"],
            }
            logger.info(
                f"Cache hit for {ticker} ({asset_type}): metadata retrieved"
            )
            return metadata

        logger.debug(f"Cache entry for {ticker} ({asset_type}) is invalid/expired")
        return None

    def get_cached_metadata_batch(
        self, tickers: List[str], asset_type: str
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get cached metadata for multiple tickers.

        Args:
            tickers: List of asset tickers
            asset_type: Asset type for all tickers

        Returns:
            Dictionary mapping ticker to metadata dict (or None if missing/invalid)
        """
        cache = self._load_cache()
        result: Dict[str, Optional[Dict[str, Any]]] = {}

        if cache.empty:
            for ticker in tickers:
                result[ticker] = None
            return result

        for ticker in tickers:
            matches = cache[
                (cache["ticker"] == ticker) & (cache["asset_type"] == asset_type)
            ]

            if matches.empty:
                logger.debug(f"No cache entry found for {ticker} ({asset_type})")
                result[ticker] = None
                continue

            cache_entry = matches.iloc[0]

            if self._is_cache_valid(cache_entry):
                metadata = {
                    "name": cache_entry["name"],
                    "sector": cache_entry["sector"],
                    "industry": cache_entry["industry"],
                    "country": cache_entry["country"],
                    "market_cap": cache_entry["market_cap"] if pd.notna(cache_entry["market_cap"]) else None,
                    "category": cache_entry["category"],
                }
                result[ticker] = metadata
            else:
                logger.debug(f"Cache entry for {ticker} ({asset_type}) is invalid/expired")
                result[ticker] = None

        cached_count = sum(1 for v in result.values() if v is not None)
        if cached_count > 0:
            logger.info(
                f"Cache hit for {cached_count} of {len(tickers)} tickers ({asset_type})"
            )

        return result

    def set_cached_metadata(
        self,
        ticker: str,
        asset_type: str,
        metadata: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Store metadata in cache.

        Args:
            ticker: Asset ticker
            asset_type: Asset type
            metadata: Metadata dictionary
            timestamp: Timestamp (default: current time)
        """
        cache = self._load_cache()

        if timestamp is None:
            timestamp = datetime.now(pytz.UTC)

        new_entry = pd.DataFrame(
            [
                {
                    "ticker": ticker,
                    "asset_type": asset_type,
                    "name": metadata.get("name", ticker),
                    "sector": metadata.get("sector", "N/A"),
                    "industry": metadata.get("industry", "N/A"),
                    "country": metadata.get("country", "N/A"),
                    "market_cap": metadata.get("market_cap"),
                    "category": metadata.get("category", "unknown"),
                    "timestamp": timestamp,
                }
            ]
        )

        cache = cache[
            ~((cache["ticker"] == ticker) & (cache["asset_type"] == asset_type))
        ]

        cache = concat_dataframes([cache, new_entry], ignore_index=True)
        self._cache = cache

        logger.debug(f"Stored metadata in cache for {ticker} ({asset_type})")
        self._save_cache()

    def set_cached_metadata_batch(
        self, metadata_list: List[Dict[str, Any]]
    ) -> None:
        """Store multiple metadata entries in cache efficiently.

        Args:
            metadata_list: List of dicts, each containing:
                - ticker: str
                - asset_type: str
                - metadata: Dict[str, Any]
                - timestamp: Optional[datetime]
        """
        if not metadata_list:
            return

        cache = self._load_cache()

        new_entries = []
        for entry_data in metadata_list:
            ticker = entry_data["ticker"]
            asset_type = entry_data["asset_type"]
            metadata = entry_data["metadata"]
            timestamp = entry_data.get("timestamp")
            if timestamp is None:
                timestamp = datetime.now(pytz.UTC)

            # Remove existing entry for this ticker/asset_type
            cache = cache[
                ~((cache["ticker"] == ticker) & (cache["asset_type"] == asset_type))
            ]

            new_entries.append(
                {
                    "ticker": ticker,
                    "asset_type": asset_type,
                    "name": metadata.get("name", ticker),
                    "sector": metadata.get("sector", "N/A"),
                    "industry": metadata.get("industry", "N/A"),
                    "country": metadata.get("country", "N/A"),
                    "market_cap": metadata.get("market_cap"),
                    "category": metadata.get("category", "unknown"),
                    "timestamp": timestamp,
                }
            )

        if new_entries:
            new_df = pd.DataFrame(new_entries)
            cache = concat_dataframes([cache, new_df], ignore_index=True)
            self._cache = cache

            logger.debug(
                f"Stored {len(new_entries)} metadata entries in cache (batch)"
            )
            self._save_cache()


class AssetService:
    """Service for retrieving and caching asset metadata."""

    def __init__(self, cache_file: Optional[Path] = None, price_service: Optional["PriceService"] = None):
        """Initialize asset service.

        Args:
            cache_file: Path to cache file (default: Config.ASSET_METADATA_CACHE_FILE)
            price_service: Optional PriceService instance for retrieving metadata via retrievers
        """
        self.cache = AssetMetadataCache(cache_file)
        self.price_service = price_service

    def _extract_metadata_from_info(
        self, info: Dict[str, Any], ticker: str, asset_type: str
    ) -> Dict[str, Any]:
        """Extract and normalize metadata from yfinance .info dict.

        Args:
            info: yfinance .info dictionary
            ticker: Asset ticker (for fallback)
            asset_type: Asset type

        Returns:
            Normalized metadata dictionary
        """
        metadata: Dict[str, Any] = {}

        # Name: longName or shortName or name or ticker (fallback)
        metadata["name"] = (
            info.get("longName")
            or info.get("shortName")
            or info.get("name")
            or ticker
        )

        # Sector, industry, country (equities only, fallback to "N/A")
        if asset_type in ("Stock", "ETF"):
            metadata["sector"] = info.get("sector", "N/A")
            metadata["industry"] = info.get("industry", "N/A")
            metadata["country"] = info.get("country", "N/A")
        else:
            metadata["sector"] = "N/A"
            metadata["industry"] = "N/A"
            metadata["country"] = "N/A"

        # Market cap: marketCap or totalAssets or None (fallback)
        metadata["market_cap"] = info.get("marketCap") or info.get("totalAssets")

        # Category: category or "unknown" (fallback)
        metadata["category"] = info.get("category", "unknown")

        return metadata

    def get_metadata(
        self, ticker: str, asset_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get metadata for a single asset.

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type ("Stock", "ETF", or "Crypto")

        Returns:
            Metadata dictionary, or None if retrieval fails
        """
        logger.debug(f"Retrieving metadata for {ticker} ({asset_type})")

        # Check cache first
        cached_metadata = self.cache.get_cached_metadata(ticker, asset_type)
        if cached_metadata is not None:
            logger.info(f"Retrieved metadata for {ticker} ({asset_type})")
            return cached_metadata

        # Fetch from retriever if price_service is available
        if self.price_service is None:
            logger.warning(
                f"PriceService not provided to AssetService. Cannot retrieve metadata for {ticker} ({asset_type})"
            )
            return None

        try:
            # For crypto metadata, use YahooFinanceRetriever (supports metadata)
            # For other asset types, use the standard retriever
            if asset_type == "Crypto":
                retriever = self.price_service.get_stock_retriever()  # YahooFinanceRetriever
            else:
                retriever = self.price_service.get_retriever(asset_type)
            
            if not retriever.metadata_supported:
                logger.warning(
                    f"Retriever for {asset_type} does not support metadata retrieval. "
                    f"Cannot retrieve metadata for {ticker}"
                )
                return None

            metadata = retriever.get_metadata(ticker, asset_type)

            if metadata is None:
                logger.warning(f"No metadata available for {ticker} ({asset_type})")
                return None

            # Update cache
            self.cache.set_cached_metadata(ticker, asset_type, metadata)

            logger.info(f"Retrieved metadata for {ticker} ({asset_type})")
            return metadata

        except NotImplementedError as e:
            logger.warning(f"Metadata retrieval not supported for {ticker} ({asset_type}): {e}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching metadata for {ticker} ({asset_type}): {e}")
            return None

    def get_metadata_batch(
        self, tickers: List[str], asset_type: str
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get metadata for multiple assets with batch optimization.

        Args:
            tickers: List of asset ticker symbols
            asset_type: Asset type for all tickers

        Returns:
            Dictionary mapping ticker to metadata dict (or None if retrieval fails)
        """
        if not tickers:
            return {}

        logger.debug(
            f"Batch retrieving metadata for {len(tickers)} {asset_type} assets"
        )

        # Check cache for all tickers first
        cached_results = self.cache.get_cached_metadata_batch(tickers, asset_type)

        # Identify stale/missing tickers
        stale_missing_tickers = [
            ticker for ticker, metadata in cached_results.items() if metadata is None
        ]

        if not stale_missing_tickers:
            # All tickers found in cache
            logger.info(
                f"Retrieved metadata for {len(tickers)} assets: {len(tickers)} from cache, 0 from API"
            )
            return cached_results

        # Fetch stale/missing tickers from retriever if price_service is available
        fetched_results: Dict[str, Optional[Dict[str, Any]]] = {}
        
        # Early return if price_service is not available
        if self.price_service is None:
            logger.warning(
                f"PriceService not provided to AssetService. Cannot retrieve metadata for {len(stale_missing_tickers)} tickers"
            )
            for ticker in stale_missing_tickers:
                fetched_results[ticker] = None
            # Continue to cache update and result combination below
        
        # Get retriever for asset type
        retriever = None
        try:
            # For crypto metadata, use YahooFinanceRetriever (supports metadata)
            # For other asset types, use the standard retriever
            if asset_type == "Crypto":
                retriever = self.price_service.get_stock_retriever()  # YahooFinanceRetriever
            else:
                retriever = self.price_service.get_retriever(asset_type)
        except Exception as e:
            logger.warning(
                f"Error getting retriever for {asset_type}: {e}"
            )
            for ticker in stale_missing_tickers:
                fetched_results[ticker] = None
            retriever = None
        
        # Early return if retriever doesn't support metadata
        if retriever is not None and not retriever.metadata_supported:
            logger.warning(
                f"Retriever for {asset_type} does not support metadata retrieval. "
                f"Cannot retrieve metadata for {len(stale_missing_tickers)} tickers"
            )
            for ticker in stale_missing_tickers:
                fetched_results[ticker] = None
            retriever = None
        
        # Fetch metadata for each ticker
        if retriever is not None:
            for ticker in stale_missing_tickers:
                try:
                    metadata = retriever.get_metadata(ticker, asset_type)
                    fetched_results[ticker] = metadata
                except NotImplementedError as e:
                    logger.debug(
                        f"Metadata retrieval not supported for {ticker} ({asset_type}): {e}"
                    )
                    fetched_results[ticker] = None
                except Exception as e:
                    logger.debug(
                        f"Error fetching metadata for {ticker} ({asset_type}): {e}"
                    )
                    fetched_results[ticker] = None

        # Update cache for all newly fetched metadata
        cache_updates = []
        for ticker, metadata in fetched_results.items():
            if metadata is not None:
                cache_updates.append(
                    {
                        "ticker": ticker,
                        "asset_type": asset_type,
                        "metadata": metadata,
                    }
                )

        if cache_updates:
            self.cache.set_cached_metadata_batch(cache_updates)

        # Combine cached and fetched results
        result = cached_results.copy()
        result.update(fetched_results)

        cached_count = sum(1 for v in cached_results.values() if v is not None)
        fetched_count = sum(1 for v in fetched_results.values() if v is not None)

        logger.info(
            f"Retrieved metadata for {len(tickers)} assets: {cached_count} from cache, {fetched_count} from API"
        )

        return result

    def update_metadata(
        self, ticker: str, asset_type: str, info_dict: Dict[str, Any]
    ) -> None:
        """Update cache from yfinance .info dict.

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type
            info_dict: yfinance .info dictionary
        """
        if not info_dict or len(info_dict) == 0:
            return

        metadata = self._extract_metadata_from_info(info_dict, ticker, asset_type)
        self.cache.set_cached_metadata(ticker, asset_type, metadata)
        logger.debug(f"Updated metadata cache for {ticker} ({asset_type})")

    def update_metadata_batch(
        self, metadata_dict: Dict[str, Dict[str, Any]]
    ) -> None:
        """Update cache for multiple tickers in batch.

        Args:
            metadata_dict: Dictionary mapping (ticker, asset_type) tuple to info_dict
                Format: {(ticker, asset_type): info_dict, ...}
        """
        if not metadata_dict:
            return

        cache_updates = []
        for (ticker, asset_type), info_dict in metadata_dict.items():
            if not info_dict or len(info_dict) == 0:
                continue

            metadata = self._extract_metadata_from_info(info_dict, ticker, asset_type)
            cache_updates.append(
                {
                    "ticker": ticker,
                    "asset_type": asset_type,
                    "metadata": metadata,
                }
            )

        if cache_updates:
            self.cache.set_cached_metadata_batch(cache_updates)
            logger.debug(
                f"Updated metadata cache for {len(cache_updates)} assets (batch)"
            )
