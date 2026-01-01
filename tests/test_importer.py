"""Tests for CSV import functionality."""

import pytest
import pandas as pd
from datetime import date
from decimal import Decimal
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock

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
                "Price": [150.0],
                "Currency": ["USD"],
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
                "Price": [150.0],
                "Currency": ["USD"],
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
                "Price": [150.0],
                "Currency": ["USD"],
                "Quantity": [10.0],
            }
        )
        validate_csv_structure(df)  # Should not raise


class TestParseTradeRow:
    """Tests for parsing CSV row to Trade object."""

    @patch("wpm.importer.CurrencyService")
    def test_parse_valid_row(self, mock_currency_service_class):
        """Test parsing a valid CSV row."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Order Instruction": "Limit",
                "Trade Type": "Discretionary",
                "Price": 150.0,
                "Currency": "USD",
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
        assert trade.currency == "USD"
        assert trade.price == 150.0
        assert trade.price_native == 150.0
        assert trade.quantity == Decimal('10.0')

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_without_optional_fields(self, mock_currency_service_class):
        """Test parsing row without optional Order Instruction and Trade Type columns."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price": 150.0,
                "Currency": "USD",
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.order_instruction is None
        assert trade.trade_type is None
        assert trade.currency == "USD"

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_with_only_order_instruction(self, mock_currency_service_class):
        """Test parsing row with only Order Instruction."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Order Instruction": "Limit",
                "Price": 150.0,
                "Currency": "USD",
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.order_instruction == "Limit"
        assert trade.trade_type is None

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_with_only_trade_type(self, mock_currency_service_class):
        """Test parsing row with only Trade Type."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Trade Type": "Recurring buy",
                "Price": 150.0,
                "Currency": "USD",
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.order_instruction is None
        assert trade.trade_type == "Recurring buy"

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_with_equity_type(self, mock_currency_service_class):
        """Test parsing row with Equity type (should map to Stock)."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Equity",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price": 150.0,
                "Currency": "USD",
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.asset.asset_type == "Stock"

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_with_case_insensitive_asset_type(self, mock_currency_service_class):
        """Test parsing row with case-insensitive asset type."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price": 150.0,
                "Currency": "USD",
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.asset.asset_type == "Stock"

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_with_crypto(self, mock_currency_service_class):
        """Test parsing row with crypto asset."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 50000.0
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "BTC-USD",
                "Asset Type": "Crypto",
                "Action": "Buy",
                "Broker": "Coinbase",
                "Price": 50000.0,
                "Currency": "USD",
                "Quantity": 0.1,
            }
        )

        trade = parse_trade_row(row)
        assert trade.asset.ticker == "BTC-USD"
        assert trade.asset.asset_type == "Crypto"

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_invalid_date(self, mock_currency_service_class):
        """Test parsing row with invalid date."""
        mock_service = Mock()
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "invalid-date",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price": 150.0,
                "Currency": "USD",
                "Quantity": 10.0,
            }
        )

        with pytest.raises(ValidationError):
            parse_trade_row(row)

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_invalid_price(self, mock_currency_service_class):
        """Test parsing row with invalid price."""
        mock_service = Mock()
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price": -150.0,
                "Currency": "USD",
                "Quantity": 10.0,
            }
        )

        with pytest.raises(ValidationError):
            parse_trade_row(row)

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_with_hkd_currency(self, mock_currency_service_class):
        """Test parsing row with HKD currency and conversion."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 12.8  # 100 HKD * 0.128 = 12.8 USD
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "2800.HK",
                "Asset Type": "ETF",
                "Action": "Buy",
                "Broker": "Futu",
                "Price": 100.0,
                "Currency": "HKD",
                "Quantity": 10.0,
            }
        )

        trade = parse_trade_row(row)
        assert trade.currency == "HKD"
        assert trade.price_native == 100.0
        assert trade.price == 12.8  # Converted to USD
        mock_service.convert_to_usd.assert_called_once_with(100.0, "HKD")

    @patch("wpm.importer.CurrencyService")
    def test_parse_row_missing_currency(self, mock_currency_service_class):
        """Test parsing row with missing currency raises error."""
        mock_service = Mock()
        mock_currency_service_class.return_value = mock_service

        row = pd.Series(
            {
                "Date": "2024-01-15",
                "Asset Name/Ticker": "GOOG",
                "Asset Type": "Stock",
                "Action": "Buy",
                "Broker": "IBKR",
                "Price": 150.0,
                # Currency missing
                "Quantity": 10.0,
            }
        )

        with pytest.raises(ValidationError):
            parse_trade_row(row)


