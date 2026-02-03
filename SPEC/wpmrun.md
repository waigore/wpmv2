# WPM Command Line Utility Specification

## Purpose

The `wpm` command-line utility serves as an orchestrator for the WPM library. It provides a user-friendly interface for importing trade data from CSV files, managing composite portfolios, and querying portfolio information interactively. The utility preserves encapsulation by delegating all business logic to the appropriate WPM modules.

## File Location

- `src/wpm/cli/` - Command-line utility package (located in package source)
  - `src/wpm/cli/__init__.py` - Package initialization and backward compatibility exports
  - `src/wpm/cli/main.py` - Main entry point and orchestration
  - `src/wpm/cli/args.py` - Argument parsing
  - `src/wpm/cli/logging_config.py` - CLI-specific logging configuration
  - `src/wpm/cli/formatters.py` - Output formatting functions
  - `src/wpm/cli/interactive.py` - Interactive command loop
  - `src/wpm/cli/commands/` - Command handlers subpackage
    - `src/wpm/cli/commands/portfolio.py` - Portfolio-related commands
    - `src/wpm/cli/commands/asset.py` - Asset-related commands
    - `src/wpm/cli/commands/breakdown.py` - Breakdown command
    - `src/wpm/cli/commands/help.py` - Help command
- Console script entry point: `wpm` (configured via `pyproject.toml`, points to `wpm.cli:main`)

## Command Line Interface

### Initial Commands

The utility accepts one of two commands with optional parameters:

#### `wpm import [--end-date YYYY-MM-DD]`

Import trade data from CSV files.

**Note:** The `wpm` command is available after installing the package (via console script entry point defined in `pyproject.toml`). Alternatively, it can be run as a Python module: `python -m wpm.cli import`

**Parameters:**
- `--end-date YYYY-MM-DD` (optional): End date for historical portfolio import. If provided:
  - Only trades with date <= end_date are included
  - All created portfolios will have `is_historical=True`
  - Historical prices will be fetched for calculations
  - Clear messaging is displayed indicating historical import mode

**Behavior:**
- Scans the `import/` directory for all CSV files
- Imports each CSV file as a separate sub-portfolio
- If `--end-date` is provided, filters trades and creates historical portfolios
- Creates a composite portfolio containing all imported sub-portfolios
- Each sub-portfolio is named based on the CSV filename (see Portfolio Naming below)
- After import, fetches prices for all assets via PriceService (which manages cache internally)
  - For historical portfolios, uses historical prices from the end_date
- After price fetching, automatically creates SPY and BTC-USD buy-and-hold reference portfolios for baseline comparison
  - The reference portfolios mirror the composite portfolio's trade structure but invest all cost basis into SPY and BTC-USD respectively
  - If a reference portfolio creation fails (e.g., price service unavailable), logs a warning and continues without that reference portfolio (other reference portfolios are still created if successful)
- Enters interactive mode after successful import

**Error Handling:**
- If no CSV files are found in `import/` directory, display an error message and exit
- If CSV import fails for any file, display an error message and exit immediately with error code 1 (do not continue processing other files)
- If price retrieval fails for any asset and no price data exists in cache, display an error message and exit immediately with error code 1
- If price data exists in cache but is stale (invalid), log a warning but continue processing using the stale cache data

#### `wpm import-sheets [--end-date YYYY-MM-DD]`

Import trade data from Google Sheets.

**Prerequisites:**
- Google Sheets API credentials must be configured (service account JSON key file)
- Environment variables must be set in `.env` file:
  - `GOOGLE_SHEETS_CREDENTIALS_PATH`: Path to service account JSON key file (required)
  - `GOOGLE_SHEETS_DRIVE_PATH`: Google Drive path to spreadsheet (e.g., "Folder/Subfolder/SpreadsheetName") (optional, alternative to spreadsheet ID)
  - `GOOGLE_SHEETS_SPREADSHEET_ID`: Direct spreadsheet ID from URL (optional, alternative to Drive path)

**Parameters:**
- `--end-date YYYY-MM-DD` (optional): End date for historical portfolio import. If provided:
  - Only trades with date <= end_date are included
  - All created portfolios will have `is_historical=True`
  - Historical prices will be fetched for calculations
  - Clear messaging is displayed indicating historical import mode

**Behavior:**
- Authenticates with Google Sheets API using service account credentials
- Resolves the spreadsheet identifier (Drive path takes precedence over spreadsheet ID)
- Lists all sheet tabs in the spreadsheet
- Imports each sheet as a separate sub-portfolio (fail-fast: any error stops entire import)
- Validates sheet structure (same column requirements as CSV import)
- Creates a composite portfolio containing all imported sheets as sub-portfolios
- Each sub-portfolio is named after the sheet tab name
- After import, fetches prices for all assets via PriceService (same as CSV import)
- After price fetching, automatically creates SPY and BTC-USD buy-and-hold reference portfolios for baseline comparison
- Enters interactive mode after successful import

