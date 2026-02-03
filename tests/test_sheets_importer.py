"""Tests for sheets_importer module."""

import pytest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from wpm.models import Asset, Trade, ValidationError
from wpm.sheets_importer import (
    get_sheets_service,
    get_drive_service,
    resolve_spreadsheet_id,
    sheet_to_dataframe,
    import_trades_from_sheet,
    list_sheet_names,
    import_sheets_workbook,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_credentials_path(tmp_path):
    """Create a temporary credentials file."""
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"type": "service_account"}')
    return str(creds_file)


@pytest.fixture
def sample_sheet_data():
    """Sample valid sheet data for testing."""
    return [
        ["Date", "Asset Name/Ticker", "Asset Type", "Action", "Broker", "Price", "Currency", "Quantity"],
        ["2024-01-15", "GOOG", "Stock", "Buy", "IBKR", "150.00", "USD", "10"],
        ["2024-02-15", "AAPL", "Stock", "Buy", "IBKR", "175.00", "USD", "5"],
    ]


@pytest.fixture
def sample_sheet_df():
    """Sample DataFrame representing sheet data."""
    return pd.DataFrame({
        "Date": ["2024-01-15", "2024-02-15"],
        "Asset Name/Ticker": ["GOOG", "AAPL"],
        "Asset Type": ["Stock", "Stock"],
        "Action": ["Buy", "Buy"],
        "Broker": ["IBKR", "IBKR"],
        "Price": ["150.00", "175.00"],
        "Currency": ["USD", "USD"],
        "Quantity": ["10", "5"],
    })


# =============================================================================
# Tests for get_sheets_service()
# =============================================================================

@patch('wpm.sheets_importer.build')
@patch('wpm.sheets_importer.service_account.Credentials')
def test_get_sheets_service_with_credentials_path(mock_creds_class, mock_build, mock_credentials_path):
    """Test get_sheets_service with explicit credentials path."""
    mock_credentials = Mock()
    mock_creds_class.from_service_account_file.return_value = mock_credentials
    mock_service = Mock()
    mock_build.return_value = mock_service
    
    result = get_sheets_service(credentials_path=mock_credentials_path)
    
    mock_creds_class.from_service_account_file.assert_called_once()
    mock_build.assert_called_once_with("sheets", "v4", credentials=mock_credentials)
    assert result == mock_service


@patch('wpm.sheets_importer.build')
@patch('wpm.sheets_importer.service_account.Credentials')
@patch('wpm.sheets_importer.Config')
def test_get_sheets_service_with_config(mock_config_class, mock_creds_class, mock_build, mock_credentials_path):
    """Test get_sheets_service uses Config.GOOGLE_SHEETS_CREDENTIALS_PATH when path not provided."""
    mock_config_class.GOOGLE_SHEETS_CREDENTIALS_PATH = mock_credentials_path
    mock_credentials = Mock()
    mock_creds_class.from_service_account_file.return_value = mock_credentials
    mock_service = Mock()
    mock_build.return_value = mock_service
    
    result = get_sheets_service()
    
    mock_creds_class.from_service_account_file.assert_called_once()
    mock_build.assert_called_once_with("sheets", "v4", credentials=mock_credentials)
    assert result == mock_service


@patch('wpm.sheets_importer.Config')
def test_get_sheets_service_missing_config(mock_config_class):
    """Test get_sheets_service raises ValidationError when credentials not configured."""
    mock_config_class.GOOGLE_SHEETS_CREDENTIALS_PATH = None
    
    with pytest.raises(ValidationError, match="credentials path not configured"):
        get_sheets_service()


def test_get_sheets_service_missing_file():
    """Test get_sheets_service raises ValidationError when credentials file not found."""
    with pytest.raises(ValidationError, match="Credentials file not found"):
        get_sheets_service(credentials_path="/nonexistent/path/credentials.json")


@patch('wpm.sheets_importer.HAS_GOOGLE_SHEETS', False)
def test_get_sheets_service_import_error():
    """Test get_sheets_service raises ImportError when Google API libraries not installed."""
    with pytest.raises(ImportError, match="google-api-python-client"):
        get_sheets_service(credentials_path="/fake/path.json")


# =============================================================================
# Tests for get_drive_service()
# =============================================================================

