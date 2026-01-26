#!/usr/bin/env python3
"""Command-line utility for WPM (Wealth Portfolio Manager).

This utility orchestrates CSV imports, creates composite portfolios,
updates price caches, and provides an interactive command interface.
"""

import argparse
import logging
import shlex
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from wpm.asset import AssetService
from wpm.currency import CurrencyService
from wpm.importer import import_csv_files
from wpm.metrics import (
    breakdown_by_asset_type,
    breakdown_by_broker,
    breakdown_by_purchase_period,
    breakdown_by_ticker,
)
from wpm.models import (
    Asset,
    Lot,
    Portfolio,
    PortfolioHistoryPoint,
    Position,
    ValidationError,
)
from wpm.cost_basis import calculate_lots_from_trades
from wpm.portfolio import (
    CompositePortfolio,
    _calculate_percentage_return_from_lots,
    _position_from_lots,
    fetch_price_map,
    get_historical_allocations,
    get_historical_performance,
    SimplePortfolio,
)
from wpm.pricing import PriceService
from wpm.reference.portfolio import create_reference_portfolio
from wpm.reference.strategy import BuyAndHoldStrategy
from wpm.utils import normalize_date

logger = logging.getLogger(__name__)

# Constants
IMPORT_DIR = Path("import")
PROMPT = "wpm> "


def setup_cli_logging() -> None:
    """Configure CLI-specific logging to write to logs/wpmcli.log.
    
    This function configures logging for the CLI only, directing all logs
    to logs/wpmcli.log and suppressing stdout/stderr output. This ensures
    a clean CLI interface while preserving logs for debugging.
    
    Library users are not affected and can still configure their own logging
    using wpm.utils.setup_logging().
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Get the root "wpm" logger to capture all module logs
    wpm_logger = logging.getLogger("wpm")
    wpm_logger.setLevel(logging.INFO)
    
    # Remove any existing StreamHandlers to suppress stdout/stderr output
    # This ensures no logs appear in the console
    for handler in wpm_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            wpm_logger.removeHandler(handler)
    
    # Add FileHandler for logs/wpmcli.log
    log_file = logs_dir / "wpmcli.log"
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setLevel(logging.INFO)
    
    # Use the same formatter as setup_logging() for consistency
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    
    # Only add handler if it doesn't already exist (avoid duplicates on reload)
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(log_file.absolute()) 
               for h in wpm_logger.handlers):
        wpm_logger.addHandler(file_handler)


def parse_args() -> argparse.Namespace:
    """Parse and validate command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="WPM Command-Line Utility for Portfolio Management"
    )
    parser.add_argument(
        "command",
        choices=["import"],
        help="Command to execute (currently only 'import' is supported)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD) for historical portfolio import. "
             "Only trades on or before this date will be included.",
    )

    return parser.parse_args()


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


def format_currency(value: float) -> str:
    """Format currency value with $ prefix and 2 decimal places.

    Args:
        value: Currency value to format

    Returns:
        Formatted string (e.g., "$1,234.56")
    """
    return f"${value:,.2f}"


def format_unrealized_pnl(value: float) -> str:
    """Format unrealized P/L with + prefix for profit, - for loss.

    Args:
        value: Unrealized P/L value to format

    Returns:
        Formatted string with sign prefix (e.g., "+$1,234.56" or "-$1,234.56")
    """
    if value >= 0:
        return f"+{format_currency(value)}"
    else:
        # value is negative, format_currency will handle the - sign
        return format_currency(value)


def format_quantity(value) -> str:
    """Format quantity value appropriately.

    Handles Decimal and float values, rounding to 8 decimal places
    (standard for crypto precision) and removes trailing zeros.

    Args:
        value: Quantity value to format (Decimal or float)

    Returns:
        Formatted string (integer if whole number, decimal otherwise)
    """
    # Convert Decimal to float for formatting
    if isinstance(value, Decimal):
        float_value = float(value)
    else:
        float_value = float(value)
    
    # Round to 8 decimal places to handle floating point precision issues
    rounded = round(float_value, 8)
    
    # If it's effectively a whole number after rounding, return as integer
    if abs(rounded - round(rounded)) < 1e-10:
        return str(int(round(rounded)))
    
    # Format with up to 8 decimal places and strip trailing zeros
    formatted = f"{rounded:.8f}".rstrip('0').rstrip('.')
    return formatted


