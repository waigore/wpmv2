# Google Sheets Integration Specification

## Overview

Extend WPM to support importing trade data directly from Google Sheets using service account authentication. Users can configure either a Google Drive file path (user-friendly) or a direct spreadsheet ID in `.env`, then run `wpm import-sheets` to import.

## Design Principles

1. **Follow existing patterns**: Use same Config class, .env loading, and CLI structure as existing code
2. **User-friendly configuration**: Support both Drive file path AND direct spreadsheet ID
3. **Service account auth**: JSON key file path in .env, service account email shares the sheet
4. **Parallel to CSV import**: Same validation, same portfolio creation logic
5. **Minimal changes**: Reuse existing `parse_trade_row()`, `validate_csv_structure()`
6. **Fail-fast**: If any sheet fails to import, the entire operation fails (no partial imports)
7. **Lazy config validation**: Google Sheets config is only validated when `import-sheets` command is run

---

## Configuration (.env)

Add to `.env.example`:

```bash
# Google Sheets Integration (optional)
# Required for 'wpm import-sheets' command
# 
# 1. Create service account: https://console.cloud.google.com/iam-admin/serviceaccounts
# 2. Download JSON key file
# 3. Share your Google Sheet with the service account email (Viewer access)
# 4. Set the path to the JSON key file:
# GOOGLE_SHEETS_CREDENTIALS_PATH=/path/to/service-account-key.json
#
# 5. Configure EITHER a Drive path OR a spreadsheet ID:
#
#    Option A: Google Drive path (recommended, more user-friendly)
#    Format: "Folder/Subfolder/Filename" (omit .gsheet extension)
#    Example: If your sheet is "My Drive/Investments/Trades.gsheet", use:
# GOOGLE_SHEETS_DRIVE_PATH=Investments/Trades
#
#    Option B: Direct spreadsheet ID (from URL)
#    Example: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
# GOOGLE_SHEETS_SPREADSHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
#
# Note: If both are set, GOOGLE_SHEETS_DRIVE_PATH takes precedence
# The service account must have access to the sheet via sharing
```

---

## Module: wpm/config.py

Add to `Config` class:

```python
# Google Sheets Configuration (loaded from .env)
# These are optional - only validated when import-sheets command is used
GOOGLE_SHEETS_CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
GOOGLE_SHEETS_DRIVE_PATH = os.getenv("GOOGLE_SHEETS_DRIVE_PATH")
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
```

---

## Module: wpm/sheets_importer.py (New)

### Purpose
Import trades from Google Sheets using same validation and parsing as CSV imports.

### Key Functions

#### `get_sheets_service(credentials_path: Optional[str] = None) -> Resource`
Create authenticated Google Sheets API service.

**Raises:**
- `ValidationError`: If credentials not configured or file not found
- `ImportError`: If google-api-python-client not installed

#### `resolve_spreadsheet_id(
    drive_path: Optional[str] = None,
    spreadsheet_id: Optional[str] = None,
    credentials_path: Optional[str] = None
) -> str`
Resolve spreadsheet identifier to spreadsheet ID.

**Priority:**
1. If `drive_path` provided: resolve via Drive API
2. Else if `spreadsheet_id` provided: return as-is
3. Else: raise ValidationError

**Drive Path Resolution Algorithm:**
1. Parse path components (split by "/")
2. Use Drive API to traverse folders:
   - Start from root (`root`)
   - For each folder name: query `mimeType='application/vnd.google-apps.folder' and name='{folder}' and '{parent_id}' in parents`
   - Track folder ID
3. Final component: query `mimeType='application/vnd.google-apps.spreadsheet' and name='{filename}' and '{parent_id}' in parents`
4. Return spreadsheet ID

**Raises:**
- `ValidationError`: If neither path nor ID provided, path not found, multiple matches, or not a spreadsheet

#### `sheet_to_dataframe(service, spreadsheet_id: str, sheet_name: str) -> pd.DataFrame`
Fetch sheet data via Sheets API and convert to DataFrame.

**Implementation:**
- Use `spreadsheets().values().get()` with range `{sheet_name}!A:Z`
- First row = headers, remaining rows = data
- Handle empty cells as empty strings

**Raises:**
- `ValidationError`: If sheet empty or not found

#### `import_trades_from_sheet(
    spreadsheet_id: str,
    sheet_name: str,
    credentials_path: Optional[str] = None,
    currency_service: Optional[CurrencyService] = None,
    end_date: Optional[date] = None
) -> List[Trade]`

Import trades from a single sheet tab.

**Implementation:**
1. Get sheets service
2. Fetch data as DataFrame via `sheet_to_dataframe()`
3. Call `validate_csv_structure(df)` (reuse CSV validation)
4. Iterate rows, call `parse_trade_row(row, currency_service)` (reuse CSV parsing)
5. Filter by `end_date` if provided
6. Return `List[Trade]`

**Raises:**
- `ValidationError`: On structure errors or parsing failures

#### `list_sheet_names(
    spreadsheet_id: str,
    credentials_path: Optional[str] = None
) -> List[str]`

Return all sheet (tab) names in spreadsheet.

#### `import_sheets_workbook(
    spreadsheet_id: str,
    credentials_path: Optional[str] = None,
    end_date: Optional[date] = None
) -> CompositePortfolio`

Import ALL sheets as sub-portfolios, aggregate into CompositePortfolio.

**Fail-Fast Behavior:**
- ALL sheets in the spreadsheet are imported (no filtering option)
- If ANY sheet fails to import (validation error, parsing error, etc.), the ENTIRE operation fails
- No partial portfolios are created on error

**Implementation:**
1. List all sheet names in the spreadsheet
2. Pre-validate: Check all sheets are accessible
3. For each sheet: `import_trades_from_sheet()` → create `SimplePortfolio` → add to composite
4. Return `CompositePortfolio`

**Note:** Each sheet becomes a portfolio named after the sheet tab.

**Raises:**
- `ValidationError`: If any sheet fails validation or parsing

---

## Module: wpm/cli/args.py

Add to `parse_args()`:

```python
parser.add_argument(
    "command",
    choices=["import", "import-sheets"],  # Add import-sheets
    help="Command to execute",
)
```

`--end-date` works with both `import` and `import-sheets`.

**Note:** No `--sheets` filter option - all sheets in the spreadsheet are always imported.

---

## Module: wpm/cli/main.py

Add `import-sheets` command handling:

```python
def main() -> None:
    setup_cli_logging()
    args = parse_args()

    if args.command == "import":
        # Existing CSV import logic
        ...
    
    elif args.command == "import-sheets":
        _handle_import_sheets(args)