@patch('wpm.sheets_importer.build')
@patch('wpm.sheets_importer.service_account.Credentials')
def test_get_drive_service_with_credentials_path(mock_creds_class, mock_build, mock_credentials_path):
    """Test get_drive_service with explicit credentials path."""
    mock_credentials = Mock()
    mock_creds_class.from_service_account_file.return_value = mock_credentials
    mock_service = Mock()
    mock_build.return_value = mock_service
    
    result = get_drive_service(credentials_path=mock_credentials_path)
    
    mock_creds_class.from_service_account_file.assert_called_once()
    mock_build.assert_called_once_with("drive", "v3", credentials=mock_credentials)
    assert result == mock_service


@patch('wpm.sheets_importer.build')
@patch('wpm.sheets_importer.service_account.Credentials')
@patch('wpm.sheets_importer.Config')
def test_get_drive_service_with_config(mock_config_class, mock_creds_class, mock_build, mock_credentials_path):
    """Test get_drive_service uses Config.GOOGLE_SHEETS_CREDENTIALS_PATH when path not provided."""
    mock_config_class.GOOGLE_SHEETS_CREDENTIALS_PATH = mock_credentials_path
    mock_credentials = Mock()
    mock_creds_class.from_service_account_file.return_value = mock_credentials
    mock_service = Mock()
    mock_build.return_value = mock_service
    
    result = get_drive_service()
    
    mock_creds_class.from_service_account_file.assert_called_once()
    mock_build.assert_called_once_with("drive", "v3", credentials=mock_credentials)
    assert result == mock_service


@patch('wpm.sheets_importer.Config')
def test_get_drive_service_missing_config(mock_config_class):
    """Test get_drive_service raises ValidationError when credentials not configured."""
    mock_config_class.GOOGLE_SHEETS_CREDENTIALS_PATH = None
    
    with pytest.raises(ValidationError, match="credentials path not configured"):
        get_drive_service()


def test_get_drive_service_missing_file():
    """Test get_drive_service raises ValidationError when credentials file not found."""
    with pytest.raises(ValidationError, match="Credentials file not found"):
        get_drive_service(credentials_path="/nonexistent/path/credentials.json")


@patch('wpm.sheets_importer.HAS_GOOGLE_SHEETS', False)
def test_get_drive_service_import_error():
    """Test get_drive_service raises ImportError when Google API libraries not installed."""
    with pytest.raises(ImportError, match="google-api-python-client"):
        get_drive_service(credentials_path="/fake/path.json")


# =============================================================================
# Tests for resolve_spreadsheet_id()
# =============================================================================

