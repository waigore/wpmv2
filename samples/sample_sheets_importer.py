"""Google Sheets import functionality for WPM.

This module provides parallel import functionality to CSV imports,
but sources data from Google Sheets instead of files.
"""

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

import pandas as pd

from wpm.currency import CurrencyService
from wpm.importer import parse_trade_row, validate_csv_structure
from wpm.models import Trade, ValidationError
from wpm.portfolio import CompositePortfolio, SimplePortfolio

logger = logging.getLogger(__name__)

# Google Sheets API scope for read-only access
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def _get_sheets_service(credentials_path: Optional[str] = None):
    """Create and return a Google Sheets API service instance.
    
    Args:
        credentials_path: Path to service account JSON key file.
            If None, uses GOOGLE_SHEETS_CREDENTIALS_PATH from environment.
    
    Returns:
        Google Sheets API service instance
    
    Raises:
        ValidationError: If credentials file not found or invalid
        ImportError: If google-api-python-client not installed
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:
        raise ImportError(
            "Google Sheets support requires 'google-api-python-client' and "
            "'google-auth'. Install with: pip install google-api-python-client google-auth"
        ) from e
    
    # Get credentials path
    creds_path = credentials_path
    if creds_path is None:
        from wpm.config import Config
        creds_path = Config.GOOGLE_SHEETS_CREDENTIALS_PATH
    
    if not creds_path:
        raise ValidationError(
            "Google Sheets credentials path not configured. "
            "Set GOOGLE_SHEETS_CREDENTIALS_PATH environment variable "
            "or pass credentials_path parameter."
        )
    
    creds_path = Path(creds_path)
    if not creds_path.exists():
        raise ValidationError(
            f"Google Sheets credentials file not found: {creds_path}"
        )
    
    # Create credentials and service
    credentials = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=SCOPES
    )
    
    return build('sheets', 'v4', credentials=credentials)


def _sheet_to_dataframe(service, spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
    """Fetch a sheet from Google Sheets and convert to pandas DataFrame.
    
    Args:
        service: Google Sheets API service instance
        spreadsheet_id: The spreadsheet ID (from URL)
        sheet_name: Name of the sheet tab to fetch
    
    Returns:
        DataFrame with sheet data (first row as headers)
    
    Raises:
        ValidationError: If sheet is empty or not found
    """
    # Fetch all columns (A to Z should be sufficient)
    range_name = f"{sheet_name}!A:Z"
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
    except Exception as e:
        raise ValidationError(f"Error fetching sheet '{sheet_name}': {e}") from e
    
    values = result.get('values', [])
    
    if not values:
        raise ValidationError(f"Sheet '{sheet_name}' is empty or not found")
    
    if len(values) < 2:
        raise ValidationError(f"Sheet '{sheet_name}' has headers but no data")
    
    # First row is headers, rest is data
    headers = values[0]
    data = values[1:]
    
    # Create DataFrame
    df = pd.DataFrame(data, columns=headers)
    
    logger.debug(f"Fetched {len(df)} rows from sheet '{sheet_name}'")
    return df


def import_trades_from_sheet(
    spreadsheet_id: str,
    sheet_name: str,
    credentials_path: Optional[str] = None,
    currency_service: Optional[CurrencyService] = None,
    end_date: Optional[date] = None
) -> List[Trade]:
    """Import trades from a single Google Sheet.
    
    This function mirrors import_trades_from_csv() but sources data from
    Google Sheets instead of a CSV file. It uses the same validation and
    parsing logic.
    
    Args:
        spreadsheet_id: Google Sheets spreadsheet ID (from URL)
        sheet_name: Name of the sheet tab containing trades
        credentials_path: Path to service account JSON key file (optional)
        currency_service: CurrencyService for FX conversion (optional)
        end_date: If provided, only import trades on or before this date
    
    Returns:
        List of Trade objects
    
    Raises:
        ValidationError: If sheet structure is invalid or data cannot be parsed
        ImportError: If Google API libraries not installed
    
    Example:
        >>> trades = import_trades_from_sheet(
        ...     spreadsheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
        ...     sheet_name="IBKR_Trades"
        ... )
    """
    logger.info(
        f"Importing from sheet '{sheet_name}' "
        f"in spreadsheet '{spreadsheet_id}'"
    )
    
    if end_date is not None:
        logger.info(f"Filtering trades up to end date: {end_date}")
    
    # Get service and fetch data
    service = _get_sheets_service(credentials_path)
    df = _sheet_to_dataframe(service, spreadsheet_id, sheet_name)
    
    logger.info(f"Loaded {len(df)} rows from sheet")
    
    # Validate structure (same as CSV)
    validate_csv_structure(df)
    logger.debug("Sheet structure validation passed")
    
    # Parse trades
    if currency_service is None:
        currency_service = CurrencyService()
    
    trades: List[Trade] = []
    errors: List[str] = []
    
    for idx, row in df.iterrows():
        try:
            trade = parse_trade_row(row, currency_service)
            
            # Filter by end_date if provided
            if end_date is not None and trade.date > end_date:
                logger.debug(
                    f"Skipping trade on {trade.date} (after end_date {end_date})"
                )
                continue
            
            trades.append(trade)
        except ValidationError as e:
            error_msg = f"Row {idx + 1}: {str(e)}"
            errors.append(error_msg)
            logger.warning(error_msg)
    
    if errors:
        logger.warning(f"Encountered {len(errors)} validation errors during import")
    
    logger.info(f"Sheet import completed. Successfully imported {len(trades)} trades")
    
    if end_date is not None:
        logger.info(f"Filtered to {len(trades)} trades on or before {end_date}")
    
    if not trades and errors:
        error_summary = "\n".join(errors)
        raise ValidationError(
            f"No valid trades found in sheet. Errors:\n{error_summary}"
        )
    
    return trades


def list_sheet_names(
    spreadsheet_id: str,
    credentials_path: Optional[str] = None
) -> List[str]:
    """List all sheet names in a Google Sheets workbook.
    
    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        credentials_path: Path to service account JSON key file (optional)
    
    Returns:
        List of sheet names (tabs) in the workbook
    
    Raises:
        ValidationError: If API call fails
    """
    service = _get_sheets_service(credentials_path)
    
    try:
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()
    except Exception as e:
        raise ValidationError(f"Error fetching spreadsheet: {e}") from e
    
    sheet_names = [
        sheet['properties']['title'] 
        for sheet in spreadsheet['sheets']
    ]
    
    logger.debug(f"Found sheets: {sheet_names}")
    return sheet_names


def import_sheets_workbook(
    spreadsheet_id: str,
    credentials_path: Optional[str] = None,
    sheet_filter: Optional[List[str]] = None,
    end_date: Optional[date] = None
) -> CompositePortfolio:
    """Import all sheets from a Google Sheets workbook as portfolios.
    
    Each sheet in the workbook becomes a SimplePortfolio (named after the sheet),
    and all sheets are aggregated into a CompositePortfolio. This mirrors the
    behavior of import_csv_files() but for Google Sheets.
    
    Args:
        spreadsheet_id: Google Sheets spreadsheet ID (from URL)
        credentials_path: Path to service account JSON key file (optional)
        sheet_filter: If provided, only import these sheet names
        end_date: If provided, only import trades on or before this date,
                 and mark portfolios as historical
    
    Returns:
        CompositePortfolio containing all imported sheets as sub-portfolios
    
    Raises:
        ValidationError: If no sheets found or import fails
        ImportError: If Google API libraries not installed
    
    Example:
        >>> portfolio = import_sheets_workbook(
        ...     spreadsheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        ... )
        >>> print(portfolio.name)  # "Composite"
        >>> print(len(portfolio.sub_portfolios))  # Number of sheets
    """
    logger.info(f"Scanning workbook: {spreadsheet_id}")
    
    if end_date is not None:
        logger.info(f"Importing historical portfolio up to {end_date}")
    
    # Get list of sheets
    sheet_names = list_sheet_names(spreadsheet_id, credentials_path)
    
    if not sheet_names:
        raise ValidationError(f"No sheets found in spreadsheet '{spreadsheet_id}'")
    
    # Apply filter if provided
    if sheet_filter:
        sheet_names = [s for s in sheet_names if s in sheet_filter]
        if not sheet_names:
            raise ValidationError(
                f"None of the specified sheets found in workbook. "
                f"Available: {', '.join(list_sheet_names(spreadsheet_id, credentials_path))}"
            )
    
    logger.info(f"Found {len(sheet_names)} sheet(s): {', '.join(sheet_names)}")
    
    # Create composite portfolio
    is_historical = end_date is not None
    composite = CompositePortfolio("Composite", is_historical=is_historical)
    
    currency_service = CurrencyService()
    
    for sheet_name in sheet_names:
        logger.info(f"Processing sheet: {sheet_name}")
        
        try:
            trades = import_trades_from_sheet(
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                credentials_path=credentials_path,
                currency_service=currency_service,
                end_date=end_date
            )
            
            # Create portfolio for this sheet
            portfolio = SimplePortfolio(sheet_name, is_historical=is_historical)
            for trade in trades:
                portfolio.add_trade(trade)
            
            composite.add_sub_portfolio(portfolio)
            logger.info(
                f"Successfully imported {len(trades)} trades into "
                f"portfolio '{sheet_name}'"
            )
            
        except ValidationError as e:
            logger.error(f"Failed to import sheet '{sheet_name}': {e}")
            raise
    
    logger.info(
        f"Successfully created composite portfolio with "
        f"{len(sheet_names)} sub-portfolio(s)"
    )
    return composite


# Convenience function for single-sheet import
def import_sheet_as_portfolio(
    spreadsheet_id: str,
    sheet_name: str,
    credentials_path: Optional[str] = None,
    end_date: Optional[date] = None
) -> SimplePortfolio:
    """Import a single sheet as a SimplePortfolio.
    
    Convenience function for when you only need to import one sheet.
    
    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        sheet_name: Name of the sheet tab
        credentials_path: Path to service account JSON key file (optional)
        end_date: If provided, only import trades on or before this date
    
    Returns:
        SimplePortfolio containing trades from the sheet
    """
    trades = import_trades_from_sheet(
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        credentials_path=credentials_path,
        end_date=end_date
    )
    
    is_historical = end_date is not None
    portfolio = SimplePortfolio(sheet_name, is_historical=is_historical)
    
    for trade in trades:
        portfolio.add_trade(trade)
    
    return portfolio
