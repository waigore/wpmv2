"""Google Sheets import functionality for WPM.

This module provides parallel import functionality to CSV imports,
but sources data from Google Sheets instead of files.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from wpm.config import Config
from wpm.currency import CurrencyService
from wpm.importer import adjust_trade_for_splits, parse_trade_row, validate_csv_structure
from wpm.models import Trade, ValidationError
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.pricing.splits import SplitService
from wpm.utils import validate_asset_type

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    HAS_GOOGLE_SHEETS = True
except ImportError:
    HAS_GOOGLE_SHEETS = False
    service_account = None
    build = None

logger = logging.getLogger(__name__)

# Google Sheets API scope for read-only access
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_sheets_service(credentials_path: Optional[str] = None):
    """Create authenticated Google Sheets API service.

    Args:
        credentials_path: Path to service account JSON key file.
            If None, uses GOOGLE_SHEETS_CREDENTIALS_PATH from Config.

    Returns:
        Google Sheets API service instance

    Raises:
        ValidationError: If credentials not configured or file not found
        ImportError: If google-api-python-client not installed
    """
    if not HAS_GOOGLE_SHEETS:
        raise ImportError(
            "Google Sheets support requires 'google-api-python-client' and "
            "'google-auth'. Install with: pip install google-api-python-client google-auth"
        )

    # Get credentials path
    creds_path = credentials_path
    if creds_path is None:
        creds_path = Config.GOOGLE_SHEETS_CREDENTIALS_PATH

    if not creds_path:
        raise ValidationError(
            "Google Sheets credentials path not configured. "
            "Set GOOGLE_SHEETS_CREDENTIALS_PATH environment variable "
            "or pass credentials_path parameter."
        )

    creds_path = Path(creds_path)
    if not creds_path.exists():
        raise ValidationError(f"Credentials file not found: {creds_path}")

    # Create credentials and service
    credentials = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=SCOPES
    )

    return build("sheets", "v4", credentials=credentials)


def get_drive_service(credentials_path: Optional[str] = None):
    """Create authenticated Google Drive API service.

    Args:
        credentials_path: Path to service account JSON key file.
            If None, uses GOOGLE_SHEETS_CREDENTIALS_PATH from Config.

    Returns:
        Google Drive API service instance

    Raises:
        ValidationError: If credentials not configured or file not found
        ImportError: If google-api-python-client not installed
    """
    if not HAS_GOOGLE_SHEETS:
        raise ImportError(
            "Google Sheets support requires 'google-api-python-client' and "
            "'google-auth'. Install with: pip install google-api-python-client google-auth"
        )

    # Get credentials path
    creds_path = credentials_path
    if creds_path is None:
        creds_path = Config.GOOGLE_SHEETS_CREDENTIALS_PATH

    if not creds_path:
        raise ValidationError(
            "Google Sheets credentials path not configured. "
            "Set GOOGLE_SHEETS_CREDENTIALS_PATH environment variable "
            "or pass credentials_path parameter."
        )

    creds_path = Path(creds_path)
    if not creds_path.exists():
        raise ValidationError(f"Credentials file not found: {creds_path}")

    # Create credentials and service
    credentials = service_account.Credentials.from_service_account_file(
        str(creds_path), scopes=SCOPES
    )

    return build("drive", "v3", credentials=credentials)


def resolve_spreadsheet_id(
    drive_path: Optional[str] = None,
    spreadsheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None,
) -> str:
    """Resolve spreadsheet identifier to spreadsheet ID.

    Priority:
    1. If drive_path provided: resolve via Drive API
    2. Else if spreadsheet_id provided: return as-is
    3. Else: raise ValidationError

    Drive Path Resolution Algorithm:
    1. Parse path components (split by "/")
    2. Use Drive API to traverse folders:
       - Start from root (root)
       - For each folder name: query mimeType='application/vnd.google-apps.folder'
         and name='{folder}' and '{parent_id}' in parents
       - Track folder ID
    3. Final component: query mimeType='application/vnd.google-apps.spreadsheet'
       and name='{filename}' and '{parent_id}' in parents
    4. Return spreadsheet ID

    Args:
        drive_path: Google Drive path like "Folder/Subfolder/Filename"
        spreadsheet_id: Direct spreadsheet ID from URL
        credentials_path: Path to service account JSON key file

    Returns:
        Spreadsheet ID string

    Raises:
        ValidationError: If neither path nor ID provided, path not found,
                        multiple matches, or not a spreadsheet
    """
    # Priority 1: Drive path takes precedence
    if drive_path:
        logger.info(f"Resolving Google Drive path: {drive_path}")
        service = get_drive_service(credentials_path)

        # Parse path components
        path_parts = [p.strip() for p in drive_path.split("/") if p.strip()]
        if not path_parts:
            raise ValidationError(f"Invalid drive path: '{drive_path}'")

        # Traverse folders
        parent_id = "root"
        for i, folder_name in enumerate(path_parts[:-1]):
            query = (
                f"mimeType='application/vnd.google-apps.folder' "
                f"and name='{folder_name}' "
                f"and '{parent_id}' in parents "
                f"and trashed=false"
            )

            try:
                results = (
                    service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
                )
                items = results.get("files", [])
            except Exception as e:
                raise ValidationError(f"Error querying Drive API: {e}") from e

            if not items:
                raise ValidationError(
                    f"Folder not found: '{folder_name}' "
                    f"(in path '{drive_path}')"
                )
            if len(items) > 1:
                raise ValidationError(
                    f"Multiple folders match: '{folder_name}' "
                    f"(in path '{drive_path}')"
                )

            parent_id = items[0]["id"]
            logger.debug(f"Resolved folder '{folder_name}' -> {parent_id}")

        # Find the spreadsheet file
        filename = path_parts[-1]
        query = (
            f"mimeType='application/vnd.google-apps.spreadsheet' "
            f"and name='{filename}' "
            f"and '{parent_id}' in parents "
            f"and trashed=false"
        )

        try:
            results = (
                service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
            )
            items = results.get("files", [])
        except Exception as e:
            raise ValidationError(f"Error querying Drive API: {e}") from e

        if not items:
            raise ValidationError(
                f"Spreadsheet not found: '{filename}' " f"(in path '{drive_path}')"
            )
        if len(items) > 1:
            raise ValidationError(
                f"Multiple spreadsheets match: '{filename}' " f"(in path '{drive_path}')"
            )

        resolved_id = items[0]["id"]
        logger.info(f"Resolved path '{drive_path}' -> spreadsheet ID: {resolved_id}")
        return resolved_id

    # Priority 2: Direct spreadsheet ID
    if spreadsheet_id:
        logger.info(f"Using direct spreadsheet ID: {spreadsheet_id}")
        return spreadsheet_id

    # Priority 3: Neither provided
    raise ValidationError(
        "Either drive_path or spreadsheet_id must be provided "
        "to resolve spreadsheet"
    )


def sheet_to_dataframe(service, spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
    """Fetch sheet data via Sheets API and convert to DataFrame.

    Args:
        service: Google Sheets API service instance
        spreadsheet_id: The spreadsheet ID
        sheet_name: Name of the sheet tab to fetch

    Returns:
        DataFrame with sheet data (first row as headers)

    Raises:
        ValidationError: If sheet empty or not found
    """
    range_name = f"{sheet_name}!A:Z"

    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
    except Exception as e:
        raise ValidationError(f"Error fetching sheet '{sheet_name}': {e}") from e

    values = result.get("values", [])

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
    end_date: Optional[date] = None,
    split_service: Optional[SplitService] = None,
) -> List[Trade]:
    """Import trades from a single sheet tab.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        sheet_name: Name of the sheet tab containing trades
        credentials_path: Path to service account JSON key file (optional)
        currency_service: CurrencyService for FX conversion (optional)
        end_date: If provided, only import trades on or before this date
        split_service: Optional SplitService instance for adjusting trades for stock splits.
                      If provided, trades will be adjusted for splits that occurred after the trade date.

    Returns:
        List of Trade objects

    Raises:
        ValidationError: On structure errors or parsing failures
        ImportError: If Google API libraries not installed
    """
    logger.info(f"Importing from sheet '{sheet_name}' in spreadsheet '{spreadsheet_id}'")

    if end_date is not None:
        logger.info(f"Filtering trades up to end date: {end_date}")

    # Get service and fetch data
    service = get_sheets_service(credentials_path)
    df = sheet_to_dataframe(service, spreadsheet_id, sheet_name)

    logger.info(f"Loaded {len(df)} rows from sheet")

    # Validate structure (reuse existing CSV validation)
    validate_csv_structure(df)
    logger.debug("Sheet structure validation passed")

    # Parse trades
    if currency_service is None:
        currency_service = CurrencyService()

    # Batch optimization: one get_splits for Stock/ETF; include all tickers for adjust_trade_for_splits
    ticker_splits: Optional[Dict[str, pd.Series]] = None
    if split_service is not None:
        unique_all: Set[str] = set()
        unique_stock_etf: Set[str] = set()
        for idx, row in df.iterrows():
            try:
                ticker = str(row["Asset Name/Ticker"]).strip()
                asset_type_str = str(row["Asset Type"]).strip()
                asset_type = validate_asset_type(asset_type_str)
                unique_all.add(ticker)
                if asset_type in ("Stock", "ETF"):
                    unique_stock_etf.add(ticker)
            except Exception:
                pass

        ticker_splits = {}
        if unique_stock_etf:
            logger.debug(f"Prefetching split data for {len(unique_stock_etf)} unique tickers")
            ticker_splits = split_service.get_splits(list(unique_stock_etf))
        for t in unique_all:
            if t not in ticker_splits:
                ticker_splits[t] = pd.Series(dtype=float)

    trades: List[Trade] = []
    errors: List[str] = []

    for idx, row in df.iterrows():
        try:
            trade = parse_trade_row(row, currency_service)

            # Filter by end_date if provided
            if end_date is not None and trade.date > end_date:
                logger.debug(f"Skipping trade on {trade.date} (after end_date {end_date})")
                continue

            # Adjust for splits if split_service provided (ticker_splits includes all tickers)
            if split_service is not None:
                adjust_trade_for_splits(trade, ticker_splits, current_date=end_date)

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
        raise ValidationError(f"No valid trades found in sheet. Errors:\n{error_summary}")

    return trades


def list_sheet_names(spreadsheet_id: str, credentials_path: Optional[str] = None) -> List[str]:
    """Return all sheet (tab) names in spreadsheet.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        credentials_path: Path to service account JSON key file (optional)

    Returns:
        List of sheet names (tabs) in the workbook

    Raises:
        ValidationError: If API call fails
    """
    service = get_sheets_service(credentials_path)

    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    except Exception as e:
        raise ValidationError(f"Error fetching spreadsheet: {e}") from e

    sheet_names = [sheet["properties"]["title"] for sheet in spreadsheet["sheets"]]

    logger.debug(f"Found sheets: {sheet_names}")
    return sheet_names


def import_sheets_workbook(
    spreadsheet_id: str,
    credentials_path: Optional[str] = None,
    end_date: Optional[date] = None,
) -> CompositePortfolio:
    """Import ALL sheets as sub-portfolios, aggregate into CompositePortfolio.

    Fail-Fast Behavior:
    - ALL sheets in the spreadsheet are imported (no filtering option)
    - If ANY sheet fails to import (validation error, parsing error, etc.),
      the ENTIRE operation fails
    - No partial portfolios are created on error

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        credentials_path: Path to service account JSON key file (optional)
        end_date: If provided, only import trades on or before this date,
                 and mark portfolios as historical

    Returns:
        CompositePortfolio containing all imported sheets as sub-portfolios

    Raises:
        ValidationError: If any sheet fails validation or parsing
        ImportError: If Google API libraries not installed
    """
    logger.info(f"Scanning workbook: {spreadsheet_id}")

    if end_date is not None:
        logger.info(f"Importing historical portfolio up to {end_date}")

    # Get list of sheets
    sheet_names = list_sheet_names(spreadsheet_id, credentials_path)

    if not sheet_names:
        raise ValidationError(f"No sheets found in spreadsheet '{spreadsheet_id}'")

    logger.info(f"Found {len(sheet_names)} sheet(s): {', '.join(sheet_names)}")

    # Fail-fast: Pre-validate all sheets first
    service = get_sheets_service(credentials_path)
    for sheet_name in sheet_names:
        try:
            df = sheet_to_dataframe(service, spreadsheet_id, sheet_name)
            validate_csv_structure(df)
            logger.debug(f"Pre-validation passed for sheet: {sheet_name}")
        except ValidationError:
            logger.error(f"Pre-validation failed for sheet: {sheet_name}")
            raise

    # All sheets validated, now import
    is_historical = end_date is not None
    composite = CompositePortfolio("Composite", is_historical=is_historical)
    currency_service = CurrencyService()
    split_service = SplitService()

    for sheet_name in sheet_names:
        logger.info(f"Processing sheet: {sheet_name}")

        trades = import_trades_from_sheet(
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            credentials_path=credentials_path,
            currency_service=currency_service,
            end_date=end_date,
            split_service=split_service,
        )

        # Create portfolio for this sheet
        portfolio = SimplePortfolio(sheet_name, is_historical=is_historical)
        for trade in trades:
            portfolio.add_trade(trade)

        composite.add_sub_portfolio(portfolio)
        logger.info(
            f"Successfully imported {len(trades)} trades into portfolio '{sheet_name}'"
        )

    logger.info(
        f"Successfully created composite portfolio with {len(sheet_names)} sub-portfolio(s)"
    )
    return composite
