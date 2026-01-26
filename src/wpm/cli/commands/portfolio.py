"""Portfolio-related command handlers."""

import logging
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from wpm.cost_basis import calculate_lots_from_trades
from wpm.metrics import (
    calculate_realized_pnl_percentage,
    calculate_unrealized_pnl_percentage,
    format_weekly_performance_summary,
)
from wpm.models import Portfolio
from wpm.portfolio import (
    CompositePortfolio,
    fetch_price_map,
    get_historical_performance,
)
from wpm.pricing import PriceService

from ..formatters import format_currency, format_position_line, format_unrealized_pnl

logger = logging.getLogger(__name__)


def fetch_prices_for_portfolio(
    portfolio: CompositePortfolio, price_service: PriceService
) -> None:
    """Fetch prices for all assets in portfolio via PriceService.

    For historical portfolios, uses historical prices.

    Args:
        portfolio: Composite portfolio containing all assets
        price_service: Price service for retrieving prices

    Raises:
        SystemExit: If price retrieval fails for any asset with no cache entry
    """
    positions = portfolio.get_positions()
    assets = list(positions.keys())

    if not assets:
        logger.info("No assets found in portfolio, skipping price fetch")
        return

    if portfolio.is_historical:
        logger.info(
            f"Fetching historical prices for {len(assets)} assets "
            f"(historical portfolio up to {portfolio.end_date})..."
        )
    else:
        logger.info(f"Fetching prices for {len(assets)} assets...")

    # Use helper function to fetch prices (automatically uses historical prices for historical portfolios)
    price_map = fetch_price_map(portfolio, price_service)

    # Check for any missing prices and exit if found (this function requires all prices)
    missing_prices = [asset for asset, price in price_map.items() if price is None]
    if not missing_prices:
        # Display summary
        total = len(assets)
        price_type = "historical prices" if portfolio.is_historical else "prices"
        summary = f"{price_type.capitalize()} fetched for {total} assets"
        print(summary)
        logger.info(summary)
        return

    # Group missing assets by type for error message
    missing_by_type: Dict[str, List[str]] = defaultdict(list)
    for asset in missing_prices:
        missing_by_type[asset.asset_type].append(asset.ticker)

    error_parts = [
        f"{', '.join(tickers)} ({asset_type})"
        for asset_type, tickers in missing_by_type.items()
    ]
    price_type = "historical price" if portfolio.is_historical else "price"
    error_msg = (
        f"Error: No {price_type} data available for: {', '.join(error_parts)}. "
        f"API retrieval failed and no cache entry exists."
    )
    print(error_msg, file=sys.stderr)
    logger.error(error_msg)
    sys.exit(1)


def cmd_list_portfolios(composite: CompositePortfolio) -> None:
    """Handle 'list portfolios' command.

    Args:
        composite: Composite portfolio containing sub-portfolios
    """
    sub_portfolios = composite.get_sub_portfolios()

    if not sub_portfolios:
        print("No portfolios found.")
        return

    names = sorted(sub_portfolios.keys())
    for name in names:
        print(name)


def cmd_show_portfolio(
    composite: CompositePortfolio,
    name: str,
    price_service: PriceService,
    up_to_date: Optional[date] = None,
) -> None:
    """Handle 'show portfolio <name>' command.

    Args:
        composite: Composite portfolio containing sub-portfolios
        name: Name of sub-portfolio to show
        price_service: Price service for retrieving current prices
        up_to_date: Optional date for historical portfolios to show state up to this date with weekly summary
    """
    sub_portfolios = composite.get_sub_portfolios()

    if name not in sub_portfolios:
        print(f"Portfolio '{name}' not found.")
        return

    portfolio = sub_portfolios[name]

    # Handle --up-to argument for historical portfolios
    if up_to_date is not None:
        if not portfolio.is_historical:
            print("Error: --up-to can only be used with historical portfolios.")
            return

        if portfolio.start_date is None:
            print("Error: Portfolio has no start date, cannot calculate historical performance.")
            return

        # Show weekly performance summary
        try:
            history_points = get_historical_performance(
                portfolio, price_service, portfolio.start_date, up_to_date
            )
            format_weekly_performance_summary(history_points)
            return
        except Exception as e:
            print(f"Error calculating historical performance: {e}")
            logger.error(f"Error calculating historical performance: {e}", exc_info=True)
            return

    positions = portfolio.get_positions()

    if not positions:
        print(f"Portfolio '{name}' has no assets.")
        return

    # Fetch prices using helper function
    price_map = fetch_price_map(portfolio, price_service)

    # Calculate allocations if prices are available
    allocations = {}
    has_prices = any(price is not None for price in price_map.values())
    if has_prices:
        try:
            allocations = portfolio.get_all_allocations(price_map)
        except Exception as e:
            logger.debug(f"Failed to calculate allocations: {e}")
            # Continue without allocations (backward compatible)

    # Sort positions by ticker and display
    sorted_positions = sorted(positions.items(), key=lambda x: x[0].ticker)
    for asset, position in sorted_positions:
        price = price_map.get(asset)
        allocation = allocations.get(asset) if allocations else None
        print(format_position_line(position, price, portfolio.is_historical, portfolio.end_date, allocation))

    # Display summary
    print()  # Blank line before summary
    total_cost_basis = portfolio.get_total_cost_basis()
    total_market_value = portfolio.get_total_market_value(price_map)
    total_unrealized_pnl = portfolio.get_total_unrealized_pnl(price_map)
    total_realized_pnl = portfolio.get_total_realized_pnl()

    # Check if we have any prices available
    has_prices = any(price is not None for price in price_map.values())

    print(f"Total Market Value: {format_currency(total_market_value) if has_prices else 'N/A'}")
    print(f"Total Cost Basis: {format_currency(total_cost_basis)}")
    if has_prices:
        print(f"Total Unrealized P/L: {format_unrealized_pnl(total_unrealized_pnl)}")
    else:
        print("Total Unrealized P/L: N/A")
    print(f"Total Realized P/L: {format_unrealized_pnl(total_realized_pnl)}")


