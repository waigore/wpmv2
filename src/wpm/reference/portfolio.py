"""Reference portfolio creation functions."""

import logging
from typing import TYPE_CHECKING, Optional

from wpm.currency import CurrencyService
from wpm.models import Portfolio
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.reference.fetcher import DefaultHistoricalPriceFetcher, HistoricalPriceFetcher
from wpm.reference.strategy import ReferenceStrategy

if TYPE_CHECKING:
    from wpm.pricing.service import PriceService

logger = logging.getLogger(__name__)


def create_reference_portfolio(
    original_portfolio: Portfolio,
    strategy: ReferenceStrategy,
    price_service: "PriceService",
    currency_service: CurrencyService,
    name: Optional[str] = None,
    price_fetcher: Optional[HistoricalPriceFetcher] = None,
) -> Portfolio:
    """Create a reference portfolio from an original portfolio using a strategy.
    
    Iterates through all trades in the original portfolio and creates corresponding
    reference trades using the provided strategy. The reference portfolio preserves
    the structure (SimplePortfolio or CompositePortfolio) and is_historical flag
    of the original portfolio.
    
    Before processing trades, calls strategy.prepare() to allow the strategy to
    initialize resources (e.g., prefetch prices via the price fetcher). This ensures
    prices are available for all trade dates, including weekends and holidays.
    
    The created reference portfolio works seamlessly with get_historical_performance(),
    allowing easy comparison with the original portfolio.
    
    Args:
        original_portfolio: Original portfolio (SimplePortfolio or CompositePortfolio)
        strategy: Reference strategy to apply (e.g., BuyAndHoldStrategy)
        price_service: Service for fetching historical prices for reference assets
        currency_service: Currency service for currency conversion.
            Note: Currently not used by BuyAndHoldStrategy since it works in USD,
            but required for interface consistency and may be needed for future strategies.
        name: Optional name for reference portfolio. If None, defaults to
            "{original_name} (Reference)"
        price_fetcher: Optional historical price fetcher with fallback logic.
            If None, creates a DefaultHistoricalPriceFetcher with 1-week lookback.
        
    Returns:
        New Portfolio instance (SimplePortfolio or CompositePortfolio) with reference trades.
        The portfolio type and is_historical flag match the original portfolio.
        
    Raises:
        ValueError: If historical prices cannot be retrieved for reference assets,
            or if other required data is unavailable
        PortfolioError: If portfolio structure is invalid
    """
    
    # Determine portfolio name
    if name is None:
        name = f"{original_portfolio.name} (Reference)"
    
    logger.info(
        f"Creating reference portfolio '{name}' from '{original_portfolio.name}' "
        f"using strategy {strategy.__class__.__name__}"
    )
    
    # Create price fetcher if not provided
    if price_fetcher is None:
        price_fetcher = DefaultHistoricalPriceFetcher(price_service=price_service, lookback_days=7)
    
    # Call strategy prepare phase to allow prefetching prices
    # This ensures prices are available for all trade dates, including weekends/holidays
    strategy.prepare(original_portfolio, price_fetcher)
    
    # Handle SimplePortfolio
    if isinstance(original_portfolio, SimplePortfolio):
        return _create_reference_simple_portfolio(
            original_portfolio=original_portfolio,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
            name=name,
            price_fetcher=price_fetcher,
        )
    
    # Handle CompositePortfolio
    if isinstance(original_portfolio, CompositePortfolio):
        return _create_reference_composite_portfolio(
            original_portfolio=original_portfolio,
            strategy=strategy,
            price_service=price_service,
            currency_service=currency_service,
            name=name,
            price_fetcher=price_fetcher,
        )
    
    # Should not reach here, but handle gracefully
    raise ValueError(
        f"Unsupported portfolio type: {type(original_portfolio)}. "
        f"Expected SimplePortfolio or CompositePortfolio."
    )


