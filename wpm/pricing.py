"""Market price data retrieval module with caching and rate limiting."""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pytz
import yfinance as yf
from pycoingecko import CoinGeckoAPI

from wpm.config import Config
from wpm.models import Asset
from wpm.utils import concat_dataframes, is_us_market_open, is_within_trading_hours

logger = logging.getLogger(__name__)


class PriceRetriever(ABC):
    """Abstract base class for price retrievers."""

    @abstractmethod
    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get current price for an asset.

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type ("Stock", "ETF", or "Crypto")

        Returns:
            Current price in USD

        Raises:
            ValueError: If price cannot be retrieved
        """
        pass


class YahooFinanceRetriever(PriceRetriever):
    """Price retriever using yfinance for stocks and ETFs."""

    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get current price from Yahoo Finance.

        Args:
            ticker: Stock/ETF ticker symbol
            asset_type: Asset type (should be "Stock" or "ETF")

        Returns:
            Current price in USD

        Raises:
            ValueError: If price cannot be retrieved
        """
        logger.debug(f"Fetching price from Yahoo Finance for {ticker} ({asset_type})")

        try:
            ticker_obj = yf.Ticker(ticker)
            data = ticker_obj.history(period="1d", interval="1m")

            if data.empty:
                raise ValueError(f"No price data available for {ticker}")

            latest_price = data["Close"].iloc[-1]

            if pd.isna(latest_price) or latest_price <= 0:
                raise ValueError(f"Invalid price data for {ticker}")

            logger.debug(f"Retrieved price for {ticker}: ${latest_price:.2f}")
            return float(latest_price)

        except Exception as e:
            raise ValueError(f"Error fetching price for {ticker} from Yahoo Finance: {str(e)}") from e


