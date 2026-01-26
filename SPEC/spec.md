# WPM (Wealth Portfolio Manager) Library Specification

## Purpose

WPM is a Python library designed to manage and analyze financial portfolios. It enables users to track asset positions across multiple portfolios, aggregate values and quantities, and generate comprehensive portfolio metrics. The library supports portfolios containing stocks, ETFs, and cryptocurrencies, with the ability to create hierarchical portfolio structures (portfolios of portfolios). WPM provides CSV import functionality for trade data, calculates cost basis using FIFO method, retrieves current market prices, and generates detailed breakdowns by asset type, ticker, purchase period, and broker.

## Package Layout

- `wpm/__init__.py` - Package initialization and public API exports
- `wpm/models.py` - Core data models (Asset, Trade, Position, Portfolio)
- `wpm/config.py` - Application-level configuration module
- `wpm/portfolio.py` - Portfolio class implementation with aggregation logic
- `wpm/importer.py` - CSV import functionality using pandas
- `wpm/cost_basis.py` - Cost basis calculation methods (FIFO)
- `wpm/pricing/` - Market price data retrieval package (yfinance and CoinGecko integration)
  - `wpm/pricing/__init__.py` - Package initialization and public API exports
  - `wpm/pricing/base.py` - Abstract base class for price retrievers
  - `wpm/pricing/yahoo.py` - Yahoo Finance price retriever implementation
  - `wpm/pricing/coingecko.py` - CoinGecko API price retriever implementation
  - `wpm/pricing/cache.py` - Persistent Parquet-based price cache management
  - `wpm/pricing/rate_limiter.py` - Rate limiting utility for API calls
  - `wpm/pricing/service.py` - Service that orchestrates price retrieval with caching and rate limiting
- `wpm/metrics.py` - Portfolio metrics and breakdown generation
- `wpm/utils.py` - Utility functions for validation, logging setup, and helpers
- `wpm/currency.py` - Currency conversion module using yfinance for forex rates
- `wpm/asset.py` - Asset metadata retrieval and caching module
- `wpm/reference/` - Reference portfolio creation package (baseline comparison portfolios)
  - `wpm/reference/__init__.py` - Package initialization and public API exports
  - `wpm/reference/strategy.py` - Abstract strategy interface and concrete implementations
  - `wpm/reference/portfolio.py` - Reference portfolio creation functions
  - `wpm/reference/fetcher.py` - Historical price fetcher interface and implementations
- `wpm/docs/` - Generated markdown documentation (included in version control and package distribution)

## Module Requirements

For detailed module requirements including responsibilities, key classes, functions, and implementation details for each module, see [modules.md](modules.md).

The library consists of the following modules:

