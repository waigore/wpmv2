"""Manages persistent Parquet-based historical price cache."""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import pytz

from wpm.config import Config
from wpm.utils import concat_dataframes

logger = logging.getLogger(__name__)


class HistoricalPriceCache:
    """Manages persistent Parquet-based historical price cache.

    Stores daily prices for date ranges per asset. Historical cache entries
    are always valid (no expiration).
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize historical price cache.

        Args:
            cache_file: Path to cache file (default: Config.HISTORICAL_CACHE_FILE)
        """
        self.cache_file = cache_file or Config.HISTORICAL_CACHE_FILE
        self._cache: Optional[pd.DataFrame] = None
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        cache_dir = self.cache_file.parent
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created cache directory: {cache_dir}")

    def _load_cache(self) -> pd.DataFrame:
        """Load historical price cache from Parquet file.

        Returns:
            DataFrame with columns: ticker, asset_type, date, price, native_price, native_currency
        """
        if self._cache is not None:
            return self._cache

        expected_columns = [
            "ticker",
            "asset_type",
            "date",
            "price",
            "native_price",
            "native_currency",
        ]

        if not self.cache_file.exists():
            logger.debug("Historical cache file does not exist, starting with empty cache")
            self._cache = pd.DataFrame(columns=expected_columns)
            return self._cache

        try:
            self._cache = pd.read_parquet(self.cache_file)
            logger.info(
                f"Loaded historical price cache from {self.cache_file} with {len(self._cache)} entries"
            )

            # Ensure date column is date type
            if "date" in self._cache.columns:
                self._cache["date"] = pd.to_datetime(self._cache["date"]).dt.date

        except Exception as e:
            logger.warning(f"Error loading historical cache file: {e}. Starting with empty cache")
            self._cache = pd.DataFrame(columns=expected_columns)

        return self._cache

    def _save_cache(self) -> None:
        """Save historical price cache to Parquet file."""
        if self._cache is None:
            return

        try:
            self._cache.to_parquet(self.cache_file, index=False)
            logger.debug(f"Saved historical price cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Error saving historical cache file: {e}")

    def get_cached_prices(
        self, ticker: str, asset_type: str, start_date: date, end_date: date
    ) -> Optional[pd.DataFrame]:
        """Get cached prices for a date range.

        Returns DataFrame only if cache has complete coverage for the requested range.

        Args:
            ticker: Asset ticker
            asset_type: Asset type
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            DataFrame with date index and price column if cache has full coverage,
            None otherwise
        """
        cache = self._load_cache()

        if cache.empty:
            return None

        # Filter by ticker and asset_type
        matches = cache[
            (cache["ticker"] == ticker) & (cache["asset_type"] == asset_type)
        ].copy()

        if matches.empty:
            logger.debug(f"No cache entry found for {ticker} ({asset_type})")
            return None

        # Filter by date range
        # Convert date column to date type if needed
        matches["date"] = pd.to_datetime(matches["date"]).dt.date
        date_matches = matches[
            (matches["date"] >= start_date) & (matches["date"] <= end_date)
        ]

        if date_matches.empty:
            logger.debug(
                f"No cached prices for {ticker} ({asset_type}) in range {start_date} to {end_date}"
            )
            return None

        # Check if we have complete coverage
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        cached_dates = set(pd.to_datetime(date_matches["date"]).dt.date)
        required_dates = set(date_range.date)

        # For historical prices, we don't need every single day (markets are closed on weekends/holidays)
        # However, we must ensure the cache extends to or beyond the requested end_date
        # Forward fill should only fill gaps within the cached range, not extend beyond it
        if not cached_dates:
            return None
        
        # Check if cache extends to or beyond the requested end_date
        # If not, return None to trigger a fetch for the missing dates
        all_cached_dates = sorted([d for d in matches["date"]])
        max_cached_date = max(all_cached_dates) if all_cached_dates else None
        if max_cached_date is None or max_cached_date < end_date:
            # Cache doesn't extend to end_date, need to fetch missing dates
            return None

        # Create DataFrame with date index and price column
        result_df = date_matches[["date", "price"]].copy()
        # Convert date to datetime for indexing
        result_df["date"] = pd.to_datetime(result_df["date"])
        result_df.set_index("date", inplace=True)
        result_df.sort_index(inplace=True)

        # Forward fill to handle missing trading days
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        result_df = result_df.reindex(date_range, method="ffill")

        return result_df

    def get_cached_price(
        self, ticker: str, asset_type: str, target_date: date
    ) -> Optional[float]:
        """Get cached price for a specific date (most recent available up to target_date).

        Args:
            ticker: Asset ticker
            asset_type: Asset type
            target_date: Target date (inclusive)

        Returns:
            Cached price if available, None otherwise
        """
        cache = self._load_cache()

        if cache.empty:
            return None

        # Filter by ticker, asset_type, and date <= target_date
        # Convert date column to date type if needed
        cache_date = pd.to_datetime(cache["date"]).dt.date
        matches = cache[
            (cache["ticker"] == ticker)
            & (cache["asset_type"] == asset_type)
            & (cache_date <= target_date)
        ]

        if matches.empty:
            logger.debug(
                f"No cache entry found for {ticker} ({asset_type}) on or before {target_date}"
            )
            return None

        # Get the most recent price
        matches = matches.sort_values("date", ascending=False)
        most_recent = matches.iloc[0]
        price = float(most_recent["price"])

        logger.debug(
            f"Retrieved cached historical price for {ticker} ({asset_type}) on {target_date}: ${price:.2f}"
        )
        return price

    def set_cached_prices(
        self,
        ticker: str,
        asset_type: str,
        prices_df: pd.DataFrame,
        native_prices_df: Optional[pd.DataFrame] = None,
        native_currency: str = "USD",
    ) -> None:
        """Store daily prices for a date range.

        Args:
            ticker: Asset ticker
            asset_type: Asset type
            prices_df: DataFrame with date index and price column (USD prices)
            native_prices_df: Optional DataFrame with date index and native_price column
            native_currency: Native currency code (default: "USD")
        """
        cache = self._load_cache()

        # Prepare new entries
        new_entries = []
        for date_idx, price in prices_df.iterrows():
            # Handle both date index and datetime index
            if isinstance(date_idx, pd.Timestamp):
                date_val = date_idx.date()
            elif isinstance(date_idx, date):
                date_val = date_idx
            else:
                date_val = pd.to_datetime(date_idx).date()

            native_price = price.iloc[0] if native_prices_df is None else native_prices_df.loc[date_idx].iloc[0]

            new_entries.append(
                {
                    "ticker": ticker,
                    "asset_type": asset_type,
                    "date": date_val,
                    "price": float(price.iloc[0]),
                    "native_price": float(native_price),
                    "native_currency": native_currency,
                }
            )

        if not new_entries:
            logger.warning(f"No price data to cache for {ticker} ({asset_type})")
            return

        new_df = pd.DataFrame(new_entries)

        # Remove existing entries for this ticker/asset_type/date range
        if not cache.empty:
            date_range_set = set(new_df["date"])
            # Convert cache dates to date type for comparison
            cache_date = pd.to_datetime(cache["date"]).dt.date
            cache = cache[
                ~(
                    (cache["ticker"] == ticker)
                    & (cache["asset_type"] == asset_type)
                    & (cache_date.isin(date_range_set))
                )
            ]

        # Combine with new entries
        cache = concat_dataframes([cache, new_df], ignore_index=True)
        self._cache = cache

        self._save_cache()
        logger.debug(
            f"Cached {len(new_entries)} historical prices for {ticker} ({asset_type})"
        )

    def remove_cached_prices(
        self, ticker: str, asset_type: str, start_date: date, end_date: date
    ) -> None:
        """Remove cached prices for a date range.
        
        Used to invalidate cache when splits occur or prices need to be refreshed.
        
        Args:
            ticker: Asset ticker
            asset_type: Asset type
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
        """
        cache = self._load_cache()
        if cache.empty:
            logger.debug(f"No cache entries to remove for {ticker} ({asset_type})")
            return
        
        before_count = len(cache)
        
        # Convert cache dates to date type for comparison
        cache_date = pd.to_datetime(cache["date"]).dt.date
        
        # Remove entries matching ticker, asset_type, and date range
        cache = cache[
            ~(
                (cache["ticker"] == ticker)
                & (cache["asset_type"] == asset_type)
                & (cache_date >= start_date)
                & (cache_date <= end_date)
            )
        ]
        
        after_count = len(cache)
        self._cache = cache
        self._save_cache()
        
        cleared_count = before_count - after_count
        if cleared_count > 0:
            logger.info(
                f"Removed {cleared_count} cached prices for {ticker} ({asset_type}) "
                f"from {start_date} to {end_date}"
            )
        else:
            logger.debug(
                f"No cached prices to remove for {ticker} ({asset_type}) "
                f"from {start_date} to {end_date}"
            )

    def clear_asset(self, ticker: str, asset_type: str) -> None:
        """Clear all cached prices for a specific asset.

        Args:
            ticker: Asset ticker
            asset_type: Asset type
        """
        cache = self._load_cache()

        if cache.empty:
            logger.debug(f"No cache entries to clear for {ticker} ({asset_type})")
            return

        before_count = len(cache)
        cache = cache[
            ~((cache["ticker"] == ticker) & (cache["asset_type"] == asset_type))
        ]
        after_count = len(cache)

        self._cache = cache
        self._save_cache()

        cleared_count = before_count - after_count
        logger.info(
            f"Cleared {cleared_count} cached prices for {ticker} ({asset_type})"
        )

    def clear_all(self) -> None:
        """Clear entire historical cache."""
        cache = self._load_cache()

        if cache.empty:
            logger.debug("Historical cache is already empty")
            return

        entry_count = len(cache)
        self._cache = pd.DataFrame(
            columns=[
                "ticker",
                "asset_type",
                "date",
                "price",
                "native_price",
                "native_currency",
            ]
        )
        self._save_cache()

        logger.info(f"Cleared entire historical cache ({entry_count} entries)")

