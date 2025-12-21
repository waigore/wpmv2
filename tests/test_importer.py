"""Tests for CSV import functionality."""

import pytest
import pandas as pd
from datetime import date
import tempfile
import os

from wpm.importer import (
    import_trades_from_csv,
    parse_trade_row,
    validate_csv_structure,
)
from wpm.models import Asset, Trade, ValidationError


class TestValidateCSVStructure:
    """Tests for CSV structure validation."""

    def test_valid_structure(self):
        """Test validation with valid CSV structure."""
        df = pd.DataFrame(
            {
                "Date": ["2024-01-15"],
                "Asset Name/Ticker": ["GOOG"],
                "Asset Type": ["Stock"],
                "Action": ["Buy"],
                "Broker": ["IBKR"],
                "Type": ["Limit"],
                "Price (USD)": [150.0],
                "Quantity": [10.0],
            }
        )
        validate_csv_structure(df)  # Should not raise

    def test_missing_required_column(self):
        """Test validation with missing required column."""
        df = pd.DataFrame(
            {
                "Date": ["2024-01-15"],
                "Asset Name/Ticker": ["GOOG"],
                # Missing Asset Type
                "Action": ["Buy"],
                "Broker": ["IBKR"],
                "Price (USD)": [150.0],
                "Quantity": [10.0],
            }
        )

        with pytest.raises(ValidationError, match="Missing required columns"):
            validate_csv_structure(df)

    def test_missing_optional_column(self):
        """Test validation allows missing optional columns."""
        df = pd.DataFrame(
            {
                "Date": ["2024-01-15"],
                "Asset Name/Ticker": ["GOOG"],
                "Asset Type": ["Stock"],
                "Action": ["Buy"],
                "Broker": ["IBKR"],
                # Type is optional
                "Price (USD)": [150.0],
                "Quantity": [10.0],
            }
        )
        validate_csv_structure(df)  # Should not raise


class TestParseTradeRow:
    """Tests for parsing CSV row to Trade object."""

    def test_parse_valid_row(self):
        """Test parsing a valid CSV row."""
        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Type": "Limit",
                "Price (USD)": 150.0,
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)

        assert trade.date == date(2024, 1, 15)
        assert trade.asset.ticker == "GOOG"
        assert trade.asset.asset_type == "Stock"
        assert trade.action == "Buy"
        assert trade.broker == "IBKR"
        assert trade.order_type == "Limit"
        assert trade.price == 150.0
        assert trade.quantity == 10.0

    def test_parse_row_without_optional_type(self):
        """Test parsing row without optional Type column."""
        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price (USD)": 150.0,
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.order_type is None

    def test_parse_row_with_equity_type(self):
        """Test parsing row with Equity type (should map to Stock)."""
        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Equity",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price (USD)": 150.0,
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.asset.asset_type == "Stock"

    def test_parse_row_with_case_insensitive_asset_type(self):
        """Test parsing row with case-insensitive asset type."""
        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price (USD)": 150.0,
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.asset.asset_type == "Stock"

    def test_parse_row_with_crypto(self):
        """Test parsing row with crypto asset."""
        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "BTC-USD",
                "Asset Type": "Crypto",
                "Action": "Buy",
                "Broker": "Coinbase",
                "Price (USD)": 50000.0,
                "Quantity": 0.1,
            }
        )

        trade = parse_trade_row(row)
        assert trade.asset.ticker == "BTC-USD"
        assert trade.asset.asset_type == "Crypto"

    def test_parse_row_invalid_date(self):
        """Test parsing row with invalid date."""
        row = pd.Series(
            {
                "Date": "invalid-date",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price (USD)": 150.0,
                "Quantity": 10.0,
            }
        )

        with pytest.raises(ValidationError):
            parse_trade_row(row)

    def test_parse_row_invalid_price(self):
        """Test parsing row with invalid price."""
        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price (USD)": -150.0,
                "Quantity": 10.0,
            }
        )

        with pytest.raises(ValidationError):
            parse_trade_row(row)


class TestImportTradesFromCSV:
    """Tests for importing trades from CSV file."""

    def test_import_valid_csv(self):
        """Test importing valid CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Type,Price (USD),Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,Limit,150.0,10.0\n")
            f.write("2024-02-15,AAPL,Stock,Buy,IBKR,Market,200.0,5.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 2

            assert trades[0].asset.ticker == "GOOG"
            assert trades[0].quantity == 10.0

            assert trades[1].asset.ticker == "AAPL"
            assert trades[1].quantity == 5.0
        finally:
            os.unlink(temp_path)

    def test_import_csv_with_equity_type(self):
        """Test importing CSV with Equity type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Type,Price (USD),Quantity\n"
            )
            f.write("2024-01-15,GOOG,Equity,Buy,IBKR,Limit,150.0,10.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 1
            assert trades[0].asset.asset_type == "Stock"
        finally:
            os.unlink(temp_path)

    def test_import_csv_without_optional_type_column(self):
        """Test importing CSV without optional Type column."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,150.0,10.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 1
            assert trades[0].order_type is None
        finally:
            os.unlink(temp_path)

    def test_import_csv_with_invalid_row(self):
        """Test importing CSV with some invalid rows."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Type,Price (USD),Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,Limit,150.0,10.0\n")
            f.write("invalid-date,GOOG,Stock,Buy,IBKR,Limit,150.0,10.0\n")
            f.write("2024-02-15,AAPL,Stock,Buy,IBKR,Market,200.0,5.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            # Should import valid trades, skip invalid ones
            assert len(trades) == 2
        finally:
            os.unlink(temp_path)

    def test_import_csv_missing_required_columns(self):
        """Test importing CSV with missing required columns."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Date,Asset Name/Ticker,Action,Broker\n")
            f.write("2024-01-15,GOOG,Buy,IBKR\n")
            temp_path = f.name

        try:
            with pytest.raises(ValidationError, match="Missing required columns"):
                import_trades_from_csv(temp_path)
        finally:
            os.unlink(temp_path)

    def test_import_nonexistent_file(self):
        """Test importing from nonexistent file."""
        with pytest.raises(ValidationError):
            import_trades_from_csv("nonexistent_file.csv")

    def test_import_empty_csv(self):
        """Test importing empty CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Type,Price (USD),Quantity\n"
            )
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 0
        finally:
            os.unlink(temp_path)

