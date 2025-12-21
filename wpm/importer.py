"""CSV import functionality using pandas."""

import logging
from typing import List

import pandas as pd

from wpm.models import Asset, Trade, ValidationError
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

        quantity = float(row["Quantity"])

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