def parse_up_to_date(args: List[str]) -> tuple[Optional[date], List[str]]:
    """Parse --up-to date argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (up_to_date or None, remaining args without --up-to flag and date)
    """
    up_to_date = None
    remaining_args = []
    i = 0
    while i < len(args):
        if args[i] == "--up-to" and i + 1 < len(args):
            try:
                up_to_date = normalize_date(args[i + 1])
                i += 2  # Skip both --up-to and the date
            except ValueError:
                # Invalid date format, keep the --up-to flag in remaining args
                remaining_args.append(args[i])
                i += 1
        else:
            remaining_args.append(args[i])
            i += 1
    return up_to_date, remaining_args


def parse_from_date(args: List[str]) -> tuple[Optional[date], List[str]]:
    """Parse --from date argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (from_date or None, remaining args without --from flag and date)
    """
    from_date = None
    remaining_args = []
    i = 0
    while i < len(args):
        if args[i] == "--from" and i + 1 < len(args):
            try:
                from_date = normalize_date(args[i + 1])
                i += 2  # Skip both --from and the date
            except ValueError:
                # Invalid date format, keep the --from flag in remaining args
                remaining_args.append(args[i])
                i += 1
        else:
            remaining_args.append(args[i])
            i += 1
    return from_date, remaining_args


def parse_brokers(args: List[str]) -> tuple[Optional[List[str]], List[str]]:
    """Parse --brokers argument from command args.

    Args:
        args: Command arguments list

    Returns:
        Tuple of (brokers list or None, remaining args without --brokers flag and value)
    """
    brokers = None
    remaining_args = []
    i = 0
    while i < len(args):
        if args[i] == "--brokers" and i + 1 < len(args):
            brokers_str = args[i + 1]
            # Strip outer quotes if present (handles "broker1,broker2" format)
            if brokers_str.startswith('"') and brokers_str.endswith('"'):
                brokers_str = brokers_str[1:-1]
            elif brokers_str.startswith("'") and brokers_str.endswith("'"):
                brokers_str = brokers_str[1:-1]
            # Split by comma and strip whitespace from each broker name
            brokers = [broker.strip() for broker in brokers_str.split(",") if broker.strip()]
            # If empty list after stripping, set to None
            if not brokers:
                brokers = None
            i += 2  # Skip both --brokers and the value
        else:
            remaining_args.append(args[i])
            i += 1
    return brokers, remaining_args


def _display_weekly_summary(history_points: List[PortfolioHistoryPoint]) -> None:
    """Display weekly performance summary from history points.

    Groups history points by calendar week (Monday-Sunday) and displays
    weekly totals (date range and total_market_value).

    Args:
        history_points: List of PortfolioHistoryPoint objects to summarize
    """
    if not history_points:
        print("No history points to display.")
        return

    # Group history points by calendar week
    # Week starts on Monday (weekday 0) and ends on Sunday (weekday 6)
    weekly_groups: Dict[date, List[PortfolioHistoryPoint]] = defaultdict(list)

    for point in history_points:
        # Calculate the Monday of the week for this date
        # weekday() returns 0 for Monday, 6 for Sunday
        days_since_monday = point.date.weekday()
        week_start = point.date - timedelta(days=days_since_monday)
        weekly_groups[week_start].append(point)

    # Sort weeks by start date
    sorted_weeks = sorted(weekly_groups.items())

    print("Weekly Performance Summary:")
    print()  # Blank line

    for week_start, week_points in sorted_weeks:
        # Get week end (Sunday)
        week_end = week_start + timedelta(days=6)

        # Sort points within week by date
        week_points.sort(key=lambda p: p.date)

        # Display week range and total market value with percentage return
        # Use the last day's value for the week (or average if preferred)
        # For simplicity, use the last day's value in the week
        last_point = week_points[-1]
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")

        # Format percentage return with 2 decimal places and + sign for positive returns
        percentage_str = f"{last_point.percentage_return:+.2f}%"
        print(
            f"Week of {week_start_str} to {week_end_str}: "
            f"{format_currency(last_point.total_market_value)} ({percentage_str})"
        )