@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_direct_id(mock_get_drive_service):
    """Test resolve_spreadsheet_id returns direct spreadsheet ID."""
    result = resolve_spreadsheet_id(spreadsheet_id="abc123")
    assert result == "abc123"
    mock_get_drive_service.assert_not_called()


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_drive_path_single_folder(mock_get_drive_service):
    """Test resolve_spreadsheet_id resolves Drive path with single folder."""
    mock_service = Mock()
    mock_get_drive_service.return_value = mock_service
    
    # Mock folder query
    mock_folder_response = {"files": [{"id": "folder_123", "name": "Trades"}]}
    
    # Mock spreadsheet query
    mock_sheet_response = {"files": [{"id": "sheet_456", "name": "Portfolio"}]}
    
    mock_service.files().list().execute.side_effect = [mock_folder_response, mock_sheet_response]
    
    result = resolve_spreadsheet_id(drive_path="Trades/Portfolio", credentials_path="/fake/creds.json")
    
    assert result == "sheet_456"


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_drive_path_nested(mock_get_drive_service):
    """Test resolve_spreadsheet_id resolves nested Drive path."""
    mock_service = Mock()
    mock_get_drive_service.return_value = mock_service
    
    # Mock nested folder queries
    mock_folder1_response = {"files": [{"id": "folder_1", "name": "Data"}]}
    mock_folder2_response = {"files": [{"id": "folder_2", "name": "2024"}]}
    mock_sheet_response = {"files": [{"id": "sheet_789", "name": "Trades"}]}
    
    mock_service.files().list().execute.side_effect = [
        mock_folder1_response,
        mock_folder2_response,
        mock_sheet_response
    ]
    
    result = resolve_spreadsheet_id(drive_path="Data/2024/Trades", credentials_path="/fake/creds.json")
    
    assert result == "sheet_789"


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_folder_not_found(mock_get_drive_service):
    """Test resolve_spreadsheet_id raises ValidationError when folder not found."""
    mock_service = Mock()
    mock_get_drive_service.return_value = mock_service
    
    # Mock empty folder response
    mock_service.files().list().execute.return_value = {"files": []}
    
    with pytest.raises(ValidationError, match="Folder not found"):
        resolve_spreadsheet_id(drive_path="Nonexistent/Sheet", credentials_path="/fake/creds.json")


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_multiple_folders(mock_get_drive_service):
    """Test resolve_spreadsheet_id raises ValidationError when multiple folders match."""
    mock_service = Mock()
    mock_get_drive_service.return_value = mock_service
    
    # Mock multiple folder matches
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": "folder_1", "name": "Trades"},
            {"id": "folder_2", "name": "Trades"},
        ]
    }
    
    with pytest.raises(ValidationError, match="Multiple folders match"):
        resolve_spreadsheet_id(drive_path="Trades/Sheet", credentials_path="/fake/creds.json")


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_spreadsheet_not_found(mock_get_drive_service):
    """Test resolve_spreadsheet_id raises ValidationError when spreadsheet not found."""
    mock_service = Mock()
    mock_get_drive_service.return_value = mock_service
    
    # Mock folder found but spreadsheet not found
    mock_folder_response = {"files": [{"id": "folder_123", "name": "Trades"}]}
    mock_empty_response = {"files": []}
    
    mock_service.files().list().execute.side_effect = [mock_folder_response, mock_empty_response]
    
    with pytest.raises(ValidationError, match="Spreadsheet not found"):
        resolve_spreadsheet_id(drive_path="Trades/MissingSheet", credentials_path="/fake/creds.json")


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_multiple_spreadsheets(mock_get_drive_service):
    """Test resolve_spreadsheet_id raises ValidationError when multiple spreadsheets match."""
    mock_service = Mock()
    mock_get_drive_service.return_value = mock_service
    
    # Mock folder found but multiple spreadsheets match
    mock_folder_response = {"files": [{"id": "folder_123", "name": "Trades"}]}
    mock_multi_response = {
        "files": [
            {"id": "sheet_1", "name": "Portfolio"},
            {"id": "sheet_2", "name": "Portfolio"},
        ]
    }
    
    mock_service.files().list().execute.side_effect = [mock_folder_response, mock_multi_response]
    
    with pytest.raises(ValidationError, match="Multiple spreadsheets match"):
        resolve_spreadsheet_id(drive_path="Trades/Portfolio", credentials_path="/fake/creds.json")


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_drive_takes_priority(mock_get_drive_service):
    """Test resolve_spreadsheet_id prioritizes drive_path over spreadsheet_id."""
    mock_service = Mock()
    mock_get_drive_service.return_value = mock_service
    
    mock_sheet_response = {"files": [{"id": "from_drive", "name": "Sheet"}]}
    mock_service.files().list().execute.return_value = mock_sheet_response
    
    result = resolve_spreadsheet_id(
        drive_path="Folder/Sheet",
        spreadsheet_id="direct_id",
        credentials_path="/fake/creds.json"
    )
    
    # Should resolve via Drive path, not return direct ID
    assert result == "from_drive"


def test_resolve_spreadsheet_id_neither_provided():
    """Test resolve_spreadsheet_id raises ValidationError when neither path nor ID provided."""
    with pytest.raises(ValidationError, match="drive_path or spreadsheet_id must be provided"):
        resolve_spreadsheet_id()


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_invalid_path(mock_get_drive_service):
    """Test resolve_spreadsheet_id raises ValidationError for invalid path."""
    with pytest.raises(ValidationError, match="Invalid drive path"):
        resolve_spreadsheet_id(drive_path="///", credentials_path="/fake/creds.json")


@patch('wpm.sheets_importer.get_drive_service')
def test_resolve_spreadsheet_id_api_error(mock_get_drive_service):
    """Test resolve_spreadsheet_id handles Drive API errors."""
    mock_service = Mock()
    mock_get_drive_service.return_value = mock_service
    mock_service.files().list().execute.side_effect = Exception("API Error")
    
    with pytest.raises(ValidationError, match="Error querying Drive API"):
        resolve_spreadsheet_id(drive_path="Folder/Sheet", credentials_path="/fake/creds.json")


# =============================================================================
# Tests for sheet_to_dataframe()
# =============================================================================

