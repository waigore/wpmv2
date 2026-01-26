"""Historical price fetcher interface and implementations for reference portfolios."""

import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import TYPE_CHECKING, Dict, Optional

from wpm.models import Asset

if TYPE_CHECKING:
    from wpm.pricing.service import PriceService

logger = logging.getLogger(__name__)


class HistoricalPriceFetcher(ABC):
    """Abstract base class for historical price fetchers.
    
    Provides an interface for retrieving historical prices with fallback logic
    to handle cases where prices may not be available on the exact target date
    (e.g., weekends, holidays).
    """

    @abstractmethod
    def get_historical_price(self, asset: Asset, target_date: date) -> float:
        """Get historical price for asset on target_date with fallback logic.
        
        Args:
            asset: Asset to get price for
            target_date: Target date for price retrieval
            
        Returns:
            Historical price in USD
            
        Raises:
            ValueError: If price cannot be retrieved for the asset on or before target_date
        """
        pass

    @abstractmethod
    def prefetch_prices(self, asset: Asset, start_date: date, end_date: date) -> None:
        """Batch fetch prices for asset over date range and cache them.
        
        This method should be called before processing trades to avoid
        slow per-day fetches for portfolios with long histories. All implementations
        must provide this method to enable efficient batch fetching of prices.
        
        Args:
            asset: Asset to prefetch prices for
            start_date: Start date for prefetch range (inclusive)
            end_date: End date for prefetch range (inclusive)
        """
        pass


class DefaultHistoricalPriceFetcher(HistoricalPriceFetcher):
    """Default historical price fetcher with lookback fallback.
    
    First attempts to get the price for the exact target_date. If that fails
    (e.g., weekend/holiday), expands the date range backward by lookback_days
    to find the previous trading day with a valid price.
    
    Example:
        If target_date is Saturday 2025-05-17 and lookback_days=7:
        1. Try to get price for 2025-05-17 (fails - market closed)
        2. Expand range to 2025-05-10 to 2025-05-17
        3. Find most recent date <= 2025-05-17 with valid price (e.g., 2025-05-16)
        4. Return price from 2025-05-16
    """

    def __init__(self, price_service: "PriceService", lookback_days: int = 7):
        """Initialize default historical price fetcher.
        
        Args:
            price_service: Price service for retrieving historical prices
            lookback_days: Number of days to look back when exact date fails (default: 7)
        """
        self.price_service = price_service
        self.lookback_days = lookback_days
        self._price_cache: Dict[date, float] = {}  # Internal cache for batch-fetched prices
        self._cache_asset: Optional[Asset] = None  # Track which asset is cached
        logger.info(
            f"Initialized DefaultHistoricalPriceFetcher with lookback_days={lookback_days}"
        )

    def prefetch_prices(self, asset: Asset, start_date: date, end_date: date) -> None:
        """Batch fetch prices for asset over date range and cache them.
        
        Fetches all prices for the asset in the specified date range and stores
        them in an internal cache for efficient lookup during trade processing.
        
        Args:
            asset: Asset to prefetch prices for
            start_date: Start date for prefetch range (inclusive)
            end_date: End date for prefetch range (inclusive)
        """
        try:
            prices = self.price_service.get_historical_prices(
                [asset.ticker],
                asset.asset_type,
                start_date,
                end_date,
                cached_prices_only=False,  # Normal fetch, populate cache
            )
            if asset.ticker in prices and prices[asset.ticker]:
                self._price_cache = prices[asset.ticker]
                self._cache_asset = asset
                logger.info(
                    f"Prefetched {len(self._price_cache)} prices for {asset.ticker} "
                    f"from {start_date} to {end_date}"
                )
            else:
                logger.warning(
                    f"No prices returned when prefetching {asset.ticker} "
                    f"from {start_date} to {end_date}"
                )
        except ValueError as e:
            logger.warning(
                f"Failed to prefetch prices for {asset.ticker} "
                f"from {start_date} to {end_date}: {e}"
            )
            # Don't raise - allow fallback to per-day fetching

    def get_historical_price(self, asset: Asset, target_date: date) -> float:
        """Get historical price for asset on target_date with lookback fallback.
        
        First checks internal cache if available. If cache hit, returns cached price
        (exact date or most recent <= target_date). If cache miss, falls back to
        price service. When using lookback, uses cached_prices_only=True to prevent
        retriever from being called for weekends/holidays.
        
        Args:
            asset: Asset to get price for
            target_date: Target date for price retrieval
            
        Returns:
            Historical price in USD (from target_date or most recent available date)
            
        Raises:
            ValueError: If price cannot be retrieved for the asset within lookback_days
                of target_date
        """
        # First check internal cache if available and matches asset
        if self._cache_asset == asset and self._price_cache:
            # Check for exact date match
            if target_date in self._price_cache:
                return self._price_cache[target_date]
            
            # Find most recent date <= target_date in cache
            available_dates = [d for d in self._price_cache.keys() if d <= target_date]
            if available_dates:
                most_recent_date = max(available_dates)
                price = self._price_cache[most_recent_date]
                logger.debug(
                    f"Found price for {asset.ticker} from cache: "
                    f"{most_recent_date} -> ${price:.2f} (requested: {target_date})"
                )
                return price
        
        # Cache miss or different asset - try exact date via price service
        try:
            price = self.price_service.get_historical_price(
                ticker=asset.ticker,
                asset_type=asset.asset_type,
                target_date=target_date,
                in_native_currency=False,  # Always use USD
            )
            return price
        except ValueError:
            # Exact date failed (e.g., weekend/holiday), expand range backward
            # Use cached_prices_only=True to prevent retriever from being called
            start_date = target_date - timedelta(days=self.lookback_days)
            end_date = target_date
            
            try:
                prices = self.price_service.get_historical_prices(
                    [asset.ticker],
                    asset.asset_type,
                    start_date,
                    end_date,
                    cached_prices_only=True,  # Only use cache, don't call retriever
                )
            except ValueError as e:
                raise ValueError(
                    f"No historical price data available for {asset.ticker} "
                    f"({asset.asset_type}) within {self.lookback_days} days of {target_date}: {e}"
                ) from e

            if asset.ticker not in prices or not prices[asset.ticker]:
                raise ValueError(
                    f"No historical price data available for {asset.ticker} "
                    f"({asset.asset_type}) within {self.lookback_days} days of {target_date}"
                )

            ticker_prices = prices[asset.ticker]
            
            # Find most recent date <= target_date with valid price
            available_dates = [d for d in ticker_prices.keys() if d <= target_date]
            if not available_dates:
                raise ValueError(
                    f"No historical price data available for {asset.ticker} "
                    f"({asset.asset_type}) on or before {target_date}"
                )

            most_recent_date = max(available_dates)
            price = ticker_prices[most_recent_date]
            
            logger.debug(
                f"Found price for {asset.ticker} using lookback: "
                f"{most_recent_date} -> ${price:.2f} (requested: {target_date})"
            )
            
            return price
