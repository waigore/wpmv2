# WPM (Wealth Portfolio Manager) Library Specification

## Purpose

WPM is a Python library designed to manage and analyze financial portfolios. It enables users to track asset positions across multiple portfolios, aggregate values and quantities, and generate comprehensive portfolio metrics. The library supports portfolios containing stocks, ETFs, and cryptocurrencies, with the ability to create hierarchical portfolio structures (portfolios of portfolios). WPM provides CSV import functionality for trade data, calculates cost basis using multiple methods, retrieves current market prices, and generates detailed breakdowns by asset type, ticker, purchase period, and broker.

## Package Layout

- `wpm/__init__.py` - Package initialization and public API exports
- `wpm/models.py` - Core data models (Asset, Trade, Position, Portfolio)
- `wpm/portfolio.py` - Portfolio class implementation with aggregation logic
- `wpm/importer.py` - CSV import functionality using pandas
- `wpm/cost_basis.py` - Cost basis calculation methods (FIFO and Average Cost)
- `wpm/pricing.py` - Market price data retrieval module (yfinance and CoinGecko integration)
- `wpm/metrics.py` - Portfolio metrics and breakdown generation
- `wpm/utils.py` - Utility functions for validation, logging setup, and helpers

## Module Requirements

### wpm/models.py

**Responsibilities:**
- Define core data structures used throughout the library
- Provide validation logic for data integrity
- Implement immutable data classes where appropriate

**Key Classes:**
- `Asset`: Represents a financial asset with ticker and type
- `Trade`: Represents a single buy/sell transaction
- `Position`: Represents current holdings for an asset (quantity and cost basis)
- `Portfolio`: Base portfolio class (abstract or concrete base)

**Artefacts:**
- Data model classes with validation
- Custom exception classes for validation errors

### wpm/portfolio.py

**Responsibilities:**
- Implement portfolio management logic
- Handle aggregation of positions across sub-portfolios
- Calculate total values and quantities
- Support both simple portfolios (containing assets) and composite portfolios (containing other portfolios)

**Key Classes:**
- `Portfolio`: Main portfolio class with aggregation capabilities
- `SimplePortfolio`: Portfolio containing direct asset positions
- `CompositePortfolio`: Portfolio containing sub-portfolios

**Key Functions:**
- `add_trade(trade)`: Add a trade to the portfolio
- `get_positions()`: Get all asset positions in the portfolio
- `get_total_cost_basis()`: Calculate total cost basis
- `get_total_quantity(ticker)`: Get total quantity for a specific asset
- `add_sub_portfolio(portfolio)`: Add a sub-portfolio (for composite portfolios)

**Artefacts:**
- Portfolio class implementations
- Aggregation logic for hierarchical structures

### wpm/importer.py

**Responsibilities:**
- Parse CSV files containing trade data
- Validate CSV structure and data types
- Convert CSV rows to Trade objects
- Handle missing or malformed data gracefully

**Key Functions:**
- `import_trades_from_csv(file_path)`: Main import function
- `validate_csv_structure(df)`: Validate CSV has required columns
- `parse_trade_row(row)`: Convert CSV row to Trade object

**Artefacts:**
- Imported Trade objects
- Validation error reports

### wpm/cost_basis.py

**Responsibilities:**
- Calculate cost basis using FIFO method
- Calculate cost basis using Average Cost method
- Handle both buy and sell transactions
- Track remaining positions after sells

**Key Functions:**
- `calculate_fifo_cost_basis(trades)`: Calculate positions using FIFO
- `calculate_average_cost_basis(trades)`: Calculate positions using average cost
- `apply_sell(trades, sell_trade)`: Apply sell transaction against existing positions

**Artefacts:**
- Position objects with calculated cost basis and quantities

### wpm/pricing.py

**Responsibilities:**
- Retrieve current market prices for stocks/ETFs from Yahoo Finance via yfinance
- Retrieve current market prices for cryptocurrencies from CoinGecko API
- Implement rate limiting to respect API free tier limits
- Cache price data persistently using Parquet file format to minimize API calls across program runs
- Manage cache file lifecycle (load, save, expiration)
- Validate cache entries per asset based on asset type and trading hours
- Handle API errors and missing data gracefully