def format_position_line(
    position: Position,
    price: Optional[float],
    is_historical: bool = False,
    end_date: Optional[date] = None,
    allocation: Optional[Decimal] = None,
) -> str:
    """Format a position line for display.

    Args:
        position: Position to format
        price: Current or historical price (None if unavailable)
        is_historical: Whether this is a historical portfolio
        end_date: End date for historical portfolios (used in label)
        allocation: Optional allocation percentage (Decimal, None if unavailable)

    Returns:
        Formatted position line
    """
    asset = position.asset
    ticker = asset.ticker
    asset_type = asset.asset_type
    quantity = format_quantity(position.quantity)
    avg_cost = format_currency(position.get_average_cost())
    cost_basis = format_currency(position.cost_basis)

    # Determine value label
    if is_historical and end_date is not None:
        value_label = f"Historical Value ({end_date.strftime('%Y-%m-%d')})"
    else:
        value_label = "Current Value"

    # Format allocation if available
    allocation_str = ""
    if allocation is not None and price is not None:
        allocation_str = f" | Allocation: {allocation:.2f}%"

    if price is not None:
        # Convert Decimal quantity to float for market value calculation
        market_value = float(position.quantity) * price
        market_value_str = format_currency(market_value)
        price_str = format_currency(price)
        return (
            f"{ticker} ({asset_type}): {quantity} @ {avg_cost} = {cost_basis} | "
            f"{value_label} = {market_value_str} @ {price_str}{allocation_str}"
        )

    return (
        f"{ticker} ({asset_type}): {quantity} @ {avg_cost} = {cost_basis} | "
        f"{value_label} = N/A"
    )


def format_historical_asset_line(
    history_point: PortfolioHistoryPoint,
    ticker: str,
    asset_type: str,
    allocation: Optional[Decimal] = None,
    percentage_return: Optional[float] = None,
) -> str:
    """Format a simplified line for historical asset positions.

    Args:
        history_point: History point containing position and price data
        ticker: Asset ticker symbol
        asset_type: Asset type (e.g., "Stock", "ETF", "Crypto")
        allocation: Optional allocation percentage (Decimal, None if unavailable)
        percentage_return: Optional percentage return for this asset (float, None if unavailable)

    Returns:
        Formatted string: YYYY-MM-DD: Ticker (Asset Type): Quantity = Position Value @ Price | Allocation: XX.XX% | Return: XX.XX%
    """
    date_str = history_point.date.strftime("%Y-%m-%d")
    position_value = history_point.asset_positions.get(ticker, 0.0)
    position_value_str = format_currency(position_value)
    price = history_point.prices.get(ticker)
    quantity = history_point.quantities.get(ticker)

    # Format quantity
    if quantity is not None:
        quantity_str = format_quantity(Decimal(str(quantity)))
    else:
        quantity_str = "N/A"

    # Format allocation if available
    allocation_str = ""
    if allocation is not None:
        allocation_str = f" | Allocation: {allocation:.2f}%"

    # Format percentage return if available
    return_str = ""
    if percentage_return is not None:
        return_str = f" | Return: {percentage_return:.2f}%"

    if price is not None:
        price_str = format_currency(price)
        return f"{date_str}: {ticker} ({asset_type}): {quantity_str} = {position_value_str} @ {price_str}{allocation_str}{return_str}"

    return f"{date_str}: {ticker} ({asset_type}): {quantity_str} = {position_value_str} @ N/A{allocation_str}{return_str}"


def _format_broker_breakdown(broker_positions: Dict[str, Position]) -> None:
    """Format broker breakdown section for display.

    Args:
        broker_positions: Dictionary mapping broker names to Position objects
    """
    if not broker_positions:
        return

    print()  # Blank line before breakdown
    print("Broker Breakdown:")

    for broker, position in broker_positions.items():
        quantity = format_quantity(position.quantity)
        avg_cost = format_currency(position.get_average_cost())
        cost_basis = format_currency(position.cost_basis)
        print(f"{broker}: {quantity} @ {avg_cost} = {cost_basis}")


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
            _display_weekly_summary(history_points)
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


