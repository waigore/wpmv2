# WPMv2 Library Study Notes & Google Sheets Integration Plan

## Library Overview

**WPM (Wealth Portfolio Manager)** is a Python library for managing and analyzing financial portfolios. It tracks asset positions across multiple portfolios, calculates FIFO cost basis, fetches market prices, and generates portfolio metrics.

## Current Architecture

### Core Data Flow
```
CSV Files → importer.py → Trade objects → Portfolio → Positions/Lots → Metrics
```

### Key Modules

1. **wpm/models.py** - Core data structures
   - `Asset`: ticker + asset_type (Stock/ETF/Crypto)
   - `Trade`: buy/sell transaction with date, price, quantity, broker
   - `Position`: current holdings (quantity, cost_basis)
   - `Lot`: purchase record with FIFO sell matching
   - `Portfolio`: SimplePortfolio (trades) or CompositePortfolio (sub-portfolios)

2. **wpm/importer.py** - CSV import functionality
   - `import_trades_from_csv()`: Parses CSV → List[Trade]
   - `import_csv_files()`: Imports directory of CSVs → CompositePortfolio
   - Required columns: Date, Asset Name/Ticker, Asset Type, Action, Broker, Price, Currency, Quantity
   - Optional: Order Instruction, Trade Type

3. **wpm/portfolio.py** - Portfolio management
   - SimplePortfolio: holds trades, calculates positions via FIFO
   - CompositePortfolio: aggregates sub-portfolios
   - Historical portfolio support (is_historical flag)

