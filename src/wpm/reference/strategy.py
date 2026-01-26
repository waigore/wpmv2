"""Reference investment strategies for creating baseline comparison portfolios."""

import logging
from abc import ABC, abstractmethod
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from wpm.models import Asset, Portfolio, Trade

if TYPE_CHECKING:
    from wpm.currency import CurrencyService
    from wpm.pricing.service import PriceService
    from wpm.reference.fetcher import HistoricalPriceFetcher

logger = logging.getLogger(__name__)


class ReferenceStrategy(ABC):
    """Abstract base class for reference investment strategies.
    
    A reference strategy defines how to convert trades from an original portfolio
    into corresponding trades in a reference portfolio. The strategy invests the
    full cost basis of the original trade, but the result can be one or more trades
    depending on how the strategy is implemented.
    """

    def prepare(
        self,
        portfolio: Portfolio,
        price_fetcher: "HistoricalPriceFetcher",
    ) -> None:
        """Optional pre-init phase called before processing trades.
        
        Allows strategy to prepare resources, prefetch prices, etc.
        Default implementation does nothing (backward compatible).
        
        Args:
            portfolio: Original portfolio to prepare for
            price_fetcher: Historical price fetcher to use for prefetching
        """
        pass

    @abstractmethod
    def generate_trades(
        self,
        original_trade: Trade,
        price_service: "PriceService",
        currency_service: "CurrencyService",
        price_fetcher: Optional["HistoricalPriceFetcher"] = None,
    ) -> List[Trade]:
        """Generate reference trade(s) from an original trade.
        
        The strategy invests the full cost basis of the original trade into the
        reference asset(s). For Buy trades, this means investing the full cost basis.
        For Sell trades, this means selling the same cost basis amount.
        
        Args:
            original_trade: The original trade to convert
            price_service: Service to fetch historical prices for the reference asset
            currency_service: Service for currency conversion (if needed)
            price_fetcher: Optional historical price fetcher with fallback logic.
                If provided, use this instead of price_service.get_historical_price().
                If None, use price_service.get_historical_price() (backward compatible).
            
        Returns:
            List of reference trades (can be one or more). The trades should preserve
            the original trade's date, broker, order_instruction, and trade_type.
            
        Raises:
            ValueError: If historical price cannot be retrieved for the reference asset
                on the trade date, or if other required data is unavailable
        """
        pass


