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
- `wpm/docs/` - Generated markdown documentation (included in version control and package distribution)

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
- `Lot`: Represents a purchase record with FIFO sell matching
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

**Portfolio Properties:**
- `is_historical` (bool): Flag indicating whether this is a historical portfolio (default: False)
- `start_date` (Optional[date]): Computed property returning the earliest trade date (SimplePortfolio) or earliest start_date of sub-portfolios (CompositePortfolio)
- `end_date` (Optional[date]): Computed property returning the most recent trade date (SimplePortfolio) or most recent end_date of sub-portfolios (CompositePortfolio)

**Historical Portfolio Support:**
- Historical portfolios are created by filtering trades up to a specific end_date
- Historical portfolios have `is_historical=True` and use historical prices for calculations
- For composite portfolios, all sub-portfolios must have identical `is_historical` flags (enforced in `add_sub_portfolio()`)
- When fetching prices for historical portfolios, the system automatically uses historical prices from the portfolio's `end_date`

**Key Functions:**
- `add_trade(trade)`: Add a trade to the portfolio
- `get_positions(asset_type=None, tickers=None)`: Get all asset positions in the portfolio
  - Optional `asset_type` parameter (single string): Filter by asset type (e.g., "Stock", "ETF", "Crypto")
  - Optional `tickers` parameter (list of strings): Filter by one or more ticker symbols
  - Both filters can be used together (AND logic - both conditions must match)
  - Uses LRU caching (manual cache with OrderedDict, max size 128)
  - Cache key: trades list + asset_type + tickers tuple
- `get_asset_trades(ticker, start_date=None, end_date=None)`: Get all trades for a specified asset (ticker) within the portfolio
  - `ticker` (str, required): Asset ticker symbol to filter trades by
  - `start_date` (date, optional): Start date for date range filter (inclusive). If not specified, includes trades from the very beginning
  - `end_date` (date, optional): End date for date range filter (inclusive). If not specified, includes trades to the very end
  - Returns list of Trade objects matching the ticker and date range (includes both Buy and Sell trades)
  - For SimplePortfolio: Filters trades from `_trades` list by ticker and date range
  - For CompositePortfolio: Aggregates asset trades from all sub-portfolios by calling `get_asset_trades` on each sub-portfolio and returning the combined result list
- `get_asset_lots(ticker, start_date=None, end_date=None, prices=None)`: Get all lots for a specified asset (ticker) within the portfolio
  - `ticker` (str, required): Asset ticker symbol to filter lots by
  - `start_date` (date, optional): Start date for date range filter (inclusive)
  - `end_date` (date, optional): End date for date range filter (inclusive)
  - `prices` (Dict[Asset, Optional[float]], optional): Current prices for P/L calculations
  - Returns list of Lot objects for the ticker
  - For SimplePortfolio: Calculates lots from filtered trades (benefits from cached lot calculations)
  - For CompositePortfolio: Aggregates lots from all sub-portfolios
- `get_total_cost_basis()`: Calculate total cost basis
  - Uses LRU caching (manual cache with OrderedDict, max size 128)
  - Cache key: trades list
- `get_total_market_value(prices)`: Calculate total market value from prices
  - NOT cached (prices change frequently)
- `get_total_unrealized_pnl(prices)`: Calculate total unrealized profit/loss
  - NOT cached (prices change frequently)
