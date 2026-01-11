#!/usr/bin/env python3
"""Command-line utility for WPM (Wealth Portfolio Manager).

This utility orchestrates CSV imports, creates composite portfolios,
updates price caches, and provides an interactive command interface.
"""

import argparse
import logging
import sys
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

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
from wpm.portfolio import (
    CompositePortfolio,
    fetch_price_map,
    get_historical_performance,
    SimplePortfolio,
)
from wpm.pricing import PriceService
from wpm.utils import normalize_date, setup_logging

logger = logging.getLogger(__name__)

# Constants
IMPORT_DIR = Path("import")
PROMPT = "wpm> "


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

        # Display week range and total market value
        # Use the last day's value for the week (or average if preferred)
        # For simplicity, use the last day's value in the week
        last_point = week_points[-1]
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")

        print(
            f"Week of {week_start_str} to {week_end_str}: "
            f"{format_currency(last_point.total_market_value)}"
        )


def format_position_line(
    position: Position,
    price: Optional[float],
    is_historical: bool = False,
    end_date: Optional[date] = None,
) -> str:
    """Format a position line for display.

    Args:
        position: Position to format
        price: Current or historical price (None if unavailable)
        is_historical: Whether this is a historical portfolio
        end_date: End date for historical portfolios (used in label)

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

    if price is not None:
        # Convert Decimal quantity to float for market value calculation
        market_value = float(position.quantity) * price
        market_value_str = format_currency(market_value)
        price_str = format_currency(price)
        return (
            f"{ticker} ({asset_type}): {quantity} @ {avg_cost} = {cost_basis} | "
            f"{value_label} = {market_value_str} @ {price_str}"
        )

    return (
        f"{ticker} ({asset_type}): {quantity} @ {avg_cost} = {cost_basis} | "
        f"{value_label} = N/A"
    )


def cmd_list_portfolios(composite: CompositePortfolio) -> None:
    """Handle 'list portfolios' command.

    Args:
        composite: Composite portfolio containing sub-portfolios
    """
    sub_portfolios = composite._sub_portfolios

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
    sub_portfolios = composite._sub_portfolios

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

    # Sort positions by ticker and display
    sorted_positions = sorted(positions.items(), key=lambda x: x[0].ticker)
    for asset, position in sorted_positions:
        price = price_map.get(asset)
        print(format_position_line(position, price, portfolio.is_historical, portfolio.end_date))

    # Display summary
    print()  # Blank line before summary
    total_cost_basis = portfolio.get_total_cost_basis()
    total_market_value = portfolio.get_total_market_value(price_map)
    total_unrealized_pnl = portfolio.get_total_unrealized_pnl(price_map)

    # Check if we have any prices available
    has_prices = any(price is not None for price in price_map.values())

    print(f"Total Market Value: {format_currency(total_market_value) if has_prices else 'N/A'}")
    print(f"Total Cost Basis: {format_currency(total_cost_basis)}")
    if has_prices:
        print(f"Total Unrealized P/L: {format_unrealized_pnl(total_unrealized_pnl)}")
    else:
        print("Total Unrealized P/L: N/A")


def cmd_show_all(
    composite: CompositePortfolio,
    price_service: PriceService,
    up_to_date: Optional[date] = None,
) -> None:
    """Handle 'show all' command.

    Args:
        composite: Composite portfolio
        price_service: Price service for retrieving current prices
        up_to_date: Optional date for historical portfolios to show state up to this date with weekly summary
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

    # Sort positions by ticker and display
    sorted_positions = sorted(positions.items(), key=lambda x: x[0].ticker)
    for asset, position in sorted_positions:
        price = price_map.get(asset)
        print(format_position_line(position, price, composite.is_historical, composite.end_date))

    # Display summary
    print()  # Blank line before summary
    total_cost_basis = composite.get_total_cost_basis()
    total_market_value = composite.get_total_market_value(price_map)
    total_unrealized_pnl = composite.get_total_unrealized_pnl(price_map)

    # Check if we have any prices available
    has_prices = any(price is not None for price in price_map.values())

    print(f"Total Market Value: {format_currency(total_market_value) if has_prices else 'N/A'}")
    print(f"Total Cost Basis: {format_currency(total_cost_basis)}")
    if has_prices:
        print(f"Total Unrealized P/L: {format_unrealized_pnl(total_unrealized_pnl)}")
    else:
        print("Total Unrealized P/L: N/A")


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
        sub_portfolios = composite._sub_portfolios
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


def run_interactive_mode(
    composite: CompositePortfolio, price_service: PriceService
) -> None:
    """Run interactive command loop.

    Args:
        composite: Composite portfolio
        price_service: Price service for retrieving prices
    """
    print("Entering interactive mode. Type 'Quit' to exit.")
    logger.info("Entering interactive mode")

    while True:
        try:
            user_input = input(PROMPT).strip()

            if not user_input:
                continue

            # Parse command
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
                        cmd_show_all(composite, price_service, up_to_date)
                elif len(args) >= 2 and args[0] == "portfolio":
                    # Parse --up-to argument if present
                    portfolio_name = args[1]
                    up_to_date, remaining_args = parse_up_to_date(args[2:])
                    if remaining_args:
                        print("Unknown arguments: 'show portfolio <name>' only accepts --up-to YYYY-MM-DD")
                    else:
                        cmd_show_portfolio(composite, portfolio_name, price_service, up_to_date)
                else:
                    print("Unknown command: 'show'. Usage: 'show portfolio <name> [--up-to YYYY-MM-DD]' or 'show all [--up-to YYYY-MM-DD]'")
            elif command == "breakdown":
                cmd_breakdown(composite, args)
            elif command == "lots":
                if len(args) == 1:
                    cmd_show_lots(composite, args[0], price_service)
                else:
                    print("Error: Ticker required. Usage: lots <ticker>")
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
    # Initialize logging
    setup_logging()

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

        # Enter interactive mode
        run_interactive_mode(composite, price_service)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

