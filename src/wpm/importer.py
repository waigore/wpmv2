"""CSV import functionality using pandas."""

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from wpm.currency import CurrencyService
from wpm.models import Asset, Trade, ValidationError
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.pricing.splits import SplitService, compute_cumulative_split_factor_from_splits
from wpm.utils import normalize_date, validate_asset_type

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "Date",
    "Asset Name/Ticker",
    "Asset Type",
    "Action",
    "Broker",
    "Price",
    "Currency",
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


def parse_trade_row(row: pd.Series, currency_service: CurrencyService = None) -> Trade:
    """Convert CSV row to Trade object.

    Maps "Equity" asset type to "Stock" as per spec requirement.

    Args:
        row: Pandas Series representing a CSV row
        currency_service: CurrencyService instance for currency conversion (default: creates new instance)

    Returns:
        Trade object

    Raises:
        ValidationError: If row data is invalid
    """
    if currency_service is None:
        currency_service = CurrencyService()

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

        order_instruction = None
        if "Order Instruction" in row and pd.notna(row["Order Instruction"]):
            order_instruction = str(row["Order Instruction"]).strip()

        trade_type = None
        if "Trade Type" in row and pd.notna(row["Trade Type"]):
            trade_type = str(row["Trade Type"]).strip()

        # Read Currency column (required)
        currency = str(row["Currency"]).strip().upper()
        if not currency:
            raise ValidationError("Currency column cannot be empty")

        # Read Price column (required)
        price_native = float(row["Price"])

        # Convert price to USD using currency service if currency != USD
        if currency == "USD":
            price_usd = price_native
        else:
            price_usd = currency_service.convert_to_usd(price_native, currency)
            logger.debug(
                f"Converted {price_native} {currency} to {price_usd:.2f} USD "
                f"for trade {ticker} on {trade_date}"
            )

        # Parse quantity as Decimal to avoid floating point precision issues
        quantity = Decimal(str(row["Quantity"]))

        trade = Trade(
            date=trade_date,
            asset=asset,
            action=action,
            broker=broker,
            order_instruction=order_instruction,
            trade_type=trade_type,
            currency=currency,
            price=price_usd,
            price_native=price_native,
            quantity=quantity,
        )

        logger.debug(
            f"Parsed trade: {trade_date} {asset.ticker} {action} "
            f"{quantity} @ {price_native} {currency} (${price_usd:.2f} USD) via {broker}"
        )

        return trade

    except (ValueError, KeyError, TypeError) as e:
        raise ValidationError(f"Error parsing trade row: {str(e)}") from e


def adjust_trade_for_splits(
    trade: Trade,
    ticker_splits: Dict[str, pd.Series],
    current_date: Optional[date] = None,
) -> Trade:
    """Adjust trade for stock splits by calculating and setting split adjustment factor.

    Caller must supply pre-fetched ticker_splits and ensure the trade's ticker
    is present; otherwise ValidationError is raised.

    For stocks and ETFs, calculates cumulative split factor from splits that occurred
    after the trade date. For crypto assets, sets factor to 1.0 (no adjustment).

    Args:
        trade: Trade object to adjust
        ticker_splits: Required dict of ticker -> splits Series (from e.g. SplitService.get_splits).
                      Must contain an entry for the trade's ticker.
        current_date: Optional end date for split calculation (default: today).
                     For historical portfolios, use the portfolio's end_date.

    Returns:
        Trade object with updated split_adjustment_factor (modified in-place)

    Raises:
        ValidationError: If ticker_splits is None or if the trade's ticker is not in ticker_splits.
    """
    if ticker_splits is None:
        raise ValidationError("ticker_splits is required")

    ticker = trade.asset.ticker
    if ticker not in ticker_splits:
        raise ValidationError(f"ticker_splits must contain an entry for ticker {ticker}")

    # Crypto assets don't have splits - set factor to 1.0
    if trade.asset.asset_type == "Crypto":
        trade.split_adjustment_factor = Decimal('1.0')
        logger.debug(f"Skipping split adjustment for crypto asset {ticker}")
        return trade

    try:
        splits = ticker_splits[ticker]
        factor = compute_cumulative_split_factor_from_splits(
            splits, trade.date, current_date
        )
        trade.split_adjustment_factor = factor

        if factor != Decimal('1.0'):
            logger.info(
                f"Adjusted trade {ticker} on {trade.date}: "
                f"factor={factor}, original={trade.quantity}@{trade.price}, "
                f"adjusted={trade.adjusted_quantity}@{trade.adjusted_price:.2f}"
            )
        else:
            logger.debug(f"No split adjustment needed for {ticker} on {trade.date}")

    except Exception as e:
        logger.warning(
            f"Failed to adjust trade {ticker} on {trade.date} for splits: {e}. "
            f"Using default factor 1.0"
        )
        trade.split_adjustment_factor = Decimal('1.0')

    return trade