def _handle_import_sheets(args) -> None:
    """Handle 'import-sheets' command."""
    from wpm.config import Config
    from wpm.sheets_importer import (
        import_sheets_workbook,
        resolve_spreadsheet_id,
        ValidationError as SheetsValidationError
    )
    
    # Check credentials configuration (required)
    if not Config.GOOGLE_SHEETS_CREDENTIALS_PATH:
        print("Error: GOOGLE_SHEETS_CREDENTIALS_PATH not configured in .env", file=sys.stderr)
        sys.exit(1)
    
    # Check that at least one of drive path or spreadsheet ID is configured
    if not Config.GOOGLE_SHEETS_DRIVE_PATH and not Config.GOOGLE_SHEETS_SPREADSHEET_ID:
        print(
            "Error: Either GOOGLE_SHEETS_DRIVE_PATH or GOOGLE_SHEETS_SPREADSHEET_ID "
            "must be configured in .env",
            file=sys.stderr
        )
        sys.exit(1)
    
    # Parse end_date if provided
    end_date = _parse_end_date(args.end_date)
    
    # Resolve to spreadsheet ID (drive path takes precedence)
    try:
        if Config.GOOGLE_SHEETS_DRIVE_PATH:
            print(f"Resolving Google Drive path: {Config.GOOGLE_SHEETS_DRIVE_PATH}")
        spreadsheet_id = resolve_spreadsheet_id(
            drive_path=Config.GOOGLE_SHEETS_DRIVE_PATH,
            spreadsheet_id=Config.GOOGLE_SHEETS_SPREADSHEET_ID,
            credentials_path=Config.GOOGLE_SHEETS_CREDENTIALS_PATH
        )
        print(f"Using spreadsheet: {spreadsheet_id}")
    except SheetsValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Import ALL sheets from the spreadsheet (fail-fast: any error stops entire import)
    try:
        composite = import_sheets_workbook(
            spreadsheet_id=spreadsheet_id,
            credentials_path=Config.GOOGLE_SHEETS_CREDENTIALS_PATH,
            end_date=end_date
        )
        print(f"Successfully imported {len(composite.sub_portfolios)} sheet(s) from Google Sheets")
        if end_date:
            print(f"Historical portfolio (end_date: {end_date})")
    except SheetsValidationError as e:
        print(f"Import failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Fetch prices (same as CSV import)
    price_service = PriceService()
    fetch_prices_for_portfolio(composite, price_service)
    
    # Create reference portfolios (same as CSV import)
    reference_portfolios = _create_reference_portfolios(composite, price_service)
    
    # Enter interactive mode
    run_interactive_mode(composite, price_service, reference_portfolios)
```

---

## Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing deps ...
    "google-api-python-client>=2.100.0",
    "google-auth>=2.20.0",
]
```

**Note:** These dependencies are installed for all users, but are only imported when `import-sheets` command is used. The `.env` configuration is only validated when the command runs, so users who don't use Google Sheets won't be affected.

---

## CLI Usage

### Basic Usage (Drive Path)

```bash
# .env configured with:
# GOOGLE_SHEETS_CREDENTIALS_PATH=/home/user/.wpm/service-account.json
# GOOGLE_SHEETS_DRIVE_PATH=Investments/Trades

wpm import-sheets
```

### Basic Usage (Spreadsheet ID)

```bash
# .env configured with:
# GOOGLE_SHEETS_CREDENTIALS_PATH=/home/user/.wpm/service-account.json
# GOOGLE_SHEETS_SPREADSHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms

wpm import-sheets
```

### With End Date (Historical)

```bash
wpm import-sheets --end-date 2024-12-31
```

**Note:** All sheets in the spreadsheet are imported. If any sheet has errors, the entire import fails.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Credentials not configured | Exit with error: "GOOGLE_SHEETS_CREDENTIALS_PATH not configured" |
| Neither drive path nor spreadsheet ID configured | Exit with error: "Either GOOGLE_SHEETS_DRIVE_PATH or GOOGLE_SHEETS_SPREADSHEET_ID must be configured" |
| Credentials file not found | Exit with error: "Credentials file not found: {path}" |
| Drive path not found | Exit with error: "Path not found: {path}" |
| Multiple files match path | Exit with error: "Multiple files match path: {path}" |
| **Any sheet fails validation** | **Exit immediately with error - no partial import** |
| **Any sheet fails parsing** | **Exit immediately with error - no partial import** |
| Price fetch failure | Same as CSV import (exit if no cache) |

### Fail-Fast Import Behavior

- All sheets are validated BEFORE any portfolios are created
- If any sheet has structural errors (missing columns, invalid data format), the import stops immediately
- No `CompositePortfolio` is created if any sheet fails
- User sees clear error message indicating which sheet failed and why

---

## Security Considerations

1. **Service account principle of least privilege**: Service account only needs Google Sheets "Viewer" access
2. **Credentials file protection**: User's responsibility to secure JSON key file (chmod 600 recommended)
3. **No credential logging**: Never log credential paths or file contents
4. **.env in .gitignore**: Already handled by existing .gitignore

---

## Sheet Format

Same CSV format as existing import:

| Date | Asset Name/Ticker | Asset Type | Action | Broker | Order Instruction | Trade Type | Price | Currency | Quantity |
|------|------------------|------------|--------|--------|------------------|------------|-------|----------|----------|
| 2024-01-15 | AAPL | Stock | Buy | IBKR | Market | Discretionary | 150.00 | USD | 10 |

**Notes:**
- First row must be headers (exact column names)
- Sheet names become portfolio names
- Optional columns (Order Instruction, Trade Type) can be omitted

---

## Testing Strategy

### Unit Tests (in tests/test_sheets_importer.py)

1. **Mock Google API responses** for Drive and Sheets APIs
2. **Test path resolution:**
   - Single folder path: "Folder/Sheet" → resolves correctly
   - Nested path: "Folder/Subfolder/Sheet" → resolves correctly
   - Direct spreadsheet ID → returned as-is
   - Path not found → raises ValidationError
   - Multiple matches → raises ValidationError
3. **Test sheet import:**
   - Valid sheet → returns List[Trade]
   - Missing required columns → raises ValidationError
   - Invalid data → raises ValidationError (fail-fast)
4. **Test workbook import (fail-fast behavior):**
   - All sheets valid → CompositePortfolio with all sub-portfolios
   - One sheet invalid → raises ValidationError, no portfolio returned
   - Empty spreadsheet → raises ValidationError

### Integration Tests (manual)

1. Create test Google Sheet with sample trades
2. Share with service account
3. Configure .env
4. Run `wpm import-sheets` and verify output matches CSV import

---

## Implementation Phases

### Phase 1: Core Module
- Create `wpm/sheets_importer.py` with core functions
- Add `resolve_drive_path()` using Drive API
- Reuse existing validation/parsing

### Phase 2: Configuration
- Update `wpm/config.py` with new env vars
- Update `.env.example` with documentation

### Phase 3: CLI Integration
- Update `wpm/cli/args.py` with new command
- Update `wpm/cli/main.py` with handler
- Extract common logic (price fetching, ref portfolios) if needed

### Phase 4: Documentation
- Update SPEC/modules.md with sheets_importer module
- Update SPEC/wpmrun.md with import-sheets command
- Add usage examples to README

---

## Specification Review Checklist

- [ ] Configuration approach follows existing patterns (Config class, .env)
- [ ] CLI command structure matches existing (`wpm import-sheets`)
- [ ] Reuses existing validation and parsing logic
- [ ] Error handling matches CSV import behavior
- [ ] Security considerations addressed
- [ ] Testing strategy defined
- [ ] Documentation updates specified

