"""Service that orchestrates price retrieval with caching and rate limiting."""

import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from wpm.currency import CurrencyService
from wpm.pricing.base import PriceRetriever
from wpm.pricing.cache import PriceCache
from wpm.pricing.coingecko import CoinGeckoRetriever
from wpm.pricing.historical_cache import HistoricalPriceCache
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
        historical_cache_file: Optional[Path] = None,
        rate_limit_per_minute: int = 60,
        currency_service: CurrencyService = None,
    ):
        """Initialize price service.

        Args:
            cache_file: Path to cache file (default: Config.CACHE_FILE)
            historical_cache_file: Path to historical cache file (default: Config.HISTORICAL_CACHE_FILE)
            rate_limit_per_minute: Rate limit for API calls per minute
            currency_service: CurrencyService instance (default: creates new instance)
        """
        self.cache = PriceCache(cache_file)
        self.historical_cache = HistoricalPriceCache(historical_cache_file)
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

    def get_historical_price(
        self,
        ticker: str,
        asset_type: str,
        target_date: date,
        in_native_currency: bool = False,
    ) -> float:
        """Get historical price for an asset on a specific date.

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type ("Stock", "ETF", or "Crypto")
            target_date: Target date (inclusive). Returns most recent price available up to this date
            in_native_currency: If True, return price in native currency; if False, return USD (default)

        Returns:
            Historical price in USD (or native currency if in_native_currency=True)

        Raises:
            ValueError: If price cannot be retrieved
        """
        logger.info(
            f"Historical price request for {ticker} ({asset_type}) on {target_date}"
        )

        # Use a small date range around target_date for caching efficiency
        # We'll fetch a range and then extract the specific date
        start_date = target_date
        end_date = target_date

        prices = self.get_historical_prices(
            [ticker], asset_type, start_date, end_date, in_native_currency=in_native_currency
        )

        if ticker not in prices:
            raise ValueError(
                f"No historical price data available for {ticker} ({asset_type}) on {target_date}"
            )

        return prices[ticker]

    def get_historical_prices(
        self,
        tickers: List[str],
        asset_type: str,
        start_date: date,
        end_date: date,
        in_native_currency: bool = False,
    ) -> Dict[str, float]:
        """Get historical prices for multiple assets over a date range.

        Returns prices for the end_date (most recent available up to end_date).

        Args:
            tickers: List of asset ticker symbols
            asset_type: Asset type for all tickers
            start_date: Start date (inclusive)
            end_date: End date (inclusive). Prices returned are for this date (most recent available)
            in_native_currency: If True, return prices in native currency; if False, return USD (default)

        Returns:
            Dictionary mapping ticker to price on end_date (in USD or native currency)

        Raises:
            ValueError: If no price data can be obtained for a ticker
        """
        logger.info(
            f"Historical price request for {len(tickers)} {asset_type} assets "
            f"from {start_date} to {end_date}"
        )

        if not tickers:
            return {}

        prices: Dict[str, float] = {}
        uncached_tickers: List[str] = []

        # Check historical cache for all tickers first
        for ticker in tickers:
            cached_price = self.historical_cache.get_cached_price(
                ticker, asset_type, end_date
            )
            if cached_price is not None:
                # Check if we need native currency price
                if in_native_currency:
                    # For historical prices, we need to get native price from cache
                    # For now, if in_native_currency and asset is not USD, we'll need to fetch
                    # For simplicity, we'll fetch if in_native_currency is True
                    # This could be optimized later
                    uncached_tickers.append(ticker)
                else:
                    prices[ticker] = cached_price
            else:
                uncached_tickers.append(ticker)

        # Fetch missing prices
        if uncached_tickers:
            self.rate_limiter.wait_if_needed()

            # For historical crypto prices, use YahooFinanceRetriever (yfinance supports longer ranges)
            # For current prices, CoinGeckoRetriever is still used
            if asset_type == "Crypto":
                retriever = self._stock_retriever  # YahooFinanceRetriever
            else:
                retriever = self._get_retriever(asset_type)

            # Track failed tickers
            failed_tickers: List[str] = []

            # Fetch historical prices for each ticker
            for ticker in uncached_tickers:
                try:
                    # Get historical prices DataFrame
                    native_prices_df = retriever.get_historical_prices(
                        ticker, asset_type, start_date, end_date
                    )

                    if native_prices_df.empty:
                        logger.warning(
                            f"No historical price data for {ticker} ({asset_type}) "
                            f"from {start_date} to {end_date}"
                        )
                        failed_tickers.append(ticker)
                        continue

                    # Get price on end_date (most recent available)
                    # Find the most recent non-NaN price up to end_date
                    price_series = native_prices_df["price"].dropna()
                    if price_series.empty:
                        logger.warning(
                            f"No valid prices for {ticker} ({asset_type}) in date range"
                        )
                        failed_tickers.append(ticker)
                        continue

                    # Filter to prices on or before end_date
                    # Handle both DatetimeIndex and date index
                    if isinstance(price_series.index, pd.DatetimeIndex):
                        # Convert DatetimeIndex to date for comparison
                        price_series = price_series[price_series.index.date <= end_date]
                    else:
                        # Assume index is already date objects
                        price_series = price_series[price_series.index <= end_date]
                    
                    if price_series.empty:
                        logger.warning(
                            f"No valid prices for {ticker} ({asset_type}) on or before {end_date}"
                        )
                        failed_tickers.append(ticker)
                        continue

                    # Get the most recent price (last non-NaN value on or before end_date)
                    native_price = float(price_series.iloc[-1])

                    # Convert to USD for stocks/ETFs
                    if asset_type in ("Stock", "ETF"):
                        currency = self._stock_retriever._detect_currency(ticker)
                        if currency == "USD":
                            price_usd = native_price
                        else:
                            # For historical prices, we need historical forex rates
                            # For now, use current exchange rate (could be improved)
                            price_usd = self.currency_service.convert_to_usd(
                                native_price, currency
                            )
                    else:  # Crypto
                        currency = "USD"
                        price_usd = native_price

                    # Store in historical cache
                    # Convert native prices to USD prices DataFrame
                    usd_prices_df = native_prices_df.copy()
                    if asset_type in ("Stock", "ETF"):
                        currency = self._stock_retriever._detect_currency(ticker)
                        if currency != "USD":
                            # Convert each price to USD (using current rate for now)
                            # This could be improved with historical forex rates
                            usd_prices_df["price"] = native_prices_df["price"].apply(
                                lambda p: self.currency_service.convert_to_usd(p, currency)
                            )
                    else:
                        currency = "USD"
                        # Crypto prices are already in USD
                        usd_prices_df = native_prices_df.copy()

                    self.historical_cache.set_cached_prices(
                        ticker,
                        asset_type,
                        usd_prices_df,
                        native_prices_df=native_prices_df,
                        native_currency=currency,
                    )

                    # Return requested currency
                    result_price = native_price if in_native_currency else price_usd
                    prices[ticker] = result_price

                except Exception as e:
                    logger.warning(
                        f"Error fetching historical prices for {ticker} ({asset_type}): {e}"
                    )
                    # Try to get stale cached price
                    stale_price = self.historical_cache.get_cached_price(
                        ticker, asset_type, end_date
                    )
                    if stale_price is not None:
                        logger.warning(
                            f"Using stale cached historical price for {ticker} ({asset_type}): {stale_price:.2f}"
                        )
                        prices[ticker] = stale_price
                    else:
                        failed_tickers.append(ticker)

            # After processing all tickers, check if we have any failures
            # Only raise if we have no prices at all (all tickers failed and no cache)
            if failed_tickers and not prices:
                # All tickers failed and no cache - raise error
                failed_list = ", ".join(failed_tickers)
                raise ValueError(
                    f"No historical price data available for any of the requested tickers ({asset_type}): "
                    f"{failed_list}. API retrieval failed and no cache entries exist."
                )
            elif failed_tickers:
                # Some tickers failed but we have some prices - log warning but continue
                failed_list = ", ".join(failed_tickers)
                logger.warning(
                    f"Failed to retrieve historical prices for some tickers ({asset_type}): {failed_list}. "
                    f"Continuing with available prices."
                )

        return prices