def calculate_unrealized_pnl_percentage(
    portfolio: Portfolio,
    price_map: Dict[Asset, Optional[float]],
    target_date: Optional[date] = None,
) -> Optional[float]:
    """Calculate unrealized P/L percentage return.
    
    Formula: (unrealized_pnl / cost_basis_of_remaining_lots) * 100
    
    Uses _calculate_percentage_return_from_lots which calculates percentage return
    from lots (unrealized P/L / cost basis).
    
    Args:
        portfolio: Portfolio to calculate percentage for
        price_map: Dictionary mapping Asset to current/historical price (None if unavailable)
        target_date: Optional date to filter trades up to (for historical calculations)
    
    Returns:
        Percentage return as float, or None if cost basis is 0 or prices unavailable
    """
    # Get all trades from portfolio
    all_trades = portfolio.get_all_trades()
    
    # Filter trades up to target_date if provided
    if target_date is not None:
        filtered_trades = [t for t in all_trades if t.date <= target_date]
    else:
        filtered_trades = all_trades
    
    if not filtered_trades:
        return None
    
    # Convert price_map (Dict[Asset, Optional[float]]) to prices_by_ticker (Dict[str, float])
    # Only include assets that have valid prices
    prices_by_ticker: Dict[str, float] = {}
    for asset, price in price_map.items():
        if price is not None:
            prices_by_ticker[asset.ticker] = price
    
    if not prices_by_ticker:
        return None
    
    # Use existing function to calculate percentage return
    try:
        percentage = _calculate_percentage_return_from_lots(
            filtered_trades, prices_by_ticker, ticker_filter=None
        )
        return percentage
    except (ValueError, ZeroDivisionError):
        return None


def calculate_realized_pnl_percentage(
    portfolio: Portfolio,
    target_date: Optional[date] = None,
) -> Optional[float]:
    """Calculate realized P/L percentage return.
    
    Formula: (realized_pnl / cost_basis_of_sold_lots) * 100
    
    Args:
        portfolio: Portfolio to calculate percentage for
        target_date: Optional date to filter trades up to (for historical calculations)
    
    Returns:
        Percentage return as float, or None if cost basis of sold lots is 0
    """
    # Get all trades from portfolio
    all_trades = portfolio.get_all_trades()
    
    # Filter trades up to target_date if provided
    if target_date is not None:
        filtered_trades = [t for t in all_trades if t.date <= target_date]
    else:
        filtered_trades = all_trades
    
    if not filtered_trades:
        return None
    
    # Calculate lots from filtered trades
    lots_by_asset = calculate_lots_from_trades(filtered_trades)
    
    # Calculate cost basis of sold lots and realized P/L
    # Since we filtered trades by target_date, the lots already only contain matched_sells up to target_date
    total_cost_basis_of_sold_lots = 0.0
    total_realized_pnl = 0.0
    
    for asset, lots in lots_by_asset.items():
        for lot in lots:
            # Calculate cost basis of sold lots: sum(purchase_price * quantity_sold) for all matched_sells
            # matched_sells are already filtered by target_date since we filtered trades before calculating lots
            for sell_trade, quantity_sold in lot.matched_sells:
                cost_basis_sold = float(quantity_sold) * lot.purchase_price
                total_cost_basis_of_sold_lots += cost_basis_sold
            
            # Get realized P/L from this lot
            # Since lots are calculated from filtered trades, get_realized_pnl() already returns filtered P/L
            realized_pnl = lot.get_realized_pnl()
            total_realized_pnl += realized_pnl
    
    # Calculate percentage return: (realized_pnl / cost_basis_of_sold_lots) * 100
    if total_cost_basis_of_sold_lots == 0:
        return None
    
    return (total_realized_pnl / total_cost_basis_of_sold_lots) * 100


