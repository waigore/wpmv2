# Module Requirements

## wpm/models.py

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

## wpm/portfolio.py

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
- `clone(start_date=None, end_date=None)`: Create a deep copy of the portfolio
  - `start_date` (date, optional): Start date for filtering trades/sub-portfolios (inclusive). Must be within portfolio's date range if provided
  - `end_date` (date, optional): End date for filtering trades/sub-portfolios (inclusive). Must be within portfolio's date range if provided
  - Returns new Portfolio instance with cloned data
  - For SimplePortfolio: Deep clones all trades (creates new Trade objects). If date range provided, filters trades to those within the range (inclusive)
  - For CompositePortfolio: Recursively clones all sub-portfolios. If date range provided, passes it to sub-portfolio clones
  - Date range validation: For historical portfolios, the provided date range must be wholly contained within the portfolio's date range (inclusive)

**Key Functions:**
- `fetch_price_map(portfolio, price_service, target_date=None)`: Fetch prices for all assets in portfolio
  - Extracts assets from portfolio positions, groups them by asset type for batch processing
  - For historical portfolios (`is_historical=True`), automatically uses historical prices
  - If `target_date` is provided and portfolio is historical, uses that date; otherwise uses `portfolio.end_date`
  - For non-historical portfolios, uses current prices
  - Returns dictionary mapping Asset to Optional[float] price (None if price unavailable)
  - Handles exceptions gracefully by setting None for assets that fail to fetch
- `generate_historical_snapshots(portfolio, start_date, end_date)`: Generate historical snapshots of a portfolio for each date in range
  - `portfolio` (Portfolio, required): Portfolio to generate snapshots for
  - `start_date` (date, required): Start date for snapshot generation (inclusive)
  - `end_date` (date, required): End date for snapshot generation (inclusive)
  - Returns list of Portfolio clones, one for each date in the range
  - Each snapshot represents the portfolio state as of that date (cloned with `end_date=current_date`)
  - Date range must be within portfolio's date range (if portfolio has a date range)
- `get_historical_performance(portfolio, price_service, start_date, end_date)`: Get historical performance of a portfolio over a date range
  - `portfolio` (Portfolio, required): Portfolio to analyze (SimplePortfolio or CompositePortfolio)
  - `price_service` (PriceService, required): Price service for retrieving historical prices
  - `start_date` (date, required): Start date for performance tracking (inclusive)
  - `end_date` (date, required): End date for performance tracking (inclusive)
  - Returns list of PortfolioHistoryPoint objects, one for each day from start_date to end_date (inclusive)
  - Each history point contains:
    - `date`: The date this point represents
    - `total_market_value`: Total market value of the portfolio on that date
    - `asset_positions`: Dictionary mapping ticker symbols to position values (quantity * historical price)
  - Fetches all prices upfront in batch using `price_service.get_historical_prices()` once per asset type for the entire date range
  - Filters trades directly instead of cloning portfolio snapshots for better performance
  - For assets that exist in the final portfolio but weren't purchased by a given date, position value is 0.0
  - For composite portfolios, asset positions from sub-portfolios with the same ticker are automatically merged (summed)
  - Raises PortfolioError if date range is invalid or outside portfolio's date range
  - Raises ValueError if historical prices cannot be retrieved for any required assets (per user requirement)
  - Daily frequency means one history point per calendar day, including weekends (markets may be closed but portfolio state is valid)

**Artefacts:**
- Portfolio class implementations
- Aggregation logic for hierarchical structures

## wpm/importer.py

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

## wpm/cost_basis.py

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

## wpm/config.py

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

## wpm/pricing/

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

### wpm/pricing/base.py

**Responsibilities:**
- Define abstract base class for price retrievers
- Establish interface contract for single and batch price retrieval

**Key Classes:**
- `PriceRetriever`: Abstract base class for price retrieval (supports both single and batch retrieval)

**Key Methods:**
- `get_price(ticker, asset_type)`: Abstract method to get current price for an asset
- `get_prices(tickers, asset_type)`: Abstract method to get current prices for multiple assets in a batch request
- `get_historical_prices(ticker, asset_type, start_date, end_date)`: Abstract method to get historical prices over a date range
  - `ticker`: Asset ticker symbol (str) or list of ticker symbols (List[str]) for batch retrieval
  - Returns DataFrame with date index and price column (native currency) if ticker is str
  - Returns Dict[str, pd.DataFrame] mapping ticker to DataFrame if ticker is List[str] (batch mode)

