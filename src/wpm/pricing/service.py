"""Service that orchestrates price retrieval with caching and rate limiting."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from wpm.currency import CurrencyService
from wpm.pricing.base import PriceRetriever
from wpm.pricing.cache import PriceCache
from wpm.pricing.coingecko import CoinGeckoRetriever
from wpm.pricing.rate_limiter import RateLimiter
from wpm.pricing.yahoo import YahooFinanceRetriever

logger = logging.getLogger(__name__)


class PriceService:
    """Service that orchestrates price retrieval with caching and rate limiting."""

    # Mapping of asset types to retriever instances
    _RETRIEVER_MAP: Dict[str, str] = {
        "Stock": "_stock_retriever",
        "ETF": "_stock_retriever",
        "Crypto": "_crypto_retriever",
    }

    def __init__(
        self,
        cache_file: Optional[Path] = None,
        rate_limit_per_minute: int = 60,
        currency_service: CurrencyService = None,
    ):
        """Initialize price service.

        Args:
            cache_file: Path to cache file (default: Config.CACHE_FILE)
            rate_limit_per_minute: Rate limit for API calls per minute
            currency_service: CurrencyService instance (default: creates new instance)
        """
        self.cache = PriceCache(cache_file)
        self.rate_limiter = RateLimiter(rate_limit_per_minute)
        self.currency_service = currency_service or CurrencyService()
        self._stock_retriever = YahooFinanceRetriever(self.currency_service)
        self._crypto_retriever = CoinGeckoRetriever()

    def _get_retriever(self, asset_type: str) -> PriceRetriever:
        """Get appropriate price retriever for asset type.

        Args:
            asset_type: Asset type

        Returns:
            PriceRetriever instance

        Raises:
            ValueError: If asset type is not supported
        """
        retriever_attr = self._RETRIEVER_MAP.get(asset_type)
        if retriever_attr is None:
            raise ValueError(f"Unsupported asset type: {asset_type}")

        return getattr(self, retriever_attr)

    def get_price(
        self, ticker: str, asset_type: str, in_native_currency: bool = False
    ) -> float:
        """Get current price for an asset (checks cache first).

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type ("Stock", "ETF", or "Crypto")
            in_native_currency: If True, return price in native currency; if False, return USD (default)

        Returns:
            Current price in USD (or native currency if in_native_currency=True)
        """
        logger.info(f"Price request for {ticker} ({asset_type})")

        # Check cache first
        if in_native_currency:
            cached_price = self.cache.get_cached_price_native(ticker, asset_type)
        else:
            cached_price = self.cache.get_cached_price(ticker, asset_type)

        if cached_price is not None:
            return cached_price

        self.rate_limiter.wait_if_needed()

        retriever = self._get_retriever(asset_type)
        native_price = retriever.get_price(ticker, asset_type)

        # For stocks/ETFs, detect currency and convert to USD
        # For crypto, native_price is already in USD
        if asset_type in ("Stock", "ETF"):
            currency = self._stock_retriever._detect_currency(ticker)
            if currency == "USD":
                price_usd = native_price
            else:
                price_usd = self.currency_service.convert_to_usd(native_price, currency)
        else:  # Crypto
            currency = "USD"
            price_usd = native_price

        # Store both native and USD prices in cache
        self.cache.set_cached_price(
            ticker, asset_type, price_usd, native_price, currency
        )

        # Return requested currency
        return native_price if in_native_currency else price_usd

    def get_prices(
        self, tickers: List[str], asset_type: str, in_native_currency: bool = False
    ) -> Dict[str, float]:
        """Batch price retrieval with rate limiting and batch API calls.

        Args:
            tickers: List of asset ticker symbols
            asset_type: Asset type for all tickers
            in_native_currency: If True, return prices in native currency; if False, return USD (default)

        Returns:
            Dictionary mapping ticker to price (in USD or native currency)

        Raises:
            ValueError: If no price data can be obtained for a ticker (no API response and no cache)
        """
        logger.info(f"Batch price request for {len(tickers)} {asset_type} assets")

        if not tickers:
            return {}

        prices: Dict[str, float] = {}
        uncached_tickers: List[str] = []

        # Check cache for all tickers first
        for ticker in tickers:
            if in_native_currency:
                cached_price = self.cache.get_cached_price_native(ticker, asset_type)
            else:
                cached_price = self.cache.get_cached_price(ticker, asset_type)

            if cached_price is not None:
                prices[ticker] = cached_price
            else:
                uncached_tickers.append(ticker)

        # If there are uncached tickers, fetch them in a batch
        if uncached_tickers:
            self.rate_limiter.wait_if_needed()

            retriever = self._get_retriever(asset_type)
            api_native_prices = retriever.get_prices(uncached_tickers, asset_type)

            # Convert to USD and store in cache
            for ticker, native_price in api_native_prices.items():
                # For stocks/ETFs, detect currency and convert to USD
                # For crypto, native_price is already in USD
                if asset_type in ("Stock", "ETF"):
                    currency = self._stock_retriever._detect_currency(ticker)
                    if currency == "USD":
                        price_usd = native_price
                    else:
                        price_usd = self.currency_service.convert_to_usd(
                            native_price, currency
                        )
                else:  # Crypto
                    currency = "USD"
                    price_usd = native_price

                # Store both native and USD prices in cache
                self.cache.set_cached_price(
                    ticker, asset_type, price_usd, native_price, currency
                )

                # Add to results in requested currency
                prices[ticker] = native_price if in_native_currency else price_usd

            # Handle tickers that failed API retrieval
            failed_tickers = set(uncached_tickers) - set(api_native_prices.keys())
            for ticker in failed_tickers:
                if in_native_currency:
                    stale_price = self.cache.get_stale_cached_price_native(
                        ticker, asset_type
                    )
                else:
                    stale_price = self.cache.get_stale_cached_price(ticker, asset_type)

                if stale_price is not None:
                    logger.warning(
                        f"API retrieval failed for {ticker} ({asset_type}), "
                        f"using stale cached price: {stale_price:.2f}"
                    )
                    prices[ticker] = stale_price
                else:
                    # No price data available at all (no API response and no cache)
                    raise ValueError(
                        f"No price data available for {ticker} ({asset_type}): "
                        f"API retrieval failed and no cache entry exists"
                    )

        return prices

