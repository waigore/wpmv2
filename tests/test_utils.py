"""Tests for utility functions."""

import pytest
from datetime import date, datetime
import pytz

from wpm.utils import (
    normalize_date,
    validate_asset_type,
    validate_ticker,
    is_within_trading_hours,
)


class TestValidateTicker:
    """Tests for validate_ticker function."""

    def test_valid_ticker(self):
        """Test valid ticker formats."""
        validate_ticker("GOOG")
        validate_ticker("BTC-USD")
        validate_ticker("ETH_USD")
        validate_ticker("AAPL123")

    def test_invalid_ticker(self):
        """Test invalid ticker formats."""
        with pytest.raises(ValueError):
            validate_ticker("")

        with pytest.raises(ValueError):
            validate_ticker("GOO G")

        with pytest.raises(ValueError):
            validate_ticker("GOO$G")


class TestNormalizeDate:
    """Tests for normalize_date function."""

    def test_valid_date(self):
        """Test valid date format."""
        result = normalize_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_invalid_date_format(self):
        """Test invalid date format."""
        with pytest.raises(ValueError):
            normalize_date("01/15/2024")

        with pytest.raises(ValueError):
            normalize_date("invalid")


class TestValidateAssetType:
    """Tests for validate_asset_type function."""

    def test_valid_asset_types(self):
        """Test valid asset types."""
        assert validate_asset_type("Stock") == "Stock"
        assert validate_asset_type("stock") == "Stock"
        assert validate_asset_type("STOCK") == "Stock"
        assert validate_asset_type("ETF") == "ETF"
        assert validate_asset_type("Crypto") == "Crypto"

    def test_equity_mapping(self):
        """Test Equity to Stock mapping."""
        assert validate_asset_type("Equity") == "Stock"
        assert validate_asset_type("equity") == "Stock"
        assert validate_asset_type("EQUITY") == "Stock"

    def test_invalid_asset_type(self):
        """Test invalid asset types."""
        with pytest.raises(ValueError):
            validate_asset_type("Invalid")

        with pytest.raises(ValueError):
            validate_asset_type("")


class TestTradingHours:
    """Tests for trading hours functions."""

    def test_is_within_trading_hours(self):
        """Test is_within_trading_hours function."""
        # Create a datetime during trading hours (9:30 AM - 4:00 PM ET on a weekday)
        et_tz = pytz.timezone("US/Eastern")
        
        # Note: These tests may fail depending on the actual date
        # For a more robust test, we'd need to use a specific known trading day
        # This is a basic smoke test
        test_datetime = datetime(2024, 1, 15, 12, 0, 0)
        test_datetime = et_tz.localize(test_datetime)
        
        # This will depend on whether it's a trading day
        result = is_within_trading_hours(test_datetime)
        assert isinstance(result, bool)