### wpm/pricing/yahoo.py

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
  - `ticker`: Asset ticker symbol (str) or list of ticker symbols (List[str]) for batch retrieval
  - Uses `yf.download()` with start and end date parameters
  - When ticker is str: Returns DataFrame with date index and Close prices (native currency, USD for crypto)
  - When ticker is List[str]: Uses `yf.download()` with `group_by='ticker'` for batch retrieval, returns Dict[str, pd.DataFrame] mapping ticker to DataFrame
  - Supports crypto tickers (e.g., "BTC-USD", "ETH-USD") via yfinance
  - Uses `_map_crypto_ticker()` to map crypto tickers to yfinance format when needed (e.g., "SUI-USD" → "SUI20947-USD")
  - Batch mode fetches multiple tickers in a single API call for better performance

### wpm/pricing/coingecko.py

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

### wpm/pricing/cache.py

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

### wpm/pricing/historical_cache.py

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

### wpm/pricing/rate_limiter.py

**Responsibilities:**
- Implement rate limiting to respect API free tier limits
- Track API call timestamps and enforce maximum calls per minute

**Key Classes:**
- `RateLimiter`: Rate limiting utility for API calls

**Key Methods:**
- `wait_if_needed()`: Wait if rate limit would be exceeded (blocks execution until rate limit allows)

### wpm/pricing/service.py

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
  - Returns prices for all dates in the range (start_date to end_date, inclusive) for each ticker
  - Return type: `Dict[str, Dict[date, float]]` mapping ticker to dictionary mapping date to price
  - Fetches all prices for the entire date range upfront using batch retrieval
  - Checks historical cache first, fetches missing data from retrievers in batch
  - **For crypto**: Uses `YahooFinanceRetriever` (yfinance) instead of `CoinGeckoRetriever` to support longer historical ranges
  - **For stocks/ETFs**: Uses `YahooFinanceRetriever` as before
  - Uses batch ticker fetching when multiple tickers are provided (single API call per asset type)
  - Stores fetched prices in historical cache
  - Handles currency conversion for stocks/ETFs
  - Returns USD prices by default, native currency prices if `in_native_currency=True`
- `_get_retriever(asset_type)`: Internal method to get appropriate price retriever for current prices (YahooFinanceRetriever for Stock/ETF, CoinGeckoRetriever for Crypto)
  - Note: For historical prices, crypto uses YahooFinanceRetriever instead of CoinGeckoRetriever

**Artefacts:**
- Current market prices for assets

## wpm/metrics.py

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

## wpm/currency.py

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

## wpm/utils.py

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

## wpm/cli.py

**Responsibilities:**
- Provide command-line interface for portfolio management
- Handle CSV import and portfolio creation
- Interactive command loop for portfolio analysis
- Display portfolio information and metrics

**Key Functions:**
- `main()`: Main entry point for wpm CLI
- `run_interactive_mode(composite, price_service)`: Run interactive command loop
- `cmd_show_all(composite, price_service, up_to_date=None)`: Handle 'show all' command
  - `up_to_date` (Optional[date]): If provided and portfolio is historical, shows portfolio state up to this date with weekly performance summary
- `cmd_show_portfolio(composite, name, price_service, up_to_date=None)`: Handle 'show portfolio <name>' command
  - `up_to_date` (Optional[date]): If provided and portfolio is historical, shows portfolio state up to this date with weekly performance summary
- `cmd_list_portfolios(composite)`: Handle 'list portfolios' command
- `cmd_breakdown(composite, args)`: Handle 'breakdown' command
- `cmd_show_lots(composite, ticker, price_service)`: Handle 'lots <ticker>' command
- `parse_up_to_date(args)`: Parse --up-to date argument from command args
  - Returns tuple of (up_to_date or None, remaining args)
  - Parses `--up-to YYYY-MM-DD` format

**CLI Commands:**
- `import [--end-date YYYY-MM-DD]`: Import CSV files and create composite portfolio
  - `--end-date`: Optional end date for historical portfolio import
- `show all [--up-to YYYY-MM-DD]`: Show all assets in composite portfolio
  - `--up-to`: Optional date for historical portfolios. Shows weekly performance summary up to (and including) this date
- `show portfolio <name> [--up-to YYYY-MM-DD]`: Show specific portfolio
  - `--up-to`: Optional date for historical portfolios. Shows weekly performance summary up to (and including) this date
- `list portfolios`: List all sub-portfolios
- `breakdown [<name>] <type>`: Show portfolio breakdown by type (asset_type, ticker, purchase_period, broker)
- `lots <ticker>`: Show lots for a specific ticker

**Weekly Performance Summary:**
- When `--up-to` is specified for historical portfolios, displays weekly performance summary
- Uses `get_historical_performance()` to calculate history points from portfolio start_date to up_to_date
- Groups history points by calendar week (Monday to Sunday)
- Displays weekly totals: date range and total_market_value for each week
- Shows portfolio's weekly overall performance progression

**Artefacts:**
- Command-line interface for portfolio management
- Interactive command loop
