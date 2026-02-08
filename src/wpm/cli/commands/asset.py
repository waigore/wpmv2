"""Asset-related command handlers."""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from wpm.asset import AssetService
from wpm.models import Asset, Trade
from wpm.portfolio import (
    CompositePortfolio,
    _adjust_trades_for_historical_date,
    _calculate_percentage_return_from_lots,
    _position_from_lots,
    fetch_price_map,
    get_historical_allocations,
    get_historical_performance,
)
from wpm.pricing import PriceService
from wpm.pricing.splits import SplitService

from ..formatters import (
    format_currency,
    format_historical_asset_line,
    format_lot_line,
    format_market_cap,
    format_position_line,
    format_unrealized_pnl,
    _format_broker_breakdown,
)

logger = logging.getLogger(__name__)


def cmd_show_asset(
    composite: CompositePortfolio,
    ticker: str,
    price_service: PriceService,
    from_date: Optional[date] = None,
    brokers: Optional[List[str]] = None,
) -> None:
    """Handle 'show asset <ticker>' command.

    Args:
        composite: Composite portfolio
        ticker: Asset ticker symbol to show
        price_service: Price service for retrieving prices
        from_date: Optional start date for historical portfolios
        brokers: Optional list of broker names to filter by
    """
    # Get asset from current portfolio to validate it exists and get asset_type
    positions = composite.get_positions(tickers=[ticker])

    if not positions:
        print(f"Asset '{ticker}' not found in portfolio.")
        return

    # Get the asset object (should only be one)
    asset = next(iter(positions.keys()))
    asset_type = asset.asset_type

    # Handle historical portfolios
    if composite.is_historical:
        # Validate portfolio has end_date
        if composite.end_date is None:
            print("Error: Portfolio has no end date, cannot calculate historical performance.")
            return
        # Validate --from argument
        if from_date is not None:
            if composite.end_date is None:
                print("Error: Portfolio has no end date, cannot calculate historical performance.")
                return

            if from_date > composite.end_date:
                print(f"Error: --from date ({from_date}) is after portfolio end date ({composite.end_date}).")
                return

            if composite.start_date is not None and from_date < composite.start_date:
                print(f"Error: --from date ({from_date}) is before portfolio start date ({composite.start_date}).")
                return

            start_date = from_date
        else:
            # Default to past 30 days
            if composite.end_date is None:
                print("Error: Portfolio has no end date, cannot calculate historical performance.")
                return

            start_date = composite.end_date - timedelta(days=30)
            if composite.start_date is not None and start_date < composite.start_date:
                start_date = composite.start_date

        end_date = composite.end_date

        try:
            history_points = get_historical_performance(
                composite, price_service, start_date, end_date, brokers=brokers
            )
            allocations_list = get_historical_allocations(
                composite, price_service, start_date, end_date, brokers=brokers,
                history_points=history_points,
            )
        except Exception as e:
            print(f"Error calculating historical performance: {e}")
            logger.error(f"Error calculating historical performance: {e}", exc_info=True)
            return

        # Get final portfolio positions to establish ticker-to-Asset mapping
        final_positions = composite.get_positions()
        ticker_to_asset: Dict[str, Asset] = {asset.ticker: asset for asset in final_positions.keys()}

        # Get all trades once for lot calculation
        all_trades = composite.get_all_trades()
        if brokers is not None:
            all_trades = [t for t in all_trades if t.broker in brokers]

        # Reuse price_service's SplitService so split data is already cached from get_historical_performance
        split_service = price_service.get_split_service()
        # Prefetch split data once (Principle 6); pass ticker_splits to _adjust_trades_for_historical_date
        stock_etf_tickers = [
            t.asset.ticker for t in all_trades
            if t.asset.asset_type in ("Stock", "ETF")
        ]
        ticker_splits = (
            split_service.get_splits(list(dict.fromkeys(stock_etf_tickers)))
            if stock_etf_tickers else {}
        )

        # Cache adjusted trades by date to avoid recalculating for each history point
        # This significantly improves performance when displaying many dates
        adjusted_trades_cache: Dict[date, List[Trade]] = {}
        
        # Pre-calculate adjusted trades for all unique dates in history_points
        unique_dates = sorted(set(hp.date for hp in history_points))
        for unique_date in unique_dates:
            # Filter trades up to this date
            filtered_trades = [t for t in all_trades if t.date <= unique_date]
            # Adjust trades for splits up to this historical date
            adjusted_trades = _adjust_trades_for_historical_date(
                filtered_trades, ticker_splits, unique_date
            )
            adjusted_trades_cache[unique_date] = adjusted_trades

        # Filter and display history points for this ticker
        for i, history_point in enumerate(history_points):
            position_value = history_point.asset_positions.get(ticker, 0.0)
            # Skip days where asset has no position
            if position_value > 0:
                # Get pre-calculated adjusted trades for this date from cache
                adjusted_trades = adjusted_trades_cache.get(history_point.date, [])
                
                asset_price = history_point.prices.get(ticker)
                prices_dict = {ticker: asset_price} if asset_price is not None else {}

                # Calculate percentage return for this asset using cached adjusted trades
                asset_percentage_return = (
                    _calculate_percentage_return_from_lots(
                        adjusted_trades, prices_dict, ticker_filter=ticker
                    )
                    if asset_price is not None
                    else None
                )

                # Get allocation for this date if available
                allocation = None
                if i < len(allocations_list) and ticker in ticker_to_asset:
                    asset_obj = ticker_to_asset[ticker]
                    allocations = allocations_list[i]
                    allocation = allocations.get(asset_obj)
                print(
                    format_historical_asset_line(
                        history_point, ticker, asset_type, allocation, asset_percentage_return
                    )
                )
        return

    # Handle current portfolios
    # If brokers filter is provided, calculate position from filtered lots
    if brokers is not None:
        # Get filtered lots
        lots = composite.get_asset_lots(ticker, brokers=brokers)
        if not lots:
            print(f"No positions found for ticker '{ticker}' with specified brokers.")
            return
        # Calculate position from lots using helper from portfolio module
        try:
            position = _position_from_lots(lots)
        except ValueError:
            print(f"No positions found for ticker '{ticker}' with specified brokers.")
            return
    else:
        position = positions[asset]

    # Fetch price using helper function
    price_map = fetch_price_map(composite, price_service)
    price = price_map.get(asset)

    # Calculate allocation if price is available
    allocation = None
    if price is not None:
        try:
            allocation = composite.get_asset_allocation(asset, price_map)
        except Exception as e:
            logger.debug(f"Failed to calculate allocation: {e}")
            # Continue without allocation (backward compatible)

    # Display position line
    print(format_position_line(position, price, composite.is_historical, composite.end_date, allocation))

    # Display broker breakdown for current portfolios (no broker filter applied)
    if brokers is None:
        broker_positions = composite.get_asset_positions_by_broker(ticker)
        if broker_positions:
            _format_broker_breakdown(broker_positions)

    # Display summary
    print()  # Blank line before summary
    cost_basis = position.cost_basis
    market_value = float(position.quantity) * price if price is not None else 0.0
    unrealized_pnl = market_value - cost_basis if price is not None else 0.0
    # Calculate realized P/L for the asset (accounting for broker filter)
    realized_pnl = composite.get_asset_realized_pnl(ticker, brokers=brokers)

    print(f"Total Market Value: {format_currency(market_value) if price is not None else 'N/A'}")
    print(f"Total Cost Basis: {format_currency(cost_basis)}")
    if price is not None:
        print(f"Total Unrealized P/L: {format_unrealized_pnl(unrealized_pnl)}")
    else:
        print("Total Unrealized P/L: N/A")
    print(f"Realized P/L: {format_unrealized_pnl(realized_pnl)}")


