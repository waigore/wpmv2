"""Manages persistent Parquet-based price cache."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytz

from wpm.config import Config
from wpm.utils import concat_dataframes

logger = logging.getLogger(__name__)


class CacheValidityStatus(Enum):
    """Cache validity status enumeration."""

    VALID = "valid"
    PARTIAL = "partial"
    STALE = "stale"


@dataclass
class CacheValidity:
    """Cache validity status and stale entries.

    Attributes:
        status: The validity status of the cache
        stale_entries: List of stale cache entries, each containing:
            - ticker: str
            - asset_type: str
            - price: float
            - timestamp: datetime
    """

    status: CacheValidityStatus
    stale_entries: List[Dict[str, Any]]


class PriceCache:
    """Manages persistent Parquet-based price cache."""

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize price cache.

        Args:
            cache_file: Path to cache file (default: Config.CACHE_FILE)
        """
        self.cache_file = cache_file or Config.CACHE_FILE
        self._cache: Optional[pd.DataFrame] = None
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        cache_dir = self.cache_file.parent
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created cache directory: {cache_dir}")

    def _load_cache(self) -> pd.DataFrame:
        """Load price cache from Parquet file.

        Returns:
            DataFrame with columns: ticker, asset_type, price, timestamp
        """
        if self._cache is not None:
            return self._cache

        if not self.cache_file.exists():
            logger.debug("Cache file does not exist, starting with empty cache")
            self._cache = pd.DataFrame(
                columns=["ticker", "asset_type", "price", "timestamp"]
            )
            return self._cache

        try:
            self._cache = pd.read_parquet(self.cache_file)
            logger.info(f"Loaded price cache from {self.cache_file} with {len(self._cache)} entries")
        except Exception as e:
            logger.warning(f"Error loading cache file: {e}. Starting with empty cache")
            self._cache = pd.DataFrame(
                columns=["ticker", "asset_type", "price", "timestamp"]
            )

        return self._cache

    def _save_cache(self) -> None:
        """Save price cache to Parquet file."""
        if self._cache is None:
            return

        try:
            self._cache.to_parquet(self.cache_file, index=False)
            logger.debug(f"Saved price cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Error saving cache file: {e}")

    def _normalize_timestamp(self, cache_timestamp: Any) -> Optional[datetime]:
        """Normalize cache timestamp to timezone-aware datetime.

        Args:
            cache_timestamp: Timestamp value from cache (can be various types)

        Returns:
            Normalized datetime in UTC, or None if timestamp is invalid
        """
        # Check for NaN/NaT/None values
        if cache_timestamp is None:
            return None

        # Handle pd.NaT and other NA values
        try:
            if pd.isna(cache_timestamp):
                return None
        except (ValueError, TypeError):
            # If pd.isna() fails (e.g., on array-like values), treat as invalid
            return None

        # Convert to datetime if it's a string
        if isinstance(cache_timestamp, str):
            try:
                cache_timestamp = pd.to_datetime(cache_timestamp)
            except (ValueError, TypeError):
                return None

        # Convert pandas Timestamp to Python datetime if needed
        try:
            # Try pandas Timestamp conversion first (most common case)
            if isinstance(cache_timestamp, pd.Timestamp):
                cache_timestamp = cache_timestamp.to_pydatetime()
            # If it's already a datetime, ensure it's timezone-aware
            elif isinstance(cache_timestamp, datetime):
                pass  # Already a datetime, will handle timezone below
            else:
                # Try to convert using pandas as fallback
                cache_timestamp = pd.to_datetime(cache_timestamp).to_pydatetime()
        except (ValueError, TypeError, AttributeError):
            return None

        # Ensure timezone-aware
        if cache_timestamp.tzinfo is None:
            cache_timestamp = pytz.UTC.localize(cache_timestamp)
        else:
            cache_timestamp = cache_timestamp.astimezone(pytz.UTC)

        return cache_timestamp

    def _is_cache_valid(self, cache_entry: pd.Series, asset_type: str) -> bool:
        """Check if cached price is valid for a specific asset.

        Args:
            cache_entry: Cache entry (row from DataFrame)
            asset_type: Asset type to validate against

        Returns:
            True if cache is valid, False otherwise
        """
        cache_timestamp = cache_entry["timestamp"]
        normalized_timestamp = self._normalize_timestamp(cache_timestamp)

        if normalized_timestamp is None:
            return False

        now = datetime.now(pytz.UTC)
        age_minutes = (now - normalized_timestamp).total_seconds() / 60

        if asset_type in ("Stock", "ETF"):
            return self._is_stock_cache_valid(cache_entry, age_minutes)

        if asset_type == "Crypto":
            return self._is_crypto_cache_valid(cache_entry, age_minutes)

        return False

    def _is_stock_cache_valid(self, cache_entry: pd.Series, age_minutes: float) -> bool:
        """Check if stock/ETF cache is valid based on age.

        Args:
            cache_entry: Cache entry
            age_minutes: Age of cache in minutes

        Returns:
            True if cache is valid, False otherwise
        """
        is_valid = age_minutes < Config.CACHE_VALIDITY_MINUTES
        logger.debug(
            f"Cache validity for {cache_entry['ticker']}: "
            f"{is_valid} (age: {age_minutes:.1f} min)"
        )
        return is_valid

    def _is_crypto_cache_valid(self, cache_entry: pd.Series, age_minutes: float) -> bool:
        """Check if crypto cache is valid based on age.

        Args:
            cache_entry: Cache entry
            age_minutes: Age of cache in minutes

        Returns:
            True if cache is valid, False otherwise
        """
        is_valid = age_minutes < Config.CACHE_VALIDITY_MINUTES
        logger.debug(
            f"Cache validity for {cache_entry['ticker']}: "
            f"{is_valid} (age: {age_minutes:.1f} min)"
        )
        return is_valid

    def get_cached_price(self, ticker: str, asset_type: str) -> Optional[float]:
        """Get cached price if valid.

        Args:
            ticker: Asset ticker
            asset_type: Asset type

        Returns:
            Cached price if valid, None otherwise
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

        if self._is_cache_valid(cache_entry, asset_type):
            logger.info(
                f"Cache hit for {ticker} ({asset_type}): ${cache_entry['price']:.2f}"
            )
            return float(cache_entry["price"])

        logger.debug(f"Cache entry for {ticker} ({asset_type}) is invalid/expired")
        return None

    def get_stale_cached_price(self, ticker: str, asset_type: str) -> Optional[float]:
        """Get cached price even if it's expired/invalid (stale).

        Args:
            ticker: Asset ticker
            asset_type: Asset type

        Returns:
            Cached price if entry exists (even if stale), None if no cache entry exists at all
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
        price = float(cache_entry["price"])
        logger.debug(f"Retrieved stale cache entry for {ticker} ({asset_type}): ${price:.2f}")
        return price

    def set_cached_price(
        self, ticker: str, asset_type: str, price: float, timestamp: Optional[datetime] = None
    ) -> None:
        """Set cached price.

        Args:
            ticker: Asset ticker
            asset_type: Asset type
            price: Price to cache
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
                    "price": price,
                    "timestamp": timestamp,
                }
            ]
        )

        cache = cache[
            ~((cache["ticker"] == ticker) & (cache["asset_type"] == asset_type))
        ]

        cache = concat_dataframes([cache, new_entry], ignore_index=True)
        self._cache = cache

        self._save_cache()

    def get_cache_validity(self, tickers: Optional[List[str]] = None) -> CacheValidity:
        """Get cache validity status.

        Args:
            tickers: Optional list of tickers to check. If None, checks all entries.

        Returns:
            CacheValidity object with status and stale entries
        """
        cache = self._load_cache()

        # If cache is empty, return STALE status
        if cache.empty:
            return CacheValidity(
                status=CacheValidityStatus.STALE,
                stale_entries=[]
            )

        # Filter cache by tickers if provided
        if tickers is not None:
            cache = cache[cache["ticker"].isin(tickers)]
            # If no entries match the provided tickers, return STALE status
            if cache.empty:
                return CacheValidity(
                    status=CacheValidityStatus.STALE,
                    stale_entries=[]
                )

        stale_entries: List[Dict[str, Any]] = []
        valid_count = 0
        stale_count = 0

        # Check validity of each entry
        for _, row in cache.iterrows():
            asset_type = row["asset_type"]
            is_valid = self._is_cache_valid(row, asset_type)

            if is_valid:
                valid_count += 1
            else:
                stale_count += 1
                # Convert timestamp to datetime if needed
                timestamp = row["timestamp"]
                if isinstance(timestamp, pd.Timestamp):
                    timestamp = timestamp.to_pydatetime()
                elif isinstance(timestamp, str):
                    timestamp = pd.to_datetime(timestamp).to_pydatetime()
                elif not isinstance(timestamp, datetime):
                    try:
                        timestamp = pd.to_datetime(timestamp).to_pydatetime()
                    except (ValueError, TypeError):
                        # If we can't convert, use as-is
                        pass

                stale_entries.append({
                    "ticker": str(row["ticker"]),
                    "asset_type": str(row["asset_type"]),
                    "price": float(row["price"]),
                    "timestamp": timestamp,
                })

        # Determine status
        if stale_count == 0 and valid_count > 0:
            status = CacheValidityStatus.VALID
        elif stale_count > 0 and valid_count > 0:
            status = CacheValidityStatus.PARTIAL
        else:
            status = CacheValidityStatus.STALE

        return CacheValidity(
            status=status,
            stale_entries=stale_entries
        )

