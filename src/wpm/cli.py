#!/usr/bin/env python3
"""Command-line utility for WPM (Wealth Portfolio Manager).

This utility orchestrates CSV imports, creates composite portfolios,
updates price caches, and provides an interactive command interface.
"""

import argparse
import logging
import sys
from collections import defaultdict
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
from wpm.models import Asset, Portfolio, Position, ValidationError
from wpm.portfolio import CompositePortfolio, fetch_price_map, SimplePortfolio
from wpm.pricing import PriceService
from wpm.utils import setup_logging

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

    return parser.parse_args()


def fetch_prices_for_portfolio(
    portfolio: CompositePortfolio, price_service: PriceService
) -> None:
    """Fetch prices for all assets in portfolio via PriceService.

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

    logger.info(f"Fetching prices for {len(assets)} assets...")

    # Use helper function to fetch prices
    price_map = fetch_price_map(portfolio, price_service)

    # Check for any missing prices and exit if found (this function requires all prices)
    missing_prices = [asset for asset, price in price_map.items() if price is None]
    if not missing_prices:
        # Display summary
        total = len(assets)
        summary = f"Prices fetched for {total} assets"
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
    error_msg = (
        f"Error: No price data available for: {', '.join(error_parts)}. "
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


def format_position_line(position: Position, price: Optional[float]) -> str:
    """Format a position line for display.

    Args:
        position: Position to format
        price: Current price (None if unavailable)

    Returns:
        Formatted position line
    """
    asset = position.asset
    ticker = asset.ticker
    asset_type = asset.asset_type
    quantity = format_quantity(position.quantity)
    avg_cost = format_currency(position.get_average_cost())
    cost_basis = format_currency(position.cost_basis)

    if price is not None:
        # Convert Decimal quantity to float for market value calculation
        market_value = float(position.quantity) * price
        current_value_str = format_currency(market_value)
        return (
            f"{ticker} ({asset_type}): {quantity} @ {avg_cost} = {cost_basis} | "
            f"Current Value = {current_value_str}"
        )

    return (
        f"{ticker} ({asset_type}): {quantity} @ {avg_cost} = {cost_basis} | "
        f"Current Value = N/A"
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
    composite: CompositePortfolio, name: str, price_service: PriceService
) -> None:
    """Handle 'show portfolio <name>' command.

    Args:
        composite: Composite portfolio containing sub-portfolios
        name: Name of sub-portfolio to show
        price_service: Price service for retrieving current prices
    """
    sub_portfolios = composite._sub_portfolios

    if name not in sub_portfolios:
        print(f"Portfolio '{name}' not found.")
        return

    portfolio = sub_portfolios[name]
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
        print(format_position_line(position, price))

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
    composite: CompositePortfolio, price_service: PriceService
) -> None:
    """Handle 'show all' command.

    Args:
        composite: Composite portfolio
        price_service: Price service for retrieving current prices
    """
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
        print(format_position_line(position, price))

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
                if len(args) == 1 and args[0] == "all":
                    cmd_show_all(composite, price_service)
                elif len(args) == 2 and args[0] == "portfolio":
                    cmd_show_portfolio(composite, args[1], price_service)
                else:
                    print("Unknown command: 'show'. Usage: 'show portfolio <name>' or 'show all'")
            elif command == "breakdown":
                cmd_breakdown(composite, args)
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
        # Import CSV files
        try:
            composite = import_csv_files(IMPORT_DIR)
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

