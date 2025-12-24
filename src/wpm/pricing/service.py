"""Service that orchestrates price retrieval with caching and rate limiting."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from wpm.pricing.base import PriceRetriever
from wpm.pricing.cache import PriceCache
from wpm.pricing.coingecko import CoinGeckoRetriever
from wpm.pricing.rate_limiter import RateLimiter
from wpm.pricing.yahoo import YahooFinanceRetriever

logger = logging.getLogger(__name__)


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
        """Batch price retrieval with rate limiting and batch API calls.

        Args:
            tickers: List of asset ticker symbols
            asset_type: Asset type for all tickers

        Returns:
            Dictionary mapping ticker to price

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
            cached_price = self.cache.get_cached_price(ticker, asset_type)
            if cached_price is not None:
                prices[ticker] = cached_price
            else:
                uncached_tickers.append(ticker)

        # If there are uncached tickers, fetch them in a batch
        if uncached_tickers:
            self.rate_limiter.wait_if_needed()

            retriever = self._get_retriever(asset_type)
            api_prices = retriever.get_prices(uncached_tickers, asset_type)

            # Update cache for successfully retrieved prices
            for ticker, price in api_prices.items():
                prices[ticker] = price
                self.cache.set_cached_price(ticker, asset_type, price)

            # Handle tickers that failed API retrieval
            failed_tickers = set(uncached_tickers) - set(api_prices.keys())
            for ticker in failed_tickers:
                stale_price = self.cache.get_stale_cached_price(ticker, asset_type)
                if stale_price is not None:
                    logger.warning(
                        f"API retrieval failed for {ticker} ({asset_type}), "
                        f"using stale cached price: ${stale_price:.2f}"
                    )
                    prices[ticker] = stale_price
                else:
                    # No price data available at all (no API response and no cache)
                    raise ValueError(
                        f"No price data available for {ticker} ({asset_type}): "
                        f"API retrieval failed and no cache entry exists"
                    )

        return prices