**Fail-Fast Behavior:**
- ALL sheets in the spreadsheet are imported (no filtering option)
- If ANY sheet fails to import (validation error, parsing error, etc.), the ENTIRE operation fails
- No partial portfolios are created on error

**Error Handling:**
- If `GOOGLE_SHEETS_CREDENTIALS_PATH` is not configured: Display error message and exit with code 1
- If neither `GOOGLE_SHEETS_DRIVE_PATH` nor `GOOGLE_SHEETS_SPREADSHEET_ID` is configured: Display error message and exit with code 1
- If credentials file not found: Display error message and exit with code 1
- If Drive path resolution fails (folder not found, spreadsheet not found, multiple matches): Display error message and exit with code 1
- If any sheet fails validation or parsing: Display error message and exit with code 1 (fail-fast)
- If price retrieval fails for any asset and no price data exists in cache: Display error message and exit immediately with error code 1

### Portfolio Naming

Portfolio names are extracted from CSV filenames by:
1. Removing the `.csv` extension
2. Extracting the meaningful portion after the last dash or hyphen (if present)
3. Stripping all whitespace (leading, trailing, and internal) from the extracted portion
4. If no dash/hyphen is found, use the full filename without extension and strip all whitespace

**Examples:**
- `Asset Trades - Crypto.csv` → `Crypto` (leading space after dash is stripped)
- `Asset Trades - US Stocks.csv` → `USStocks` (leading space and internal space are stripped)
- `MyPortfolio.csv` → `MyPortfolio`
- `Trades - 2024.csv` → `2024` (leading space after dash is stripped)
- `  Portfolio Name.csv` → `PortfolioName` (all spaces stripped)
- `Asset -  Crypto  .csv` → `Crypto` (all spaces stripped)
- `My  Portfolio  Name.csv` → `MyPortfolioName` (all spaces stripped)

**Validation:**
- All whitespace (leading, trailing, and internal) must be stripped from all portfolio names
- If multiple CSV files would result in the same portfolio name (after whitespace stripping), append a numeric suffix (e.g., `Crypto`, `Crypto_2`, `Crypto_3`)
- Portfolio names must be non-empty after extraction and whitespace stripping

## Interactive Mode

After successful import, the utility enters an interactive command loop. The prompt should be:

```
wpm> 
```

### Supported Commands

#### `metadata <ticker>`

See detailed description below in the Commands section.

#### `list portfolios`

**Description:** Lists all sub-portfolios within the composite portfolio by name.

**Output Format:**
- One portfolio name per line
- Sorted alphabetically
- Example:
  ```
  Crypto
  US Stocks
  ```

**Error Handling:**
- If no portfolios exist, display: "No portfolios found."

#### `show portfolio <name> [--up-to YYYY-MM-DD]`

**Description:** Lists all assets in the specified sub-portfolio, including current market value.

**Arguments:**
- `<name>`: Name of the sub-portfolio (required)
- `[--up-to YYYY-MM-DD]`: Optional date for historical portfolios. Shows weekly performance summary up to (and including) this date

**Output Format:**
- For each asset, display: `Ticker (Asset Type): Quantity @ Average Cost = Cost Basis | {Value Label} = Market Value @ Price | Allocation: XX.XX%`
- One asset per line
- Sorted by ticker
- Market Value is calculated as: `Quantity × Current/Historical Price`
- Price is retrieved using batch fetching via `PriceService.get_prices()` or `PriceService.get_historical_prices()` (grouped by asset_type)
- Prices are fetched in batches for efficiency - PriceService handles cache checking and API fetching internally
- Value Label:
  - For historical portfolios: `Historical Value (yyyy-MM-dd)` where the date is the portfolio's `end_date`
  - For current portfolios: `Current Value`