def cmd_metadata(
    composite: CompositePortfolio, ticker: str, asset_service: AssetService
) -> None:
    """Handle 'metadata <ticker>' command.

    Args:
        composite: Composite portfolio containing all assets
        ticker: Asset ticker symbol to show metadata for
        asset_service: Asset service for retrieving metadata
    """
    # Get asset type from lightweight asset cache (no calculations)
    try:
        assets = composite.get_assets()
        asset = assets.get(ticker)
    except Exception:
        # If get_assets() fails, fall back to inferring asset type from ticker
        asset = None

    if asset is not None:
        asset_type = asset.asset_type
    else:
        # Ticker not in portfolio, infer from format
        if ticker.endswith("-USD"):
            asset_type = "Crypto"
        else:
            asset_type = "Stock"  # Default assumption

    # Retrieve metadata
    metadata = asset_service.get_metadata(ticker, asset_type)

    if metadata is None:
        print(f"No metadata available for '{ticker}'.")
        return

    # Display metadata
    print(f"Ticker: {ticker}")
    print(f"Name: {metadata.get('name', 'N/A')}")
    print(f"Type: {asset_type}")
    print(f"Market Cap: {format_market_cap(metadata.get('market_cap'))}")
    print(f"Sector: {metadata.get('sector', 'N/A')}")
    print(f"Industry: {metadata.get('industry', 'N/A')}")
    print(f"Country: {metadata.get('country', 'N/A')}")
    print(f"Category: {metadata.get('category', 'unknown')}")


def cmd_show_lots(
    composite: CompositePortfolio, ticker: str, price_service: PriceService
) -> None:
    """Handle 'lots <ticker>' command.

    Args:
        composite: Composite portfolio containing all assets
        ticker: Asset ticker symbol to show lots for
        price_service: Price service for retrieving current prices
    """
    # Get lots for the ticker
    lots = composite.get_asset_lots(ticker)
    
    if not lots:
        print(f"No lots found for ticker '{ticker}'.")
        return
    
    # Sort lots by purchase date (oldest first)
    sorted_lots = sorted(lots, key=lambda lot: lot.purchase_date)
    
    # Determine asset type from first lot to fetch current price
    asset = sorted_lots[0].asset
    current_price = None
    
    try:
        current_price = price_service.get_price(ticker, asset.asset_type)
    except Exception as e:
        logger.warning(f"Price retrieval failed for {ticker}: {e}")
        # Continue with None price - will show N/A for unrealized/total P/L
    
    # Display each lot
    for lot in sorted_lots:
        print(format_lot_line(lot, current_price))