def test_sheet_to_dataframe_valid(sample_sheet_data):
    """Test sheet_to_dataframe with valid sheet data."""
    mock_service = Mock()
    
    # Mock the sheets API response
    mock_response = {"values": sample_sheet_data}
    mock_service.spreadsheets().values().get().execute.return_value = mock_response
    
    result = sheet_to_dataframe(mock_service, "spreadsheet_123", "Trades")
    
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert list(result.columns) == sample_sheet_data[0]
    assert result.iloc[0]["Asset Name/Ticker"] == "GOOG"
    assert result.iloc[1]["Asset Name/Ticker"] == "AAPL"


def test_sheet_to_dataframe_empty():
    """Test sheet_to_dataframe raises ValidationError for empty sheet."""
    mock_service = Mock()
    mock_service.spreadsheets().values().get().execute.return_value = {"values": []}
    
    with pytest.raises(ValidationError, match="is empty or not found"):
        sheet_to_dataframe(mock_service, "spreadsheet_123", "EmptySheet")


def test_sheet_to_dataframe_headers_only():
    """Test sheet_to_dataframe raises ValidationError for sheet with only headers."""
    mock_service = Mock()
    mock_service.spreadsheets().values().get().execute.return_value = {
        "values": [["Date", "Asset Name/Ticker", "Asset Type"]]
    }
    
    with pytest.raises(ValidationError, match="has headers but no data"):
        sheet_to_dataframe(mock_service, "spreadsheet_123", "HeadersOnly")


def test_sheet_to_dataframe_api_error():
    """Test sheet_to_dataframe handles API errors."""
    mock_service = Mock()
    mock_service.spreadsheets().values().get().execute.side_effect = Exception("API Error")
    
    with pytest.raises(ValidationError, match="Error fetching sheet"):
        sheet_to_dataframe(mock_service, "spreadsheet_123", "ErrorSheet")


# =============================================================================
# Tests for import_trades_from_sheet()
# =============================================================================

@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
def test_import_trades_from_sheet_valid(mock_get_sheets_service, mock_sheet_to_df, sample_sheet_df):
    """Test import_trades_from_sheet with valid data."""
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    mock_sheet_to_df.return_value = sample_sheet_df
    
    trades = import_trades_from_sheet("spreadsheet_123", "Trades", credentials_path="/fake/creds.json")
    
    assert len(trades) == 2
    assert all(isinstance(t, Trade) for t in trades)
    assert trades[0].asset.ticker == "GOOG"
    assert trades[0].action == "Buy"
    assert trades[0].quantity == Decimal("10")
    assert trades[1].asset.ticker == "AAPL"


@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
def test_import_trades_from_sheet_with_end_date(mock_get_sheets_service, mock_sheet_to_df):
    """Test import_trades_from_sheet filters by end_date."""
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    
    # Create DataFrame with trades on different dates
    df = pd.DataFrame({
        "Date": ["2024-01-15", "2024-03-15", "2024-02-15"],
        "Asset Name/Ticker": ["GOOG", "AAPL", "MSFT"],
        "Asset Type": ["Stock", "Stock", "Stock"],
        "Action": ["Buy", "Buy", "Buy"],
        "Broker": ["IBKR", "IBKR", "IBKR"],
        "Price": ["150.00", "175.00", "200.00"],
        "Currency": ["USD", "USD", "USD"],
        "Quantity": ["10", "5", "8"],
    })
    mock_sheet_to_df.return_value = df
    
    end_date = date(2024, 2, 20)
    trades = import_trades_from_sheet("spreadsheet_123", "Trades", end_date=end_date)
    
    # Should only get trades on or before 2024-02-20
    assert len(trades) == 2
    assert all(t.date <= end_date for t in trades)


@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
def test_import_trades_from_sheet_missing_columns(mock_get_sheets_service, mock_sheet_to_df):
    """Test import_trades_from_sheet raises ValidationError for missing columns."""
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    
    # DataFrame missing required columns
    df = pd.DataFrame({
        "Date": ["2024-01-15"],
        "Asset Name/Ticker": ["GOOG"],
        # Missing other required columns
    })
    mock_sheet_to_df.return_value = df
    
    with pytest.raises(ValidationError, match="Missing required columns"):
        import_trades_from_sheet("spreadsheet_123", "Trades")


