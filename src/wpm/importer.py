"""CSV import functionality using pandas."""

import logging
from decimal import Decimal
from pathlib import Path
from typing import List, Set

import pandas as pd

from wpm.models import Asset, Trade, ValidationError
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.utils import normalize_date, validate_asset_type

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Date",
    "Asset Name/Ticker",
    "Asset Type",
    "Action",
    "Broker",
    "Price (USD)",
    "Quantity",
]


def validate_csv_structure(df: pd.DataFrame) -> None:
    """Validate CSV has required columns.

    Args:
        df: DataFrame to validate

    Raises:
        ValidationError: If required columns are missing
    """
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]

    if missing_columns:
        raise ValidationError(
            f"Missing required columns: {', '.join(missing_columns)}"
        )


def parse_trade_row(row: pd.Series) -> Trade:
    """Convert CSV row to Trade object.

    Maps "Equity" asset type to "Stock" as per spec requirement.

    Args:
        row: Pandas Series representing a CSV row

    Returns:
        Trade object

    Raises:
        ValidationError: If row data is invalid
    """
    try:
        date_str = str(row["Date"])
        trade_date = normalize_date(date_str)

        ticker = str(row["Asset Name/Ticker"]).strip()

        asset_type_str = str(row["Asset Type"]).strip()
        # Map "Equity" to "Stock" as per spec
        asset_type = validate_asset_type(asset_type_str)

        asset = Asset(ticker=ticker, asset_type=asset_type)

        action = str(row["Action"]).strip()

        broker = str(row["Broker"]).strip()

        order_type = None
        if "Type" in row and pd.notna(row["Type"]):
            order_type = str(row["Type"]).strip()

        price = float(row["Price (USD)"])

        # Parse quantity as Decimal to avoid floating point precision issues
        quantity = Decimal(str(row["Quantity"]))

        trade = Trade(
            date=trade_date,
            asset=asset,
            action=action,
            broker=broker,
            order_type=order_type,
            price=price,
            quantity=quantity,
        )

        logger.debug(
            f"Parsed trade: {trade_date} {asset.ticker} {action} "
            f"{quantity} @ ${price} via {broker}"
        )

        return trade

    except (ValueError, KeyError, TypeError) as e:
        raise ValidationError(f"Error parsing trade row: {str(e)}") from e


def import_trades_from_csv(file_path: str) -> List[Trade]:
    """Import trades from CSV file.

    Args:
        file_path: Path to CSV file

    Returns:
        List of Trade objects

    Raises:
        ValidationError: If CSV structure is invalid or data cannot be parsed
    """
    logger.info(f"Starting CSV import from '{file_path}'")

    try:
        df = pd.read_csv(file_path)
        logger.info(f"Loaded CSV with {len(df)} rows")
    except Exception as e:
        raise ValidationError(f"Error reading CSV file: {str(e)}") from e

    validate_csv_structure(df)
    logger.debug("CSV structure validation passed")

    trades: List[Trade] = []
    errors: List[str] = []

    for idx, row in df.iterrows():
        try:
            trade = parse_trade_row(row)
            trades.append(trade)
        except ValidationError as e:
            error_msg = f"Row {idx + 1}: {str(e)}"
            errors.append(error_msg)
            logger.warning(error_msg)

    if errors:
        error_summary = "\n".join(errors)
        logger.warning(f"Encountered {len(errors)} validation errors during import")

    logger.info(f"CSV import completed. Successfully imported {len(trades)} trades")

    if not trades and errors:
        raise ValidationError(
            f"No valid trades found in CSV. Errors:\n{error_summary}"
        )

    return trades


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
        ValueError: If no CSV files found in directory
        ValidationError: If CSV import fails
    """
    logger.info(f"Scanning directory for CSV files: {import_dir}")

    csv_files = sorted(import_dir.glob("*.csv"))

    if not csv_files:
        logger.error(f"No CSV files found in {import_dir}")
        raise ValueError(f"No CSV files found in '{import_dir}' directory")

    logger.info(f"Found {len(csv_files)} CSV file(s)")

    composite = CompositePortfolio("Composite")
    existing_names: Set[str] = set()

    for csv_file in csv_files:
        logger.info(f"Processing CSV file: {csv_file}")

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

    logger.info(f"Successfully created composite portfolio with {len(existing_names)} sub-portfolio(s)")
    return composite