def _create_reference_simple_portfolio(
    original_portfolio: SimplePortfolio,
    strategy: ReferenceStrategy,
    price_service: "PriceService",
    currency_service: CurrencyService,
    name: str,
    price_fetcher: HistoricalPriceFetcher,
) -> SimplePortfolio:
    """Create a reference SimplePortfolio from an original SimplePortfolio.
    
    Args:
        original_portfolio: Original SimplePortfolio
        strategy: Reference strategy to apply
        price_service: Service for fetching historical prices
        currency_service: Currency service
        name: Name for the reference portfolio
        price_fetcher: Historical price fetcher with fallback logic
        
    Returns:
        New SimplePortfolio with reference trades
    """
    # Create new SimplePortfolio with matching is_historical flag
    reference_portfolio = SimplePortfolio(
        name=name,
        is_historical=original_portfolio.is_historical,
    )
    
    # Get all trades from original portfolio
    original_trades = original_portfolio.get_all_trades()
    
    if not original_trades:
        logger.info(f"Original portfolio '{original_portfolio.name}' has no trades")
        return reference_portfolio
    
    logger.info(
        f"Processing {len(original_trades)} trades from original portfolio "
        f"'{original_portfolio.name}'"
    )
    
    # Iterate through trades and generate reference trades
    for original_trade in original_trades:
        try:
            # Generate reference trades using strategy with price_fetcher
            reference_trades = strategy.generate_trades(
                original_trade=original_trade,
                price_service=price_service,
                currency_service=currency_service,
                price_fetcher=price_fetcher,
            )
            
            # Add reference trades to portfolio
            for reference_trade in reference_trades:
                reference_portfolio.add_trade(reference_trade)
                
        except ValueError as e:
            # Log error and re-raise with context
            logger.error(
                f"Failed to generate reference trade for original trade "
                f"{original_trade.date} {original_trade.asset.ticker} "
                f"{original_trade.action}: {e}"
            )
            raise ValueError(
                f"Cannot create reference portfolio: failed to generate reference trade "
                f"for {original_trade.date} {original_trade.asset.ticker} "
                f"{original_trade.action}: {e}"
            ) from e
    
    logger.info(
        f"Created reference portfolio '{name}' with {len(reference_portfolio.get_all_trades())} trades"
    )
    
    return reference_portfolio


def _create_reference_composite_portfolio(
    original_portfolio: CompositePortfolio,
    strategy: ReferenceStrategy,
    price_service: "PriceService",
    currency_service: CurrencyService,
    name: str,
    price_fetcher: HistoricalPriceFetcher,
) -> CompositePortfolio:
    """Create a reference CompositePortfolio from an original CompositePortfolio.
    
    Recursively creates reference portfolios for each sub-portfolio and combines
    them into a new composite portfolio.
    
    Args:
        original_portfolio: Original CompositePortfolio
        strategy: Reference strategy to apply
        price_service: Service for fetching historical prices
        currency_service: Currency service
        name: Name for the reference portfolio
        price_fetcher: Historical price fetcher with fallback logic
        
    Returns:
        New CompositePortfolio with reference sub-portfolios
    """
    # Create new CompositePortfolio with matching is_historical flag
    reference_portfolio = CompositePortfolio(
        name=name,
        is_historical=original_portfolio.is_historical,
    )
    
    # Get all sub-portfolios
    sub_portfolios = original_portfolio.get_sub_portfolios()
    
    if not sub_portfolios:
        logger.info(f"Original composite portfolio '{original_portfolio.name}' has no sub-portfolios")
        return reference_portfolio
    
    logger.info(
        f"Processing {len(sub_portfolios)} sub-portfolios from original composite portfolio "
        f"'{original_portfolio.name}'"
    )
    
    # Recursively create reference portfolios for each sub-portfolio
    # Pass price_fetcher to maintain consistency across recursive calls
    for sub_name, sub_portfolio in sub_portfolios.items():
        try:
            # Create reference sub-portfolio (recursive call)
            # Note: price_fetcher is passed to avoid creating multiple instances
            reference_sub_portfolio = create_reference_portfolio(
                original_portfolio=sub_portfolio,
                strategy=strategy,
                price_service=price_service,
                currency_service=currency_service,
                name=f"{sub_name} (Reference)",  # Preserve sub-portfolio naming
                price_fetcher=price_fetcher,  # Reuse same fetcher instance
            )
            
            # Add reference sub-portfolio to composite
            reference_portfolio.add_sub_portfolio(reference_sub_portfolio)
            
        except (ValueError, Exception) as e:
            # Log error and re-raise with context
            logger.error(
                f"Failed to create reference portfolio for sub-portfolio '{sub_name}': {e}"
            )
            raise ValueError(
                f"Cannot create reference portfolio: failed to process sub-portfolio "
                f"'{sub_name}': {e}"
            ) from e
    
    logger.info(
        f"Created reference composite portfolio '{name}' with "
        f"{len(reference_portfolio.get_sub_portfolios())} sub-portfolios"
    )
    
    return reference_portfolio