def _display_totals_section(
    imported_portfolio: Portfolio,
    reference_portfolio: Optional[Portfolio],
    price_service: PriceService,
    target_date: Optional[date] = None,
) -> None:
    """Display totals section with P/Ls and percentage returns for both portfolios.
    
    Args:
        imported_portfolio: The main imported portfolio
        reference_portfolio: Optional reference portfolio (SPY buy-and-hold)
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
    
    # Calculate values for reference portfolio if available
    if reference_portfolio is not None:
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
            print("SPY Reference Portfolio:")
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
                f"Failed to calculate reference portfolio totals: {e}"
            )
            # Continue without displaying reference portfolio totals


def cmd_show_all(
    composite: CompositePortfolio,
    price_service: PriceService,
    up_to_date: Optional[date] = None,
    reference_portfolio: Optional[Portfolio] = None,
) -> None:
    """Handle 'show all' command.

    Args:
        composite: Composite portfolio
        price_service: Price service for retrieving current prices
        up_to_date: Optional date for historical portfolios to show state up to this date with weekly summary
        reference_portfolio: Optional reference portfolio for baseline comparison
    """
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
            _display_weekly_summary(history_points)
            
            # Display totals section with both portfolios
            _display_totals_section(
                imported_portfolio=composite,
                reference_portfolio=reference_portfolio,
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
        reference_portfolio=reference_portfolio,
        price_service=price_service,
        target_date=None,  # Current date for non-historical
    )


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
                composite, price_service, start_date, end_date, brokers=brokers
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

        # Filter and display history points for this ticker
        for i, history_point in enumerate(history_points):
            position_value = history_point.asset_positions.get(ticker, 0.0)
            # Skip days where asset has no position
            if position_value > 0:
                # Calculate asset-level percentage return for this date
                filtered_trades = [t for t in all_trades if t.date <= history_point.date]
                asset_price = history_point.prices.get(ticker)
                prices_dict = {ticker: asset_price} if asset_price is not None else {}

                # Calculate percentage return for this asset
                asset_percentage_return = (
                    _calculate_percentage_return_from_lots(
                        filtered_trades, prices_dict, ticker_filter=ticker
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


def format_breakdown_asset_type(breakdown: Dict[str, Dict]) -> None:
    """Format breakdown by asset type for display.

    Args:
        breakdown: Breakdown dictionary from breakdown_by_asset_type
    """
    for asset_type, data in sorted(breakdown.items()):
        quantity = format_quantity(data["total_quantity"])
        cost_basis = format_currency(data["total_cost_basis"])
        print(f"{asset_type}: {quantity} @ {cost_basis}")


def format_breakdown_ticker(breakdown: Dict[str, Position]) -> None:
    """Format breakdown by ticker for display.

    Args:
        breakdown: Breakdown dictionary from breakdown_by_ticker
    """
    for ticker, position in sorted(breakdown.items()):
        quantity = format_quantity(position.quantity)
        cost_basis = format_currency(position.cost_basis)
        print(f"{ticker}: {quantity} @ {cost_basis}")


def format_breakdown_purchase_period(breakdown: Dict[str, Dict]) -> None:
    """Format breakdown by purchase period for display.

    Args:
        breakdown: Breakdown dictionary from breakdown_by_purchase_period
    """
    for period, data in sorted(breakdown.items()):
        quantity = format_quantity(data["total_quantity"])
        cost_basis = format_currency(data["total_cost_basis"])
        print(f"{period}: {quantity} @ {cost_basis}")


def format_breakdown_broker(breakdown: Dict[str, Dict]) -> None:
    """Format breakdown by broker for display.

    Args:
        breakdown: Breakdown dictionary from breakdown_by_broker
    """
    for broker, data in sorted(breakdown.items()):
        broker_output = f"{broker}:"
        asset_details = []

        # Format per-asset quantities
        total_quantity = data["total_quantity"]
        if isinstance(total_quantity, dict):
            for ticker, qty in sorted(total_quantity.items()):
                qty_str = format_quantity(qty)
                asset_details.append(f"{ticker}: {qty_str}")

        cost_basis = format_currency(data["total_cost_basis"])

        if asset_details:
            print(f"{broker_output} {', '.join(asset_details)}, Total: {cost_basis}")
        else:
            print(f"{broker_output} Total: {cost_basis}")


def cmd_breakdown(composite: CompositePortfolio, args: List[str]) -> None:
    """Handle 'breakdown [<name>] <by>' command.

    Args:
        composite: Composite portfolio
        args: Command arguments (optional portfolio name, required breakdown type)
    """
    if len(args) < 1:
        print("Error: Breakdown type required. Valid types: asset_type, ticker, purchase_period, broker")
        return

    # Determine if first arg is portfolio name or breakdown type
    breakdown_type = args[-1]
    portfolio_name = None

    if len(args) == 2:
        # First arg is portfolio name, second is breakdown type
        portfolio_name = args[0]
        breakdown_type = args[1]

    # Get portfolio to use
    portfolio = composite
    if portfolio_name:
        sub_portfolios = composite.get_sub_portfolios()
        if portfolio_name not in sub_portfolios:
            print(f"Portfolio '{portfolio_name}' not found.")
            return
        portfolio = sub_portfolios[portfolio_name]

    # Route to appropriate breakdown function
    try:
        breakdown = _execute_breakdown(portfolio, breakdown_type)
        if breakdown is None:
            print("No data available for breakdown.")
            return

        _format_breakdown(breakdown, breakdown_type)
    except Exception as e:
        logger.error(f"Error generating breakdown: {e}", exc_info=True)
        print("No data available for breakdown.")


def _execute_breakdown(portfolio: Portfolio, breakdown_type: str) -> Optional[Dict]:
    """Execute breakdown calculation based on type.

    Args:
        portfolio: Portfolio to analyze
        breakdown_type: Type of breakdown to perform

    Returns:
        Breakdown data dictionary, or None if invalid type or no data
    """
    if breakdown_type == "asset_type":
        return breakdown_by_asset_type(portfolio)
    if breakdown_type == "ticker":
        return breakdown_by_ticker(portfolio)
    if breakdown_type == "purchase_period":
        return breakdown_by_purchase_period(portfolio, period="month")
    if breakdown_type == "broker":
        return breakdown_by_broker(portfolio)

    print(
        f"Invalid breakdown type '{breakdown_type}'. "
        f"Valid types: asset_type, ticker, purchase_period, broker"
    )
    return None


def _format_breakdown(breakdown: Dict, breakdown_type: str) -> None:
    """Format and display breakdown data.

    Args:
        breakdown: Breakdown data dictionary
        breakdown_type: Type of breakdown
    """
    if breakdown_type == "asset_type":
        format_breakdown_asset_type(breakdown)
    elif breakdown_type == "ticker":
        format_breakdown_ticker(breakdown)
    elif breakdown_type == "purchase_period":
        format_breakdown_purchase_period(breakdown)
    elif breakdown_type == "broker":
        format_breakdown_broker(breakdown)


def format_lot_line(lot: Lot, current_price: Optional[float]) -> str:
    """Format a lot line with matched sells for display.

    Args:
        lot: Lot to format
        current_price: Current price (None if unavailable)

    Returns:
        Multi-line formatted string (lot summary + matched sells if any)
    """
    # Format purchase date
    purchase_date_str = lot.purchase_date.strftime("%Y-%m-%d")
    
    # Format quantities and prices
    original_qty = format_quantity(lot.original_quantity)
    remaining_qty = format_quantity(lot.remaining_quantity)
    purchase_price_str = format_currency(lot.purchase_price)
    remaining_cost_basis = float(lot.remaining_quantity) * lot.purchase_price
    remaining_cost_basis_str = format_currency(remaining_cost_basis)
    
    # Calculate P/L
    realized_pnl = lot.get_realized_pnl()
    realized_pnl_str = format_unrealized_pnl(realized_pnl) if realized_pnl != 0.0 else format_currency(0.0)
    
    if current_price is not None:
        unrealized_pnl = lot.get_unrealized_pnl(current_price)
        total_pnl = lot.get_total_pnl(current_price)
        unrealized_pnl_str = format_unrealized_pnl(unrealized_pnl)
        total_pnl_str = format_unrealized_pnl(total_pnl)
    else:
        unrealized_pnl_str = "N/A"
        total_pnl_str = "N/A"
    
    # Build main lot line
    lot_line = (
        f"{purchase_date_str}: {original_qty} @ {purchase_price_str} | "
        f"Remaining: {remaining_qty} @ {purchase_price_str} = {remaining_cost_basis_str} | "
        f"Realized: {realized_pnl_str} | "
        f"Unrealized: {unrealized_pnl_str} | "
        f"Total: {total_pnl_str}"
    )
    
    # Add matched sells if any
    lines = [lot_line]
    if lot.matched_sells:
        # Sort matched sells by date (oldest first)
        sorted_sells = sorted(lot.matched_sells, key=lambda x: x[0].date)
        for sell_trade, quantity_sold in sorted_sells:
            sell_date_str = sell_trade.date.strftime("%Y-%m-%d")
            qty_sold_str = format_quantity(quantity_sold)
            sell_price_str = format_currency(sell_trade.price)
            lines.append(f"  Sold: {sell_date_str}, {qty_sold_str} @ {sell_price_str}")
    
    return "\n".join(lines)


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


def format_market_cap(value: Optional[float]) -> str:
    """Format market cap value for display.

    Args:
        value: Market cap value (can be None)

    Returns:
        Formatted string (e.g., "$1.23B", "$1,234.56M", or "N/A")
    """
    if value is None:
        return "N/A"
    
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    else:
        return f"${value:,.2f}"


def cmd_help() -> None:
    """Handle 'help' command.

    Displays a list of available commands and their usage.
    """
    print("Available commands:")
    print()
    print("  list portfolios")
    print("    List all sub-portfolios within the composite portfolio")
    print()
    print("  show portfolio <name> [--up-to YYYY-MM-DD]")
    print("    Show all assets in the specified sub-portfolio")
    print("    --up-to: Optional date for historical portfolios (shows weekly summary)")
    print()
    print("  show all [--up-to YYYY-MM-DD]")
    print("    Show all assets in the composite portfolio (aggregated)")
    print("    --up-to: Optional date for historical portfolios (shows weekly summary)")
    print()
    print("  show asset <ticker> [--from YYYY-MM-DD] [--brokers \"broker1,broker2,...\"]")
    print("    Show asset position for the specified ticker")
    print("    --from: Optional start date for historical portfolios")
    print("    --brokers: Optional comma-separated list of broker names to filter by")
    print()
    print("  metadata <ticker>")
    print("    Display metadata for the specified asset ticker")
    print()
    print("  lots <ticker>")
    print("    Display all lots (FIFO purchase records) for the specified ticker")
    print()
    print("  breakdown [<name>] <by>")
    print("    Show portfolio breakdown by dimension")
    print("    <by>: asset_type, ticker, purchase_period, or broker")
    print("    [<name>]: Optional sub-portfolio name")
    print()
    print("  help")
    print("    Display this help message")
    print()
    print("  quit, exit")
    print("    Exit the interactive mode")


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


def run_interactive_mode(
    composite: CompositePortfolio,
    price_service: PriceService,
    reference_portfolio: Optional[Portfolio] = None,
) -> None:
    """Run interactive command loop.

    Args:
        composite: Composite portfolio
        price_service: Price service for retrieving prices
        reference_portfolio: Optional reference portfolio for baseline comparison
    """
    print("Entering interactive mode. Type 'Quit' to exit.")
    logger.info("Entering interactive mode")
    
    # Initialize asset service for metadata commands (with price_service for retriever access)
    asset_service = AssetService(price_service=price_service)

    while True:
        try:
            user_input = input(PROMPT).strip()

            if not user_input:
                continue

            # Parse command using shlex to properly handle quoted strings
            try:
                parts = shlex.split(user_input)
            except ValueError:
                # If shlex fails (e.g., unmatched quotes), fall back to simple split
                parts = user_input.split()
            command = parts[0].lower()
            args = parts[1:]

            # Handle quit/exit (case-insensitive)
            if command in ("quit", "exit"):
                print("Exiting...")
                logger.info("Exiting interactive mode")
                sys.exit(0)

            # Route to command handlers
            if command == "list" and len(args) == 1 and args[0] == "portfolios":
                cmd_list_portfolios(composite)
            elif command == "show":
                if len(args) >= 1 and args[0] == "all":
                    # Parse --up-to argument if present
                    up_to_date, remaining_args = parse_up_to_date(args[1:])
                    if remaining_args:
                        print("Unknown arguments: 'show all' only accepts --up-to YYYY-MM-DD")
                    else:
                        cmd_show_all(composite, price_service, up_to_date, reference_portfolio)
                elif len(args) >= 2 and args[0] == "portfolio":
                    # Parse --up-to argument if present
                    portfolio_name = args[1]
                    up_to_date, remaining_args = parse_up_to_date(args[2:])
                    if remaining_args:
                        print("Unknown arguments: 'show portfolio <name>' only accepts --up-to YYYY-MM-DD")
                    else:
                        cmd_show_portfolio(composite, portfolio_name, price_service, up_to_date)
                elif len(args) >= 2 and args[0] == "asset":
                    # Parse --from and --brokers arguments if present
                    ticker = args[1]
                    # Parse --from first, then parse --brokers from remaining args
                    from_date, remaining_after_from = parse_from_date(args[2:])
                    brokers, remaining_args = parse_brokers(remaining_after_from)
                    if remaining_args:
                        print("Unknown arguments: 'show asset <ticker>' only accepts --from YYYY-MM-DD and --brokers \"broker1,broker2,...\"")
                    else:
                        if from_date is not None and not composite.is_historical:
                            print("Error: --from can only be used with historical portfolios.")
                        else:
                            cmd_show_asset(composite, ticker, price_service, from_date, brokers)
                else:
                    print("Unknown command: 'show'. Usage: 'show portfolio <name> [--up-to YYYY-MM-DD]', 'show all [--up-to YYYY-MM-DD]', or 'show asset <ticker> [--from YYYY-MM-DD] [--brokers \"broker1,broker2,...\"]'")
            elif command == "breakdown":
                cmd_breakdown(composite, args)
            elif command == "lots":
                if len(args) == 1:
                    cmd_show_lots(composite, args[0], price_service)
                else:
                    print("Error: Ticker required. Usage: lots <ticker>")
            elif command == "metadata":
                if len(args) == 1:
                    cmd_metadata(composite, args[0], asset_service)
                else:
                    print("Error: Ticker required. Usage: metadata <ticker>")
            elif command == "help":
                cmd_help()
            else:
                print(f"Unknown command: '{user_input}'. Type 'help' for available commands.")

        except EOFError:
            # Handle Ctrl+D
            print("\nExiting...")
            logger.info("Exiting interactive mode (EOF)")
            sys.exit(0)
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print("\nExiting...")
            logger.info("Exiting interactive mode (interrupt)")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error in interactive mode: {e}", exc_info=True)
            print(f"Error: {str(e)}")


def main() -> None:
    """Main entry point for wpm CLI."""
    # Initialize CLI-specific logging (directs logs to logs/wpmcli.log, suppresses stdout/stderr)
    setup_cli_logging()

    # Parse arguments
    args = parse_args()

    if args.command == "import":
        # Parse end_date if provided
        end_date: Optional[date] = None
        if args.end_date:
            try:
                end_date = normalize_date(args.end_date)
                print(f"Importing historical portfolio up to {end_date}")
                logger.info(f"Historical import requested with end_date: {end_date}")
            except ValueError as e:
                print(f"Error: Invalid end-date format: {str(e)}", file=sys.stderr)
                print("Expected format: YYYY-MM-DD", file=sys.stderr)
                logger.error(f"Invalid end-date format: {str(e)}")
                sys.exit(1)

        # Import CSV files
        try:
            composite = import_csv_files(IMPORT_DIR, end_date=end_date)
            if end_date is not None:
                print(f"Successfully created historical portfolio (end_date: {end_date})")
        except ValueError as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            logger.error(str(e))
            sys.exit(1)
        except ValidationError as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            logger.error(str(e), exc_info=True)
            sys.exit(1)

        # Fetch prices for all assets
        price_service = PriceService()
        fetch_prices_for_portfolio(composite, price_service)

        # Create SPY reference portfolio for baseline comparison
        reference_portfolio: Optional[Portfolio] = None
        try:
            spy_asset = Asset(ticker="SPY", asset_type="ETF")
            strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
            currency_service = CurrencyService()
            reference_portfolio = create_reference_portfolio(
                original_portfolio=composite,
                strategy=strategy,
                price_service=price_service,
                currency_service=currency_service,
                name="SPY Reference Portfolio",
            )
            logger.info("Successfully created SPY reference portfolio")
        except Exception as e:
            logger.warning(
                f"Failed to create SPY reference portfolio: {e}. "
                "Continuing without reference portfolio."
            )
            # Continue without reference portfolio - set to None
            reference_portfolio = None

        # Enter interactive mode
        run_interactive_mode(composite, price_service, reference_portfolio)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