- **wpm/models.py**: Core data structures (Asset, Trade, Position, Lot, Portfolio)
- **wpm/portfolio.py**: Portfolio management with aggregation logic, supporting simple and composite portfolios
- **wpm/importer.py**: CSV import functionality for trade data
- **wpm/cost_basis.py**: FIFO cost basis and lot calculation methods
- **wpm/config.py**: Application-level configuration management
- **wpm/pricing/**: Market price data retrieval package with caching and rate limiting
  - **base.py**: Abstract base class for price retrievers
  - **yahoo.py**: Yahoo Finance price retriever (stocks/ETFs and historical crypto)
  - **coingecko.py**: CoinGecko API retriever (current crypto prices)
  - **cache.py**: Persistent Parquet-based price cache
  - **historical_cache.py**: Historical price cache management
  - **rate_limiter.py**: API rate limiting utility
  - **service.py**: Price service orchestrating retrieval, caching, and rate limiting
- **wpm/metrics.py**: Portfolio metrics and breakdown generation
- **wpm/currency.py**: Currency conversion using yfinance
- **wpm/utils.py**: Utility functions for validation, logging, and trading hours
- **wpm/asset.py**: Asset metadata retrieval and caching using price retrievers
- **wpm/reference/**: Reference portfolio creation package for baseline comparison portfolios
  - **strategy.py**: Abstract strategy interface and concrete implementations (e.g., BuyAndHoldStrategy)
  - **portfolio.py**: Reference portfolio creation functions
  - **fetcher.py**: Historical price fetcher interface and implementations with lookback fallback

## Data Models

For detailed data model specifications including fields, validation rules, methods, and relationships, see [data-models.md](data-models.md).

The library defines the following core data models:

- **Asset**: Financial asset identifier with ticker and type
- **Trade**: Single buy or sell transaction with date, asset, price, quantity, and broker information
- **Position**: Current holdings for a specific asset (quantity and cost basis)
- **Lot**: Purchase record with FIFO sell matching for tracking realized/unrealized P/L
- **Portfolio**: Collection of asset positions or sub-portfolios (supports simple and composite portfolios)
- **PortfolioHistoryPoint**: Historical snapshot of portfolio state at a specific point in time, including total market value, asset positions, prices, quantities, and percentage return calculated as the ratio of unrealized P/L to cost basis aggregated across all asset lots
- **Price Cache Entry**: Cached price entry stored in Parquet format with validity rules

### CSV Import Format

**Required Columns:**
- `Date`: Trade date in YYYY-MM-DD format
- `Asset Name/Ticker`: Asset ticker symbol
- `Asset Type`: One of "Stock", "ETF", or "Crypto"
- `Action`: "Buy" or "Sell"
- `Broker`: Broker/platform name
- `Order Instruction` (optional): How the order was placed (e.g., "Limit", "Market", "Lump sum", "DRIP")
- `Trade Type` (optional): The category/strategy of the trade (e.g., "Discretionary", "Recurring buy", "DRIP")
- `Price`: Price per unit in native currency
- `Currency`: Currency code (e.g., "USD", "HKD") - required
- `Quantity`: Number of units

**Validation Rules:**
- All required columns must be present
- Date must be parseable as YYYY-MM-DD
- Asset Type must be valid (Stock, ETF, or Crypto)
- Action must be Buy or Sell
- Price and Quantity must be numeric and positive
- Missing optional fields (like Order Instruction and Trade Type) are allowed

## External Dependencies

### Core Dependencies
- **pandas** (>=1.5.0): CSV parsing and data manipulation
- **yfinance** (>=0.2.0): Yahoo Finance API for stock/ETF price data
- **pycoingecko** (>=3.1.0): CoinGecko API client for cryptocurrency price data
- **pyarrow** (>=10.0.0): Parquet file format support for persistent price caching
- **pandas_market_calendars** (>=4.3.0): US market calendar with holidays and trading hours
- **pytz** (>=2023.3): Timezone handling for trading hours calculations
- **python-dotenv** (>=1.0.0): Environment variable management from .env files

### Development Dependencies
- **pytest** (>=7.0.0): Testing framework
- **pytest-cov** (>=4.0.0): Code coverage plugin for pytest
- **pytest-mock** (>=3.10.0): Mocking utilities for tests

### Optional Dependencies
- **requests** (>=2.28.0): HTTP library (may be required by yfinance/pycoingecko)

### Documentation Dependencies
- **pydoc-markdown** (>=4.8.2): Markdown documentation generation from docstrings (development dependency)

## Documentation

### Documentation Generation

The library uses `pydoc-markdown` to generate markdown documentation from docstrings in the source code. This format is chosen for easier consumption by AI agents and human readers. `pydoc-markdown` is compatible with Python 3.13+ and supports multiple docstring styles.

**Documentation Tool:** `pydoc-markdown`

**Documentation Format:** Markdown (.md files)

**Documentation Location:** `src/wpm/docs/api.md` file within the package directory

**Documentation Scope:** All modules in `src/wpm/` directory (excluding test files)

**Generation Command:**
```bash
pydoc-markdown -I src -p wpm --render-toc > src/wpm/docs/api.md
```

**Version Control:** The generated documentation in `src/wpm/docs/` is included in version control (not in `.gitignore`) to ensure documentation is available and versioned alongside the codebase.

**Package Distribution:** The `docs/` directory is included in the distributed package via `pyproject.toml` configuration using `package-data`, ensuring users have access to the documentation upon installation. After installation, the documentation will be available at `wpm/docs/api.md` in the installed package.

**Installation:** `pydoc-markdown` is managed as a development dependency using `uv`:
```bash
uv add --dev pydoc-markdown
```

**Manual Generation:** Documentation is manually generated (not automated in CI/CD). Developers should regenerate documentation when docstrings are updated.

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
- FIFO basis calculations
- Buy and sell transaction processing
- Portfolio aggregation (simple and composite)
- Price retrieval with rate limiting
- Metrics calculation and breakdowns
- Error handling and validation

### Test Execution
- Run all tests: `pytest`
- Run with coverage: `pytest --cov=wpm --cov-report=html`
- Run specific test file: `pytest tests/test_portfolio.py`

## Portfolio Allocation Methods

The library provides methods to calculate percentage allocations of asset positions in portfolios. Allocations represent the proportion of each asset's market value relative to the total portfolio market value.

### Current Allocation Methods

- **`get_asset_allocation(asset, prices)`**: Returns the percentage allocation for a specific asset position. Calculated as (asset market value / total portfolio market value) * 100. Returns a Decimal rounded to 2 decimal places.

- **`get_all_allocations(prices, asset_types=None, asset_tickers=None)`**: Returns percentage allocations for all asset positions in the portfolio. Returns a dictionary mapping Asset to Decimal percentage. All allocations should sum to 100.00% (within rounding tolerance).
  - Optional `asset_types` parameter (list of strings): Filter by asset types (e.g., ["Stock", "ETF", "Crypto"]). If provided, only assets matching these types are included.
  - Optional `asset_tickers` parameter (list of strings): Filter by ticker symbols (e.g., ["GOOG", "AAPL"]). If provided, only assets with these tickers are included.
  - Filter logic: OR logic - an asset is included if it matches any specified asset type OR any specified ticker. If both parameters are None, all assets are included (backward compatible).
  - When filters are provided, allocations are calculated against the filtered asset list only (sum to 100% of filtered assets, not the entire portfolio).

### Historical Allocation Methods

- **`get_historical_allocations(portfolio, price_service, start_date, end_date)`**: Returns historical percentage allocations over a date range. Returns a list of dictionaries, one per date, mapping Asset to Decimal percentage allocation. Leverages batch price retrieval for efficiency.

### Utility Functions

- **`get_positions_with_allocations(portfolio, prices, asset_types=None, asset_tickers=None)`**: Combines positions and allocations in a single dictionary. Returns `Dict[Asset, Tuple[Position, Decimal]]` mapping each asset to its position and allocation percentage.
  - Optional `asset_types` parameter (list of strings): Filter by asset types using OR logic.
  - Optional `asset_tickers` parameter (list of strings): Filter by ticker symbols using OR logic.
  - Filter logic: OR logic - an asset is included if it matches any specified asset type OR any specified ticker. If both parameters are None, all assets are included (backward compatible).
  - Allocations are calculated against the filtered asset list only (sum to 100% of filtered assets).

- **`get_historical_positions_with_allocations(portfolio, price_service, start_date, end_date, asset_types=None, asset_tickers=None)`**: Combines historical positions and allocations. Returns a list of dictionaries, one per date, mapping Asset to tuple of (position_value, allocation_percentage).
  - Optional `asset_types` parameter (list of strings): Filter by asset types using OR logic.
  - Optional `asset_tickers` parameter (list of strings): Filter by ticker symbols using OR logic.
  - Filter logic: OR logic - an asset is included if it matches any specified asset type OR any specified ticker. If both parameters are None, all assets are included (backward compatible).
  - Allocations are calculated against the filtered asset list only (sum to 100% of filtered assets) for each date in the range.

### Implementation Details

- All allocation calculations use Python `Decimal` for precision to avoid floating-point errors
- Percentages are rounded to 2 decimal places using standard rounding (half up)
- Allocations are verified to sum to 100.00% (with small tolerance for rounding)
- For composite portfolios, asset positions are aggregated across sub-portfolios before calculating allocations
- Historical allocations reuse batch price retrieval from `get_historical_performance()` for efficiency

### CLI Display

The command-line interface displays allocation percentages alongside position information in the following commands:
- `show portfolio <name>`: Shows allocation for each asset in the portfolio
- `show all`: Shows allocation for each asset in the composite portfolio
- `show asset <ticker>`: Shows allocation for the specified asset (both current and historical modes)

Allocation is displayed in the format `| Allocation: XX.XX%` and is only shown when prices are available. For historical portfolios, allocation is shown for each date where the asset has a position. See [wpmrun.md](wpmrun.md) for detailed CLI command specifications.

### Reference Portfolio Integration

The CLI automatically creates SPY and BTC-USD buy-and-hold reference portfolios when importing CSV files. These reference portfolios provide baseline comparisons by mirroring the composite portfolio's trade structure but investing all cost basis into SPY and BTC-USD respectively. When using the `show all --up-to YYYY-MM-DD` command with historical portfolios, both reference portfolios' P/Ls are displayed after the weekly performance summary for easy comparison. See [wpmrun.md](wpmrun.md) for detailed CLI command specifications.

**Historical Price Fetcher:**
Reference portfolio creation uses a `HistoricalPriceFetcher` interface with a default implementation that provides fallback logic for weekends and holidays. When a crypto trade occurs on a weekend and is converted to a stock/ETF reference trade, the fetcher automatically looks back up to 1 week to find the previous trading day's price. 

Before processing trades, the strategy's `prepare()` method is called, which requests the price fetcher to batch fetch all prices for the reference asset over the entire portfolio date range (from start_date - 7 days to end_date). This ensures prices are prefetched and cached for all trade dates upfront, avoiding slow per-day fetches for portfolios with long histories. The fetcher maintains an internal cache of prefetched prices for efficient lookup during trade processing.

When requesting prices for weekends/holidays during lookback, the fetcher uses `cached_prices_only=True` to prevent the price retriever from being called (since stock prices cannot exist on non-trading days). This ensures reference portfolio creation succeeds even when original trades occur on non-trading days.

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
- INFO: Trade added, portfolio created, positions calculated, historical performance/allocation calculations
- DEBUG: Position aggregation steps, sub-portfolio traversal, allocation calculations, allocation sum verification

**wpm/cost_basis.py:**
- INFO: Cost basis calculation started/completed
- DEBUG: FIFO queue operations, sell matching

**wpm/pricing/:**
- **service.py**: INFO: Price retrieval request (ticker, asset_type), batch price request with count
- **cache.py**: INFO: Cache file load/save operations, cache hits with price, per-asset cache validation results; DEBUG: Cache entry lookups, cache validity checks (trading hours, age calculations), Parquet file I/O
- **rate_limiter.py**: INFO: Rate limit wait duration when rate limit is reached
- **yahoo.py**: DEBUG: API request details, price extraction results
- **coingecko.py**: DEBUG: API request details, coin ID mapping, price extraction results

**wpm/metrics.py:**
- INFO: Metrics calculation started/completed, breakdown generation
- DEBUG: Breakdown aggregation steps, metric computation details

**wpm/currency.py:**
- INFO: Currency cache load/save operations, cache hits with rate
- DEBUG: Forex rate retrieval details, currency conversion calculations

**wpm/asset.py:**
- INFO: Cache hits (when metadata is successfully retrieved from cache), batch retrieval summaries
- DEBUG: Cache misses, invalid entries, cache operations (load, save, validity checks), detailed retrieval steps