4. **wpm/pricing/** - Price retrieval
   - Yahoo Finance for stocks/ETFs
   - CoinGecko for crypto (current), yfinance for historical crypto
   - Parquet-based caching with 10-min validity

5. **wpm/cost_basis.py** - FIFO calculations
   - `calculate_lots_from_trades()`: Creates lots with FIFO matching
   - Broker-scoped matching (sells only match buys from same broker)

6. **wpm/currency.py** - Currency conversion
   - Uses yfinance for forex rates
   - Caches rates with 24-hour validity

7. **wpm/metrics.py** - Portfolio analysis
   - Breakdowns by asset type, ticker, broker, purchase period
   - Allocation calculations

8. **wpm/reference/** - Reference portfolios
   - Create baseline comparison portfolios (e.g., SPY buy-and-hold)

### CSV Import Format

```csv
Date,Asset Name/Ticker,Asset Type,Action,Broker,Order Instruction,Trade Type,Price,Currency,Quantity
2024-01-15,AAPL,Stock,Buy,IBKR,Market,Discretionary,150.00,USD,10
```

## Google Sheets Integration Plan

### Goal
Allow direct import from Google Sheets instead of CSV files, supporting:
- One sheet per broker/asset type (as user described)
- Direct Google Workspace API integration
- Same data validation as CSV import

### Implementation Strategy

#### Option 1: New `wpm/sheets_importer.py` Module (Recommended)

Create a parallel import path that mirrors CSV import but sources from Google Sheets:

```python
# wpm/sheets_importer.py
from wpm.importer import parse_trade_row, validate_dataframe_structure

def import_trades_from_sheet(
    spreadsheet_id: str,
    sheet_name: str,
    credentials_path: Optional[str] = None,
    currency_service: CurrencyService = None,
    end_date: Optional[date] = None
) -> List[Trade]:
    """Import trades from a single Google Sheet."""
    
def import_sheets_workbook(
    spreadsheet_id: str,
    credentials_path: Optional[str] = None,
    sheet_filter: Optional[List[str]] = None,
    end_date: Optional[date] = None
) -> CompositePortfolio:
    """Import all sheets from a workbook as sub-portfolios."""
```

#### Key Design Decisions

1. **Sheet-to-Portfolio Mapping**
   - Each sheet → One SimplePortfolio (like CSV files)
   - Sheet name becomes portfolio name
   - All sheets aggregated into CompositePortfolio

2. **Google Sheets API Integration**
   - Use `google-api-python-client` and `google-auth`
   - Service account authentication (JSON credentials file)
   - OAuth2 for user authentication (alternative)

3. **Data Validation**
   - Reuse existing `parse_trade_row()` logic
   - Validate same required columns as CSV
   - Handle empty rows gracefully

4. **Configuration**
   - Add to `wpm/config.py`:
     - `GOOGLE_SHEETS_CREDENTIALS_PATH`
     - `GOOGLE_SHEETS_TOKEN_PATH` (for OAuth)

### Implementation Steps

#### Step 1: Dependencies
Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing deps ...
    "google-api-python-client>=2.100.0",
    "google-auth>=2.20.0",
    "google-auth-oauthlib>=1.0.0",
]
```

#### Step 2: Create `wpm/sheets_importer.py`

```python
"""Google Sheets import functionality."""

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

from wpm.currency import CurrencyService
from wpm.importer import parse_trade_row, validate_csv_structure
from wpm.models import Trade, ValidationError
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.config import Config

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def get_sheets_service(credentials_path: Optional[str] = None):
    """Create Google Sheets API service."""
    creds_path = credentials_path or Config.GOOGLE_SHEETS_CREDENTIALS_PATH
    
    if not creds_path or not Path(creds_path).exists():
        raise ValidationError(
            f"Google Sheets credentials not found at {creds_path}. "
            "Set GOOGLE_SHEETS_CREDENTIALS_PATH in .env or pass credentials_path."
        )
    
    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )
    return build('sheets', 'v4', credentials=credentials)


def sheet_to_dataframe(service, spreadsheet_id: str, sheet_name: str) -> pd.DataFrame:
    """Fetch a sheet and convert to DataFrame."""
    range_name = f"{sheet_name}!A:Z"  # Fetch all columns
    
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    
    values = result.get('values', [])
    if not values:
        raise ValidationError(f"Sheet '{sheet_name}' is empty")
    
    # First row is headers
    headers = values[0]
    data = values[1:]
    
    return pd.DataFrame(data, columns=headers)


def import_trades_from_sheet(
    spreadsheet_id: str,
    sheet_name: str,
    credentials_path: Optional[str] = None,
    currency_service: CurrencyService = None,
    end_date: Optional[date] = None
) -> List[Trade]:
    """Import trades from a Google Sheet."""
    logger.info(f"Importing from sheet '{sheet_name}' in spreadsheet '{spreadsheet_id}'")
    
    service = get_sheets_service(credentials_path)
    df = sheet_to_dataframe(service, spreadsheet_id, sheet_name)
    
    # Reuse existing validation
    validate_csv_structure(df)
    
    # Parse trades (reuse CSV logic)
    if currency_service is None:
        currency_service = CurrencyService()
    
    trades = []
    errors = []
    
    for idx, row in df.iterrows():
        try:
            trade = parse_trade_row(row, currency_service)
            if end_date is not None and trade.date > end_date:
                continue
            trades.append(trade)
        except ValidationError as e:
            errors.append(f"Row {idx + 1}: {str(e)}")
    
    if errors:
        logger.warning(f"Encountered {len(errors)} validation errors")
    
    logger.info(f"Successfully imported {len(trades)} trades from sheet '{sheet_name}'")
    return trades


def list_sheets(service, spreadsheet_id: str) -> List[str]:
    """List all sheet names in a spreadsheet."""
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()
    
    return [sheet['properties']['title'] for sheet in spreadsheet['sheets']]


def import_sheets_workbook(
    spreadsheet_id: str,
    credentials_path: Optional[str] = None,
    sheet_filter: Optional[List[str]] = None,
    end_date: Optional[date] = None
) -> CompositePortfolio:
    """Import all sheets from a workbook as sub-portfolios."""
    logger.info(f"Importing workbook: {spreadsheet_id}")
    
    service = get_sheets_service(credentials_path)
    sheet_names = list_sheets(service, spreadsheet_id)
    
    if sheet_filter:
        sheet_names = [s for s in sheet_names if s in sheet_filter]
    
    logger.info(f"Found {len(sheet_names)} sheet(s): {', '.join(sheet_names)}")
    
    is_historical = end_date is not None
    composite = CompositePortfolio("Composite", is_historical=is_historical)
    
    currency_service = CurrencyService()
    
    for sheet_name in sheet_names:
        try:
            trades = import_trades_from_sheet(
                spreadsheet_id, sheet_name, credentials_path,
                currency_service, end_date
            )
            
            portfolio = SimplePortfolio(sheet_name, is_historical=is_historical)
            for trade in trades:
                portfolio.add_trade(trade)
            
            composite.add_sub_portfolio(portfolio)
            logger.info(f"Added portfolio '{sheet_name}' with {len(trades)} trades")
            
        except Exception as e:
            logger.error(f"Failed to import sheet '{sheet_name}': {e}")
            raise
    
    return composite
```

#### Step 3: Update `wpm/config.py`

```python
class Config:
    # ... existing config ...
    
    # Google Sheets Configuration
    GOOGLE_SHEETS_CREDENTIALS_PATH: Optional[str] = os.getenv(
        'GOOGLE_SHEETS_CREDENTIALS_PATH'
    )
```

#### Step 4: Update `wpm/__init__.py`

```python
# Add to public API
from wpm.sheets_importer import (
    import_trades_from_sheet,
    import_sheets_workbook,
)
```

#### Step 5: CLI Integration (Optional)

Add to `wpm/cli/`:
```python
# New command: wpm import-sheets <spreadsheet_id>
# Or: wpm import --source sheets --id <spreadsheet_id>
```

### Authentication Setup

#### Service Account (Recommended for automation)

1. Create service account in Google Cloud Console
2. Download JSON key file
3. Share Google Sheet with service account email (viewer access)
4. Set `GOOGLE_SHEETS_CREDENTIALS_PATH=/path/to/service-account.json`

#### OAuth2 (For user interactive use)

1. Create OAuth2 credentials in Google Cloud Console
2. Download client secrets
3. First run triggers browser auth flow
4. Token stored for subsequent runs

### Usage Examples

```python
from wpm import import_sheets_workbook

# Import entire workbook (each sheet = one portfolio)
portfolio = import_sheets_workbook(
    spreadsheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
)

# Import specific sheets only
portfolio = import_sheets_workbook(
    spreadsheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
    sheet_filter=["IBKR", "Fidelity"]  # Only these sheets
)

# Import with historical end date
portfolio = import_sheets_workbook(
    spreadsheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
    end_date=date(2024, 12, 31)
)
```

### Testing Considerations

1. Mock Google Sheets API responses
2. Test empty sheets, missing columns, invalid data
3. Test authentication failures
4. Test rate limiting (Google Sheets API quotas)

### Alternative: Unified Importer Interface

Consider refactoring to a unified importer interface:

```python
# wpm/importers/base.py
from abc import ABC, abstractmethod

class TradeImporter(ABC):
    @abstractmethod
    def import_trades(self) -> List[Trade]:
        pass

# wpm/importers/csv.py
class CSVImporter(TradeImporter): ...

# wpm/importers/sheets.py  
class SheetsImporter(TradeImporter): ...
```

This would allow:
```python
from wpm.importers import CSVImporter, SheetsImporter

# Same interface, different sources
importer = SheetsImporter(spreadsheet_id="...")
trades = importer.import_trades()
```

### Benefits of This Approach

1. **Minimal code duplication**: Reuses `parse_trade_row()` validation
2. **Consistent API**: Same Trade/Portfolio objects regardless of source
3. **Flexible**: Supports both single-sheet and full-workbook import
4. **Configurable**: Credentials via env var or parameter
5. **Maintainable**: Clear separation of concerns

## Summary

The WPMv2 library has a clean, modular architecture that makes extending it straightforward. The CSV import logic in `wpm/importer.py` is well-structured and can be reused for Google Sheets integration by:

1. Creating a new `wpm/sheets_importer.py` module
2. Fetching sheets via Google Sheets API
3. Converting to DataFrame (same format as CSV)
4. Reusing existing `parse_trade_row()` for validation
5. Creating portfolios same way as CSV import

The key insight is that both CSV and Sheets imports converge at the DataFrame level, allowing maximum code reuse while adding minimal complexity.
