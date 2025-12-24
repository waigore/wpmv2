#!/usr/bin/env python3
"""Command-line utility for WPM (Wealth Portfolio Manager).

This utility orchestrates CSV imports, creates composite portfolios,
updates price caches, and provides an interactive command interface.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from wpm.importer import import_trades_from_csv
from wpm.metrics import (
    breakdown_by_asset_type,
    breakdown_by_broker,
    breakdown_by_purchase_period,
    breakdown_by_ticker,
)
from wpm.models import Asset, Position
from wpm.portfolio import CompositePortfolio, SimplePortfolio
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


def extract_portfolio_name(filename: str, existing_names: Set[str]) -> str:
    """Extract and normalize portfolio name from CSV filename.

    Args:
        filename: CSV filename (with or without .csv extension)
        existing_names: Set of already used portfolio names

    Returns:
        Normalized portfolio name (whitespace stripped, duplicates handled)

    Raises:
        ValueError: If resulting name is empty
    """
    # Remove .csv extension
    name = filename
    if name.lower().endswith(".csv"):
        name = name[:-4]

    # Extract portion after last dash/hyphen if present
    if "-" in name:
        name = name.rsplit("-", 1)[-1]

    # Strip ALL whitespace (leading, trailing, internal)
    name = "".join(name.split())

    if not name:
        raise ValueError(f"Portfolio name cannot be empty after extraction from '{filename}'")

    # Handle duplicates by appending numeric suffix
    base_name = name
    counter = 1
    while name in existing_names:
        name = f"{base_name}_{counter}"
        counter += 1

    return name


def import_csv_files(import_dir: Path) -> CompositePortfolio:
    """Import CSV files and create composite portfolio.

    Args:
        import_dir: Directory containing CSV files

    Returns:
        CompositePortfolio containing all imported sub-portfolios

    Raises:
        SystemExit: If no CSV files found or any import fails
    """
    logger.info(f"Scanning directory for CSV files: {import_dir}")

    csv_files = sorted(import_dir.glob("*.csv"))

    if not csv_files:
        print(f"Error: No CSV files found in '{import_dir}' directory", file=sys.stderr)
        logger.error(f"No CSV files found in {import_dir}")
        sys.exit(1)

    logger.info(f"Found {len(csv_files)} CSV file(s)")

    composite = CompositePortfolio("Composite")
    existing_names: Set[str] = set()

    for csv_file in csv_files:
        logger.info(f"Processing CSV file: {csv_file}")

        try:
            # Extract portfolio name
            portfolio_name = extract_portfolio_name(csv_file.name, existing_names)
            existing_names.add(portfolio_name)

            # Import trades
            trades = import_trades_from_csv(str(csv_file))

            # Create portfolio and add trades
            portfolio = SimplePortfolio(portfolio_name)
            for trade in trades:
                portfolio.add_trade(trade)

            # Add to composite
            composite.add_sub_portfolio(portfolio)
            logger.info(f"Successfully imported {len(trades)} trades into portfolio '{portfolio_name}'")

        except Exception as e:
            error_msg = f"Error importing CSV file '{csv_file}': {str(e)}"
            print(error_msg, file=sys.stderr)
            logger.error(error_msg, exc_info=True)
            sys.exit(1)

    logger.info(f"Successfully created composite portfolio with {len(existing_names)} sub-portfolio(s)")
    return composite


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

    # Group assets by asset_type for batch processing
    assets_by_type: Dict[str, List[str]] = {}
    for asset in assets:
        asset_type = asset.asset_type
        if asset_type not in assets_by_type:
            assets_by_type[asset_type] = []
        assets_by_type[asset_type].append(asset.ticker)

    # Batch fetch prices for each asset type
    for asset_type, tickers in assets_by_type.items():
        try:
            # PriceService.get_prices() handles cache checking, API fetching,
            # and stale cache fallback internally
            prices = price_service.get_prices(tickers, asset_type)
            logger.info(
                f"Successfully retrieved prices for {len(prices)} {asset_type} assets"
            )
        except ValueError as e:
            # ValueError is raised when no price data exists (no API response and no cache)
            error_msg = f"Error: {str(e)}"
            print(error_msg, file=sys.stderr)
            logger.error(error_msg)
            sys.exit(1)

    # Display summary
    total = len(assets)
    summary = f"Prices fetched for {total} assets"
    print(summary)
    logger.info(summary)


def format_currency(value: float) -> str:
    """Format currency value with $ prefix and 2 decimal places.

    Args:
        value: Currency value to format

    Returns:
        Formatted string (e.g., "$1,234.56")
    """
    return f"${value:,.2f}"


def format_quantity(value) -> str:
    """Format quantity value appropriately.

    Handles Decimal and float values, rounding to 8 decimal places
    (standard for crypto precision) and removes trailing zeros.

    Args:
        value: Quantity value to format (Decimal or float)

    Returns:
        Formatted string (integer if whole number, decimal otherwise)
    """
    from decimal import Decimal
    
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

    # Group assets by asset_type for batch price retrieval
    assets_by_type: Dict[str, List[Asset]] = {}
    for asset in positions.keys():
        asset_type = asset.asset_type
        if asset_type not in assets_by_type:
            assets_by_type[asset_type] = []
        assets_by_type[asset_type].append(asset)

    # Fetch prices in batches by asset type
    price_map: Dict[Asset, Optional[float]] = {}
    for asset_type, asset_list in assets_by_type.items():
        tickers = [asset.ticker for asset in asset_list]
        try:
            prices = price_service.get_prices(tickers, asset_type)
            # Map tickers back to assets
            for asset in asset_list:
                price_map[asset] = prices.get(asset.ticker)
        except Exception as e:
            logger.warning(
                f"Price retrieval failed for {asset_type} assets: {e}"
            )
            # Set None for all assets of this type
            for asset in asset_list:
                price_map[asset] = None

    # Sort positions by ticker and display
    sorted_positions = sorted(positions.items(), key=lambda x: x[0].ticker)
    for asset, position in sorted_positions:
        price = price_map.get(asset)
        print(format_position_line(position, price))


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

    # Group assets by asset_type for batch price retrieval
    assets_by_type: Dict[str, List[Asset]] = {}
    for asset in positions.keys():
        asset_type = asset.asset_type
        if asset_type not in assets_by_type:
            assets_by_type[asset_type] = []
        assets_by_type[asset_type].append(asset)

    # Fetch prices in batches by asset type
    price_map: Dict[Asset, Optional[float]] = {}
    for asset_type, asset_list in assets_by_type.items():
        tickers = [asset.ticker for asset in asset_list]
        try:
            prices = price_service.get_prices(tickers, asset_type)
            # Map tickers back to assets
            for asset in asset_list:
                price_map[asset] = prices.get(asset.ticker)
        except Exception as e:
            logger.warning(
                f"Price retrieval failed for {asset_type} assets: {e}"
            )
            # Set None for all assets of this type
            for asset in asset_list:
                price_map[asset] = None

    # Sort positions by ticker and display
    sorted_positions = sorted(positions.items(), key=lambda x: x[0].ticker)
    for asset, position in sorted_positions:
        price = price_map.get(asset)
        print(format_position_line(position, price))


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
        if breakdown_type == "asset_type":
            breakdown = breakdown_by_asset_type(portfolio)
            if not breakdown:
                print("No data available for breakdown.")
                return
            format_breakdown_asset_type(breakdown)
        elif breakdown_type == "ticker":
            breakdown = breakdown_by_ticker(portfolio)
            if not breakdown:
                print("No data available for breakdown.")
                return
            format_breakdown_ticker(breakdown)
        elif breakdown_type == "purchase_period":
            breakdown = breakdown_by_purchase_period(portfolio, period="month")
            if not breakdown:
                print("No data available for breakdown.")
                return
            format_breakdown_purchase_period(breakdown)
        elif breakdown_type == "broker":
            breakdown = breakdown_by_broker(portfolio)
            if not breakdown:
                print("No data available for breakdown.")
                return
            format_breakdown_broker(breakdown)
        else:
            print(
                f"Invalid breakdown type '{breakdown_type}'. "
                f"Valid types: asset_type, ticker, purchase_period, broker"
            )
    except Exception as e:
        logger.error(f"Error generating breakdown: {e}", exc_info=True)
        print("No data available for breakdown.")


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
    """Main entry point for wpmrun.py."""
    # Initialize logging
    setup_logging()

    # Parse arguments
    args = parse_args()

    if args.command == "import":
        # Import CSV files
        composite = import_csv_files(IMPORT_DIR)

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

