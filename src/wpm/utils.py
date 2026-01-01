"""Utility functions for validation, logging, and trading hours."""

import logging
import re
import warnings
from datetime import date, datetime, time
from typing import Optional, Sequence

import pandas as pd
import pandas_market_calendars as mcal
import pytz

# Create NYSE calendar instance (handles holidays, early closes, etc.)
NYSE_CALENDAR = mcal.get_calendar("NYSE")

# US Eastern Time
ET_TZ = pytz.timezone("US/Eastern")

# Regular trading hours in ET
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)

# Logger instance
_logger: Optional[logging.Logger] = None


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure library logging.

    Args:
        level: Logging level (default: logging.INFO)

    Returns:
        Configured logger instance
    """
    global _logger

    if _logger is not None:
        return _logger

    _logger = logging.getLogger("wpm")
    _logger.setLevel(level)

    if not _logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        _logger.addHandler(handler)

    return _logger


def validate_ticker(ticker: str) -> None:
    """Validate ticker format.

    Args:
        ticker: Ticker symbol to validate

    Raises:
        ValidationError: If ticker format is invalid
    """
    if not ticker or not isinstance(ticker, str):
        raise ValueError("Ticker must be a non-empty string")

    # Allow alphanumeric, hyphens, underscores, and dots (for non-US stocks like 2800.HK)
    if not re.match(r"^[A-Za-z0-9_.-]+$", ticker):
        raise ValueError(
            "Ticker must contain only alphanumeric characters, hyphens, underscores, and dots"
        )


def normalize_date(date_str: str) -> date:
    """Parse and normalize date strings in YYYY-MM-DD format.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Parsed date object

    Raises:
        ValueError: If date string format is invalid
    """
    if not date_str or not isinstance(date_str, str):
        raise ValueError("Date string must be a non-empty string")

    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid date format. Expected YYYY-MM-DD, got '{date_str}'") from e


def validate_asset_type(asset_type: str) -> str:
    """Validate and normalize asset type.

    Maps "Equity" to "Stock" and normalizes case to title case.

    Args:
        asset_type: Asset type string to validate

    Returns:
        Normalized asset type ("Stock", "ETF", or "Crypto")

    Raises:
        ValueError: If asset type is invalid
    """
    if not asset_type or not isinstance(asset_type, str):
        raise ValueError("Asset type must be a non-empty string")

    normalized = asset_type.strip().title()

    # Map "Equity" to "Stock"
    if normalized == "Equity":
        normalized = "Stock"

    # Handle acronyms that title() would change (e.g., "ETF" -> "Etf")
    if normalized.upper() == "ETF":
        normalized = "ETF"

    valid_types = ("Stock", "ETF", "Crypto")
    if normalized not in valid_types:
        raise ValueError(
            f"Asset type must be one of {valid_types}, got '{asset_type}'"
        )

    return normalized


def concat_dataframes(
    objs: Sequence[pd.DataFrame], ignore_index: bool = False, **kwargs
) -> pd.DataFrame:
    """Concatenate pandas DataFrames while suppressing FutureWarning for empty DataFrames.
    
    This wrapper around pd.concat suppresses the FutureWarning that pandas emits
    when concatenating DataFrames where one may be empty or all-NA. This warning
    is about future dtype inference behavior and is not critical when DataFrames
    have matching columns.
    
    Args:
        objs: Sequence of DataFrames to concatenate
        ignore_index: If True, ignore index and use default integer index
        **kwargs: Additional arguments passed to pd.concat
    
    Returns:
        Concatenated DataFrame
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=FutureWarning, message=".*DataFrame concatenation.*"
        )
        return pd.concat(objs, ignore_index=ignore_index, **kwargs)


def is_us_market_open(timestamp: Optional[datetime] = None) -> bool:
    """Determine if US market (NYSE) is currently open for regular trading hours.

    Accounts for weekends, official holidays, and early closes using
    pandas_market_calendars.

    Args:
        timestamp: Timestamp to check (default: current time in ET timezone)

    Returns:
        True if market is open, False otherwise
    """
    if timestamp is None:
        timestamp = datetime.now(ET_TZ)
    else:
        if timestamp.tzinfo is None:
            timestamp = ET_TZ.localize(timestamp)
        else:
            timestamp = timestamp.astimezone(ET_TZ)

    now_et_date = timestamp.date()
    current_time_et = timestamp.time()

    schedule = NYSE_CALENDAR.schedule(start_date=now_et_date, end_date=now_et_date)

    if schedule.empty or now_et_date not in schedule.index:
        return False

    market_open_et = schedule.loc[now_et_date, "market_open"].time()
    market_close_et = schedule.loc[now_et_date, "market_close"].time()

    return market_open_et <= current_time_et < market_close_et


def _get_market_schedule(timestamp_date: date) -> Optional[pd.DataFrame]:
    """Get market schedule for a given date.

    Args:
        timestamp_date: Date to get schedule for

    Returns:
        Schedule DataFrame if available, None otherwise
    """
    schedule = NYSE_CALENDAR.schedule(
        start_date=timestamp_date, end_date=timestamp_date
    )

    if schedule.empty:
        return None

    # Check if date exists in index (handle both date and Timestamp types)
    timestamp_pd = pd.Timestamp(timestamp_date)
    date_in_index = (
        timestamp_date in schedule.index
        or timestamp_pd in schedule.index
        or any(
            (isinstance(idx, pd.Timestamp) and idx.date() == timestamp_date)
            or idx == timestamp_date
            for idx in schedule.index
        )
    )

    if not date_in_index:
        return None

    return schedule


def _get_market_hours(schedule: pd.DataFrame, timestamp_date: date) -> Optional[tuple[time, time]]:
    """Extract market open and close times from schedule.

    Args:
        schedule: Schedule DataFrame
        timestamp_date: Date to extract hours for

    Returns:
        Tuple of (market_open_time, market_close_time) if available, None otherwise
    """
    try:
        market_open_et = schedule.loc[timestamp_date, "market_open"].time()
        market_close_et = schedule.loc[timestamp_date, "market_close"].time()
        return (market_open_et, market_close_et)
    except KeyError:
        # If date doesn't work, try with pd.Timestamp
        timestamp_pd = pd.Timestamp(timestamp_date)
        try:
            market_open_et = schedule.loc[timestamp_pd, "market_open"].time()
            market_close_et = schedule.loc[timestamp_pd, "market_close"].time()
            return (market_open_et, market_close_et)
        except (KeyError, IndexError):
            return None


def is_within_trading_hours(timestamp: datetime) -> bool:
    """Check if a given timestamp falls within US market trading hours.

    Uses NYSE calendar to account for holidays and early closes.

    Args:
        timestamp: Timestamp to check

    Returns:
        True if timestamp is during market hours, False otherwise
    """
    if timestamp.tzinfo is None:
        timestamp = ET_TZ.localize(timestamp)
    else:
        timestamp = timestamp.astimezone(ET_TZ)

    timestamp_date = timestamp.date()
    timestamp_time = timestamp.time()

    schedule = _get_market_schedule(timestamp_date)
    if schedule is None:
        return False

    market_hours = _get_market_hours(schedule, timestamp_date)
    if market_hours is None:
        return False

    market_open_et, market_close_et = market_hours
    return market_open_et <= timestamp_time < market_close_et

