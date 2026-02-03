"""Main entry point for WPM CLI."""

import logging
import sys
from datetime import date
from pathlib import Path
from typing import Dict, Optional

from wpm.currency import CurrencyService
from wpm.importer import import_csv_files
from wpm.models import Asset, Portfolio, ValidationError
from wpm.pricing import PriceService
from wpm.reference.portfolio import create_reference_portfolio
from wpm.reference.strategy import BuyAndHoldStrategy
from wpm.utils import normalize_date

from .commands.portfolio import fetch_prices_for_portfolio
from .interactive import run_interactive_mode
from .logging_config import setup_cli_logging
from .args import parse_args

logger = logging.getLogger(__name__)

# Constants
IMPORT_DIR = Path("import")


def _create_reference_portfolios(composite: Portfolio, price_service: PriceService) -> Dict[str, Portfolio]:
    """Create reference portfolios (SPY and BTC-USD) for baseline comparison.
    
    Args:
        composite: The main portfolio to create references for
        price_service: PriceService instance for fetching prices
        
    Returns:
        Dictionary mapping reference portfolio names to Portfolio objects
    """
    reference_portfolios: Dict[str, Portfolio] = {}
    currency_service = CurrencyService()
    
    # Create SPY reference portfolio
    try:
        spy_asset = Asset(ticker="SPY", asset_type="ETF")
        spy_strategy = BuyAndHoldStrategy(reference_asset=spy_asset)
        spy_reference = create_reference_portfolio(
            original_portfolio=composite,
            strategy=spy_strategy,
            price_service=price_service,
            currency_service=currency_service,
            name="SPY Reference Portfolio",
        )
        reference_portfolios["SPY Reference Portfolio"] = spy_reference
        logger.info("Successfully created SPY reference portfolio")
    except Exception as e:
        logger.warning(
            f"Failed to create SPY reference portfolio: {e}. "
            "Continuing without SPY reference portfolio."
        )
    
    # Create BTC-USD reference portfolio
    try:
        btc_asset = Asset(ticker="BTC-USD", asset_type="Crypto")
        btc_strategy = BuyAndHoldStrategy(reference_asset=btc_asset)
        btc_reference = create_reference_portfolio(
            original_portfolio=composite,
            strategy=btc_strategy,
            price_service=price_service,
            currency_service=currency_service,
            name="BTC-USD Reference Portfolio",
        )
        reference_portfolios["BTC-USD Reference Portfolio"] = btc_reference
        logger.info("Successfully created BTC-USD reference portfolio")
    except Exception as e:
        logger.warning(
            f"Failed to create BTC-USD reference portfolio: {e}. "
            "Continuing without BTC-USD reference portfolio."
        )
    
    return reference_portfolios


def _handle_import_sheets(args) -> None:
    """Handle 'import-sheets' command."""
    from wpm.config import Config
    from wpm.sheets_importer import (
        import_sheets_workbook,
        resolve_spreadsheet_id,
        ValidationError as SheetsValidationError,
    )

    # Check credentials configuration (required)
    if not Config.GOOGLE_SHEETS_CREDENTIALS_PATH:
        print(
            "Error: GOOGLE_SHEETS_CREDENTIALS_PATH not configured in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check that at least one of drive path or spreadsheet ID is configured
    if not Config.GOOGLE_SHEETS_DRIVE_PATH and not Config.GOOGLE_SHEETS_SPREADSHEET_ID:
        print(
            "Error: Either GOOGLE_SHEETS_DRIVE_PATH or GOOGLE_SHEETS_SPREADSHEET_ID "
            "must be configured in .env",
            file=sys.stderr,
        )
        sys.exit(1)

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

    # Resolve to spreadsheet ID (drive path takes precedence)
    try:
        if Config.GOOGLE_SHEETS_DRIVE_PATH:
            print(f"Resolving Google Drive path: {Config.GOOGLE_SHEETS_DRIVE_PATH}")
        spreadsheet_id = resolve_spreadsheet_id(
            drive_path=Config.GOOGLE_SHEETS_DRIVE_PATH,
            spreadsheet_id=Config.GOOGLE_SHEETS_SPREADSHEET_ID,
            credentials_path=Config.GOOGLE_SHEETS_CREDENTIALS_PATH,
        )
        print(f"Using spreadsheet: {spreadsheet_id}")
    except SheetsValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Import ALL sheets from the spreadsheet (fail-fast: any error stops entire import)
    try:
        composite = import_sheets_workbook(
            spreadsheet_id=spreadsheet_id,
            credentials_path=Config.GOOGLE_SHEETS_CREDENTIALS_PATH,
            end_date=end_date,
        )
        print(
            f"Successfully imported {len(composite.sub_portfolios)} sheet(s) from Google Sheets"
        )
        if end_date:
            print(f"Historical portfolio (end_date: {end_date})")
    except SheetsValidationError as e:
        print(f"Import failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Fetch prices (same as CSV import)
    price_service = PriceService()
    fetch_prices_for_portfolio(composite, price_service)

    # Create reference portfolios (same as CSV import)
    reference_portfolios = _create_reference_portfolios(composite, price_service)

    # Enter interactive mode
    run_interactive_mode(composite, price_service, reference_portfolios)


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

        # Create reference portfolios for baseline comparison
        reference_portfolios = _create_reference_portfolios(composite, price_service)

        # Enter interactive mode
        run_interactive_mode(composite, price_service, reference_portfolios)

    elif args.command == "import-sheets":
        _handle_import_sheets(args)

    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(1)