**Key Classes:**
- `PriceRetriever`: Base class for price retrieval
- `YahooFinanceRetriever`: yfinance-based retriever for stocks/ETFs
- `CoinGeckoRetriever`: CoinGecko API retriever for cryptocurrencies
- `RateLimiter`: Rate limiting utility
- `PriceCache`: Manages persistent Parquet-based price cache

**Key Functions:**
- `get_price(ticker, asset_type)`: Get current price for an asset (checks cache first, validates per asset)
- `get_prices(tickers, asset_type)`: Batch price retrieval with rate limiting
- `_load_cache()`: Load price cache from Parquet file
- `_save_cache()`: Save price cache to Parquet file
- `_is_cache_valid(cache_entry, asset_type)`: Check if cached price is valid for a specific asset
  - For US stocks/ETFs: Uses `wpm.utils.is_us_market_open()` and `wpm.utils.is_within_trading_hours()` to determine validity. If current time is outside trading hours and cache timestamp was outside trading hours, cache is valid. If within trading hours, cache must be less than 10 minutes old.
  - For crypto: Cache must be less than 10 minutes old regardless of time of day.
- `_rate_limit_check()`: Internal rate limiting enforcement

**Artefacts:**
- Current market prices for assets
- Persistent Parquet cache file (default: `~/.wpm/price_cache.parquet` or configurable path)
- Cache file contains: ticker, asset_type, price, timestamp columns

### wpm/metrics.py

**Responsibilities:**
- Generate portfolio metrics and breakdowns
- Calculate per-asset cost basis and quantity
- Calculate overall portfolio cost basis (including sub-portfolios)
- Generate breakdowns by asset type, ticker, purchase period, and broker
- Calculate market values when price data is available

**Key Functions:**
- `calculate_portfolio_metrics(portfolio, cost_basis_method='fifo')`: Main metrics calculation
- `breakdown_by_asset_type(portfolio)`: Group metrics by asset type
- `breakdown_by_ticker(portfolio)`: Group metrics by ticker
- `breakdown_by_purchase_period(portfolio, period='month')`: Group by time period
- `breakdown_by_broker(portfolio)`: Group metrics by broker
- `calculate_market_value(portfolio, prices)`: Calculate current market value

**Artefacts:**
- Metrics dictionaries/dataframes
- Breakdown reports

### wpm/utils.py

**Responsibilities:**
- Provide utility functions for validation
- Set up centralized logging configuration
- Helper functions for date parsing, ticker normalization, etc.
- Determine US market trading hours for cache validity calculations

**Key Functions:**
- `setup_logging(level=logging.INFO)`: Configure library logging
- `validate_ticker(ticker)`: Validate ticker format
- `normalize_date(date_str)`: Parse and normalize date strings
- `validate_asset_type(asset_type)`: Validate asset type values
- `is_us_market_open(timestamp=None)`: Determine if US market (NYSE) is currently open for regular trading hours
  - Accounts for weekends, official holidays, and early closes using pandas_market_calendars
  - Returns True if market is open, False otherwise
  - If timestamp is None, uses current time
- `is_within_trading_hours(timestamp)`: Check if a given timestamp falls within US market trading hours
  - Uses NYSE calendar to account for holidays and early closes
  - Returns True if timestamp is during market hours, False otherwise

**Artefacts:**
- Configured logger instance
- Validation utilities

## Data Models

### Asset

Represents a financial asset identifier.

**Fields:**
- `ticker` (str, required): Asset ticker symbol (e.g., "BTC-USD", "GOOG", "IAU")
  - Validation: Non-empty string, alphanumeric with hyphens/underscores allowed
- `asset_type` (str, required): Type of asset - one of "Stock", "ETF", or "Crypto"
  - Validation: Must be one of the allowed values (case-insensitive, normalized to title case)

**Methods:**
- `__eq__()`: Equality comparison based on ticker and asset_type
- `__hash__()`: Hashable for use in sets/dictionaries

### Trade

Represents a single buy or sell transaction.

**Fields:**
- `date` (datetime.date, required): Date of the trade
  - Validation: Valid date object, not in the future
- `asset` (Asset, required): The asset being traded
- `action` (str, required): "Buy" or "Sell"
  - Validation: Must be "Buy" or "Sell" (case-insensitive, normalized to title case)
- `broker` (str, required): Broker/platform where trade was executed
  - Validation: Non-empty string
