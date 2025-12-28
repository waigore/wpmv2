"""Tests for CSV import functionality."""

import pytest
import pandas as pd
from datetime import date
from decimal import Decimal
import tempfile
import os
from pathlib import Path

from wpm.importer import (
    import_csv_files,
    import_trades_from_csv,
    parse_trade_row,
    validate_csv_structure,
)
from wpm.models import Asset, Trade, ValidationError
from wpm.portfolio import CompositePortfolio


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
                "Order Instruction": ["Limit"],
                "Trade Type": ["Discretionary"],
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
                # Order Instruction and Trade Type are optional
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
                "Order Instruction": "Limit",
                "Trade Type": "Discretionary",
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
        assert trade.order_instruction == "Limit"
        assert trade.trade_type == "Discretionary"
        assert trade.price == 150.0
        assert trade.quantity == Decimal('10.0')

    def test_parse_row_without_optional_fields(self):
        """Test parsing row without optional Order Instruction and Trade Type columns."""
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
        assert trade.order_instruction is None
        assert trade.trade_type is None

    def test_parse_row_with_only_order_instruction(self):
        """Test parsing row with only Order Instruction."""
        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Order Instruction": "Limit",
                "Price (USD)": 150.0,
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.order_instruction == "Limit"
        assert trade.trade_type is None

    def test_parse_row_with_only_trade_type(self):
        """Test parsing row with only Trade Type."""
        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Trade Type": "Recurring buy",
                "Price (USD)": 150.0,
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.order_instruction is None
        assert trade.trade_type == "Recurring buy"

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
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price (USD),Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,Limit,Discretionary,150.0,10.0\n")
            f.write("2024-02-15,AAPL,Stock,Buy,IBKR,Market,Recurring buy,200.0,5.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 2

            assert trades[0].asset.ticker == "GOOG"
            assert trades[0].order_instruction == "Limit"
            assert trades[0].trade_type == "Discretionary"
            assert trades[0].quantity == Decimal('10.0')

            assert trades[1].asset.ticker == "AAPL"
            assert trades[1].order_instruction == "Market"
            assert trades[1].trade_type == "Recurring buy"
            assert trades[1].quantity == Decimal('5.0')
        finally:
            os.unlink(temp_path)

    def test_import_csv_with_equity_type(self):
        """Test importing CSV with Equity type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price (USD),Quantity\n"
            )
            f.write("2024-01-15,GOOG,Equity,Buy,IBKR,Limit,Discretionary,150.0,10.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 1
            assert trades[0].asset.asset_type == "Stock"
        finally:
            os.unlink(temp_path)

    def test_import_csv_without_optional_columns(self):
        """Test importing CSV without optional Order Instruction and Trade Type columns."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,150.0,10.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 1
            assert trades[0].order_instruction is None
            assert trades[0].trade_type is None
        finally:
            os.unlink(temp_path)

    def test_import_csv_with_invalid_row(self):
        """Test importing CSV with some invalid rows."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price (USD),Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,Limit,Discretionary,150.0,10.0\n")
            f.write("invalid-date,GOOG,Stock,Buy,IBKR,Limit,Discretionary,150.0,10.0\n")
            f.write("2024-02-15,AAPL,Stock,Buy,IBKR,Market,Recurring buy,200.0,5.0\n")
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
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price (USD),Quantity\n"
            )
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 0
        finally:
            os.unlink(temp_path)


class TestImportCSVFiles:
    """Tests for batch CSV import functionality."""

    def test_import_multiple_csv_files(self):
        """Test importing multiple CSV files successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create first CSV file
            csv1_path = Path(temp_dir) / "Asset Trades - Crypto.csv"
            csv1_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
                "2024-01-15,BTC-USD,Crypto,Buy,Coinbase,50000.0,0.1\n"
            )

            # Create second CSV file
            csv2_path = Path(temp_dir) / "Asset Trades - US Stocks.csv"
            csv2_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
                "2024-01-15,GOOG,Stock,Buy,IBKR,150.0,10.0\n"
                "2024-02-15,AAPL,Stock,Buy,IBKR,200.0,5.0\n"
            )

            composite = import_csv_files(Path(temp_dir))

            assert isinstance(composite, CompositePortfolio)
            assert composite.name == "Composite"
            assert len(composite._sub_portfolios) == 2

            # Check portfolio names were extracted correctly
            assert "Crypto" in composite._sub_portfolios
            assert "USStocks" in composite._sub_portfolios

            # Check trades were imported correctly
            crypto_portfolio = composite._sub_portfolios["Crypto"]
            stocks_portfolio = composite._sub_portfolios["USStocks"]

            crypto_positions = crypto_portfolio.get_positions()
            stocks_positions = stocks_portfolio.get_positions()

            assert len(crypto_positions) == 1
            assert len(stocks_positions) == 2

    def test_import_csv_files_empty_directory(self):
        """Test that ValueError is raised when no CSV files found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="No CSV files found"):
                import_csv_files(Path(temp_dir))

    def test_import_csv_files_invalid_csv(self):
        """Test that ValidationError propagates from invalid CSV files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create CSV file with missing required columns
            csv_path = Path(temp_dir) / "invalid.csv"
            csv_path.write_text("Date,Asset Name/Ticker\n2024-01-15,GOOG\n")

            with pytest.raises(ValidationError, match="Missing required columns"):
                import_csv_files(Path(temp_dir))

    def test_import_csv_files_portfolio_name_extraction(self):
        """Test portfolio names are extracted correctly from filenames."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test various filename patterns
            csv1_path = Path(temp_dir) / "Asset Trades - Crypto.csv"
            csv1_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
                "2024-01-15,BTC-USD,Crypto,Buy,Coinbase,50000.0,0.1\n"
            )

            csv2_path = Path(temp_dir) / "simple_name.csv"
            csv2_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
                "2024-01-15,GOOG,Stock,Buy,IBKR,150.0,10.0\n"
            )

            csv3_path = Path(temp_dir) / "File With Spaces.csv"
            csv3_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
                "2024-01-15,AAPL,Stock,Buy,IBKR,200.0,5.0\n"
            )

            composite = import_csv_files(Path(temp_dir))

            # Check portfolio names
            assert "Crypto" in composite._sub_portfolios
            assert "simple_name" in composite._sub_portfolios
            assert "FileWithSpaces" in composite._sub_portfolios

    def test_import_csv_files_duplicate_names(self):
        """Test duplicate portfolio names are handled with numeric suffixes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple CSV files that would result in the same portfolio name
            csv1_path = Path(temp_dir) / "Asset Trades - Crypto.csv"
            csv1_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
                "2024-01-15,BTC-USD,Crypto,Buy,Coinbase,50000.0,0.1\n"
            )

            csv2_path = Path(temp_dir) / "Other File - Crypto.csv"
            csv2_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
                "2024-01-15,ETH-USD,Crypto,Buy,Coinbase,3000.0,1.0\n"
            )

            csv3_path = Path(temp_dir) / "Another - Crypto.csv"
            csv3_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price (USD),Quantity\n"
                "2024-01-15,DOGE-USD,Crypto,Buy,Coinbase,0.5,1000.0\n"
            )

            composite = import_csv_files(Path(temp_dir))

            # Check that duplicate names were handled
            assert len(composite._sub_portfolios) == 3
            assert "Crypto" in composite._sub_portfolios
            assert "Crypto_1" in composite._sub_portfolios
            assert "Crypto_2" in composite._sub_portfolios