- `get_total_realized_pnl(prices)`: Calculate total realized profit/loss (derives from lots)
  - NOT cached (prices change frequently, though realized P/L doesn't depend on current prices)
- `get_total_quantity(ticker)`: Get total quantity for a specific asset
- `add_sub_portfolio(portfolio)`: Add a sub-portfolio (for composite portfolios)

**Key Functions:**
- `fetch_price_map(portfolio, price_service, target_date=None)`: Fetch prices for all assets in portfolio
  - Extracts assets from portfolio positions, groups them by asset type for batch processing
  - For historical portfolios (`is_historical=True`), automatically uses historical prices
  - If `target_date` is provided and portfolio is historical, uses that date; otherwise uses `portfolio.end_date`
  - For non-historical portfolios, uses current prices
  - Returns dictionary mapping Asset to Optional[float] price (None if price unavailable)
  - Handles exceptions gracefully by setting None for assets that fail to fetch

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
- `import_trades_from_csv(file_path, currency_service=None, end_date=None)`: Main import function
  - `end_date` (Optional[date]): If provided, only trades with date <= end_date are included
- `import_csv_files(import_dir, end_date=None)`: Import CSV files and create composite portfolio
  - `end_date` (Optional[date]): If provided, filters trades and creates historical portfolios with `is_historical=True`
- `validate_csv_structure(df)`: Validate CSV has required columns
- `parse_trade_row(row)`: Convert CSV row to Trade object

**Artefacts:**
- Imported Trade objects
- Validation error reports

### wpm/cost_basis.py

**Responsibilities:**
- Calculate lots from trades using FIFO method
- Calculate cost basis using FIFO method (now derives from lots)
- Handle both buy and sell transactions
- Track remaining positions after sells
- Cache lot calculations using LRU cache

**Key Functions:**
- `calculate_lots_from_trades(trades)`: Calculate lots from trades using FIFO
  - Processes trades chronologically
  - Creates lots from buy trades
  - Matches sell trades to lots using FIFO (earliest lots first)
  - Returns dictionary mapping Asset to list of Lot objects
  - Uses LRU caching (manual cache with OrderedDict, max size 128)
  - Cache key: hashable tuple of trade identifiers (date, asset, action, quantity, price)
- `calculate_fifo_cost_basis(trades)`: Calculate positions using FIFO
  - Now derives positions from lots internally
  - Aggregates lots into positions: quantity = sum of remaining_quantity, cost_basis = sum of purchase_price * remaining_quantity
  - Maintains same signature and behavior for backward compatibility

**Artefacts:**
- Lot objects with purchase records and matched sells
- Position objects with calculated cost basis and quantities (derived from lots)

### wpm/config.py

**Responsibilities:**
- Manage application-level configuration
- Load sensitive configuration (API keys, access tokens) from `.env` file using python-dotenv
- Define storage configuration (cache directories, file paths) as class variables
- Provide centralized configuration access for other modules

**Key Classes:**
- `Config`: Configuration class containing all application settings

**Configuration Categories:**
1. **Sensitive Configuration (from .env file):**
   - `COINGECKO_API_KEY`: Optional API key for CoinGecko API (loaded via `os.getenv()`)
   - Loaded using `python-dotenv`'s `load_dotenv()` function at module import time
   - Missing `.env` file is handled gracefully (optional values default to None)

2. **Storage Configuration (class variables):**
   - `CACHE_DIR`: Default cache directory path (`Path.home() / ".wpm"`)
   - `CACHE_FILE`: Default cache file path (`CACHE_DIR / "price_cache.parquet"`)
   - `CACHE_VALIDITY_MINUTES`: Cache validity threshold in minutes (default: 10)
   - `CURRENCY_CACHE_FILE`: Default currency cache file path (`CACHE_DIR / "currency_cache.parquet"`)
   - `CURRENCY_CACHE_VALIDITY_MINUTES`: Currency cache validity threshold in minutes (default: 1440, i.e., 24 hours)
   - `HISTORICAL_CACHE_FILE`: Default historical price cache file path (`CACHE_DIR / "historical_price_cache.parquet"`)

**Usage:**
- Other modules import `Config` class and access configuration via class attributes
- Example: `from wpm.config import Config; cache_file = Config.CACHE_FILE`
- Sensitive values are automatically loaded from `.env` file if present

**Artefacts:**
- Configuration class accessible throughout the application
- Sample `.env.example` file with placeholder values for sensitive configuration

### wpm/pricing/

**Responsibilities:**
- Retrieve current market prices for stocks/ETFs from Yahoo Finance via yfinance
- Retrieve current market prices for cryptocurrencies from CoinGecko API (with optional API key from `wpm.config.Config`)
- Implement rate limiting to respect API free tier limits
- Cache price data persistently using Parquet file format to minimize API calls across program runs
- Manage cache file lifecycle (load, save, expiration)
- Validate cache entries per asset based on asset type and trading hours
- Handle API errors and missing data gracefully
- Orchestrate price retrieval with caching and rate limiting via service layer
- References `wpm.config.Config` for cache directory, cache file path, cache validity duration, and CoinGecko API key

#### wpm/pricing/base.py

**Responsibilities:**
- Define abstract base class for price retrievers
- Establish interface contract for single and batch price retrieval

**Key Classes:**
- `PriceRetriever`: Abstract base class for price retrieval (supports both single and batch retrieval)

**Key Methods:**
- `get_price(ticker, asset_type)`: Abstract method to get current price for an asset
- `get_prices(tickers, asset_type)`: Abstract method to get current prices for multiple assets in a batch request
- `get_historical_prices(ticker, asset_type, start_date, end_date)`: Abstract method to get historical prices over a date range
  - Returns DataFrame with date index and price column (native currency)

#### wpm/pricing/yahoo.py

**Responsibilities:**
- Implement Yahoo Finance price retrieval using yfinance
- Support both single and batch price retrieval for stocks/ETFs
- Support historical price retrieval for crypto (via yfinance)
- Handle yfinance API responses and data extraction
- Use trading hours to determine appropriate price source (real-time prices during market hours, close prices otherwise)
- Detect currency from ticker suffix (e.g., `.HK` → `HKD`)
- Support Hong Kong stocks (ticker format: `XXXX.HK`, currency: `HKD`)
- Map crypto tickers to yfinance format when needed

**Key Classes:**
- `YahooFinanceRetriever`: yfinance-based retriever for stocks/ETFs and historical crypto prices (implements batch retrieval by default)

**Key Methods:**
- `_detect_currency(ticker)`: Detect currency from ticker suffix
  - Returns "HKD" for Hong Kong stocks (`.HK` suffix)
  - Returns "USD" for US stocks/ETFs (default)
- `_map_crypto_ticker(ticker)`: Map crypto ticker to yfinance ticker format
  - Returns mapped ticker if mapping exists (e.g., "SUI-USD" → "SUI20947-USD"), otherwise returns original ticker
  - Used internally by `get_historical_prices()` when `asset_type == "Crypto"`
- `get_price(ticker, asset_type)`: Get current price for a single stock/ETF in native currency
  - Detects currency from ticker
  - During trading hours: tries `currentPrice` or `regularMarketPrice` from `ticker.info` first, falls back to `Close` from historical data if unavailable
  - Outside trading hours: uses `Close` from historical data (`ticker.history()`)
  - Returns price in native currency (not USD)
- `get_prices(tickers, asset_type)`: Batch price retrieval using `yf.download()` to fetch multiple tickers in a single API request
  - During trading hours: tries `currentPrice` or `regularMarketPrice` from `ticker.info` for each ticker, falls back to `Close` from batch download if unavailable
  - Outside trading hours: uses `Close` from batch download
  - Returns prices in native currency (not USD)
- `get_historical_prices(ticker, asset_type, start_date, end_date)`: Get historical prices over a date range
  - Uses `yf.download()` with start and end date parameters
  - Returns DataFrame with date index and Close prices (native currency, USD for crypto)
  - Handles single ticker and multiple tickers (batch retrieval)
  - Supports crypto tickers (e.g., "BTC-USD", "ETH-USD") via yfinance
  - Uses `_map_crypto_ticker()` to map crypto tickers to yfinance format when needed (e.g., "SUI-USD" → "SUI20947-USD")

#### wpm/pricing/coingecko.py

**Responsibilities:**
- Implement CoinGecko API price retrieval
- Support both single and batch price retrieval for cryptocurrencies
- Handle ticker to CoinGecko coin ID mapping
- Use optional API key from `wpm.config.Config` for authenticated requests

**Key Classes:**
- `CoinGeckoRetriever`: CoinGecko API retriever for cryptocurrencies (implements batch retrieval by default)

**Key Methods:**
- `get_price(ticker, asset_type)`: Get current price for a single cryptocurrency
- `get_prices(tickers, asset_type)`: Batch price retrieval using CoinGecko's batch API endpoint to fetch multiple tickers in a single API request
- `get_historical_prices(ticker, asset_type, start_date, end_date)`: Get historical prices over a date range
  - **Note**: This method is NOT used for historical crypto prices. Historical crypto prices use `YahooFinanceRetriever` via `PriceService.get_historical_prices()`.
  - CoinGeckoRetriever is only used for current price retrieval (`get_price()`, `get_prices()`)
  - Historical price retrieval for crypto was moved to yfinance due to CoinGecko free tier limitations (365 days)

#### wpm/pricing/cache.py

**Responsibilities:**
- Manage persistent Parquet-based price cache
- Handle cache file lifecycle (load, save)
- Validate cache entries per asset based on asset type and age
- Provide methods to get valid cached prices and stale cached prices

**Key Classes:**
- `PriceCache`: Manages persistent Parquet-based price cache
- `CacheValidityStatus`: Enumeration for cache validity status (VALID, PARTIAL, STALE)
- `CacheValidity`: Dataclass containing cache validity status and stale entries

**Key Methods:**
- `get_cached_price(ticker, asset_type)`: Get cached USD price if valid (returns None if invalid or missing)
- `get_cached_price_native(ticker, asset_type)`: Get cached native currency price if valid (returns None if invalid or missing)
- `get_stale_cached_price(ticker, asset_type)`: Get cached USD price even if expired (returns None only if no cache entry exists)
- `get_stale_cached_price_native(ticker, asset_type)`: Get cached native currency price even if expired (returns None only if no cache entry exists)
- `set_cached_price(ticker, asset_type, price, native_price, native_currency, timestamp)`: Set/update cached price with both USD and native currency prices
- `get_cache_validity(tickers=None)`: Get cache validity status for all entries or specific tickers
  - Returns `CacheValidity` dataclass with:
    - `status`: One of `CacheValidityStatus.VALID`, `CacheValidityStatus.PARTIAL`, or `CacheValidityStatus.STALE`
    - `stale_entries`: List of dictionaries containing ticker, asset_type, price, and timestamp for stale entries
  - If `tickers` is provided, only checks those specific tickers; otherwise checks all cache entries
  - Empty cache returns `STALE` status with empty stale_entries list
  - Status determination:
    - `VALID`: All checked entries are valid (no stale entries)
    - `PARTIAL`: Some entries are valid, some are stale
    - `STALE`: All checked entries are stale (or cache is empty)
- `_load_cache()`: Load price cache from Parquet file (lazy loading, cached in memory)
- `_save_cache()`: Save price cache to Parquet file
- `_is_cache_valid(cache_entry, asset_type)`: Check if cached price is valid for a specific asset
  - For US stocks/ETFs: Cache must be less than 10 minutes old regardless of time of day.
  - For crypto: Cache must be less than 10 minutes old regardless of time of day.

**Artefacts:**
- Persistent Parquet cache file (default path from `wpm.config.Config.CACHE_FILE`, configurable via constructor parameter)
- Cache file contains: ticker, asset_type, price (USD), native_price, native_currency, timestamp columns
- Cache schema migration: Automatically migrates old cache files (without native_price/native_currency) to new schema

#### wpm/pricing/historical_cache.py

**Responsibilities:**
- Manage persistent Parquet-based historical price cache
- Store daily prices for date ranges per asset
- Provide methods to retrieve historical prices for specific dates or date ranges
- Support clearing prices for specific assets or entire cache

**Key Classes:**
- `HistoricalPriceCache`: Manages persistent Parquet-based historical price cache

**Key Methods:**
- `get_cached_prices(ticker, asset_type, start_date, end_date)`: Get cached prices for a date range
  - Returns DataFrame with date index and price column if cache has coverage for the range
  - Returns None if no cache entry exists
- `get_cached_price(ticker, asset_type, target_date)`: Get cached price for a specific date
  - Returns most recent price available up to target_date
  - Returns None if no cache entry exists
- `set_cached_prices(ticker, asset_type, prices_df, native_prices_df, native_currency)`: Store daily prices for a date range
  - Stores both USD and native currency prices
  - Merges with existing cached data (overwrites overlapping dates)
- `clear_asset(ticker, asset_type)`: Clear all cached prices for a specific asset
- `clear_all()`: Clear entire historical cache

**Artefacts:**
- Persistent Parquet cache file (default path from `wpm.config.Config.HISTORICAL_CACHE_FILE`)
- Cache file contains: ticker, asset_type, date, price (USD), native_price, native_currency columns
- Cache validity: Historical cache entries are always valid (no expiration)

#### wpm/pricing/rate_limiter.py

**Responsibilities:**
- Implement rate limiting to respect API free tier limits
- Track API call timestamps and enforce maximum calls per minute

**Key Classes:**
- `RateLimiter`: Rate limiting utility for API calls

**Key Methods:**
- `wait_if_needed()`: Wait if rate limit would be exceeded (blocks execution until rate limit allows)

#### wpm/pricing/service.py

**Responsibilities:**
- Orchestrate price retrieval with caching and rate limiting
- Coordinate between cache, rate limiter, and appropriate price retriever
- Provide unified API for single and batch price retrieval

**Key Classes:**
- `PriceService`: Service that orchestrates price retrieval with caching and rate limiting

**Key Methods:**
- `get_price(ticker, asset_type, in_native_currency=False)`: Get current price for an asset (checks cache first, validates per asset, uses appropriate retriever if cache miss)
  - Returns USD price by default (accounting currency)
  - Returns native currency price if `in_native_currency=True`
  - For stocks/ETFs: detects currency from ticker, retrieves native price, converts to USD, stores both in cache
  - For crypto: price is already in USD (native currency is USD)
- `get_prices(tickers, asset_type, in_native_currency=False)`: Batch price retrieval with rate limiting (uses batch API calls by default)
  - Checks cache for all tickers first
  - Fetches uncached tickers using batch API call from appropriate retriever
  - For stocks/ETFs: detects currency for each ticker, converts native prices to USD, stores both in cache
  - Returns USD prices by default, native currency prices if `in_native_currency=True`
  - For tickers that fail API retrieval: if stale cache exists, log warning and use stale price; if no cache exists, raise ValueError
- `get_historical_price(ticker, asset_type, target_date, in_native_currency=False)`: Get historical price for an asset on a specific date
  - Returns price for target_date (most recent available up to target_date)
  - Returns USD price by default, native currency price if `in_native_currency=True`
  - Uses historical cache and retrievers as needed
- `get_historical_prices(tickers, asset_type, start_date, end_date, in_native_currency=False)`: Get historical prices for multiple assets over a date range
  - Returns prices for end_date (most recent available up to end_date) for each ticker
  - Checks historical cache first, fetches missing data from retrievers
  - **For crypto**: Uses `YahooFinanceRetriever` (yfinance) instead of `CoinGeckoRetriever` to support longer historical ranges
  - **For stocks/ETFs**: Uses `YahooFinanceRetriever` as before
  - Stores fetched prices in historical cache
  - Handles currency conversion for stocks/ETFs
  - Returns USD prices by default, native currency prices if `in_native_currency=True`
- `_get_retriever(asset_type)`: Internal method to get appropriate price retriever for current prices (YahooFinanceRetriever for Stock/ETF, CoinGeckoRetriever for Crypto)
  - Note: For historical prices, crypto uses YahooFinanceRetriever instead of CoinGeckoRetriever

**Artefacts:**
- Current market prices for assets

### wpm/metrics.py

**Responsibilities:**
- Generate portfolio metrics and breakdowns
- Calculate per-asset cost basis and quantity
- Calculate overall portfolio cost basis (including sub-portfolios)
- Generate breakdowns by asset type, ticker, purchase period, and broker
- Calculate market values when price data is available

**Key Functions:**
- `calculate_portfolio_metrics(portfolio)`: Main metrics calculation
- `breakdown_by_asset_type(portfolio)`: Group metrics by asset type
- `breakdown_by_ticker(portfolio)`: Group metrics by ticker
- `breakdown_by_purchase_period(portfolio, period='month')`: Group by time period
- `breakdown_by_broker(portfolio)`: Group metrics by broker
- `calculate_market_value(portfolio, prices)`: Calculate current market value

**Artefacts:**
- Metrics dictionaries/dataframes
- Breakdown reports

### wpm/currency.py

**Responsibilities:**
- Retrieve forex exchange rates using yfinance API
- Convert amounts between currencies (with USD as default counter currency)
- Cache forex rates with 24-hour validity to minimize API calls
- Manage currency cache file lifecycle

**Key Classes:**
- `CurrencyService`: Service for currency conversion using yfinance
- `CurrencyCache`: Manages persistent Parquet-based currency rate cache

**Key Methods:**
- `CurrencyService.get_forex_rate(base_currency, counter_currency="USD")`: Get forex exchange rate
  - Uses yfinance API with format `{BASE}{COUNTER}=X` (e.g., `HKDUSD=X`)
  - Returns exchange rate where 1 base = X counter
  - Uses CurrencyCache for caching
- `CurrencyService.convert_to_usd(amount, from_currency)`: Convert amount from any currency to USD
  - Returns amount unchanged if from_currency is USD
- `CurrencyCache.get_cached_rate(base_currency, counter_currency="USD")`: Get cached rate if valid (24-hour validity)
- `CurrencyCache.set_cached_rate(base_currency, counter_currency, rate, timestamp)`: Set/update cached rate

**Artefacts:**
- Persistent Parquet currency cache file (default path from `wpm.config.Config.CURRENCY_CACHE_FILE`)
- Cache file contains: base_currency, counter_currency, rate, timestamp columns
- Cache validity: 24 hours (1440 minutes)

### wpm/utils.py

**Responsibilities:**
- Provide utility functions for validation
- Set up centralized logging configuration
- Helper functions for date parsing, ticker normalization, etc.
- Determine US market trading hours for price fetching logic

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
- `order_instruction` (str, optional): How the order was placed (e.g., "Limit", "Market", "Lump sum", "DRIP")
  - Validation: Non-empty string if provided
- `trade_type` (str, optional): The category/strategy of the trade (e.g., "Discretionary", "Recurring buy", "DRIP")
  - Validation: Non-empty string if provided
- `currency` (str, required): Original trade currency code (e.g., "USD", "HKD")
  - Validation: Non-empty string
- `price` (float, required): Price per unit in USD (accounting currency)
  - Validation: Positive number, greater than 0
- `price_native` (float, required): Price per unit in native currency (if currency is USD, this equals price)
  - Validation: Positive number, greater than 0
  - Must equal `price` when `currency` is "USD"
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
- `cost_basis_method` (str, required): Method used ("fifo")
- `average_cost` (float, computed): Average cost per unit
  - Calculation: `cost_basis / quantity` if quantity > 0, else 0

**Methods:**
- `get_average_cost()`: Returns average cost per unit

### Lot

Represents a purchase record (lot) for an asset with FIFO sell matching. A lot tracks the original purchase and accounts for sell trades using FIFO method.

**Fields:**
- `purchase_date` (date, required): Date of the buy trade that created this lot
  - Validation: Valid date object
- `purchase_price` (float, required): Price per unit from the buy trade (USD)
  - Validation: Positive number, greater than 0
- `original_quantity` (Decimal, required): Original quantity from the buy trade
  - Validation: Positive number, greater than 0
- `remaining_quantity` (Decimal, required): Quantity remaining after FIFO sell matching
  - Validation: Non-negative number, must be <= original_quantity
- `cost_basis` (float, required): Total cost basis (purchase_price * original_quantity)
  - Validation: Non-negative number
- `asset` (Asset, required): The asset this lot represents
  - Validation: Must be an Asset object
- `broker` (str, required): Broker from the buy trade that created this lot
  - Validation: Non-empty string
  - The broker value is derived from the initial buy trade that created the lot
- `matched_sells` (List[Tuple[Trade, Decimal]], required): List of (sell_trade, quantity_sold) tuples
  - Tracks which sell trades matched against this lot and how much was sold
  - Validation: List of tuples where first element is a Trade object and second is a positive Decimal

**Methods:**
- `get_realized_pnl()`: Calculate realized profit/loss from matched sells
  - Returns: Sum of (sell_price - purchase_price) * quantity_sold for all matched sells
- `get_unrealized_pnl(current_price)`: Calculate unrealized profit/loss for remaining quantity
  - Args: `current_price` (float): Current market price per unit
  - Returns: (current_price - purchase_price) * remaining_quantity
- `get_total_pnl(current_price)`: Calculate total profit/loss (realized + unrealized)
  - Args: `current_price` (Optional[float]): Current market price per unit
  - Returns: Sum of realized P/L and unrealized P/L

### Portfolio

Represents a collection of asset positions or sub-portfolios.

**Fields:**
- `name` (str, required): Portfolio identifier/name
  - Validation: Non-empty string
- `trades` (list[Trade], optional): List of trades in this portfolio (for simple portfolios)
- `sub_portfolios` (list[Portfolio], optional): List of sub-portfolios (for composite portfolios)

**Computed Properties:**
- `positions`: Dictionary mapping Asset to Position objects
  - For simple portfolios: Calculated from trades using FIFO cost basis method (now derives from lots)
  - For composite portfolios: Aggregated from sub-portfolios
- `total_quantity(asset)`: Total quantity for a specific asset across all positions

**ETL Flow:**
- Trades (from CSV) → Lots (derived on-demand) → Position (aggregated from lots)

**Methods:**
- `add_trade(trade)`: Add a trade to the portfolio
- `get_positions(asset_type=None, tickers=None)`: Get all positions as a dictionary
  - Optional `asset_type` parameter (single string): Filter by asset type (e.g., "Stock", "ETF", "Crypto")
  - Optional `tickers` parameter (list of strings): Filter by one or more ticker symbols
  - Both filters can be used together (AND logic - both conditions must match)
  - For simple portfolios: Calculated from trades using specified cost basis method, then filtered
  - For composite portfolios: Aggregated from sub-portfolios with filters applied at sub-portfolio level
- `get_position(asset)`: Get position for a specific asset
- `get_asset_trades(ticker, start_date=None, end_date=None)`: Get all trades for a specified asset (ticker) within the portfolio
  - `ticker` (str, required): Asset ticker symbol to filter trades by
  - `start_date` (date, optional): Start date for date range filter (inclusive). If not specified, includes trades from the very beginning
  - `end_date` (date, optional): End date for date range filter (inclusive). If not specified, includes trades to the very end
  - Returns list of Trade objects matching the ticker and date range (includes both Buy and Sell trades)
  - For simple portfolios: Filters trades from `_trades` list by ticker and date range
  - For composite portfolios: Aggregates asset trades from all sub-portfolios by calling `get_asset_trades` on each sub-portfolio and returning the combined result list
- `get_asset_lots(ticker, start_date=None, end_date=None, prices=None)`: Get all lots for a specified asset (ticker) within the portfolio
  - `ticker` (str, required): Asset ticker symbol to filter lots by
  - `start_date` (date, optional): Start date for date range filter (inclusive). If not specified, includes lots from the very beginning
  - `end_date` (date, optional): End date for date range filter (inclusive). If not specified, includes lots to the very end
  - `prices` (Dict[Asset, Optional[float]], optional): Current prices for P/L calculations
  - Returns list of Lot objects for the ticker
  - For simple portfolios: Calculates lots from filtered trades using FIFO
  - For composite portfolios: Aggregates lots from all sub-portfolios
- `get_total_cost_basis()`: Calculate total cost basis
  - For simple portfolios: Sum of all position cost_basis values (uses LRU caching)
  - For composite portfolios: Sum of total_cost_basis from all sub-portfolios
- `get_total_market_value(prices)`: Calculate total market value
  - For simple portfolios: Sum of (quantity * price) for all positions where price is available
  - For composite portfolios: Sum of total_market_value from all sub-portfolios
  - Accepts `prices: Dict[Asset, Optional[float]]` parameter
  - Assets with missing/None prices are excluded from the sum
  - Note: NOT cached due to frequent price changes
- `get_total_unrealized_pnl(prices)`: Calculate total unrealized profit/loss
  - For simple portfolios: `total_market_value - total_cost_basis`
  - For composite portfolios: Sum of total_unrealized_pnl from all sub-portfolios
  - Accepts `prices: Dict[Asset, Optional[float]]` parameter
  - Unrealized P/L is calculated as market_value - cost_basis
  - Note: NOT cached due to frequent price changes
- `get_total_realized_pnl(prices)`: Calculate total realized profit/loss
  - Derives from lots' realized P/L: Sum of `lot.get_realized_pnl()` for all lots in portfolio
  - For simple portfolios: Calculate lots from trades, sum realized P/L from all lots
  - For composite portfolios: Sum realized P/L from all sub-portfolios
  - Accepts `prices: Dict[Asset, Optional[float]]` parameter (for consistency, though realized P/L doesn't depend on current prices)
  - Returns total realized profit/loss in USD
  - Note: NOT cached due to frequent price changes (though realized P/L doesn't actually depend on current prices)
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
- `price` (float, required): Cached price in USD (accounting currency)
  - Validation: Positive number
- `native_price` (float, required): Cached price in native currency
  - Validation: Positive number
- `native_currency` (str, required): Currency code (e.g., "HKD", "USD")
  - Validation: Non-empty string
- `timestamp` (datetime, required): When the price was retrieved and cached
  - Validation: Valid datetime object

**Cache Validity Rules:**

Validity is determined per asset individually based on asset type:

1. **US Stocks/ETFs:**
   - Cache is valid only if less than 10 minutes old from current time, regardless of time of day.

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