- `order_type` (str, optional): Type of order (e.g., "Limit", "Market", "Lump sum", "Recurring buy", "DRIP")
  - Validation: Non-empty string if provided
- `price` (float, required): Price per unit in USD
  - Validation: Positive number, greater than 0
- `quantity` (float, required): Number of units traded
  - Validation: Positive number, greater than 0

**Computed Properties:**
- `total_value`: `price * quantity` (total cost for buys, total proceeds for sells)

**Methods:**
- `is_buy()`: Returns True if action is "Buy"
- `is_sell()`: Returns True if action is "Sell"

### Position

Represents current holdings for a specific asset within a portfolio.

**Fields:**
- `asset` (Asset, required): The asset this position represents
- `quantity` (float, required): Current quantity held
  - Validation: Non-negative number (can be 0 if fully sold)
- `cost_basis` (float, required): Total cost basis in USD
  - Validation: Non-negative number
  - Calculation: Sum of (price * quantity) for all buy transactions minus cost basis of sold units
- `cost_basis_method` (str, required): Method used ("fifo" or "average")
- `average_cost` (float, computed): Average cost per unit
  - Calculation: `cost_basis / quantity` if quantity > 0, else 0

**Methods:**
- `get_average_cost()`: Returns average cost per unit

### Portfolio

Represents a collection of asset positions or sub-portfolios.

**Fields:**
- `name` (str, required): Portfolio identifier/name
  - Validation: Non-empty string
- `trades` (list[Trade], optional): List of trades in this portfolio (for simple portfolios)
- `sub_portfolios` (list[Portfolio], optional): List of sub-portfolios (for composite portfolios)
- `cost_basis_method` (str, default="fifo"): Method for cost basis calculation
  - Validation: Must be "fifo" or "average"

**Computed Properties:**
- `positions`: Dictionary mapping Asset to Position objects
  - For simple portfolios: Calculated from trades using specified cost basis method
  - For composite portfolios: Aggregated from sub-portfolios
- `total_cost_basis`: Sum of all position cost_basis values
- `total_quantity(asset)`: Total quantity for a specific asset across all positions

**Methods:**
- `add_trade(trade)`: Add a trade to the portfolio
- `get_positions()`: Get all positions as a dictionary
- `get_position(asset)`: Get position for a specific asset
- `get_total_cost_basis()`: Calculate total cost basis
- `add_sub_portfolio(portfolio)`: Add a sub-portfolio (composite only)
- `get_all_trades()`: Get all trades including from sub-portfolios (recursive)

**Validation:**
- Portfolio cannot be both simple (has trades) and composite (has sub-portfolios) simultaneously
- Sub-portfolios must have unique names within a composite portfolio

### Price Cache Entry

Represents a cached price entry stored in the Parquet cache file.

**Fields:**
- `ticker` (str, required): Asset ticker symbol
- `asset_type` (str, required): Asset type ("Stock", "ETF", or "Crypto")
- `price` (float, required): Cached price in USD
  - Validation: Positive number
- `timestamp` (datetime, required): When the price was retrieved and cached
  - Validation: Valid datetime object

**Cache Validity Rules:**

Validity is determined per asset individually based on asset type and current time:

1. **US Stocks/ETFs:**
   - If current time is **outside trading hours** AND the cache timestamp was also outside trading hours: Cache is valid (assumes most current price from last trading session).
   - If current time is **within trading hours**: Cache is valid only if less than 10 minutes old from current time.
   - Trading hours determination: Uses `wpm.utils.is_us_market_open()` and `wpm.utils.is_within_trading_hours()` which leverage pandas_market_calendars to account for NYSE regular trading hours (9:30 AM - 4:00 PM ET), weekends, official holidays, and early closes.

2. **Cryptocurrencies:**
   - Cache is valid only if less than 10 minutes old from current time, regardless of time of day.

**Validation Logic:**
- Each cache entry is validated individually when accessed
- Invalid entries trigger fresh API retrieval for that specific asset
- Cache file may contain entries with varying validity statuses

### CSV Import Format

**Required Columns:**
- `Date`: Trade date in YYYY-MM-DD format
- `Asset Name/Ticker`: Asset ticker symbol
- `Asset Type`: One of "Stock", "ETF", or "Crypto"
- `Action`: "Buy" or "Sell"
- `Broker`: Broker/platform name
- `Type`: Order type (e.g., "Limit", "Market", "Lump sum", etc.)
- `Price (USD)`: Price per unit in USD
- `Quantity`: Number of units