@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
def test_import_trades_from_sheet_invalid_data(mock_get_sheets_service, mock_sheet_to_df):
    """Test import_trades_from_sheet with some invalid data rows."""
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    
    # DataFrame with one valid and one invalid row
    df = pd.DataFrame({
        "Date": ["2024-01-15", "invalid-date"],
        "Asset Name/Ticker": ["GOOG", "AAPL"],
        "Asset Type": ["Stock", "Stock"],
        "Action": ["Buy", "Buy"],
        "Broker": ["IBKR", "IBKR"],
        "Price": ["150.00", "175.00"],
        "Currency": ["USD", "USD"],
        "Quantity": ["10", "5"],
    })
    mock_sheet_to_df.return_value = df
    
    trades = import_trades_from_sheet("spreadsheet_123", "Trades")
    
    # Should still get the valid trade
    assert len(trades) == 1
    assert trades[0].asset.ticker == "GOOG"


@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
def test_import_trades_from_sheet_all_invalid(mock_get_sheets_service, mock_sheet_to_df):
    """Test import_trades_from_sheet raises ValidationError when all rows invalid."""
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    
    # DataFrame with all invalid rows
    df = pd.DataFrame({
        "Date": ["invalid-date", "another-invalid"],
        "Asset Name/Ticker": ["GOOG", "AAPL"],
        "Asset Type": ["Stock", "Stock"],
        "Action": ["Buy", "Buy"],
        "Broker": ["IBKR", "IBKR"],
        "Price": ["150.00", "175.00"],
        "Currency": ["USD", "USD"],
        "Quantity": ["10", "5"],
    })
    mock_sheet_to_df.return_value = df
    
    with pytest.raises(ValidationError, match="No valid trades found"):
        import_trades_from_sheet("spreadsheet_123", "Trades")


# =============================================================================
# Tests for list_sheet_names()
# =============================================================================

@patch('wpm.sheets_importer.get_sheets_service')
def test_list_sheet_names(mock_get_sheets_service):
    """Test list_sheet_names returns all sheet names."""
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    
    # Mock spreadsheet metadata
    mock_response = {
        "sheets": [
            {"properties": {"title": "Trades"}},
            {"properties": {"title": "Positions"}},
            {"properties": {"title": "Summary"}},
        ]
    }
    mock_service.spreadsheets().get().execute.return_value = mock_response
    
    result = list_sheet_names("spreadsheet_123", credentials_path="/fake/creds.json")
    
    assert result == ["Trades", "Positions", "Summary"]


@patch('wpm.sheets_importer.get_sheets_service')
def test_list_sheet_names_empty(mock_get_sheets_service):
    """Test list_sheet_names returns empty list for spreadsheet with no sheets."""
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    
    mock_response = {"sheets": []}
    mock_service.spreadsheets().get().execute.return_value = mock_response
    
    result = list_sheet_names("spreadsheet_123")
    
    assert result == []


@patch('wpm.sheets_importer.get_sheets_service')
def test_list_sheet_names_api_error(mock_get_sheets_service):
    """Test list_sheet_names handles API errors."""
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    mock_service.spreadsheets().get().execute.side_effect = Exception("API Error")
    
    with pytest.raises(ValidationError, match="Error fetching spreadsheet"):
        list_sheet_names("spreadsheet_123")


# =============================================================================
# Tests for import_sheets_workbook()
# =============================================================================

@patch('wpm.sheets_importer.import_trades_from_sheet')
@patch('wpm.sheets_importer.list_sheet_names')
@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
def test_import_sheets_workbook_all_valid(mock_get_sheets_service, mock_sheet_to_df, mock_list_sheet_names, mock_import_trades, mock_credentials_path, sample_sheet_df):
    """Test import_sheets_workbook with all valid sheets."""
    from wpm.portfolio import CompositePortfolio, SimplePortfolio
    
    mock_list_sheet_names.return_value = ["Sheet1", "Sheet2"]
    mock_get_sheets_service.return_value = Mock()
    mock_sheet_to_df.return_value = sample_sheet_df
    
    # Mock trades for each sheet
    trade1 = Trade(
        date=date(2024, 1, 15),
        asset=Asset(ticker="GOOG", asset_type="Stock"),
        action="Buy",
        broker="IBKR",
        currency="USD",
        price=150.0,
        price_native=150.0,
        quantity=Decimal("10"),
    )
    trade2 = Trade(
        date=date(2024, 2, 15),
        asset=Asset(ticker="AAPL", asset_type="Stock"),
        action="Buy",
        broker="IBKR",
        currency="USD",
        price=175.0,
        price_native=175.0,
        quantity=Decimal("5"),
    )
    
    mock_import_trades.side_effect = [[trade1], [trade2]]
    
    result = import_sheets_workbook("spreadsheet_123", credentials_path=mock_credentials_path)
    
    assert isinstance(result, CompositePortfolio)
    assert result.name == "Composite"
    assert result.is_historical == False
    # Should have 2 sub-portfolios
    all_trades = result.get_all_trades()
    assert len(all_trades) == 2