class TestImportTradesFromCSV:
    """Tests for importing trades from CSV file."""

    @patch("wpm.importer.CurrencyService")
    def test_import_valid_csv(self, mock_currency_service_class):
        """Test importing valid CSV file."""
        mock_service = Mock()
        def convert_side_effect(amount, currency):
            return amount if currency == "USD" else amount * 0.128
        mock_service.convert_to_usd.side_effect = convert_side_effect
        mock_currency_service_class.return_value = mock_service

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price,Currency,Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,Limit,Discretionary,150.0,USD,10.0\n")
            f.write("2024-02-15,AAPL,Stock,Buy,IBKR,Market,Recurring buy,200.0,USD,5.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 2

            assert trades[0].asset.ticker == "GOOG"
            assert trades[0].order_instruction == "Limit"
            assert trades[0].trade_type == "Discretionary"
            assert trades[0].currency == "USD"
            assert trades[0].quantity == Decimal('10.0')

            assert trades[1].asset.ticker == "AAPL"
            assert trades[1].order_instruction == "Market"
            assert trades[1].trade_type == "Recurring buy"
            assert trades[1].currency == "USD"
            assert trades[1].quantity == Decimal('5.0')
        finally:
            os.unlink(temp_path)

    @patch("wpm.importer.CurrencyService")
    def test_import_csv_with_equity_type(self, mock_currency_service_class):
        """Test importing CSV with Equity type."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price,Currency,Quantity\n"
            )
            f.write("2024-01-15,GOOG,Equity,Buy,IBKR,Limit,Discretionary,150.0,USD,10.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 1
            assert trades[0].asset.asset_type == "Stock"
        finally:
            os.unlink(temp_path)

    @patch("wpm.importer.CurrencyService")
    def test_import_csv_without_optional_columns(self, mock_currency_service_class):
        """Test importing CSV without optional Order Instruction and Trade Type columns."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,150.0,USD,10.0\n")
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 1
            assert trades[0].order_instruction is None
            assert trades[0].trade_type is None
        finally:
            os.unlink(temp_path)

    @patch("wpm.importer.CurrencyService")
    def test_import_csv_with_invalid_row(self, mock_currency_service_class):
        """Test importing CSV with some invalid rows."""
        mock_service = Mock()
        mock_service.convert_to_usd.return_value = 150.0
        mock_currency_service_class.return_value = mock_service

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price,Currency,Quantity\n"
            )
            f.write("2024-01-15,GOOG,Stock,Buy,IBKR,Limit,Discretionary,150.0,USD,10.0\n")
            f.write("invalid-date,GOOG,Stock,Buy,IBKR,Limit,Discretionary,150.0,USD,10.0\n")
            f.write("2024-02-15,AAPL,Stock,Buy,IBKR,Market,Recurring buy,200.0,USD,5.0\n")
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
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price,Currency,Quantity\n"
            )
            temp_path = f.name

        try:
            trades = import_trades_from_csv(temp_path)
            assert len(trades) == 0
        finally:
            os.unlink(temp_path)