def _display_totals_section(
    imported_portfolio: Portfolio,
    reference_portfolios: Dict[str, Portfolio],
    price_service: PriceService,
    target_date: Optional[date] = None,
) -> None:
    """Display totals section with P/Ls and percentage returns for imported and reference portfolios.
    
    Args:
        imported_portfolio: The main imported portfolio
        reference_portfolios: Dictionary mapping reference portfolio names to Portfolio objects
        price_service: Price service for fetching prices
        target_date: Optional date to calculate values against (for --up-to)
    """
    print()  # Blank line separator
    print("Totals:")
    
    # Calculate values for imported portfolio
    try:
        imported_price_map = fetch_price_map(imported_portfolio, price_service, target_date=target_date)
        imported_unrealized_pnl = imported_portfolio.get_total_unrealized_pnl(imported_price_map)
        
        # Calculate realized P/L - if target_date is provided, calculate from filtered lots
        if target_date is not None:
            # Filter trades and calculate realized P/L from filtered lots
            all_trades = imported_portfolio.get_all_trades()
            filtered_trades = [t for t in all_trades if t.date <= target_date]
            lots_by_asset = calculate_lots_from_trades(filtered_trades)
            imported_realized_pnl = sum(
                lot.get_realized_pnl() for lots in lots_by_asset.values() for lot in lots
            )
        else:
            imported_realized_pnl = imported_portfolio.get_total_realized_pnl()
        
        imported_has_prices = any(price is not None for price in imported_price_map.values())
        
        imported_unrealized_pct = None
        if imported_has_prices:
            imported_unrealized_pct = calculate_unrealized_pnl_percentage(
                imported_portfolio, imported_price_map, target_date
            )
        imported_realized_pct = calculate_realized_pnl_percentage(imported_portfolio, target_date)
        
        # Display imported portfolio totals
        print("Imported Portfolio:")
        if imported_has_prices:
            unrealized_str = format_unrealized_pnl(imported_unrealized_pnl)
            if imported_unrealized_pct is not None:
                unrealized_str += f" ({imported_unrealized_pct:+.2f}%)"
            print(f"  Total Unrealized P/L: {unrealized_str}")
        else:
            print("  Total Unrealized P/L: N/A")
        
        realized_str = format_unrealized_pnl(imported_realized_pnl)
        if imported_realized_pct is not None:
            realized_str += f" ({imported_realized_pct:+.2f}%)"
        print(f"  Total Realized P/L: {realized_str}")
    except Exception as e:
        logger.warning(f"Failed to calculate imported portfolio totals: {e}")
        # Still try to show realized P/L which doesn't depend on prices
        try:
            if target_date is not None:
                all_trades = imported_portfolio.get_all_trades()
                filtered_trades = [t for t in all_trades if t.date <= target_date]
                lots_by_asset = calculate_lots_from_trades(filtered_trades)
                imported_realized_pnl = sum(
                    lot.get_realized_pnl() for lots in lots_by_asset.values() for lot in lots
                )
            else:
                imported_realized_pnl = imported_portfolio.get_total_realized_pnl()
            imported_realized_pct = calculate_realized_pnl_percentage(imported_portfolio, target_date)
            
            print("Imported Portfolio:")
            print("  Total Unrealized P/L: N/A")
            realized_str = format_unrealized_pnl(imported_realized_pnl)
            if imported_realized_pct is not None:
                realized_str += f" ({imported_realized_pct:+.2f}%)"
            print(f"  Total Realized P/L: {realized_str}")
        except Exception:
            # If even realized P/L fails, just show N/A
            print("Imported Portfolio:")
            print("  Total Unrealized P/L: N/A")
            print("  Total Realized P/L: N/A")
    
    # Calculate values for reference portfolios if available
    # Iterate in order: SPY first, then BTC-USD (if both exist)
    ordered_names = ["SPY Reference Portfolio", "BTC-USD Reference Portfolio"]
    for ref_name in ordered_names:
        if ref_name not in reference_portfolios:
            continue
        
        reference_portfolio = reference_portfolios[ref_name]
        try:
            reference_price_map = fetch_price_map(
                reference_portfolio, price_service, target_date=target_date
            )
            reference_unrealized_pnl = reference_portfolio.get_total_unrealized_pnl(reference_price_map)
            
            # Calculate realized P/L - if target_date is provided, calculate from filtered lots
            if target_date is not None:
                # Filter trades and calculate realized P/L from filtered lots
                all_trades = reference_portfolio.get_all_trades()
                filtered_trades = [t for t in all_trades if t.date <= target_date]
                lots_by_asset = calculate_lots_from_trades(filtered_trades)
                reference_realized_pnl = sum(
                    lot.get_realized_pnl() for lots in lots_by_asset.values() for lot in lots
                )
            else:
                reference_realized_pnl = reference_portfolio.get_total_realized_pnl()
            
            reference_has_prices = any(price is not None for price in reference_price_map.values())
            
            reference_unrealized_pct = None
            if reference_has_prices:
                reference_unrealized_pct = calculate_unrealized_pnl_percentage(
                    reference_portfolio, reference_price_map, target_date
                )
            reference_realized_pct = calculate_realized_pnl_percentage(reference_portfolio, target_date)
            
            # Display reference portfolio totals
            print(f"{ref_name}:")
            if reference_has_prices:
                unrealized_str = format_unrealized_pnl(reference_unrealized_pnl)
                if reference_unrealized_pct is not None:
                    unrealized_str += f" ({reference_unrealized_pct:+.2f}%)"
                print(f"  Total Unrealized P/L: {unrealized_str}")
            else:
                print("  Total Unrealized P/L: N/A")
            
            realized_str = format_unrealized_pnl(reference_realized_pnl)
            if reference_realized_pct is not None:
                realized_str += f" ({reference_realized_pct:+.2f}%)"
            print(f"  Total Realized P/L: {realized_str}")
        except Exception as e:
            logger.warning(
                f"Failed to calculate {ref_name} totals: {e}"
            )
            # Continue without displaying this reference portfolio totals