@patch('wpm.sheets_importer.import_trades_from_sheet')
@patch('wpm.sheets_importer.list_sheet_names')
@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
def test_import_sheets_workbook_with_end_date(mock_get_sheets_service, mock_sheet_to_df, mock_list_sheet_names, mock_import_trades, mock_credentials_path, sample_sheet_df):
    """Test import_sheets_workbook with end_date marks portfolios as historical."""
    from wpm.portfolio import CompositePortfolio
    
    mock_list_sheet_names.return_value = ["Sheet1"]
    mock_get_sheets_service.return_value = Mock()
    mock_sheet_to_df.return_value = sample_sheet_df
    
    trade = Trade(
        date=date(2024, 1, 15),
        asset=Asset(ticker="GOOG", asset_type="Stock"),
        action="Buy",
        broker="IBKR",
        currency="USD",
        price=150.0,
        price_native=150.0,
        quantity=Decimal("10"),
    )
    
    mock_import_trades.return_value = [trade]
    
    end_date = date(2024, 6, 30)
    result = import_sheets_workbook("spreadsheet_123", credentials_path=mock_credentials_path, end_date=end_date)
    
    assert isinstance(result, CompositePortfolio)
    assert result.is_historical == True


@patch('wpm.sheets_importer.list_sheet_names')
def test_import_sheets_workbook_no_sheets(mock_list_sheet_names):
    """Test import_sheets_workbook raises ValidationError when no sheets found."""
    mock_list_sheet_names.return_value = []
    
    with pytest.raises(ValidationError, match="No sheets found"):
        import_sheets_workbook("spreadsheet_123")


@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
@patch('wpm.sheets_importer.list_sheet_names')
def test_import_sheets_workbook_fail_fast(mock_list_sheet_names, mock_get_sheets_service, mock_sheet_to_df):
    """Test import_sheets_workbook fails fast when one sheet is invalid."""
    mock_list_sheet_names.return_value = ["ValidSheet", "InvalidSheet"]
    
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    
    # First sheet valid, second sheet invalid (missing columns)
    valid_df = pd.DataFrame({
        "Date": ["2024-01-15"],
        "Asset Name/Ticker": ["GOOG"],
        "Asset Type": ["Stock"],
        "Action": ["Buy"],
        "Broker": ["IBKR"],
        "Price": ["150.00"],
        "Currency": ["USD"],
        "Quantity": ["10"],
    })
    invalid_df = pd.DataFrame({
        "Date": ["2024-01-15"],
        # Missing required columns
    })
    
    mock_sheet_to_df.side_effect = [valid_df, invalid_df]
    
    # Should fail during pre-validation phase
    with pytest.raises(ValidationError, match="Missing required columns"):
        import_sheets_workbook("spreadsheet_123")


@patch('wpm.sheets_importer.sheet_to_dataframe')
@patch('wpm.sheets_importer.get_sheets_service')
@patch('wpm.sheets_importer.list_sheet_names')
def test_import_sheets_workbook_prevalidation_error(mock_list_sheet_names, mock_get_sheets_service, mock_sheet_to_df):
    """Test import_sheets_workbook pre-validates all sheets before importing."""
    mock_list_sheet_names.return_value = ["Sheet1", "Sheet2"]
    
    mock_service = Mock()
    mock_get_sheets_service.return_value = mock_service
    
    # Both sheets valid
    valid_df = pd.DataFrame({
        "Date": ["2024-01-15"],
        "Asset Name/Ticker": ["GOOG"],
        "Asset Type": ["Stock"],
        "Action": ["Buy"],
        "Broker": ["IBKR"],
        "Price": ["150.00"],
        "Currency": ["USD"],
        "Quantity": ["10"],
    })
    
    mock_sheet_to_df.return_value = valid_df
    
    # Should succeed - both sheets pass pre-validation
    result = import_sheets_workbook("spreadsheet_123")
    
    assert result is not None
    # Should have called sheet_to_dataframe twice for pre-validation
    assert mock_sheet_to_df.call_count >= 2