class CoinGeckoRetriever(PriceRetriever):
    """Price retriever using CoinGecko API for cryptocurrencies."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize CoinGecko API client.
        
        Args:
            api_key: Optional API key for CoinGecko API. If not provided, uses
                    Config.COINGECKO_API_KEY. If that is also None, uses free tier.
        """
        api_key = api_key or Config.COINGECKO_API_KEY
        self.client = CoinGeckoAPI(api_key=api_key) if api_key else CoinGeckoAPI()

    def _get_coin_id(self, ticker: str) -> str:
        """Convert ticker to CoinGecko coin ID.

        Args:
            ticker: Crypto ticker (e.g., "BTC-USD")

        Returns:
            CoinGecko coin ID (e.g., "bitcoin")
        """
        ticker_lower = ticker.lower().replace("-usd", "").replace("_usd", "")

        coin_map = {
            "btc": "bitcoin",
            "eth": "ethereum",
            "ada": "cardano",
            "dot": "polkadot",
            "sol": "solana",
            "matic": "matic-network",
            "avax": "avalanche-2",
        }

        return coin_map.get(ticker_lower, ticker_lower)

    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get current price from CoinGecko.

        Args:
            ticker: Crypto ticker symbol
            asset_type: Asset type (should be "Crypto")

        Returns:
            Current price in USD

        Raises:
            ValueError: If price cannot be retrieved
        """
        logger.debug(f"Fetching price from CoinGecko for {ticker} ({asset_type})")

        try:
            coin_id = self._get_coin_id(ticker)
            data = self.client.get_price(ids=coin_id, vs_currencies="usd")

            if not data or coin_id not in data:
                raise ValueError(f"No price data available for {ticker}")

            price = data[coin_id]["usd"]

            if price <= 0:
                raise ValueError(f"Invalid price data for {ticker}")

            logger.debug(f"Retrieved price for {ticker}: ${price:.2f}")
            return float(price)

        except Exception as e:
            raise ValueError(f"Error fetching price for {ticker} from CoinGecko: {str(e)}") from e


class RateLimiter:
    """Rate limiting utility for API calls."""

    def __init__(self, max_calls_per_minute: int = 60):
        """Initialize rate limiter.

        Args:
            max_calls_per_minute: Maximum number of API calls per minute
        """
        self.max_calls_per_minute = max_calls_per_minute
        self.call_times: List[datetime] = []

    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = datetime.now(pytz.UTC)

        minute_ago = now - timedelta(minutes=1)
        self.call_times = [t for t in self.call_times if t > minute_ago]

        if len(self.call_times) >= self.max_calls_per_minute:
            oldest_call = min(self.call_times)
            wait_until = oldest_call + timedelta(minutes=1)

            if wait_until > now:
                wait_seconds = (wait_until - now).total_seconds()
                logger.info(f"Rate limit reached. Waiting {wait_seconds:.1f} seconds")
                time.sleep(wait_seconds)

        self.call_times.append(now)


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

    def _is_cache_valid(self, cache_entry: pd.Series, asset_type: str) -> bool:
        """Check if cached price is valid for a specific asset.

        Args:
            cache_entry: Cache entry (row from DataFrame)
            asset_type: Asset type to validate against

        Returns:
            True if cache is valid, False otherwise
        """
        if pd.isna(cache_entry["timestamp"]):
            return False

        cache_timestamp = cache_entry["timestamp"]
        
        # Convert to datetime if it's a string
        if isinstance(cache_timestamp, str):
            cache_timestamp = pd.to_datetime(cache_timestamp)
        
        # Convert pandas Timestamp to Python datetime if needed
        try:
            if hasattr(cache_timestamp, 'to_pydatetime'):
                cache_timestamp = cache_timestamp.to_pydatetime()
            elif hasattr(cache_timestamp, 'timestamp'):
                # It's already a datetime-like object, ensure it's timezone-aware
                pass
            else:
                # Try to convert using pandas
                cache_timestamp = pd.to_datetime(cache_timestamp).to_pydatetime()
        except (ValueError, TypeError, AttributeError):
            return False

        if cache_timestamp.tzinfo is None:
            cache_timestamp = pytz.UTC.localize(cache_timestamp)
        else:
            cache_timestamp = cache_timestamp.astimezone(pytz.UTC)

        now = datetime.now(pytz.UTC)
        age_minutes = (now - cache_timestamp).total_seconds() / 60

        if asset_type in ("Stock", "ETF"):
            current_in_hours = is_within_trading_hours(now)
            cache_in_hours = is_within_trading_hours(cache_timestamp)

            if not current_in_hours and not cache_in_hours:
                logger.debug(
                    f"Cache valid for {cache_entry['ticker']}: both outside trading hours"
                )
                return True

            if current_in_hours:
                is_valid = age_minutes < Config.CACHE_VALIDITY_MINUTES
                logger.debug(
                    f"Cache validity for {cache_entry['ticker']}: "
                    f"{is_valid} (age: {age_minutes:.1f} min, in hours: {current_in_hours})"
                )
                return is_valid

            return False

        if asset_type == "Crypto":
            is_valid = age_minutes < Config.CACHE_VALIDITY_MINUTES
            logger.debug(
                f"Cache validity for {cache_entry['ticker']}: "
                f"{is_valid} (age: {age_minutes:.1f} min)"
            )
            return is_valid

        return False

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


class PriceService:
    """Service that orchestrates price retrieval with caching and rate limiting."""

    def __init__(
        self,
        cache_file: Optional[Path] = None,
        rate_limit_per_minute: int = 60,
    ):
        """Initialize price service.

        Args:
            cache_file: Path to cache file (default: Config.CACHE_FILE)
            rate_limit_per_minute: Rate limit for API calls per minute
        """
        self.cache = PriceCache(cache_file)
        self.rate_limiter = RateLimiter(rate_limit_per_minute)
        self._stock_retriever = YahooFinanceRetriever()
        self._crypto_retriever = CoinGeckoRetriever()

    def _get_retriever(self, asset_type: str) -> PriceRetriever:
        """Get appropriate price retriever for asset type.

        Args:
            asset_type: Asset type

        Returns:
            PriceRetriever instance
        """
        if asset_type in ("Stock", "ETF"):
            return self._stock_retriever

        if asset_type == "Crypto":
            return self._crypto_retriever

        raise ValueError(f"Unsupported asset type: {asset_type}")

    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get current price for an asset (checks cache first).

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type ("Stock", "ETF", or "Crypto")

        Returns:
            Current price in USD
        """
        logger.info(f"Price request for {ticker} ({asset_type})")

        cached_price = self.cache.get_cached_price(ticker, asset_type)
        if cached_price is not None:
            return cached_price

        self.rate_limiter.wait_if_needed()

        retriever = self._get_retriever(asset_type)
        price = retriever.get_price(ticker, asset_type)

        self.cache.set_cached_price(ticker, asset_type, price)

        return price

    def get_prices(
        self, tickers: List[str], asset_type: str
    ) -> Dict[str, float]:
        """Batch price retrieval with rate limiting.

        Args:
            tickers: List of asset ticker symbols
            asset_type: Asset type for all tickers

        Returns:
            Dictionary mapping ticker to price
        """
        logger.info(f"Batch price request for {len(tickers)} {asset_type} assets")

        prices: Dict[str, float] = {}

        for ticker in tickers:
            try:
                prices[ticker] = self.get_price(ticker, asset_type)
            except Exception as e:
                logger.warning(f"Error fetching price for {ticker}: {e}")

        return prices