def cmd_show_all(
    composite: CompositePortfolio,
    price_service: PriceService,
    up_to_date: Optional[date] = None,
    reference_portfolios: Dict[str, Portfolio] = None,
) -> None:
    """Handle 'show all' command.

    Args:
        composite: Composite portfolio
        price_service: Price service for retrieving current prices
        up_to_date: Optional date for historical portfolios to show state up to this date with weekly summary
        reference_portfolios: Dictionary mapping reference portfolio names to Portfolio objects
    """
    if reference_portfolios is None:
        reference_portfolios = {}
    # Handle --up-to argument for historical portfolios
    if up_to_date is not None:
        if not composite.is_historical:
            print("Error: --up-to can only be used with historical portfolios.")
            return

        if composite.start_date is None:
            print("Error: Portfolio has no start date, cannot calculate historical performance.")
            return

        # Show weekly performance summary
        try:
            history_points = get_historical_performance(
                composite, price_service, composite.start_date, up_to_date
            )
            format_weekly_performance_summary(history_points)
            
            # Display totals section with both portfolios
            _display_totals_section(
                imported_portfolio=composite,
                reference_portfolios=reference_portfolios,
                price_service=price_service,
                target_date=up_to_date,
            )
            
            return
        except Exception as e:
            print(f"Error calculating historical performance: {e}")
            logger.error(f"Error calculating historical performance: {e}", exc_info=True)
            return

    positions = composite.get_positions()

    if not positions:
        print("No assets found in composite portfolio.")
        return

    # Fetch prices using helper function
    price_map = fetch_price_map(composite, price_service)

    # Calculate allocations if prices are available
    allocations = {}
    has_prices = any(price is not None for price in price_map.values())
    if has_prices:
        try:
            allocations = composite.get_all_allocations(price_map)
        except Exception as e:
            logger.debug(f"Failed to calculate allocations: {e}")
            # Continue without allocations (backward compatible)

    # Sort positions by ticker and display
    sorted_positions = sorted(positions.items(), key=lambda x: x[0].ticker)
    for asset, position in sorted_positions:
        price = price_map.get(asset)
        allocation = allocations.get(asset) if allocations else None
        print(format_position_line(position, price, composite.is_historical, composite.end_date, allocation))

    # Display totals section with both portfolios
    _display_totals_section(
        imported_portfolio=composite,
        reference_portfolios=reference_portfolios,
        price_service=price_service,
        target_date=None,  # Current date for non-historical
    )