class TestImportCSVFiles:
    """Tests for batch CSV import functionality."""

    @patch("wpm.importer.CurrencyService")
    def test_import_multiple_csv_files(self, mock_currency_service_class):
        """Test importing multiple CSV files successfully."""
        mock_service = Mock()
        def convert_side_effect(amount, currency):
            return amount if currency == "USD" else amount * 0.128
        mock_service.convert_to_usd.side_effect = convert_side_effect
        mock_currency_service_class.return_value = mock_service

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create first CSV file
            csv1_path = Path(temp_dir) / "Asset Trades - Crypto.csv"
            csv1_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
                "2024-01-15,BTC-USD,Crypto,Buy,Coinbase,50000.0,USD,0.1\n"
            )

            # Create second CSV file
            csv2_path = Path(temp_dir) / "Asset Trades - US Stocks.csv"
            csv2_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
                "2024-01-15,GOOG,Stock,Buy,IBKR,150.0,USD,10.0\n"
                "2024-02-15,AAPL,Stock,Buy,IBKR,200.0,USD,5.0\n"
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

    @patch("wpm.importer.CurrencyService")
    def test_import_csv_files_portfolio_name_extraction(self, mock_currency_service_class):
        """Test portfolio names are extracted correctly from filenames."""
        mock_service = Mock()
        def convert_side_effect(amount, currency):
            return amount if currency == "USD" else amount * 0.128
        mock_service.convert_to_usd.side_effect = convert_side_effect
        mock_currency_service_class.return_value = mock_service

        with tempfile.TemporaryDirectory() as temp_dir:
            # Test various filename patterns
            csv1_path = Path(temp_dir) / "Asset Trades - Crypto.csv"
            csv1_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
                "2024-01-15,BTC-USD,Crypto,Buy,Coinbase,50000.0,USD,0.1\n"
            )

            csv2_path = Path(temp_dir) / "simple_name.csv"
            csv2_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
                "2024-01-15,GOOG,Stock,Buy,IBKR,150.0,USD,10.0\n"
            )

            csv3_path = Path(temp_dir) / "File With Spaces.csv"
            csv3_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
                "2024-01-15,AAPL,Stock,Buy,IBKR,200.0,USD,5.0\n"
            )

            composite = import_csv_files(Path(temp_dir))

            # Check portfolio names
            assert "Crypto" in composite._sub_portfolios
            assert "simple_name" in composite._sub_portfolios
            assert "FileWithSpaces" in composite._sub_portfolios

    @patch("wpm.importer.CurrencyService")
    def test_import_csv_files_duplicate_names(self, mock_currency_service_class):
        """Test duplicate portfolio names are handled with numeric suffixes."""
        mock_service = Mock()
        def convert_side_effect(amount, currency):
            return amount if currency == "USD" else amount * 0.128
        mock_service.convert_to_usd.side_effect = convert_side_effect
        mock_currency_service_class.return_value = mock_service

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create multiple CSV files that would result in the same portfolio name
            csv1_path = Path(temp_dir) / "Asset Trades - Crypto.csv"
            csv1_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
                "2024-01-15,BTC-USD,Crypto,Buy,Coinbase,50000.0,USD,0.1\n"
            )

            csv2_path = Path(temp_dir) / "Other File - Crypto.csv"
            csv2_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
                "2024-01-15,ETH-USD,Crypto,Buy,Coinbase,3000.0,USD,1.0\n"
            )

            csv3_path = Path(temp_dir) / "Another - Crypto.csv"
            csv3_path.write_text(
                "Date,Asset Name/Ticker,Asset Type,Action,Broker,Price,Currency,Quantity\n"
                "2024-01-15,DOGE-USD,Crypto,Buy,Coinbase,0.5,USD,1000.0\n"
            )

            composite = import_csv_files(Path(temp_dir))

            # Check that duplicate names were handled
            assert len(composite._sub_portfolios) == 3
            assert "Crypto" in composite._sub_portfolios
            assert "Crypto_1" in composite._sub_portfolios
            assert "Crypto_2" in composite._sub_portfolios