- Allocation percentage is calculated as: `(Asset Market Value / Total Portfolio Market Value) × 100`
- Allocation is rounded to 2 decimal places and displayed only when prices are available
- All allocations should sum to 100.00% (within rounding tolerance)
- If price retrieval fails for an asset type, display "N/A" for the value (price and allocation are not shown when value is N/A)
- After all position lines, display a summary section with:
  - Total Market Value: `<formatted_value>` (or "N/A" if no prices available)
  - Total Cost Basis: `<formatted_value>` (always displayed, doesn't depend on prices)
  - Total Unrealized P/L: `<formatted_value>` (with + prefix for profit, - for loss, or "N/A" if no prices available)
  - Total Realized P/L: `<formatted_value>` (with + prefix for profit, - for loss, always displayed since realized P/L doesn't depend on prices)
- Example (current portfolio):
  ```
  BTC-USD (Crypto): 0.5 @ $45,000.00 = $22,500.00 | Current Value = $23,000.00 @ $46,000.00 | Allocation: 35.94%
  ETH-USD (Crypto): 10.0 @ $2,500.00 = $25,000.00 | Current Value = $26,000.00 @ $2,600.00 | Allocation: 40.63%
  AAPL (Stock): 100.0 @ $150.00 = $15,000.00 | Current Value = $16,000.00 @ $160.00 | Allocation: 25.00%

  Total Market Value: $64,000.00
  Total Cost Basis: $62,500.00
  Total Unrealized P/L: +$1,500.00
  Total Realized P/L: +$200.00
  ```
- Example (historical portfolio):
  ```
  BTC-USD (Crypto): 0.5 @ $45,000.00 = $22,500.00 | Historical Value (2024-01-15) = $23,000.00 @ $46,000.00 | Allocation: 35.94%
  ETH-USD (Crypto): 10.0 @ $2,500.00 = $25,000.00 | Historical Value (2024-01-15) = $26,000.00 @ $2,600.00 | Allocation: 40.63%
  AAPL (Stock): 100.0 @ $150.00 = $15,000.00 | Historical Value (2024-01-15) = $16,000.00 @ $160.00 | Allocation: 25.00%

  Total Market Value: $64,000.00
  Total Cost Basis: $62,500.00
  Total Unrealized P/L: +$1,500.00
  Total Realized P/L: +$200.00
  ```

**Error Handling:**
- If portfolio name not found, display: "Portfolio '<name>' not found."
- If portfolio has no assets, display: "Portfolio '<name>' has no assets."
- If price retrieval fails for an asset, display "N/A" for the value (price is not shown when value is N/A) and continue displaying other assets
- If `--up-to` is used with non-historical portfolio: "Error: --up-to can only be used with historical portfolios."
- If `--up-to` date is invalid or outside portfolio date range: Display appropriate error message

**Weekly Performance Summary (when --up-to is specified):**
- When `--up-to` is specified for historical portfolios, displays weekly performance summary instead of asset list
- Uses `get_historical_performance()` to calculate history points from portfolio start_date to up_to_date
- Groups history points by calendar week (Monday to Sunday)
- Displays weekly totals: date range, total_market_value, and percentage return for each week
- Format: `Week of YYYY-MM-DD to YYYY-MM-DD: $X,XXX.XX (X.XX%)`
- Percentage return is calculated relative to the start_date's market value and shows the return from start_date to the end of each week
- Shows portfolio's weekly overall performance progression with both absolute values and percentage returns

#### `show all [--up-to YYYY-MM-DD]`

**Description:** Lists all assets in the composite portfolio (aggregated across all sub-portfolios), including current market value.

**Arguments:**
- `[--up-to YYYY-MM-DD]`: Optional date for historical portfolios. Shows weekly performance summary up to (and including) this date. When specified, totals section values are calculated against this date

**Output Format:**
- Same format as `show portfolio`, but showing aggregated positions
- If the same asset appears in multiple sub-portfolios, show the combined quantity and cost basis
- Market Value is calculated using the aggregated quantity and current/historical price
- Price is retrieved using batch fetching via `PriceService.get_prices()` or `PriceService.get_historical_prices()` (grouped by asset_type)
- Prices are fetched in batches for efficiency - PriceService handles cache checking and API fetching internally
- Value Label:
  - For historical portfolios: `Historical Value (yyyy-MM-dd)` where the date is the composite portfolio's `end_date`
  - For current portfolios: `Current Value`
- Allocation percentage is calculated as: `(Asset Market Value / Total Portfolio Market Value) × 100`
- Allocation is rounded to 2 decimal places and displayed only when prices are available
- All allocations should sum to 100.00% (within rounding tolerance)
- If price retrieval fails for an asset type, logs a warning and displays "N/A" for the value (price and allocation are not shown when value is N/A) for all assets of that type, but continues processing other asset types
- After all position lines (or after weekly summary if `--up-to` is specified), display a Totals section with:
  - **Imported Portfolio:**
    - Total Unrealized P/L: `<formatted_value> (X.XX%)` (with + prefix for profit, - for loss, or "N/A" if no prices available)
    - Total Realized P/L: `<formatted_value> (X.XX%)` (with + prefix for profit, - for loss, percentage shown if cost basis of sold lots > 0, otherwise "N/A")
  - **SPY Reference Portfolio:** (if SPY reference portfolio is available)
    - Total Unrealized P/L: `<formatted_value> (X.XX%)` (with + prefix for profit, - for loss, or "N/A" if no prices available)
    - Total Realized P/L: `<formatted_value> (X.XX%)` (with + prefix for profit, - for loss, percentage shown if cost basis of sold lots > 0, otherwise "N/A")
  - **BTC-USD Reference Portfolio:** (if BTC-USD reference portfolio is available)
    - Total Unrealized P/L: `<formatted_value> (X.XX%)` (with + prefix for profit, - for loss, or "N/A" if no prices available)
    - Total Realized P/L: `<formatted_value> (X.XX%)` (with + prefix for profit, - for loss, percentage shown if cost basis of sold lots > 0, otherwise "N/A")
  - When `--up-to` is specified, all values are calculated against that date
  - Percentage returns are calculated as:
    - Unrealized P/L percentage: `(unrealized_pnl / cost_basis_of_remaining_lots) * 100`
    - Realized P/L percentage: `(realized_pnl / cost_basis_of_sold_lots) * 100`
- Example (current portfolio):
  ```
  AAPL (Stock): 100.0 @ $150.00 = $15,000.00 | Current Value = $16,000.00 @ $160.00 | Allocation: 11.11%
  BTC-USD (Crypto): 0.5 @ $45,000.00 = $22,500.00 | Current Value = $23,000.00 @ $46,000.00 | Allocation: 15.97%
  GOOG (Stock): 50.0 @ $2,000.00 = $100,000.00 | Current Value = $105,000.00 @ $2,100.00 | Allocation: 72.92%

  Totals:
  Imported Portfolio:
    Total Unrealized P/L: +$6,500.00 (+4.73%)
    Total Realized P/L: +$500.00 (+2.50%)
  
  SPY Reference Portfolio:
    Total Unrealized P/L: +$2,000.00 (+1.45%)
    Total Realized P/L: +$100.00 (+0.50%)
  
  BTC-USD Reference Portfolio:
    Total Unrealized P/L: +$3,000.00 (+2.18%)
    Total Realized P/L: +$150.00 (+0.75%)
  ```

**Error Handling:**
- If composite portfolio has no assets, display: "No assets found in composite portfolio."
- If price retrieval fails for an asset type, logs a warning and displays "N/A" for the value (price is not shown when value is N/A) for all assets of that type, but continues processing other asset types
- If `--up-to` is used with non-historical portfolio: "Error: --up-to can only be used with historical portfolios."
- If `--up-to` date is invalid or outside portfolio date range: Display appropriate error message

**Weekly Performance Summary (when --up-to is specified):**
- When `--up-to` is specified for historical portfolios, displays weekly performance summary instead of asset list
- Uses `get_historical_performance()` to calculate history points from portfolio start_date to up_to_date
- Groups history points by calendar week (Monday to Sunday)
- Displays weekly totals: date range, total_market_value, and percentage return for each week
- Format: `Week of YYYY-MM-DD to YYYY-MM-DD: $X,XXX.XX (X.XX%)`
- Percentage return is calculated relative to the start_date's market value and shows the return from start_date to the end of each week
- Shows portfolio's weekly overall performance progression with both absolute values and percentage returns

#### `show asset <ticker> [--from YYYY-MM-DD] [--brokers "broker1,broker2,..."]`

**Description:** Shows the current or historical asset position in the imported portfolio for the specified ticker.

**Arguments:**
- `<ticker>`: Asset ticker symbol (required)
- `[--from YYYY-MM-DD]`: Optional start date for historical portfolios. Only valid for historical portfolios (imported with --end-date)
- `[--brokers "broker1,broker2,..."]`: Optional comma-separated list of broker names to filter positions by. When provided, positions are calculated only from lots matching the specified brokers. Broker names may contain spaces and should be enclosed in double quotes. Example: `show VOO --brokers "IBKR,Charles Schwab"`

**Output Format:**

**For current portfolios:**
- Same format as `show all`, but filtered to include only the specified asset
- Format: `Ticker (Asset Type): Quantity @ Average Cost = Cost Basis | Current Value = Market Value @ Price | Allocation: XX.XX%`
- Allocation percentage is calculated as: `(Asset Market Value / Total Portfolio Market Value) × 100`
- Allocation is rounded to 2 decimal places and displayed only when price is available
- After the position line, display a broker breakdown section (if not using --brokers filter) showing each broker with:
  - Broker name
  - Quantity held at that broker
  - Average cost per unit for that broker
  - Cost basis for that broker
  - Format: `Broker: Quantity @ Average Cost = Cost Basis` (mirroring the overall asset line format)
- After the broker breakdown (if shown), display a summary section with:
  - Total Market Value: `<formatted_value>` (or "N/A" if no price available)
  - Total Cost Basis: `<formatted_value>` (always displayed)
  - Total Unrealized P/L: `<formatted_value>` (with + prefix for profit, - for loss, or "N/A" if no price available)
  - Realized P/L: `<formatted_value>` (with + prefix for profit, - for loss, always displayed)
- Note that when `--brokers` filter is provided, realized P/L should only include lots matching the specified brokers
- Example:
  ```
  AAPL (Stock): 150.0 @ $150.00 = $22,500.00 | Current Value = $24,000.00 @ $160.00 | Allocation: 25.00%

  Broker Breakdown:
  IBKR: 100.0 @ $150.00 = $15,000.00
  Schwab: 50.0 @ $150.00 = $7,500.00

  Total Market Value: $24,000.00
  Total Cost Basis: $22,500.00
  Total Unrealized P/L: +$1,500.00
  Realized P/L: +$300.00
  ```

**For historical portfolios:**
- Without `--from`: Shows historical asset positions for the past 30 days (from portfolio.end_date backwards 30 days)
- With `--from`: Shows historical asset positions from the specified date to portfolio.end_date
- One line per day, showing the position on that date
- Format: `YYYY-MM-DD: Ticker (Asset Type): Quantity = Position Value @ Price | Allocation: XX.XX% | Return: XX.XX%`
- Quantity is displayed from the history point (calculated in domain layer, not CLI)
- Allocation percentage is calculated as: `(Asset Position Value / Total Portfolio Market Value) × 100` for each date
- Allocation is rounded to 2 decimal places and displayed only when price is available
- Percentage return is calculated using lot-based method: `(total_unrealized_pnl / total_cost_basis) × 100` for the asset on that date
  - Unrealized P/L and cost basis are aggregated across all lots for the asset
  - Only considers lots with remaining quantity (not fully sold)
  - Returns 0.0 if total_cost_basis is 0
  - Displayed only when price is available (None if price unavailable)
- Only shows days where the asset has a position (position_value > 0)
- Example:
  ```
  2024-01-01: AAPL (Stock): 100.0 = $15,000.00 @ $150.00 | Allocation: 30.00% | Return: 0.00%
  2024-01-02: AAPL (Stock): 100.0 = $15,200.00 @ $152.00 | Allocation: 30.40% | Return: 1.33%
  2024-01-03: AAPL (Stock): 100.0 = $15,400.00 @ $154.00 | Allocation: 30.80% | Return: 2.67%
  ...
  ```
- No summary section for historical portfolios (just daily position lines)

**Error Handling:**
- If ticker is missing: "Error: Ticker required. Usage: show asset <ticker> [--from YYYY-MM-DD] [--brokers \"broker1,broker2,...\"]"
- If asset not found: "Asset '<ticker>' not found in portfolio."
- If no positions found with specified brokers: "No positions found for ticker '<ticker>' with specified brokers."
- If `--from` is used with non-historical portfolio: "Error: --from can only be used with historical portfolios."
- If `--from` date is invalid or outside portfolio date range: Display appropriate error message
- If price is unavailable for a date (historical): Display "N/A" instead of price (e.g., `2024-01-01: AAPL (Stock): 100.0 = $15,000.00 @ N/A`)
- If quantity is unavailable for a date (historical): Display "N/A" for quantity (e.g., `2024-01-01: AAPL (Stock): N/A = $15,000.00 @ $150.00`)

#### `metadata <ticker>`

**Description:** Displays metadata for the specified asset ticker.

**Arguments:**
- `<ticker>`: Asset ticker symbol (required)

**Behavior:**
- The command attempts to determine the asset type from the portfolio if the ticker exists in the portfolio (using `get_assets()` which is a lightweight cache lookup and does not trigger FIFO calculations)
- If the ticker is not found in the portfolio, or if `get_assets()` fails, the command infers the asset type from the ticker format:
  - Tickers ending with "-USD" are assumed to be "Crypto"
  - All other tickers default to "Stock"
- This allows the metadata command to work for any ticker, even if it's not in the portfolio

**Output Format:**
- Displays all available metadata fields:
  - Ticker: The asset ticker symbol
  - Name: Asset name (longName, shortName, name, or ticker as fallback)
  - Type: Asset type (Stock, ETF, or Crypto)
  - Market Cap: Market capitalization (formatted as $X.XXB, $X.XXM, etc., or "N/A")
  - Sector: Sector (equities only, "N/A" for crypto)
  - Industry: Industry (equities only, "N/A" for crypto)
  - Country: Country (equities only, "N/A" for crypto)
  - Category: Category (or "unknown" if not available)
- Example:
  ```
  Ticker: GOOG
  Name: Alphabet Inc.
  Type: Stock
  Market Cap: $1.23T
  Sector: Technology
  Industry: Internet Content & Information
  Country: United States
  Category: unknown
  ```

**Error Handling:**
- If ticker argument is missing: "Error: Ticker required. Usage: metadata <ticker>"
- If metadata unavailable: "No metadata available for '<ticker>'."

**Note:** Available in both current and historical modes. Metadata is cached for 24 hours to minimize API calls. The command does not trigger expensive FIFO cost basis calculations.

#### `lots <ticker>`

**Description:** Displays all lots (FIFO purchase records) for the specified asset ticker across all portfolios.

**Arguments:**
- `<ticker>`: Asset ticker symbol (required)

**Output Format:**
- For each lot, display:
  - Purchase date (YYYY-MM-DD format)
  - Purchase price per unit
  - Original quantity and remaining quantity
  - Remaining cost basis (purchase_price × remaining_quantity)
  - Matched sells (if any): For each matched sell, show sell date, sell price, and quantity sold
  - Realized P/L (if any matched sells exist)
  - Unrealized P/L (if current price is available)
  - Total P/L (if current price is available)
- Lots sorted by purchase date (oldest first)
- Each lot displayed on multiple lines:
  - First line: Purchase info and summary
  - Subsequent lines: Matched sells (indented) if any exist
- Example:
  ```
  2025-10-01: 2.0 @ $600.00 | Remaining: 1.0 @ $600.00 = $600.00 | Realized: +$20.00 | Unrealized: +$30.00 | Total: +$50.00
    Sold: 2025-12-01, 1.0 @ $620.00
  2025-11-01: 1.0 @ $610.00 | Remaining: 1.0 @ $610.00 = $610.00 | Realized: $0.00 | Unrealized: +$20.00 | Total: +$20.00
  ```

**Error Handling:**
- If ticker argument is missing: "Error: Ticker required. Usage: lots <ticker>"
- If no lots found for ticker: "No lots found for ticker '<ticker>'."
- If ticker doesn't exist in portfolio: "No lots found for ticker '<ticker>'." (same message)
- If price retrieval fails for unrealized P/L: Display lots with "N/A" for unrealized and total P/L

#### `breakdown [<name>] <by>`

**Description:** Shows a breakdown of the portfolio by the specified dimension.

**Arguments:**
- `[<name>]`: Optional sub-portfolio name. If omitted, breakdown is for the entire composite portfolio
- `<by>`: Breakdown dimension - one of: `asset_type`, `ticker`, `purchase_period`, or `broker`

**Breakdown Types:**

1. **`asset_type`**: Group by asset type (Stock, ETF, Crypto)
   - Display: Asset Type, Total Quantity, Total Cost Basis
   - Example:
     ```
     Crypto: 0.5 @ $22,500.00
     Stock: 150.0 @ $115,000.00
     ```

2. **`ticker`**: Group by ticker symbol
   - Display: Ticker, Quantity, Cost Basis
   - Example:
     ```
     AAPL: 100.0 @ $15,000.00
     BTC-USD: 0.5 @ $22,500.00
     GOOG: 50.0 @ $100,000.00
     ```

3. **`purchase_period`**: Group by purchase period (default: month)
   - Display: Period, Total Quantity, Total Cost Basis
   - Format: YYYY-MM for months
   - Example:
     ```
     2024-01: 50.0 @ $10,000.00
     2024-02: 100.0 @ $20,000.00
     ```
   - Note: For purchase_period, the utility should support an optional period parameter (month/quarter/year), but for initial implementation, default to "month"

4. **`broker`**: Group by broker
   - Display: Broker name, per-asset quantities (if available), Total Cost Basis
   - Format: `Broker: Ticker: Quantity, Ticker: Quantity, ..., Total: Cost Basis`
   - Example:
     ```
     Coinbase: BTC-USD: 0.5, ETH-USD: 10, Total: $47,500.00
     Fidelity: AAPL: 100, GOOG: 50, Total: $115,000.00
     ```
   - If no per-asset quantities are available, displays: `Broker: Total: Cost Basis`

**Output Format:**
- Clear, readable format with appropriate headers
- Monetary values formatted with 2 decimal places and $ prefix
- Quantities formatted appropriately (integers for whole numbers, decimals for fractional)

**Error Handling:**
- If breakdown type is missing: "Error: Breakdown type required. Valid types: asset_type, ticker, purchase_period, broker"
- If portfolio name is provided but not found: "Portfolio '<name>' not found."
- If breakdown type is invalid: "Invalid breakdown type '<by>'. Valid types: asset_type, ticker, purchase_period, broker"
- If no data available for breakdown: "No data available for breakdown."
- If an exception occurs during breakdown generation: Logs error and displays "No data available for breakdown."

#### `Quit` or `quit` or `exit`

**Description:** Exits the interactive mode and terminates the program.

**Behavior:**
- Case-insensitive matching
- Graceful exit with exit code 0
- Display: "Exiting..."

### Command Parsing

- Commands are case-insensitive for `quit`/`exit` (handled via `.lower()`)
- Other commands are case-sensitive (e.g., `list`, `show`, `breakdown`)
- Arguments are separated by whitespace
- Portfolio names with spaces are handled as single tokens (no quoting needed if no spaces in name)
- Invalid commands display: "Unknown command: '<user_input>'. Type 'help' for available commands."
- Empty input is ignored (continues loop)

### Keyboard Interrupts

- **Ctrl+D (EOF)**: Displays "Exiting..." and exits gracefully with exit code 0
- **Ctrl+C (KeyboardInterrupt)**: Displays "Exiting..." and exits gracefully with exit code 0

### Help Command

Currently, the `help` command is mentioned in error messages but is not implemented. The error message suggests typing 'help', but this command does not exist yet and will result in "Unknown command" error.

## Architecture and Encapsulation

### Design Principles

1. **Orchestration Only**: The CLI module (`wpm.cli`) should NOT contain business logic. It should:
   - Parse command-line arguments
   - Coordinate calls to WPM modules
   - Format output for display
   - Handle user interaction

2. **Delegation**: All business logic must be delegated to appropriate WPM modules:
   - CSV import: `wpm.importer.import_trades_from_csv()`
   - Portfolio creation: `wpm.portfolio.SimplePortfolio` and `wpm.portfolio.CompositePortfolio`
   - Cost basis calculation: Handled by portfolio classes
   - Price retrieval: `wpm.pricing.PriceService` (uses batch fetching via `get_prices()`)
   - Breakdown generation: `wpm.metrics` functions
   - Position aggregation: Handled by `CompositePortfolio.get_positions()`

3. **Module Responsibilities**:
   - `wpm.cli`: CLI package providing command-line interface
     - `wpm.cli.main`: Main entry point and orchestration
     - `wpm.cli.args`: Command-line argument parsing
     - `wpm.cli.logging_config`: CLI-specific logging setup
     - `wpm.cli.formatters`: Output formatting functions
     - `wpm.cli.interactive`: Interactive command loop
     - `wpm.cli.commands`: Command handlers (portfolio, asset, breakdown, help)
   - `wpm.importer`: CSV parsing and trade import
   - `wpm.portfolio`: Portfolio management and position aggregation
   - `wpm.pricing`: Price retrieval and caching
   - `wpm.metrics`: Breakdown calculations and percentage return calculations
   - `wpm.models`: Data models (Asset, Trade, Position, Portfolio)

### Import Process Flow

1. **CSV Discovery**:
   - Scan `import/` directory for `.csv` files (relative to current working directory)
   - Use `pathlib.Path` for cross-platform compatibility
   - Sort files alphabetically for consistent processing order

2. **CSV Import**:
   - For each CSV file (in sorted order):
     - Extract portfolio name using `extract_portfolio_name()` function (handles duplicates with numeric suffixes)
     - Call `wpm.importer.import_trades_from_csv(file_path)` with string path
     - If import fails (raises exception), display error message with filename and exit immediately with error code 1
     - Create a `SimplePortfolio` with extracted name
     - Add all imported trades to the portfolio using `portfolio.add_trade()`
     - Add portfolio as sub-portfolio to composite portfolio using `composite.add_sub_portfolio()`
     - Log success with number of trades imported
   - If any import fails, stop processing immediately and do not proceed to price fetching or interactive mode
   - Log final summary with total number of sub-portfolios created

3. **Price Fetching**:
   - After all imports complete:
     - Get all unique assets from composite portfolio using `get_positions()`
     - Group assets by asset_type for batch processing
     - For each asset_type:
       - Call `PriceService.get_prices(tickers, asset_type)` to batch fetch prices
       - `PriceService` handles cache checking, API fetching, and stale cache fallback internally
     - Display summary of price fetching

4. **Interactive Mode Entry**:
   - Create command loop
   - Process user commands until `Quit`

### Price Fetching Details

- After import, fetch prices for all assets in the composite portfolio:
  - Group all assets by asset_type (Stock, ETF, Crypto)
  - For each asset_type, call `PriceService.get_prices(tickers, asset_type)` with all tickers of that type
  - The `PriceService.get_prices()` method handles:
    - Cache checking for all tickers
    - Batch API fetching for uncached tickers
    - Stale cache fallback if API fetch fails (with internal logging)
    - Cache updates automatically
  - If `PriceService.get_prices()` raises `ValueError` (no price data exists for any ticker):
    - Display error message and exit immediately with error code 1
  - PriceService manages all cache operations internally - the CLI module does not directly access the cache
- Log progress: "Fetching prices for X assets..."
- Display summary: "Prices fetched for X assets"

## Error Handling

### Import Errors

- If a CSV file cannot be read: Display error message with filename and exit immediately with error code 1
- If CSV structure is invalid: Display validation error message with filename and exit immediately with error code 1
- If trade parsing fails for some rows: The importer module handles this (may raise ValidationError if no valid trades found, or return partial list with warnings logged). If importer raises an exception, exit immediately with error code 1
- If any CSV import operation fails (raises an exception): Exit immediately with error code 1, do not process remaining files

### Price Retrieval Errors

- If price retrieval fails (API fetch raises exception) and no cache entry exists for the asset: Display error message with asset ticker and exit immediately with error code 1
- If price retrieval fails but cache entry exists (even if stale): Log warning message indicating stale cache is being used for the asset, use the stale cached price, and continue processing remaining assets
- If cache entry exists but is invalid/stale and API fetch succeeds: Update cache with new price, continue normally
- Price retrieval failures during interactive mode: Log warning, continue (don't block command execution)

### Interactive Mode Errors

- Invalid commands: Display error message, continue loop
- Invalid portfolio names: Display error message, continue loop
- Invalid breakdown types: Display error message, continue loop
- Price retrieval failures during interactive mode: Log warning, continue (don't block command execution)

### General Error Handling

- Use try-except blocks appropriately
- Log errors using `wpm.utils.setup_logging()`
- Display user-friendly error messages
- Never expose internal exceptions to users
- Exit gracefully on fatal errors

## Logging

- Initialize CLI-specific logging using `setup_cli_logging()` in `wpm.cli` module
- All logs are written to `logs/wpmcli.log` (relative to current working directory)
- Logs are **suppressed from stdout/stderr** during CLI execution to maintain a clean interface
- Only user-facing messages (via `print()`) appear in stdout; all logging output goes to the file
- The `logs/` directory is created automatically if it doesn't exist
- Log file uses append mode, so logs accumulate across CLI sessions
- Log format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Log at INFO level for:
  - Import start/completion
  - Portfolio creation
  - Price fetching operations
  - Command execution
- Log at WARNING level for:
  - Import errors
  - Price retrieval failures
  - Invalid user input
- Log at ERROR level for:
  - Fatal errors that cause exit

**Note:** This logging configuration is CLI-specific and does not affect downstream library users. Library users can configure their own logging using `wpm.utils.setup_logging()` or their own logging setup.

## Output Formatting

### Display Format

- Use clear, readable formatting
- Align columns where appropriate
- Format currency with $ prefix, 2 decimal places, and thousands separators (e.g., "$1,234.56")
- Format quantities appropriately:
  - Integers for whole numbers (e.g., "100")
  - Decimals for fractional values, rounded to 8 decimal places maximum (standard for crypto precision)
  - Trailing zeros are removed (e.g., "0.5" not "0.50000000")
  - Handles both Decimal and float types
- Use consistent spacing and indentation

### Example Output

```
Entering interactive mode. Type 'Quit' to exit.
wpm> list portfolios
Crypto
USStocks

wpm> show portfolio Crypto
BTC-USD (Crypto): 0.5 @ $45,000.00 = $22,500.00 | Current Value = $23,000.00 @ $46,000.00
ETH-USD (Crypto): 10 @ $2,500.00 = $25,000.00 | Current Value = $26,000.00 @ $2,600.00

Total Market Value: $49,000.00
Total Cost Basis: $47,500.00
Total Unrealized P/L: +$1,500.00

wpm> show all
AAPL (Stock): 100 @ $150.00 = $15,000.00 | Current Value = $16,000.00 @ $160.00
BTC-USD (Crypto): 0.5 @ $45,000.00 = $22,500.00 | Current Value = $23,000.00 @ $46,000.00
ETH-USD (Crypto): 10 @ $2,500.00 = $25,000.00 | Current Value = $26,000.00 @ $2,600.00
GOOG (Stock): 50 @ $2,000.00 = $100,000.00 | Current Value = $105,000.00 @ $2,100.00

Total Market Value: $170,000.00
Total Cost Basis: $162,500.00
Total Unrealized P/L: +$7,500.00

wpm> breakdown Crypto asset_type
Crypto: 10.5 @ $47,500.00

wpm> breakdown ticker
AAPL: 100 @ $15,000.00
BTC-USD: 0.5 @ $22,500.00
ETH-USD: 10 @ $25,000.00
GOOG: 50 @ $100,000.00

wpm> breakdown broker
Coinbase: BTC-USD: 0.5, ETH-USD: 10, Total: $47,500.00
Fidelity: AAPL: 100, GOOG: 50, Total: $115,000.00

wpm> quit
Exiting...
```

**Note:** The "Entering interactive mode. Type 'Quit' to exit." message is displayed when interactive mode starts.

## Dependencies

- All WPM modules (`wpm.importer`, `wpm.portfolio`, `wpm.pricing`, `wpm.metrics`, `wpm.models`, `wpm.utils`)
- Standard library: `argparse`, `logging`, `pathlib`, `sys`, `typing` (Dict, List, Optional, Set)
- `decimal.Decimal` for quantity formatting (handled internally)

## Testing Considerations

- Unit tests should mock WPM module calls
- Test command parsing and validation
- Test error handling scenarios
- Test output formatting
- Integration tests with actual CSV files (in test fixtures)

## Future Enhancements (Out of Scope)

- Additional commands (e.g., `add trade`, `remove portfolio`)
- Export functionality
- Interactive portfolio editing
- Price alerts
- Performance metrics display
- Graphical output/visualizations