class BuyAndHoldStrategy(ReferenceStrategy):
    """Simple buy-and-hold strategy investing in a single asset.
    
    This strategy converts each original trade into a corresponding trade in a
    single reference asset (e.g., SPY). The full cost basis of the original trade
    is invested in (or sold from) the reference asset.
    
    Example:
        If the original trade is a Buy of $1000 worth of GOOG, and SPY is $400
        on that date, this strategy creates a Buy of 2.5 shares of SPY.
    """

    def __init__(self, reference_asset: Asset):
        """Initialize buy-and-hold strategy with a reference asset.
        
        Args:
            reference_asset: The asset to invest in (e.g., Asset(ticker="SPY", asset_type="ETF"))
            
        Raises:
            ValueError: If reference_asset is not a valid Asset object
        """
        if not isinstance(reference_asset, Asset):
            raise ValueError("reference_asset must be an Asset object")
        
        self.reference_asset = reference_asset
        logger.info(
            f"Initialized BuyAndHoldStrategy with reference asset: {reference_asset.ticker} "
            f"({reference_asset.asset_type})"
        )

    def prepare(
        self,
        portfolio: Portfolio,
        price_fetcher: "HistoricalPriceFetcher",
    ) -> None:
        """Pre-fetch prices for reference asset over portfolio date range.
        
        Requests the price fetcher to batch fetch all prices for the reference asset
        from (start_date - 7 days) to end_date to ensure prices are available for
        all trade dates, including weekends and holidays.
        
        Args:
            portfolio: Original portfolio to prepare for
            price_fetcher: Historical price fetcher to use for prefetching
        """
        start_date = portfolio.start_date
        if start_date is None:
            return
        
        end_date = portfolio.end_date
        if end_date is None:
            # Get max trade date if end_date is None
            all_trades = portfolio.get_all_trades()
            if not all_trades:
                return
            end_date = max(trade.date for trade in all_trades)
        
        # Calculate prefill range: 1 week before start_date to end_date
        prefill_start = start_date - timedelta(days=7)
        
        logger.info(
            f"Preparing BuyAndHoldStrategy: prefetching prices for {self.reference_asset.ticker} "
            f"from {prefill_start} to {end_date}"
        )
        
        price_fetcher.prefetch_prices(self.reference_asset, prefill_start, end_date)

    def generate_trades(
        self,
        original_trade: Trade,
        price_service: "PriceService",
        currency_service: "CurrencyService",
        price_fetcher: Optional["HistoricalPriceFetcher"] = None,
    ) -> List[Trade]:
        """Generate a reference trade from an original trade.
        
        For Buy trades: Invests the full cost basis (total_value) into the reference asset.
        For Sell trades: Sells the same cost basis amount from the reference asset.
        
        The original trade's cost basis is already in USD (from trade.price field),
        so we work entirely in USD for reference trades.
        
        Args:
            original_trade: The original trade to convert
            price_service: Service to fetch historical prices
            currency_service: Service for currency conversion (not used in this strategy
                since we work in USD, but required by interface)
            price_fetcher: Optional historical price fetcher with fallback logic.
                If provided, use this instead of price_service.get_historical_price().
                If None, use price_service.get_historical_price() (backward compatible).
            
        Returns:
            List containing a single Trade object for the reference asset
            
        Raises:
            ValueError: If historical price cannot be retrieved for the reference asset
                on the trade date
        """
        # Get cost basis from original trade (already in USD)
        cost_basis_usd = original_trade.total_value
        
        if cost_basis_usd <= 0:
            raise ValueError(
                f"Original trade has invalid cost basis: {cost_basis_usd}. "
                f"Trade must have positive value."
            )
        
        # Get reference asset price on the trade date (in USD)
        # Use price_fetcher if provided, otherwise fall back to price_service
        if price_fetcher is not None:
            try:
                reference_price_usd = price_fetcher.get_historical_price(
                    asset=self.reference_asset,
                    target_date=original_trade.date,
                )
            except ValueError as e:
                raise ValueError(
                    f"Cannot create reference trade: historical price unavailable for "
                    f"{self.reference_asset.ticker} ({self.reference_asset.asset_type}) "
                    f"on {original_trade.date}: {e}"
                ) from e
        else:
            # Backward compatible: use price_service directly
            try:
                reference_price_usd = price_service.get_historical_price(
                    ticker=self.reference_asset.ticker,
                    asset_type=self.reference_asset.asset_type,
                    target_date=original_trade.date,
                    in_native_currency=False,  # Always use USD
                )
            except ValueError as e:
                raise ValueError(
                    f"Cannot create reference trade: historical price unavailable for "
                    f"{self.reference_asset.ticker} ({self.reference_asset.asset_type}) "
                    f"on {original_trade.date}: {e}"
                ) from e
        
        if reference_price_usd <= 0:
            raise ValueError(
                f"Reference asset {self.reference_asset.ticker} has invalid price "
                f"${reference_price_usd:.2f} on {original_trade.date}"
            )
        
        # Calculate quantity: cost_basis / price
        quantity = Decimal(str(cost_basis_usd)) / Decimal(str(reference_price_usd))
        
        # Determine currency for reference asset
        # For most assets (Stock, ETF, Crypto), currency is USD
        # We can detect this from the asset type or ticker if needed
        reference_currency = "USD"
        
        # Create reference trade
        reference_trade = Trade(
            date=original_trade.date,
            asset=self.reference_asset,
            action=original_trade.action,  # Preserve Buy/Sell
            broker=original_trade.broker,  # Preserve broker
            order_instruction=original_trade.order_instruction,  # Preserve order instruction
            trade_type=original_trade.trade_type,  # Preserve trade type
            currency=reference_currency,
            price=reference_price_usd,  # Price in USD
            price_native=reference_price_usd,  # For USD assets, native = USD
            quantity=quantity,
        )
        
        return [reference_trade]