def import_trades_from_csv(
    file_path: str,
    currency_service: CurrencyService = None,
    end_date: Optional[date] = None,
    split_service: Optional[SplitService] = None,
) -> List[Trade]:
    """Import trades from CSV file.

    Args:
        file_path: Path to CSV file
        currency_service: CurrencyService instance for currency conversion (default: creates new instance)
        end_date: Optional end date (inclusive). If provided, only trades with date <= end_date are included
        split_service: Optional SplitService instance for adjusting trades for stock splits.
                      If provided, trades will be adjusted for splits that occurred after the trade date.

    Returns:
        List of Trade objects

    Raises:
        ValidationError: If CSV structure is invalid or data cannot be parsed
    """
    logger.info(f"Starting CSV import from '{file_path}'")
    if end_date is not None:
        logger.info(f"Filtering trades up to end date: {end_date}")

    if currency_service is None:
        currency_service = CurrencyService()

    try:
        df = pd.read_csv(file_path)
        logger.info(f"Loaded CSV with {len(df)} rows")
    except Exception as e:
        raise ValidationError(f"Error reading CSV file: {str(e)}") from e

    validate_csv_structure(df)
    logger.debug("CSV structure validation passed")

    # Batch optimization: one get_splits for all Stock/ETF tickers; include all tickers so adjust_trade_for_splits has every trade's ticker
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
                logger.debug(
                    f"Skipping trade on {trade.date} (after end_date {end_date})"
                )
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
        error_summary = "\n".join(errors)
        logger.warning(f"Encountered {len(errors)} validation errors during import")

    logger.info(f"CSV import completed. Successfully imported {len(trades)} trades")
    if end_date is not None:
        logger.info(f"Filtered to {len(trades)} trades on or before {end_date}")
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


def import_csv_files(import_dir: Path, end_date: Optional[date] = None) -> CompositePortfolio:
    """Import CSV files and create composite portfolio.

    Args:
        import_dir: Directory containing CSV files
        end_date: Optional end date (inclusive). If provided, only trades with date <= end_date are included,
                  and all created portfolios will have is_historical=True

    Returns:
        CompositePortfolio containing all imported sub-portfolios

    Raises:
        ValueError: If no CSV files found in directory
        ValidationError: If CSV import fails
    """
    logger.info(f"Scanning directory for CSV files: {import_dir}")
    if end_date is not None:
        logger.info(f"Importing historical portfolio up to {end_date}")

    csv_files = sorted(import_dir.glob("*.csv"))

    if not csv_files:
        logger.error(f"No CSV files found in {import_dir}")
        raise ValueError(f"No CSV files found in '{import_dir}' directory")

    logger.info(f"Found {len(csv_files)} CSV file(s)")

    is_historical = end_date is not None
    composite = CompositePortfolio("Composite", is_historical=is_historical)
    existing_names: Set[str] = set()

    # Create SplitService for split adjustment
    split_service = SplitService()

    for csv_file in csv_files:
        logger.info(f"Processing CSV file: {csv_file}")

        # Extract portfolio name
        portfolio_name = extract_portfolio_name(csv_file.name, existing_names)
        existing_names.add(portfolio_name)

        # Import trades with split adjustment
        trades = import_trades_from_csv(
            str(csv_file), end_date=end_date, split_service=split_service
        )

        # Create portfolio and add trades
        portfolio = SimplePortfolio(portfolio_name, is_historical=is_historical)
        for trade in trades:
            portfolio.add_trade(trade)

        # Add to composite
        composite.add_sub_portfolio(portfolio)
        logger.info(f"Successfully imported {len(trades)} trades into portfolio '{portfolio_name}'")

    logger.info(f"Successfully created composite portfolio with {len(existing_names)} sub-portfolio(s)")
    return composite