**Validation Rules:**
- All required columns must be present
- Date must be parseable as YYYY-MM-DD
- Asset Type must be valid (Stock, ETF, or Crypto)
- Action must be Buy or Sell
- Price and Quantity must be numeric and positive
- Missing optional fields (like Type) are allowed

## External Dependencies

### Core Dependencies
- **pandas** (>=1.5.0): CSV parsing and data manipulation
- **yfinance** (>=0.2.0): Yahoo Finance API for stock/ETF price data
- **pycoingecko** (>=3.1.0): CoinGecko API client for cryptocurrency price data
- **pyarrow** (>=10.0.0): Parquet file format support for persistent price caching
- **pandas_market_calendars** (>=4.3.0): US market calendar with holidays and trading hours
- **pytz** (>=2023.3): Timezone handling for trading hours calculations

### Development Dependencies
- **pytest** (>=7.0.0): Testing framework
- **pytest-cov** (>=4.0.0): Code coverage plugin for pytest
- **pytest-mock** (>=3.10.0): Mocking utilities for tests

### Optional Dependencies
- **requests** (>=2.28.0): HTTP library (may be required by yfinance/pycoingecko)

## Testing

### Coverage Requirements
- Minimum 80% code coverage across all modules
- All public functions and classes must have test coverage
- Edge cases and error conditions must be tested

### Test Structure
- Tests located in `tests/` directory mirroring package structure
- Test files named `test_<module_name>.py`
- Use pytest fixtures for common test data setup
- Mock external API calls (yfinance, CoinGecko) in tests

### Test Categories
1. **Unit Tests**: Test individual functions and classes in isolation
2. **Integration Tests**: Test module interactions (e.g., import -> portfolio -> metrics)
3. **Edge Case Tests**: Test error conditions, empty data, invalid inputs
4. **Rate Limiting Tests**: Verify rate limiting behavior in pricing module

### Key Test Scenarios
- CSV import with valid and invalid data
- FIFO and Average Cost basis calculations
- Buy and sell transaction processing
- Portfolio aggregation (simple and composite)
- Price retrieval with rate limiting
- Metrics calculation and breakdowns
- Error handling and validation

### Test Execution
- Run all tests: `pytest`
- Run with coverage: `pytest --cov=wpm --cov-report=html`
- Run specific test file: `pytest tests/test_portfolio.py`

## Logging and Observability

### Logging Configuration
- Library uses Python's built-in `logging` module
- Centralized logging setup via `wpm.utils.setup_logging()`
- Default log level: INFO
- Logger name: `wpm`

### Logging Levels

**INFO Level** (for externally callable functions):
- Function entry with input parameters
- Function exit with return values/summary
- CSV import start/completion with row counts
- Portfolio creation and modification
- Price retrieval requests (ticker and asset type)
- Metrics calculation completion

**DEBUG Level** (for internal/private functions):
- Detailed step-by-step execution within functions
- Cost basis calculation intermediate steps
- Rate limiting decisions and delays
- Data validation details
- Aggregation calculations

### Log Format
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- Include timestamps, logger name, level, and message
- Use structured logging where beneficial (dictionary/JSON format for complex data)

### Logging Points

**wpm/importer.py:**
- INFO: CSV file import started, number of rows processed, import completed
- DEBUG: Row parsing details, validation checks

**wpm/portfolio.py:**
- INFO: Trade added, portfolio created, positions calculated
- DEBUG: Position aggregation steps, sub-portfolio traversal

**wpm/cost_basis.py:**
- INFO: Cost basis calculation started/completed with method
- DEBUG: FIFO queue operations, average cost calculations, sell matching

**wpm/pricing.py:**
- INFO: Price retrieval request (ticker, asset_type), rate limit wait, cache file load/save operations, per-asset cache validation results
- DEBUG: API response details, cache hits/misses, rate limit state, per-asset cache validation checks (trading hours, age calculations), Parquet file I/O

**wpm/metrics.py:**
- INFO: Metrics calculation started/completed, breakdown generation
- DEBUG: Breakdown aggregation steps, metric computation details

