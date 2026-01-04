"""Currency conversion module using yfinance for forex rates."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import pytz
import yfinance as yf

from wpm.config import Config
from wpm.utils import concat_dataframes

logger = logging.getLogger(__name__)


class CurrencyCache:
    """Manages persistent Parquet-based currency rate cache."""

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize currency cache.

        Args:
            cache_file: Path to cache file (default: Config.CURRENCY_CACHE_FILE)
        """
        self.cache_file = cache_file or Config.CURRENCY_CACHE_FILE
        self._cache: Optional[pd.DataFrame] = None
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        cache_dir = self.cache_file.parent
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created cache directory: {cache_dir}")

    def _load_cache(self) -> pd.DataFrame:
        """Load currency cache from Parquet file.

        Returns:
            DataFrame with columns: base_currency, counter_currency, rate, timestamp
        """
        if self._cache is not None:
            return self._cache

        if not self.cache_file.exists():
            logger.debug("Currency cache file does not exist, starting with empty cache")
            self._cache = pd.DataFrame(
                columns=["base_currency", "counter_currency", "rate", "timestamp"]
            )
            return self._cache

        try:
            self._cache = pd.read_parquet(self.cache_file)
            logger.info(
                f"Loaded currency cache from {self.cache_file} with {len(self._cache)} entries"
            )
        except Exception as e:
            logger.warning(f"Error loading currency cache file: {e}. Starting with empty cache")
            self._cache = pd.DataFrame(
                columns=["base_currency", "counter_currency", "rate", "timestamp"]
            )

        return self._cache

    def _save_cache(self) -> None:
        """Save currency cache to Parquet file."""
        if self._cache is None:
            return

        try:
            self._cache.to_parquet(self.cache_file, index=False)
            logger.debug(f"Saved currency cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Error saving currency cache file: {e}")

    def _normalize_timestamp(self, cache_timestamp: any) -> Optional[datetime]:
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
        """Check if cached rate is valid (24-hour validity).

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

        is_valid = age_minutes < Config.CURRENCY_CACHE_VALIDITY_MINUTES
        logger.debug(
            f"Currency cache validity for {cache_entry['base_currency']}/{cache_entry['counter_currency']}: "
            f"{is_valid} (age: {age_minutes:.1f} min)"
        )
        return is_valid

    def get_cached_rate(
        self, base_currency: str, counter_currency: str = "USD"
    ) -> Optional[float]:
        """Get cached rate if valid.

        Args:
            base_currency: Base currency code (e.g., "HKD")
            counter_currency: Counter currency code (default: "USD")

        Returns:
            Cached rate if valid, None otherwise
        """
        cache = self._load_cache()

        if cache.empty:
            return None

        matches = cache[
            (cache["base_currency"] == base_currency)
            & (cache["counter_currency"] == counter_currency)
        ]

        if matches.empty:
            logger.debug(
                f"No cache entry found for {base_currency}/{counter_currency}"
            )
            return None

        cache_entry = matches.iloc[0]

        if self._is_cache_valid(cache_entry):
            logger.info(
                f"Currency cache hit for {base_currency}/{counter_currency}: "
                f"{cache_entry['rate']:.6f}"
            )
            return float(cache_entry["rate"])

        logger.debug(
            f"Cache entry for {base_currency}/{counter_currency} is invalid/expired"
        )
        return None

    def set_cached_rate(
        self,
        base_currency: str,
        counter_currency: str,
        rate: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Set cached rate.

        Args:
            base_currency: Base currency code
            counter_currency: Counter currency code
            rate: Exchange rate to cache
            timestamp: Timestamp (default: current time)
        """
        cache = self._load_cache()

        if timestamp is None:
            timestamp = datetime.now(pytz.UTC)

        new_entry = pd.DataFrame(
            [
                {
                    "base_currency": base_currency,
                    "counter_currency": counter_currency,
                    "rate": rate,
                    "timestamp": timestamp,
                }
            ]
        )

        cache = cache[
            ~(
                (cache["base_currency"] == base_currency)
                & (cache["counter_currency"] == counter_currency)
            )
        ]

        cache = concat_dataframes([cache, new_entry], ignore_index=True)
        self._cache = cache

        self._save_cache()


class CurrencyService:
    """Service for currency conversion using yfinance."""

    def __init__(self, cache: Optional[CurrencyCache] = None):
        """Initialize currency service.

        Args:
            cache: CurrencyCache instance (default: creates new instance)
        """
        self.cache = cache or CurrencyCache()

    def get_forex_rate(
        self, base_currency: str, counter_currency: str = "USD"
    ) -> float:
        """Get forex exchange rate.

        Uses yfinance API with format {BASE}{COUNTER}=X (e.g., HKDUSD=X).
        Returns exchange rate where 1 base = X counter.

        Args:
            base_currency: Base currency code (e.g., "HKD")
            counter_currency: Counter currency code (default: "USD")

        Returns:
            Exchange rate (1 base = X counter)

        Raises:
            ValueError: If rate cannot be retrieved
        """
        # If same currency, return 1.0
        if base_currency == counter_currency:
            return 1.0

        # Check cache first
        cached_rate = self.cache.get_cached_rate(base_currency, counter_currency)
        if cached_rate is not None:
            return cached_rate

        # Fetch from yfinance
        logger.debug(
            f"Fetching forex rate from yfinance for {base_currency}/{counter_currency}"
        )

        try:
            ticker = f"{base_currency}{counter_currency}=X"
            data = yf.download(ticker, period="1d", progress=False)

            if data.empty:
                raise ValueError(
                    f"No forex rate data available for {base_currency}/{counter_currency}"
                )

            rate = data["Close"].iloc[-1]
            
            # Convert to scalar if it's a Series
            if isinstance(rate, pd.Series):
                rate = rate.iloc[0] if len(rate) > 0 else rate
            
            # Check for None/NaN before converting to float
            if pd.isna(rate):
                raise ValueError(
                    f"Invalid forex rate data for {base_currency}/{counter_currency}"
                )
            
            rate = float(rate)

            if rate <= 0:
                raise ValueError(
                    f"Invalid forex rate data for {base_currency}/{counter_currency}"
                )
            logger.debug(
                f"Retrieved forex rate for {base_currency}/{counter_currency}: {rate:.6f}"
            )

            # Cache the rate
            self.cache.set_cached_rate(base_currency, counter_currency, rate)

            return rate

        except ValueError:
            # Re-raise ValueError as-is (these are our explicit validation errors)
            raise
        except Exception as e:
            raise ValueError(
                f"Error fetching forex rate for {base_currency}/{counter_currency} "
                f"from yfinance: {str(e)}"
            ) from e

    def convert_to_usd(self, amount: float, from_currency: str) -> float:
        """Convert amount from any currency to USD.

        Args:
            amount: Amount to convert
            from_currency: Source currency code

        Returns:
            Amount in USD (unchanged if from_currency is USD)
        """
        if from_currency == "USD":
            return amount

        rate = self.get_forex_rate(from_currency, "USD")
        return amount * rate

