# Table of Contents

* [wpm](#wpm)
* [wpm.metrics](#wpm.metrics)
  * [calculate\_portfolio\_metrics](#wpm.metrics.calculate_portfolio_metrics)
  * [breakdown\_by\_asset\_type](#wpm.metrics.breakdown_by_asset_type)
  * [breakdown\_by\_ticker](#wpm.metrics.breakdown_by_ticker)
  * [breakdown\_by\_purchase\_period](#wpm.metrics.breakdown_by_purchase_period)
  * [breakdown\_by\_broker](#wpm.metrics.breakdown_by_broker)
  * [calculate\_market\_value](#wpm.metrics.calculate_market_value)
* [wpm.config](#wpm.config)
  * [Config](#wpm.config.Config)
    * [CURRENCY\_CACHE\_VALIDITY\_MINUTES](#wpm.config.Config.CURRENCY_CACHE_VALIDITY_MINUTES)
    * [COINGECKO\_API\_KEY](#wpm.config.Config.COINGECKO_API_KEY)
    * [COINGECKO\_API\_IS\_DEMO](#wpm.config.Config.COINGECKO_API_IS_DEMO)
* [wpm.importer](#wpm.importer)
  * [validate\_csv\_structure](#wpm.importer.validate_csv_structure)
  * [parse\_trade\_row](#wpm.importer.parse_trade_row)
  * [import\_trades\_from\_csv](#wpm.importer.import_trades_from_csv)
  * [extract\_portfolio\_name](#wpm.importer.extract_portfolio_name)
  * [import\_csv\_files](#wpm.importer.import_csv_files)
* [wpm.models](#wpm.models)
  * [ValidationError](#wpm.models.ValidationError)
  * [PortfolioError](#wpm.models.PortfolioError)
  * [Asset](#wpm.models.Asset)
    * [\_\_post\_init\_\_](#wpm.models.Asset.__post_init__)
    * [\_\_hash\_\_](#wpm.models.Asset.__hash__)
  * [Trade](#wpm.models.Trade)
    * [price](#wpm.models.Trade.price)
    * [price\_native](#wpm.models.Trade.price_native)
    * [\_\_post\_init\_\_](#wpm.models.Trade.__post_init__)
    * [total\_value](#wpm.models.Trade.total_value)
    * [is\_buy](#wpm.models.Trade.is_buy)
    * [is\_sell](#wpm.models.Trade.is_sell)
  * [Lot](#wpm.models.Lot)
    * [\_\_post\_init\_\_](#wpm.models.Lot.__post_init__)
    * [get\_realized\_pnl](#wpm.models.Lot.get_realized_pnl)
    * [get\_unrealized\_pnl](#wpm.models.Lot.get_unrealized_pnl)
    * [get\_total\_pnl](#wpm.models.Lot.get_total_pnl)
  * [Position](#wpm.models.Position)
    * [\_\_post\_init\_\_](#wpm.models.Position.__post_init__)
    * [get\_average\_cost](#wpm.models.Position.get_average_cost)
    * [average\_cost](#wpm.models.Position.average_cost)
  * [Portfolio](#wpm.models.Portfolio)
    * [\_\_init\_\_](#wpm.models.Portfolio.__init__)
    * [get\_positions](#wpm.models.Portfolio.get_positions)
    * [get\_total\_cost\_basis](#wpm.models.Portfolio.get_total_cost_basis)
    * [get\_all\_trades](#wpm.models.Portfolio.get_all_trades)
    * [get\_assets](#wpm.models.Portfolio.get_assets)
    * [get\_asset\_trades](#wpm.models.Portfolio.get_asset_trades)
    * [get\_total\_market\_value](#wpm.models.Portfolio.get_total_market_value)
    * [get\_total\_unrealized\_pnl](#wpm.models.Portfolio.get_total_unrealized_pnl)
    * [get\_asset\_lots](#wpm.models.Portfolio.get_asset_lots)
    * [get\_total\_realized\_pnl](#wpm.models.Portfolio.get_total_realized_pnl)
    * [get\_asset\_realized\_pnl](#wpm.models.Portfolio.get_asset_realized_pnl)
    * [clone](#wpm.models.Portfolio.clone)
    * [get\_asset\_positions\_by\_broker](#wpm.models.Portfolio.get_asset_positions_by_broker)
    * [get\_position](#wpm.models.Portfolio.get_position)
  * [PortfolioHistoryPoint](#wpm.models.PortfolioHistoryPoint)
    * [asset\_positions](#wpm.models.PortfolioHistoryPoint.asset_positions)
    * [prices](#wpm.models.PortfolioHistoryPoint.prices)
    * [quantities](#wpm.models.PortfolioHistoryPoint.quantities)
    * [\_\_post\_init\_\_](#wpm.models.PortfolioHistoryPoint.__post_init__)
* [wpm.asset](#wpm.asset)
  * [AssetMetadataCache](#wpm.asset.AssetMetadataCache)
    * [\_\_init\_\_](#wpm.asset.AssetMetadataCache.__init__)
    * [get\_cached\_metadata](#wpm.asset.AssetMetadataCache.get_cached_metadata)
    * [get\_cached\_metadata\_batch](#wpm.asset.AssetMetadataCache.get_cached_metadata_batch)
    * [set\_cached\_metadata](#wpm.asset.AssetMetadataCache.set_cached_metadata)
    * [set\_cached\_metadata\_batch](#wpm.asset.AssetMetadataCache.set_cached_metadata_batch)
  * [AssetService](#wpm.asset.AssetService)
    * [\_\_init\_\_](#wpm.asset.AssetService.__init__)
    * [get\_metadata](#wpm.asset.AssetService.get_metadata)
    * [get\_metadata\_batch](#wpm.asset.AssetService.get_metadata_batch)
    * [update\_metadata](#wpm.asset.AssetService.update_metadata)
    * [update\_metadata\_batch](#wpm.asset.AssetService.update_metadata_batch)
* [wpm.cost\_basis](#wpm.cost_basis)
  * [calculate\_lots\_from\_trades](#wpm.cost_basis.calculate_lots_from_trades)
  * [calculate\_fifo\_cost\_basis](#wpm.cost_basis.calculate_fifo_cost_basis)
* [wpm.cli](#wpm.cli)
  * [setup\_cli\_logging](#wpm.cli.setup_cli_logging)
  * [parse\_args](#wpm.cli.parse_args)
  * [fetch\_prices\_for\_portfolio](#wpm.cli.fetch_prices_for_portfolio)
  * [format\_currency](#wpm.cli.format_currency)
  * [format\_unrealized\_pnl](#wpm.cli.format_unrealized_pnl)
  * [format\_quantity](#wpm.cli.format_quantity)
  * [parse\_up\_to\_date](#wpm.cli.parse_up_to_date)
  * [parse\_from\_date](#wpm.cli.parse_from_date)
  * [parse\_brokers](#wpm.cli.parse_brokers)
  * [format\_position\_line](#wpm.cli.format_position_line)
  * [format\_historical\_asset\_line](#wpm.cli.format_historical_asset_line)
  * [cmd\_list\_portfolios](#wpm.cli.cmd_list_portfolios)
  * [cmd\_show\_portfolio](#wpm.cli.cmd_show_portfolio)
  * [cmd\_show\_all](#wpm.cli.cmd_show_all)
  * [cmd\_show\_asset](#wpm.cli.cmd_show_asset)
  * [format\_breakdown\_asset\_type](#wpm.cli.format_breakdown_asset_type)
  * [format\_breakdown\_ticker](#wpm.cli.format_breakdown_ticker)
  * [format\_breakdown\_purchase\_period](#wpm.cli.format_breakdown_purchase_period)
  * [format\_breakdown\_broker](#wpm.cli.format_breakdown_broker)
  * [cmd\_breakdown](#wpm.cli.cmd_breakdown)
  * [format\_lot\_line](#wpm.cli.format_lot_line)
  * [cmd\_show\_lots](#wpm.cli.cmd_show_lots)
  * [format\_market\_cap](#wpm.cli.format_market_cap)
  * [cmd\_help](#wpm.cli.cmd_help)
  * [cmd\_metadata](#wpm.cli.cmd_metadata)
  * [run\_interactive\_mode](#wpm.cli.run_interactive_mode)
  * [main](#wpm.cli.main)
* [wpm.cache\_utils](#wpm.cache_utils)
  * [LRUCache](#wpm.cache_utils.LRUCache)
    * [\_\_init\_\_](#wpm.cache_utils.LRUCache.__init__)
    * [get](#wpm.cache_utils.LRUCache.get)
    * [set](#wpm.cache_utils.LRUCache.set)
    * [clear](#wpm.cache_utils.LRUCache.clear)
    * [\_\_len\_\_](#wpm.cache_utils.LRUCache.__len__)
  * [trades\_to\_cache\_key](#wpm.cache_utils.trades_to_cache_key)
  * [trades\_to\_cache\_key\_with\_filters](#wpm.cache_utils.trades_to_cache_key_with_filters)
* [wpm.utils](#wpm.utils)
  * [setup\_logging](#wpm.utils.setup_logging)
  * [validate\_ticker](#wpm.utils.validate_ticker)
  * [normalize\_date](#wpm.utils.normalize_date)
  * [validate\_asset\_type](#wpm.utils.validate_asset_type)
  * [concat\_dataframes](#wpm.utils.concat_dataframes)
  * [is\_us\_market\_open](#wpm.utils.is_us_market_open)
  * [is\_within\_trading\_hours](#wpm.utils.is_within_trading_hours)
* [wpm.currency](#wpm.currency)
  * [CurrencyCache](#wpm.currency.CurrencyCache)
    * [\_\_init\_\_](#wpm.currency.CurrencyCache.__init__)
    * [get\_cached\_rate](#wpm.currency.CurrencyCache.get_cached_rate)
    * [set\_cached\_rate](#wpm.currency.CurrencyCache.set_cached_rate)
  * [CurrencyService](#wpm.currency.CurrencyService)
    * [\_\_init\_\_](#wpm.currency.CurrencyService.__init__)
    * [get\_forex\_rate](#wpm.currency.CurrencyService.get_forex_rate)
    * [convert\_to\_usd](#wpm.currency.CurrencyService.convert_to_usd)
* [wpm.portfolio](#wpm.portfolio)
  * [SimplePortfolio](#wpm.portfolio.SimplePortfolio)
    * [\_\_init\_\_](#wpm.portfolio.SimplePortfolio.__init__)
    * [add\_trade](#wpm.portfolio.SimplePortfolio.add_trade)
    * [get\_positions](#wpm.portfolio.SimplePortfolio.get_positions)
    * [get\_total\_cost\_basis](#wpm.portfolio.SimplePortfolio.get_total_cost_basis)
    * [get\_total\_market\_value](#wpm.portfolio.SimplePortfolio.get_total_market_value)
    * [get\_total\_unrealized\_pnl](#wpm.portfolio.SimplePortfolio.get_total_unrealized_pnl)
    * [get\_asset\_lots](#wpm.portfolio.SimplePortfolio.get_asset_lots)
    * [get\_asset\_positions\_by\_broker](#wpm.portfolio.SimplePortfolio.get_asset_positions_by_broker)
    * [get\_total\_realized\_pnl](#wpm.portfolio.SimplePortfolio.get_total_realized_pnl)
    * [get\_asset\_realized\_pnl](#wpm.portfolio.SimplePortfolio.get_asset_realized_pnl)
    * [get\_asset\_allocation](#wpm.portfolio.SimplePortfolio.get_asset_allocation)
    * [get\_all\_allocations](#wpm.portfolio.SimplePortfolio.get_all_allocations)
    * [get\_all\_trades](#wpm.portfolio.SimplePortfolio.get_all_trades)
    * [get\_assets](#wpm.portfolio.SimplePortfolio.get_assets)
    * [get\_asset\_trades](#wpm.portfolio.SimplePortfolio.get_asset_trades)
    * [clone](#wpm.portfolio.SimplePortfolio.clone)
    * [start\_date](#wpm.portfolio.SimplePortfolio.start_date)
    * [end\_date](#wpm.portfolio.SimplePortfolio.end_date)
  * [CompositePortfolio](#wpm.portfolio.CompositePortfolio)
    * [\_\_init\_\_](#wpm.portfolio.CompositePortfolio.__init__)
    * [add\_sub\_portfolio](#wpm.portfolio.CompositePortfolio.add_sub_portfolio)
    * [get\_sub\_portfolios](#wpm.portfolio.CompositePortfolio.get_sub_portfolios)
    * [get\_positions](#wpm.portfolio.CompositePortfolio.get_positions)
    * [get\_total\_cost\_basis](#wpm.portfolio.CompositePortfolio.get_total_cost_basis)
    * [get\_total\_market\_value](#wpm.portfolio.CompositePortfolio.get_total_market_value)
    * [get\_total\_unrealized\_pnl](#wpm.portfolio.CompositePortfolio.get_total_unrealized_pnl)
    * [get\_asset\_lots](#wpm.portfolio.CompositePortfolio.get_asset_lots)
    * [get\_asset\_positions\_by\_broker](#wpm.portfolio.CompositePortfolio.get_asset_positions_by_broker)
    * [get\_total\_realized\_pnl](#wpm.portfolio.CompositePortfolio.get_total_realized_pnl)
    * [get\_asset\_realized\_pnl](#wpm.portfolio.CompositePortfolio.get_asset_realized_pnl)
    * [get\_asset\_allocation](#wpm.portfolio.CompositePortfolio.get_asset_allocation)
    * [get\_all\_allocations](#wpm.portfolio.CompositePortfolio.get_all_allocations)
    * [get\_all\_trades](#wpm.portfolio.CompositePortfolio.get_all_trades)
    * [get\_assets](#wpm.portfolio.CompositePortfolio.get_assets)
    * [get\_asset\_trades](#wpm.portfolio.CompositePortfolio.get_asset_trades)
    * [start\_date](#wpm.portfolio.CompositePortfolio.start_date)
    * [end\_date](#wpm.portfolio.CompositePortfolio.end_date)
    * [clone](#wpm.portfolio.CompositePortfolio.clone)
  * [fetch\_price\_map](#wpm.portfolio.fetch_price_map)
  * [generate\_historical\_snapshots](#wpm.portfolio.generate_historical_snapshots)
  * [get\_historical\_performance](#wpm.portfolio.get_historical_performance)
  * [get\_historical\_allocations](#wpm.portfolio.get_historical_allocations)
  * [get\_positions\_with\_allocations](#wpm.portfolio.get_positions_with_allocations)
  * [get\_historical\_positions\_with\_allocations](#wpm.portfolio.get_historical_positions_with_allocations)
* [wpm.pricing.service](#wpm.pricing.service)
  * [PriceService](#wpm.pricing.service.PriceService)
    * [\_\_init\_\_](#wpm.pricing.service.PriceService.__init__)
    * [get\_retriever](#wpm.pricing.service.PriceService.get_retriever)
    * [get\_stock\_retriever](#wpm.pricing.service.PriceService.get_stock_retriever)
    * [detect\_currency](#wpm.pricing.service.PriceService.detect_currency)
    * [get\_price](#wpm.pricing.service.PriceService.get_price)
    * [get\_prices](#wpm.pricing.service.PriceService.get_prices)
    * [get\_historical\_price](#wpm.pricing.service.PriceService.get_historical_price)
    * [get\_historical\_prices](#wpm.pricing.service.PriceService.get_historical_prices)
* [wpm.pricing.coingecko](#wpm.pricing.coingecko)
  * [CoinGeckoRetriever](#wpm.pricing.coingecko.CoinGeckoRetriever)
    * [metadata\_supported](#wpm.pricing.coingecko.CoinGeckoRetriever.metadata_supported)
    * [\_\_init\_\_](#wpm.pricing.coingecko.CoinGeckoRetriever.__init__)
    * [get\_price](#wpm.pricing.coingecko.CoinGeckoRetriever.get_price)
    * [get\_prices](#wpm.pricing.coingecko.CoinGeckoRetriever.get_prices)
    * [get\_historical\_prices](#wpm.pricing.coingecko.CoinGeckoRetriever.get_historical_prices)
    * [get\_metadata](#wpm.pricing.coingecko.CoinGeckoRetriever.get_metadata)
* [wpm.pricing.yahoo](#wpm.pricing.yahoo)
  * [YahooFinanceRetriever](#wpm.pricing.yahoo.YahooFinanceRetriever)
    * [metadata\_supported](#wpm.pricing.yahoo.YahooFinanceRetriever.metadata_supported)
    * [\_\_init\_\_](#wpm.pricing.yahoo.YahooFinanceRetriever.__init__)
    * [get\_price](#wpm.pricing.yahoo.YahooFinanceRetriever.get_price)
    * [get\_prices](#wpm.pricing.yahoo.YahooFinanceRetriever.get_prices)
    * [get\_historical\_prices](#wpm.pricing.yahoo.YahooFinanceRetriever.get_historical_prices)
    * [get\_metadata](#wpm.pricing.yahoo.YahooFinanceRetriever.get_metadata)
* [wpm.pricing.rate\_limiter](#wpm.pricing.rate_limiter)
  * [RateLimiter](#wpm.pricing.rate_limiter.RateLimiter)
    * [\_\_init\_\_](#wpm.pricing.rate_limiter.RateLimiter.__init__)
    * [wait\_if\_needed](#wpm.pricing.rate_limiter.RateLimiter.wait_if_needed)
* [wpm.pricing.cache](#wpm.pricing.cache)
  * [CacheValidityStatus](#wpm.pricing.cache.CacheValidityStatus)
  * [CacheValidity](#wpm.pricing.cache.CacheValidity)
  * [PriceCache](#wpm.pricing.cache.PriceCache)
    * [\_\_init\_\_](#wpm.pricing.cache.PriceCache.__init__)
    * [get\_cached\_price](#wpm.pricing.cache.PriceCache.get_cached_price)
    * [get\_cached\_price\_native](#wpm.pricing.cache.PriceCache.get_cached_price_native)
    * [get\_stale\_cached\_price](#wpm.pricing.cache.PriceCache.get_stale_cached_price)
    * [get\_stale\_cached\_price\_native](#wpm.pricing.cache.PriceCache.get_stale_cached_price_native)
    * [set\_cached\_price](#wpm.pricing.cache.PriceCache.set_cached_price)
    * [get\_cache\_validity](#wpm.pricing.cache.PriceCache.get_cache_validity)
* [wpm.pricing](#wpm.pricing)
* [wpm.pricing.historical\_cache](#wpm.pricing.historical_cache)
  * [HistoricalPriceCache](#wpm.pricing.historical_cache.HistoricalPriceCache)
    * [\_\_init\_\_](#wpm.pricing.historical_cache.HistoricalPriceCache.__init__)
    * [get\_cached\_prices](#wpm.pricing.historical_cache.HistoricalPriceCache.get_cached_prices)
    * [get\_cached\_price](#wpm.pricing.historical_cache.HistoricalPriceCache.get_cached_price)
    * [set\_cached\_prices](#wpm.pricing.historical_cache.HistoricalPriceCache.set_cached_prices)
    * [clear\_asset](#wpm.pricing.historical_cache.HistoricalPriceCache.clear_asset)
    * [clear\_all](#wpm.pricing.historical_cache.HistoricalPriceCache.clear_all)
* [wpm.pricing.base](#wpm.pricing.base)
  * [PriceRetriever](#wpm.pricing.base.PriceRetriever)
    * [metadata\_supported](#wpm.pricing.base.PriceRetriever.metadata_supported)
    * [get\_price](#wpm.pricing.base.PriceRetriever.get_price)
    * [get\_prices](#wpm.pricing.base.PriceRetriever.get_prices)
    * [get\_historical\_prices](#wpm.pricing.base.PriceRetriever.get_historical_prices)
    * [get\_metadata](#wpm.pricing.base.PriceRetriever.get_metadata)

<a id="wpm"></a>

# wpm

WPM (Wealth Portfolio Manager) Library.

<a id="wpm.metrics"></a>

# wpm.metrics

Portfolio metrics and breakdown generation.

<a id="wpm.metrics.calculate_portfolio_metrics"></a>

#### calculate\_portfolio\_metrics

```python
def calculate_portfolio_metrics(portfolio: Portfolio) -> Dict
```

Calculate comprehensive portfolio metrics.

**Arguments**:

- `portfolio` - Portfolio to analyze
  

**Returns**:

  Dictionary containing portfolio metrics

<a id="wpm.metrics.breakdown_by_asset_type"></a>

#### breakdown\_by\_asset\_type

```python
def breakdown_by_asset_type(portfolio: Portfolio) -> Dict[str, Dict]
```

Generate breakdown grouped by asset type.

**Arguments**:

- `portfolio` - Portfolio to analyze
  

**Returns**:

  Dictionary mapping asset type to aggregated metrics

<a id="wpm.metrics.breakdown_by_ticker"></a>

#### breakdown\_by\_ticker

```python
def breakdown_by_ticker(portfolio: Portfolio) -> Dict[str, Position]
```

Generate breakdown grouped by ticker.

**Arguments**:

- `portfolio` - Portfolio to analyze
  

**Returns**:

  Dictionary mapping ticker to Position object

<a id="wpm.metrics.breakdown_by_purchase_period"></a>

#### breakdown\_by\_purchase\_period

```python
def breakdown_by_purchase_period(portfolio: Portfolio,
                                 period: str = "month") -> Dict[str, Dict]
```

Generate breakdown grouped by purchase period.

**Arguments**:

- `portfolio` - Portfolio to analyze
- `period` - Time period grouping ("month", "quarter", or "year")
  

**Returns**:

  Dictionary mapping period string to aggregated metrics

<a id="wpm.metrics.breakdown_by_broker"></a>

#### breakdown\_by\_broker

```python
def breakdown_by_broker(portfolio: Portfolio) -> Dict[str, Dict]
```

Generate breakdown grouped by broker.

**Arguments**:

- `portfolio` - Portfolio to analyze
  

**Returns**:

  Dictionary mapping broker name to aggregated metrics

<a id="wpm.metrics.calculate_market_value"></a>

#### calculate\_market\_value

```python
def calculate_market_value(portfolio: Portfolio, prices: Dict[Asset,
                                                              float]) -> float
```

Calculate current market value of portfolio.

**Arguments**:

- `portfolio` - Portfolio to analyze
- `prices` - Dictionary mapping Asset to current price
  

**Returns**:

  Total market value in USD

<a id="wpm.config"></a>

# wpm.config

Application-level configuration module.

This module handles all application configuration following these principles:
- Sensitive configuration (API keys, access tokens) loaded from .env file using python-dotenv
- Storage configuration (cache directories, file paths) defined as class variables

<a id="wpm.config.Config"></a>

## Config Objects

```python
class Config()
```

Application configuration class.

Sensitive configuration values are loaded from environment variables (via .env file).
Storage configuration values are defined as class variables.

<a id="wpm.config.Config.CURRENCY_CACHE_VALIDITY_MINUTES"></a>

#### CURRENCY\_CACHE\_VALIDITY\_MINUTES

24 hours

<a id="wpm.config.Config.COINGECKO_API_KEY"></a>

#### COINGECKO\_API\_KEY

Optional - None if not set

<a id="wpm.config.Config.COINGECKO_API_IS_DEMO"></a>

#### COINGECKO\_API\_IS\_DEMO

Optional - defaults to False

<a id="wpm.importer"></a>

# wpm.importer

CSV import functionality using pandas.

<a id="wpm.importer.validate_csv_structure"></a>

#### validate\_csv\_structure

```python
def validate_csv_structure(df: pd.DataFrame) -> None
```

Validate CSV has required columns.

**Arguments**:

- `df` - DataFrame to validate
  

**Raises**:

- `ValidationError` - If required columns are missing

<a id="wpm.importer.parse_trade_row"></a>

#### parse\_trade\_row

```python
def parse_trade_row(row: pd.Series,
                    currency_service: CurrencyService = None) -> Trade
```

Convert CSV row to Trade object.

Maps "Equity" asset type to "Stock" as per spec requirement.

**Arguments**:

- `row` - Pandas Series representing a CSV row
- `currency_service` - CurrencyService instance for currency conversion (default: creates new instance)
  

**Returns**:

  Trade object
  

**Raises**:

- `ValidationError` - If row data is invalid

<a id="wpm.importer.import_trades_from_csv"></a>

#### import\_trades\_from\_csv

```python
def import_trades_from_csv(file_path: str,
                           currency_service: CurrencyService = None,
                           end_date: Optional[date] = None) -> List[Trade]
```

Import trades from CSV file.

**Arguments**:

- `file_path` - Path to CSV file
- `currency_service` - CurrencyService instance for currency conversion (default: creates new instance)
- `end_date` - Optional end date (inclusive). If provided, only trades with date <= end_date are included
  

**Returns**:

  List of Trade objects
  

**Raises**:

- `ValidationError` - If CSV structure is invalid or data cannot be parsed

<a id="wpm.importer.extract_portfolio_name"></a>

#### extract\_portfolio\_name

```python
def extract_portfolio_name(filename: str, existing_names: Set[str]) -> str
```

Extract and normalize portfolio name from CSV filename.

**Arguments**:

- `filename` - CSV filename (with or without .csv extension)
- `existing_names` - Set of already used portfolio names
  

**Returns**:

  Normalized portfolio name (whitespace stripped, duplicates handled)
  

**Raises**:

- `ValueError` - If resulting name is empty

<a id="wpm.importer.import_csv_files"></a>

#### import\_csv\_files

```python
def import_csv_files(import_dir: Path,
                     end_date: Optional[date] = None) -> CompositePortfolio
```

Import CSV files and create composite portfolio.

**Arguments**:

- `import_dir` - Directory containing CSV files
- `end_date` - Optional end date (inclusive). If provided, only trades with date <= end_date are included,
  and all created portfolios will have is_historical=True
  

**Returns**:

  CompositePortfolio containing all imported sub-portfolios
  

**Raises**:

- `ValueError` - If no CSV files found in directory
- `ValidationError` - If CSV import fails

<a id="wpm.models"></a>

# wpm.models

Core data models for the WPM library.

<a id="wpm.models.ValidationError"></a>

## ValidationError Objects

```python
class ValidationError(ValueError)
```

Raised when validation of input data fails.

<a id="wpm.models.PortfolioError"></a>

## PortfolioError Objects

```python
class PortfolioError(ValueError)
```

Raised when portfolio operations are invalid.

<a id="wpm.models.Asset"></a>

## Asset Objects

```python
@dataclass(frozen=True, eq=True)
class Asset()
```

Represents a financial asset with ticker and type.

<a id="wpm.models.Asset.__post_init__"></a>

#### \_\_post\_init\_\_

```python
def __post_init__()
```

Validate asset fields after initialization.

<a id="wpm.models.Asset.__hash__"></a>

#### \_\_hash\_\_

```python
def __hash__()
```

Make Asset hashable for use in sets/dictionaries.

<a id="wpm.models.Trade"></a>

## Trade Objects

```python
@dataclass
class Trade()
```

Represents a single buy or sell transaction.

<a id="wpm.models.Trade.price"></a>

#### price

Price in USD (accounting currency)

<a id="wpm.models.Trade.price_native"></a>

#### price\_native

Price in native currency

<a id="wpm.models.Trade.__post_init__"></a>

#### \_\_post\_init\_\_

```python
def __post_init__()
```

Validate trade fields after initialization.

<a id="wpm.models.Trade.total_value"></a>

#### total\_value

```python
@property
def total_value() -> float
```

Calculate total value of the trade (price * quantity).

<a id="wpm.models.Trade.is_buy"></a>

#### is\_buy

```python
def is_buy() -> bool
```

Check if trade is a buy transaction.

<a id="wpm.models.Trade.is_sell"></a>

#### is\_sell

```python
def is_sell() -> bool
```

Check if trade is a sell transaction.

<a id="wpm.models.Lot"></a>

## Lot Objects

```python
@dataclass
class Lot()
```

Represents a purchase record (lot) for an asset with FIFO sell matching.

<a id="wpm.models.Lot.__post_init__"></a>

#### \_\_post\_init\_\_

```python
def __post_init__()
```

Validate lot fields after initialization.

<a id="wpm.models.Lot.get_realized_pnl"></a>

#### get\_realized\_pnl

```python
def get_realized_pnl() -> float
```

Calculate realized profit/loss from matched sells.

**Returns**:

  Realized P/L in USD (sum of (sell_price - purchase_price) * quantity_sold for all matched sells)

<a id="wpm.models.Lot.get_unrealized_pnl"></a>

#### get\_unrealized\_pnl

```python
def get_unrealized_pnl(current_price: float) -> float
```

Calculate unrealized profit/loss for remaining quantity.

**Arguments**:

- `current_price` - Current market price per unit
  

**Returns**:

  Unrealized P/L in USD ((current_price - purchase_price) * remaining_quantity)

<a id="wpm.models.Lot.get_total_pnl"></a>

#### get\_total\_pnl

```python
def get_total_pnl(current_price: Optional[float]) -> float
```

Calculate total profit/loss (realized + unrealized).

**Arguments**:

- `current_price` - Current market price per unit (None if unavailable)
  

**Returns**:

  Total P/L in USD (realized P/L + unrealized P/L)

<a id="wpm.models.Position"></a>

## Position Objects

```python
@dataclass
class Position()
```

Represents current holdings for a specific asset within a portfolio.

<a id="wpm.models.Position.__post_init__"></a>

#### \_\_post\_init\_\_

```python
def __post_init__()
```

Validate position fields after initialization.

<a id="wpm.models.Position.get_average_cost"></a>

#### get\_average\_cost

```python
def get_average_cost() -> float
```

Calculate average cost per unit.

<a id="wpm.models.Position.average_cost"></a>

#### average\_cost

```python
@property
def average_cost() -> float
```

Average cost per unit (computed property).

<a id="wpm.models.Portfolio"></a>

## Portfolio Objects

```python
class Portfolio(ABC)
```

Abstract base class for portfolios.

<a id="wpm.models.Portfolio.__init__"></a>

#### \_\_init\_\_

```python
def __init__(name: str, is_historical: bool = False)
```

Initialize portfolio with a name.

**Arguments**:

- `name` - Portfolio name
- `is_historical` - Whether this is a historical portfolio (default: False)

<a id="wpm.models.Portfolio.get_positions"></a>

#### get\_positions

```python
@abstractmethod
def get_positions(
        asset_type: Optional[str] = None,
        tickers: Optional[List[str]] = None) -> dict[Asset, "Position"]
```

Get all positions in the portfolio.

**Arguments**:

- `asset_type` - Optional asset type to filter by (e.g., "Stock", "ETF", "Crypto")
- `tickers` - Optional list of ticker symbols to filter by
  

**Returns**:

  Dictionary mapping Asset to Position objects

<a id="wpm.models.Portfolio.get_total_cost_basis"></a>

#### get\_total\_cost\_basis

```python
@abstractmethod
def get_total_cost_basis() -> float
```

Calculate total cost basis for the portfolio.

<a id="wpm.models.Portfolio.get_all_trades"></a>

#### get\_all\_trades

```python
@abstractmethod
def get_all_trades() -> list[Trade]
```

Get all trades in the portfolio (including sub-portfolios).

<a id="wpm.models.Portfolio.get_assets"></a>

#### get\_assets

```python
@abstractmethod
def get_assets() -> Dict[str, "Asset"]
```

Get all unique assets in the portfolio (ticker -> Asset mapping).

Returns a lightweight mapping without triggering any calculations.
This is updated automatically when trades are added.

**Returns**:

  Dictionary mapping ticker to Asset object

<a id="wpm.models.Portfolio.get_asset_trades"></a>

#### get\_asset\_trades

```python
@abstractmethod
def get_asset_trades(ticker: str,
                     start_date: Optional[date] = None,
                     end_date: Optional[date] = None) -> List[Trade]
```

Get all trades for a specified asset (ticker) within the portfolio.

**Arguments**:

- `ticker` - Asset ticker symbol to filter trades by
- `start_date` - Optional start date for date range filter (inclusive).
  If not specified, includes trades from the very beginning.
- `end_date` - Optional end date for date range filter (inclusive).
  If not specified, includes trades to the very end.
  

**Returns**:

  List of Trade objects matching the ticker and date range
  (includes both Buy and Sell trades)

<a id="wpm.models.Portfolio.get_total_market_value"></a>

#### get\_total\_market\_value

```python
@abstractmethod
def get_total_market_value(prices: Dict[Asset, Optional[float]]) -> float
```

Calculate total market value for the portfolio.

**Arguments**:

- `prices` - Dictionary mapping Asset to current price (None if unavailable)
  

**Returns**:

  Total market value in USD

<a id="wpm.models.Portfolio.get_total_unrealized_pnl"></a>

#### get\_total\_unrealized\_pnl

```python
@abstractmethod
def get_total_unrealized_pnl(prices: Dict[Asset, Optional[float]]) -> float
```

Calculate total unrealized profit/loss for the portfolio.

**Arguments**:

- `prices` - Dictionary mapping Asset to current price (None if unavailable)
  

**Returns**:

  Total unrealized profit/loss in USD (market_value - cost_basis)

<a id="wpm.models.Portfolio.get_asset_lots"></a>

#### get\_asset\_lots

```python
@abstractmethod
def get_asset_lots(
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        brokers: Optional[List[str]] = None,
        prices: Optional[Dict[Asset, Optional[float]]] = None) -> List["Lot"]
```

Get all lots for a specified asset (ticker) within the portfolio.

**Arguments**:

- `ticker` - Asset ticker symbol to filter lots by
- `start_date` - Optional start date for date range filter (inclusive).
  If not specified, includes lots from the very beginning.
- `end_date` - Optional end date for date range filter (inclusive).
  If not specified, includes lots to the very end.
- `brokers` - Optional list of broker names to filter by.
  If not specified, includes lots from all brokers.
- `prices` - Optional dictionary mapping Asset to current price for P/L calculations
  

**Returns**:

  List of Lot objects for the ticker

<a id="wpm.models.Portfolio.get_total_realized_pnl"></a>

#### get\_total\_realized\_pnl

```python
@abstractmethod
def get_total_realized_pnl() -> float
```

Calculate total realized profit/loss for the portfolio.

Derives from lots' realized P/L.

**Returns**:

  Total realized profit/loss in USD

<a id="wpm.models.Portfolio.get_asset_realized_pnl"></a>

#### get\_asset\_realized\_pnl

```python
@abstractmethod
def get_asset_realized_pnl(ticker: str,
                           brokers: Optional[List[str]] = None) -> float
```

Calculate realized profit/loss for a specific asset position.

**Arguments**:

- `ticker` - Asset ticker symbol
- `brokers` - Optional list of broker names to filter by.
  If not specified, includes lots from all brokers.
  

**Returns**:

  Realized profit/loss in USD for the specified asset

<a id="wpm.models.Portfolio.clone"></a>

#### clone

```python
@abstractmethod
def clone(start_date: Optional[date] = None,
          end_date: Optional[date] = None) -> "Portfolio"
```

Create a deep copy of the portfolio.

**Arguments**:

- `start_date` - Optional start date for filtering (inclusive).
  Must be within portfolio's date range if provided.
- `end_date` - Optional end date for filtering (inclusive).
  Must be within portfolio's date range if provided.
  

**Returns**:

  New Portfolio instance with cloned data

<a id="wpm.models.Portfolio.get_asset_positions_by_broker"></a>

#### get\_asset\_positions\_by\_broker

```python
@abstractmethod
def get_asset_positions_by_broker(ticker: str) -> Dict[str, "Position"]
```

Get positions grouped by broker for a specified asset (ticker).

Returns a dictionary mapping broker names to Position objects for the specified ticker.
This encapsulates broker grouping and position calculation logic.

**Arguments**:

- `ticker` - Asset ticker symbol to get broker positions for
  

**Returns**:

  Dictionary mapping broker names to Position objects for the ticker.
  Returns empty dictionary if ticker not found or no positions exist.
  Brokers are sorted alphabetically.

<a id="wpm.models.Portfolio.get_position"></a>

#### get\_position

```python
def get_position(asset: Asset) -> Optional["Position"]
```

Get position for a specific asset.

<a id="wpm.models.PortfolioHistoryPoint"></a>

## PortfolioHistoryPoint Objects

```python
@dataclass
class PortfolioHistoryPoint()
```

Represents a portfolio state at a specific point in time.

<a id="wpm.models.PortfolioHistoryPoint.asset_positions"></a>

#### asset\_positions

Maps ticker to position value (quantity * price)

<a id="wpm.models.PortfolioHistoryPoint.prices"></a>

#### prices

Maps ticker to price on that date

<a id="wpm.models.PortfolioHistoryPoint.quantities"></a>

#### quantities

Maps ticker to quantity held on that date

<a id="wpm.models.PortfolioHistoryPoint.__post_init__"></a>

#### \_\_post\_init\_\_

```python
def __post_init__()
```

Validate history point fields after initialization.

<a id="wpm.asset"></a>

# wpm.asset

Manages asset metadata retrieval and caching.

<a id="wpm.asset.AssetMetadataCache"></a>

## AssetMetadataCache Objects

```python
class AssetMetadataCache()
```

Manages persistent Parquet-based asset metadata cache.

<a id="wpm.asset.AssetMetadataCache.__init__"></a>

#### \_\_init\_\_

```python
def __init__(cache_file: Optional[Path] = None)
```

Initialize asset metadata cache.

**Arguments**:

- `cache_file` - Path to cache file (default: Config.ASSET_METADATA_CACHE_FILE)

<a id="wpm.asset.AssetMetadataCache.get_cached_metadata"></a>

#### get\_cached\_metadata

```python
def get_cached_metadata(ticker: str,
                        asset_type: str) -> Optional[Dict[str, Any]]
```

Get cached metadata if valid.

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
  

**Returns**:

  Cached metadata dict if valid, None otherwise

<a id="wpm.asset.AssetMetadataCache.get_cached_metadata_batch"></a>

#### get\_cached\_metadata\_batch

```python
def get_cached_metadata_batch(
        tickers: List[str],
        asset_type: str) -> Dict[str, Optional[Dict[str, Any]]]
```

Get cached metadata for multiple tickers.

**Arguments**:

- `tickers` - List of asset tickers
- `asset_type` - Asset type for all tickers
  

**Returns**:

  Dictionary mapping ticker to metadata dict (or None if missing/invalid)

<a id="wpm.asset.AssetMetadataCache.set_cached_metadata"></a>

#### set\_cached\_metadata

```python
def set_cached_metadata(ticker: str,
                        asset_type: str,
                        metadata: Dict[str, Any],
                        timestamp: Optional[datetime] = None) -> None
```

Store metadata in cache.

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
- `metadata` - Metadata dictionary
- `timestamp` - Timestamp (default: current time)

<a id="wpm.asset.AssetMetadataCache.set_cached_metadata_batch"></a>

#### set\_cached\_metadata\_batch

```python
def set_cached_metadata_batch(metadata_list: List[Dict[str, Any]]) -> None
```

Store multiple metadata entries in cache efficiently.

**Arguments**:

- `metadata_list` - List of dicts, each containing:
  - ticker: str
  - asset_type: str
  - metadata: Dict[str, Any]
  - timestamp: Optional[datetime]

<a id="wpm.asset.AssetService"></a>

## AssetService Objects

```python
class AssetService()
```

Service for retrieving and caching asset metadata.

<a id="wpm.asset.AssetService.__init__"></a>

#### \_\_init\_\_

```python
def __init__(cache_file: Optional[Path] = None,
             price_service: Optional["PriceService"] = None)
```

Initialize asset service.

**Arguments**:

- `cache_file` - Path to cache file (default: Config.ASSET_METADATA_CACHE_FILE)
- `price_service` - Optional PriceService instance for retrieving metadata via retrievers

<a id="wpm.asset.AssetService.get_metadata"></a>

#### get\_metadata

```python
def get_metadata(ticker: str, asset_type: str) -> Optional[Dict[str, Any]]
```

Get metadata for a single asset.

**Arguments**:

- `ticker` - Asset ticker symbol
- `asset_type` - Asset type ("Stock", "ETF", or "Crypto")
  

**Returns**:

  Metadata dictionary, or None if retrieval fails

<a id="wpm.asset.AssetService.get_metadata_batch"></a>

#### get\_metadata\_batch

```python
def get_metadata_batch(tickers: List[str],
                       asset_type: str) -> Dict[str, Optional[Dict[str, Any]]]
```

Get metadata for multiple assets with batch optimization.

**Arguments**:

- `tickers` - List of asset ticker symbols
- `asset_type` - Asset type for all tickers
  

**Returns**:

  Dictionary mapping ticker to metadata dict (or None if retrieval fails)

<a id="wpm.asset.AssetService.update_metadata"></a>

#### update\_metadata

```python
def update_metadata(ticker: str, asset_type: str,
                    info_dict: Dict[str, Any]) -> None
```

Update cache from yfinance .info dict.

**Arguments**:

- `ticker` - Asset ticker symbol
- `asset_type` - Asset type
- `info_dict` - yfinance .info dictionary

<a id="wpm.asset.AssetService.update_metadata_batch"></a>

#### update\_metadata\_batch

```python
def update_metadata_batch(metadata_dict: Dict[str, Dict[str, Any]]) -> None
```

Update cache for multiple tickers in batch.

**Arguments**:

- `metadata_dict` - Dictionary mapping (ticker, asset_type) tuple to info_dict
- `Format` - {(ticker, asset_type): info_dict, ...}

<a id="wpm.cost_basis"></a>

# wpm.cost\_basis

Cost basis calculation methods (FIFO).

<a id="wpm.cost_basis.calculate_lots_from_trades"></a>

#### calculate\_lots\_from\_trades

```python
def calculate_lots_from_trades(trades: List[Trade]) -> Dict[Asset, List[Lot]]
```

Calculate lots from trades using FIFO method.

Uses LRU caching to avoid recalculating lots for the same set of trades.

Sell trades must match against buy lots from the same broker. If a sell trade
cannot find a matching buy lot from the same broker, a ValidationError is raised.

**Arguments**:

- `trades` - List of trades to process
  

**Returns**:

  Dictionary mapping Asset to list of Lot objects

<a id="wpm.cost_basis.calculate_fifo_cost_basis"></a>

#### calculate\_fifo\_cost\_basis

```python
def calculate_fifo_cost_basis(trades: List[Trade]) -> Dict[Asset, Position]
```

Calculate positions using FIFO (First In, First Out) method.

Now derives positions from lots internally for consistency.

**Arguments**:

- `trades` - List of trades to process
  

**Returns**:

  Dictionary mapping Asset to Position objects

<a id="wpm.cli"></a>

# wpm.cli

Command-line utility for WPM (Wealth Portfolio Manager).

This utility orchestrates CSV imports, creates composite portfolios,
updates price caches, and provides an interactive command interface.

<a id="wpm.cli.setup_cli_logging"></a>

#### setup\_cli\_logging

```python
def setup_cli_logging() -> None
```

Configure CLI-specific logging to write to logs/wpmcli.log.

This function configures logging for the CLI only, directing all logs
to logs/wpmcli.log and suppressing stdout/stderr output. This ensures
a clean CLI interface while preserving logs for debugging.

Library users are not affected and can still configure their own logging
using wpm.utils.setup_logging().

<a id="wpm.cli.parse_args"></a>

#### parse\_args

```python
def parse_args() -> argparse.Namespace
```

Parse and validate command-line arguments.

**Returns**:

  Parsed arguments namespace

<a id="wpm.cli.fetch_prices_for_portfolio"></a>

#### fetch\_prices\_for\_portfolio

```python
def fetch_prices_for_portfolio(portfolio: CompositePortfolio,
                               price_service: PriceService) -> None
```

Fetch prices for all assets in portfolio via PriceService.

For historical portfolios, uses historical prices.

**Arguments**:

- `portfolio` - Composite portfolio containing all assets
- `price_service` - Price service for retrieving prices
  

**Raises**:

- `SystemExit` - If price retrieval fails for any asset with no cache entry

<a id="wpm.cli.format_currency"></a>

#### format\_currency

```python
def format_currency(value: float) -> str
```

Format currency value with $ prefix and 2 decimal places.

**Arguments**:

- `value` - Currency value to format
  

**Returns**:

  Formatted string (e.g., "$1,234.56")

<a id="wpm.cli.format_unrealized_pnl"></a>

#### format\_unrealized\_pnl

```python
def format_unrealized_pnl(value: float) -> str
```

Format unrealized P/L with + prefix for profit, - for loss.

**Arguments**:

- `value` - Unrealized P/L value to format
  

**Returns**:

  Formatted string with sign prefix (e.g., "+$1,234.56" or "-$1,234.56")

<a id="wpm.cli.format_quantity"></a>

#### format\_quantity

```python
def format_quantity(value) -> str
```

Format quantity value appropriately.

Handles Decimal and float values, rounding to 8 decimal places
(standard for crypto precision) and removes trailing zeros.

**Arguments**:

- `value` - Quantity value to format (Decimal or float)
  

**Returns**:

  Formatted string (integer if whole number, decimal otherwise)

<a id="wpm.cli.parse_up_to_date"></a>

#### parse\_up\_to\_date

```python
def parse_up_to_date(args: List[str]) -> tuple[Optional[date], List[str]]
```

Parse --up-to date argument from command args.

**Arguments**:

- `args` - Command arguments list
  

**Returns**:

  Tuple of (up_to_date or None, remaining args without --up-to flag and date)

<a id="wpm.cli.parse_from_date"></a>

#### parse\_from\_date

```python
def parse_from_date(args: List[str]) -> tuple[Optional[date], List[str]]
```

Parse --from date argument from command args.

**Arguments**:

- `args` - Command arguments list
  

**Returns**:

  Tuple of (from_date or None, remaining args without --from flag and date)

<a id="wpm.cli.parse_brokers"></a>

#### parse\_brokers

```python
def parse_brokers(args: List[str]) -> tuple[Optional[List[str]], List[str]]
```

Parse --brokers argument from command args.

**Arguments**:

- `args` - Command arguments list
  

**Returns**:

  Tuple of (brokers list or None, remaining args without --brokers flag and value)

<a id="wpm.cli.format_position_line"></a>

#### format\_position\_line

```python
def format_position_line(position: Position,
                         price: Optional[float],
                         is_historical: bool = False,
                         end_date: Optional[date] = None,
                         allocation: Optional[Decimal] = None) -> str
```

Format a position line for display.

**Arguments**:

- `position` - Position to format
- `price` - Current or historical price (None if unavailable)
- `is_historical` - Whether this is a historical portfolio
- `end_date` - End date for historical portfolios (used in label)
- `allocation` - Optional allocation percentage (Decimal, None if unavailable)
  

**Returns**:

  Formatted position line

<a id="wpm.cli.format_historical_asset_line"></a>

#### format\_historical\_asset\_line

```python
def format_historical_asset_line(history_point: PortfolioHistoryPoint,
                                 ticker: str,
                                 asset_type: str,
                                 allocation: Optional[Decimal] = None) -> str
```

Format a simplified line for historical asset positions.

**Arguments**:

- `history_point` - History point containing position and price data
- `ticker` - Asset ticker symbol
- `asset_type` - Asset type (e.g., "Stock", "ETF", "Crypto")
- `allocation` - Optional allocation percentage (Decimal, None if unavailable)
  

**Returns**:

  Formatted string: YYYY-MM-DD: Ticker (Asset Type): Quantity = Position Value @ Price | Allocation: XX.XX%

<a id="wpm.cli.cmd_list_portfolios"></a>

#### cmd\_list\_portfolios

```python
def cmd_list_portfolios(composite: CompositePortfolio) -> None
```

Handle 'list portfolios' command.

**Arguments**:

- `composite` - Composite portfolio containing sub-portfolios

<a id="wpm.cli.cmd_show_portfolio"></a>

#### cmd\_show\_portfolio

```python
def cmd_show_portfolio(composite: CompositePortfolio,
                       name: str,
                       price_service: PriceService,
                       up_to_date: Optional[date] = None) -> None
```

Handle 'show portfolio <name>' command.

**Arguments**:

- `composite` - Composite portfolio containing sub-portfolios
- `name` - Name of sub-portfolio to show
- `price_service` - Price service for retrieving current prices
- `up_to_date` - Optional date for historical portfolios to show state up to this date with weekly summary

<a id="wpm.cli.cmd_show_all"></a>

#### cmd\_show\_all

```python
def cmd_show_all(composite: CompositePortfolio,
                 price_service: PriceService,
                 up_to_date: Optional[date] = None) -> None
```

Handle 'show all' command.

**Arguments**:

- `composite` - Composite portfolio
- `price_service` - Price service for retrieving current prices
- `up_to_date` - Optional date for historical portfolios to show state up to this date with weekly summary

<a id="wpm.cli.cmd_show_asset"></a>

#### cmd\_show\_asset

```python
def cmd_show_asset(composite: CompositePortfolio,
                   ticker: str,
                   price_service: PriceService,
                   from_date: Optional[date] = None,
                   brokers: Optional[List[str]] = None) -> None
```

Handle 'show asset <ticker>' command.

**Arguments**:

- `composite` - Composite portfolio
- `ticker` - Asset ticker symbol to show
- `price_service` - Price service for retrieving prices
- `from_date` - Optional start date for historical portfolios
- `brokers` - Optional list of broker names to filter by

<a id="wpm.cli.format_breakdown_asset_type"></a>

#### format\_breakdown\_asset\_type

```python
def format_breakdown_asset_type(breakdown: Dict[str, Dict]) -> None
```

Format breakdown by asset type for display.

**Arguments**:

- `breakdown` - Breakdown dictionary from breakdown_by_asset_type

<a id="wpm.cli.format_breakdown_ticker"></a>

#### format\_breakdown\_ticker

```python
def format_breakdown_ticker(breakdown: Dict[str, Position]) -> None
```

Format breakdown by ticker for display.

**Arguments**:

- `breakdown` - Breakdown dictionary from breakdown_by_ticker

<a id="wpm.cli.format_breakdown_purchase_period"></a>

#### format\_breakdown\_purchase\_period

```python
def format_breakdown_purchase_period(breakdown: Dict[str, Dict]) -> None
```

Format breakdown by purchase period for display.

**Arguments**:

- `breakdown` - Breakdown dictionary from breakdown_by_purchase_period

<a id="wpm.cli.format_breakdown_broker"></a>

#### format\_breakdown\_broker

```python
def format_breakdown_broker(breakdown: Dict[str, Dict]) -> None
```

Format breakdown by broker for display.

**Arguments**:

- `breakdown` - Breakdown dictionary from breakdown_by_broker

<a id="wpm.cli.cmd_breakdown"></a>

#### cmd\_breakdown

```python
def cmd_breakdown(composite: CompositePortfolio, args: List[str]) -> None
```

Handle 'breakdown [<name>] <by>' command.

**Arguments**:

- `composite` - Composite portfolio
- `args` - Command arguments (optional portfolio name, required breakdown type)

<a id="wpm.cli.format_lot_line"></a>

#### format\_lot\_line

```python
def format_lot_line(lot: Lot, current_price: Optional[float]) -> str
```

Format a lot line with matched sells for display.

**Arguments**:

- `lot` - Lot to format
- `current_price` - Current price (None if unavailable)
  

**Returns**:

  Multi-line formatted string (lot summary + matched sells if any)

<a id="wpm.cli.cmd_show_lots"></a>

#### cmd\_show\_lots

```python
def cmd_show_lots(composite: CompositePortfolio, ticker: str,
                  price_service: PriceService) -> None
```

Handle 'lots <ticker>' command.

**Arguments**:

- `composite` - Composite portfolio containing all assets
- `ticker` - Asset ticker symbol to show lots for
- `price_service` - Price service for retrieving current prices

<a id="wpm.cli.format_market_cap"></a>

#### format\_market\_cap

```python
def format_market_cap(value: Optional[float]) -> str
```

Format market cap value for display.

**Arguments**:

- `value` - Market cap value (can be None)
  

**Returns**:

  Formatted string (e.g., "$1.23B", "$1,234.56M", or "N/A")

<a id="wpm.cli.cmd_help"></a>

#### cmd\_help

```python
def cmd_help() -> None
```

Handle 'help' command.

Displays a list of available commands and their usage.

<a id="wpm.cli.cmd_metadata"></a>

#### cmd\_metadata

```python
def cmd_metadata(composite: CompositePortfolio, ticker: str,
                 asset_service: AssetService) -> None
```

Handle 'metadata <ticker>' command.

**Arguments**:

- `composite` - Composite portfolio containing all assets
- `ticker` - Asset ticker symbol to show metadata for
- `asset_service` - Asset service for retrieving metadata

<a id="wpm.cli.run_interactive_mode"></a>

#### run\_interactive\_mode

```python
def run_interactive_mode(composite: CompositePortfolio,
                         price_service: PriceService) -> None
```

Run interactive command loop.

**Arguments**:

- `composite` - Composite portfolio
- `price_service` - Price service for retrieving prices

<a id="wpm.cli.main"></a>

#### main

```python
def main() -> None
```

Main entry point for wpm CLI.

<a id="wpm.cache_utils"></a>

# wpm.cache\_utils

Cache utilities for WPM library.

<a id="wpm.cache_utils.LRUCache"></a>

## LRUCache Objects

```python
class LRUCache(Generic[T])
```

Simple LRU cache implementation using OrderedDict.

Provides thread-safe-like operations for single-threaded use cases.
For multi-threaded scenarios, external synchronization would be needed.

<a id="wpm.cache_utils.LRUCache.__init__"></a>

#### \_\_init\_\_

```python
def __init__(maxsize: int = 128)
```

Initialize LRU cache.

**Arguments**:

- `maxsize` - Maximum number of entries in the cache

<a id="wpm.cache_utils.LRUCache.get"></a>

#### get

```python
def get(key) -> Optional[T]
```

Get value from cache, moving it to end (most recently used).

**Arguments**:

- `key` - Cache key
  

**Returns**:

  Cached value if found, None otherwise

<a id="wpm.cache_utils.LRUCache.set"></a>

#### set

```python
def set(key, value: T) -> None
```

Set value in cache, implementing LRU eviction if needed.

**Arguments**:

- `key` - Cache key
- `value` - Value to cache

<a id="wpm.cache_utils.LRUCache.clear"></a>

#### clear

```python
def clear() -> None
```

Clear all entries from the cache.

<a id="wpm.cache_utils.LRUCache.__len__"></a>

#### \_\_len\_\_

```python
def __len__() -> int
```

Return number of entries in cache.

<a id="wpm.cache_utils.trades_to_cache_key"></a>

#### trades\_to\_cache\_key

```python
def trades_to_cache_key(trades: List[Trade]) -> tuple
```

Convert trades list to hashable tuple for cache key.

**Arguments**:

- `trades` - List of Trade objects
  

**Returns**:

  Hashable tuple representation of trades

<a id="wpm.cache_utils.trades_to_cache_key_with_filters"></a>

#### trades\_to\_cache\_key\_with\_filters

```python
def trades_to_cache_key_with_filters(
        trades: List[Trade],
        asset_type: Optional[str] = None,
        tickers: Optional[List[str]] = None) -> tuple
```

Convert trades list and filters to hashable tuple for cache key.

**Arguments**:

- `trades` - List of Trade objects
- `asset_type` - Optional asset type filter
- `tickers` - Optional tickers filter
  

**Returns**:

  Hashable tuple representation

<a id="wpm.utils"></a>

# wpm.utils

Utility functions for validation, logging, and trading hours.

<a id="wpm.utils.setup_logging"></a>

#### setup\_logging

```python
def setup_logging(level: int = logging.INFO) -> logging.Logger
```

Configure library logging.

**Arguments**:

- `level` - Logging level (default: logging.INFO)
  

**Returns**:

  Configured logger instance

<a id="wpm.utils.validate_ticker"></a>

#### validate\_ticker

```python
def validate_ticker(ticker: str) -> None
```

Validate ticker format.

**Arguments**:

- `ticker` - Ticker symbol to validate
  

**Raises**:

- `ValidationError` - If ticker format is invalid

<a id="wpm.utils.normalize_date"></a>

#### normalize\_date

```python
def normalize_date(date_str: str) -> date
```

Parse and normalize date strings in YYYY-MM-DD format.

**Arguments**:

- `date_str` - Date string in YYYY-MM-DD format
  

**Returns**:

  Parsed date object
  

**Raises**:

- `ValueError` - If date string format is invalid

<a id="wpm.utils.validate_asset_type"></a>

#### validate\_asset\_type

```python
def validate_asset_type(asset_type: str) -> str
```

Validate and normalize asset type.

Maps "Equity" to "Stock" and normalizes case to title case.

**Arguments**:

- `asset_type` - Asset type string to validate
  

**Returns**:

  Normalized asset type ("Stock", "ETF", or "Crypto")
  

**Raises**:

- `ValueError` - If asset type is invalid

<a id="wpm.utils.concat_dataframes"></a>

#### concat\_dataframes

```python
def concat_dataframes(objs: Sequence[pd.DataFrame],
                      ignore_index: bool = False,
                      **kwargs) -> pd.DataFrame
```

Concatenate pandas DataFrames while suppressing FutureWarning for empty DataFrames.

This wrapper around pd.concat suppresses the FutureWarning that pandas emits
when concatenating DataFrames where one may be empty or all-NA. This warning
is about future dtype inference behavior and is not critical when DataFrames
have matching columns.

**Arguments**:

- `objs` - Sequence of DataFrames to concatenate
- `ignore_index` - If True, ignore index and use default integer index
- `**kwargs` - Additional arguments passed to pd.concat
  

**Returns**:

  Concatenated DataFrame

<a id="wpm.utils.is_us_market_open"></a>

#### is\_us\_market\_open

```python
def is_us_market_open(timestamp: Optional[datetime] = None) -> bool
```

Determine if US market (NYSE) is currently open for regular trading hours.

Accounts for weekends, official holidays, and early closes using
pandas_market_calendars.

**Arguments**:

- `timestamp` - Timestamp to check (default: current time in ET timezone)
  

**Returns**:

  True if market is open, False otherwise

<a id="wpm.utils.is_within_trading_hours"></a>

#### is\_within\_trading\_hours

```python
def is_within_trading_hours(timestamp: datetime) -> bool
```

Check if a given timestamp falls within US market trading hours.

Uses NYSE calendar to account for holidays and early closes.

**Arguments**:

- `timestamp` - Timestamp to check
  

**Returns**:

  True if timestamp is during market hours, False otherwise

<a id="wpm.currency"></a>

# wpm.currency

Currency conversion module using yfinance for forex rates.

<a id="wpm.currency.CurrencyCache"></a>

## CurrencyCache Objects

```python
class CurrencyCache()
```

Manages persistent Parquet-based currency rate cache.

<a id="wpm.currency.CurrencyCache.__init__"></a>

#### \_\_init\_\_

```python
def __init__(cache_file: Optional[Path] = None)
```

Initialize currency cache.

**Arguments**:

- `cache_file` - Path to cache file (default: Config.CURRENCY_CACHE_FILE)

<a id="wpm.currency.CurrencyCache.get_cached_rate"></a>

#### get\_cached\_rate

```python
def get_cached_rate(base_currency: str,
                    counter_currency: str = "USD") -> Optional[float]
```

Get cached rate if valid.

**Arguments**:

- `base_currency` - Base currency code (e.g., "HKD")
- `counter_currency` - Counter currency code (default: "USD")
  

**Returns**:

  Cached rate if valid, None otherwise

<a id="wpm.currency.CurrencyCache.set_cached_rate"></a>

#### set\_cached\_rate

```python
def set_cached_rate(base_currency: str,
                    counter_currency: str,
                    rate: float,
                    timestamp: Optional[datetime] = None) -> None
```

Set cached rate.

**Arguments**:

- `base_currency` - Base currency code
- `counter_currency` - Counter currency code
- `rate` - Exchange rate to cache
- `timestamp` - Timestamp (default: current time)

<a id="wpm.currency.CurrencyService"></a>

## CurrencyService Objects

```python
class CurrencyService()
```

Service for currency conversion using yfinance.

<a id="wpm.currency.CurrencyService.__init__"></a>

#### \_\_init\_\_

```python
def __init__(cache: Optional[CurrencyCache] = None)
```

Initialize currency service.

**Arguments**:

- `cache` - CurrencyCache instance (default: creates new instance)

<a id="wpm.currency.CurrencyService.get_forex_rate"></a>

#### get\_forex\_rate

```python
def get_forex_rate(base_currency: str, counter_currency: str = "USD") -> float
```

Get forex exchange rate.

Uses yfinance API with format {BASE}{COUNTER}=X (e.g., HKDUSD=X).
Returns exchange rate where 1 base = X counter.

**Arguments**:

- `base_currency` - Base currency code (e.g., "HKD")
- `counter_currency` - Counter currency code (default: "USD")
  

**Returns**:

  Exchange rate (1 base = X counter)
  

**Raises**:

- `ValueError` - If rate cannot be retrieved

<a id="wpm.currency.CurrencyService.convert_to_usd"></a>

#### convert\_to\_usd

```python
def convert_to_usd(amount: float, from_currency: str) -> float
```

Convert amount from any currency to USD.

**Arguments**:

- `amount` - Amount to convert
- `from_currency` - Source currency code
  

**Returns**:

  Amount in USD (unchanged if from_currency is USD)

<a id="wpm.portfolio"></a>

# wpm.portfolio

Portfolio class implementation with aggregation logic.

<a id="wpm.portfolio.SimplePortfolio"></a>

## SimplePortfolio Objects

```python
class SimplePortfolio(Portfolio)
```

Portfolio containing direct asset positions (trades).

<a id="wpm.portfolio.SimplePortfolio.__init__"></a>

#### \_\_init\_\_

```python
def __init__(name: str, is_historical: bool = False)
```

Initialize a simple portfolio.

**Arguments**:

- `name` - Portfolio name
- `is_historical` - Whether this is a historical portfolio (default: False)

<a id="wpm.portfolio.SimplePortfolio.add_trade"></a>

#### add\_trade

```python
def add_trade(trade: Trade) -> None
```

Add a trade to the portfolio.

**Arguments**:

- `trade` - Trade to add

<a id="wpm.portfolio.SimplePortfolio.get_positions"></a>

#### get\_positions

```python
def get_positions(
        asset_type: Optional[str] = None,
        tickers: Optional[List[str]] = None) -> Dict[Asset, Position]
```

Get all positions in the portfolio.

Uses LRU caching to avoid recalculating positions for the same trades.

**Arguments**:

- `asset_type` - Optional asset type to filter by (e.g., "Stock", "ETF", "Crypto")
- `tickers` - Optional list of ticker symbols to filter by
  

**Returns**:

  Dictionary mapping Asset to Position objects

<a id="wpm.portfolio.SimplePortfolio.get_total_cost_basis"></a>

#### get\_total\_cost\_basis

```python
def get_total_cost_basis() -> float
```

Calculate total cost basis for the portfolio.

Uses LRU caching to avoid recalculating for the same trades.

**Returns**:

  Total cost basis in USD

<a id="wpm.portfolio.SimplePortfolio.get_total_market_value"></a>

#### get\_total\_market\_value

```python
def get_total_market_value(prices: Dict[Asset, Optional[float]]) -> float
```

Calculate total market value for the portfolio.

**Arguments**:

- `prices` - Dictionary mapping Asset to current price (None if unavailable)
  

**Returns**:

  Total market value in USD

<a id="wpm.portfolio.SimplePortfolio.get_total_unrealized_pnl"></a>

#### get\_total\_unrealized\_pnl

```python
def get_total_unrealized_pnl(prices: Dict[Asset, Optional[float]]) -> float
```

Calculate total unrealized profit/loss for the portfolio.

**Arguments**:

- `prices` - Dictionary mapping Asset to current price (None if unavailable)
  

**Returns**:

  Total unrealized profit/loss in USD (market_value - cost_basis)

<a id="wpm.portfolio.SimplePortfolio.get_asset_lots"></a>

#### get\_asset\_lots

```python
def get_asset_lots(
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        brokers: Optional[List[str]] = None,
        prices: Optional[Dict[Asset, Optional[float]]] = None) -> List[Lot]
```

Get all lots for a specified asset (ticker) within the portfolio.

**Arguments**:

- `ticker` - Asset ticker symbol to filter lots by
- `start_date` - Optional start date for date range filter (inclusive).
  If not specified, includes lots from the very beginning.
- `end_date` - Optional end date for date range filter (inclusive).
  If not specified, includes lots to the very end.
- `brokers` - Optional list of broker names to filter by.
  If not specified, includes lots from all brokers.
- `prices` - Optional dictionary mapping Asset to current price for P/L calculations
  

**Returns**:

  List of Lot objects for the ticker

<a id="wpm.portfolio.SimplePortfolio.get_asset_positions_by_broker"></a>

#### get\_asset\_positions\_by\_broker

```python
def get_asset_positions_by_broker(ticker: str) -> Dict[str, Position]
```

Get positions grouped by broker for a specified asset (ticker).

Returns a dictionary mapping broker names to Position objects for the specified ticker.
This encapsulates broker grouping and position calculation logic.

**Arguments**:

- `ticker` - Asset ticker symbol to get broker positions for
  

**Returns**:

  Dictionary mapping broker names to Position objects for the ticker.
  Returns empty dictionary if ticker not found or no positions exist.
  Brokers are sorted alphabetically.

<a id="wpm.portfolio.SimplePortfolio.get_total_realized_pnl"></a>

#### get\_total\_realized\_pnl

```python
def get_total_realized_pnl() -> float
```

Calculate total realized profit/loss for the portfolio.

Derives from lots' realized P/L.

**Returns**:

  Total realized profit/loss in USD

<a id="wpm.portfolio.SimplePortfolio.get_asset_realized_pnl"></a>

#### get\_asset\_realized\_pnl

```python
def get_asset_realized_pnl(ticker: str,
                           brokers: Optional[List[str]] = None) -> float
```

Calculate realized profit/loss for a specific asset position.

Uses get_asset_lots() behind the scenes and sums realized P/L from all lots.

**Arguments**:

- `ticker` - Asset ticker symbol
- `brokers` - Optional list of broker names to filter by.
  

**Returns**:

  Realized profit/loss in USD for the specified asset

<a id="wpm.portfolio.SimplePortfolio.get_asset_allocation"></a>

#### get\_asset\_allocation

```python
def get_asset_allocation(asset: Asset,
                         prices: Dict[Asset, Optional[float]]) -> Decimal
```

Get percentage allocation of a specific asset position.

The percentage is calculated as (asset market value / total portfolio market value) * 100.
Uses Decimal for precision and rounds to 2 decimal places.

**Arguments**:

- `asset` - Asset to get allocation for
- `prices` - Dictionary mapping Asset to current price (None if unavailable)
  

**Returns**:

  Percentage allocation as Decimal rounded to 2 decimal places (0.00 if asset not in portfolio,
  missing price, or zero total market value)

<a id="wpm.portfolio.SimplePortfolio.get_all_allocations"></a>

#### get\_all\_allocations

```python
def get_all_allocations(
        prices: Dict[Asset, Optional[float]],
        asset_types: Optional[List[str]] = None,
        asset_tickers: Optional[List[str]] = None) -> Dict[Asset, Decimal]
```

Get percentage allocations for all asset positions in the portfolio.

The percentage for each asset is calculated as (asset market value / total portfolio market value) * 100.
Uses Decimal for precision and rounds to 2 decimal places. All allocations should sum to 100.00.

When filters are provided, allocations are calculated against the filtered asset list only
(sum to 100% of filtered assets, not the entire portfolio).

**Filter Logic**:

The filtering uses OR logic between `asset_types` and `asset_tickers`. An asset is included
if it matches any specified asset type OR any specified ticker. The behavior depends on which
parameters are provided:

1. **Both parameters are None** (default):
- All assets in the portfolio are included
- Allocations sum to 100% of the entire portfolio
- This is the backward compatible behavior

2. **Only `asset_types` is provided** (e.g., `asset_types=["Stock", "ETF"]`):
- Only assets whose `asset_type` matches one of the specified types are included
- Example: If portfolio has GOOG (Stock), BTC-USD (Crypto), and VOO (ETF), and
`asset_types=["Stock", "ETF"]`:
- Included: GOOG (Stock), VOO (ETF)
- Excluded: BTC-USD (Crypto)
- Allocations sum to 100% of the filtered assets only

3. **Only `asset_tickers` is provided** (e.g., `asset_tickers=["GOOG", "AAPL"]`):
- Only assets whose ticker matches one of the specified tickers are included
- Example: If portfolio has GOOG, AAPL, MSFT, and `asset_tickers=["GOOG", "AAPL"]`:
- Included: GOOG, AAPL
- Excluded: MSFT
- Allocations sum to 100% of the filtered assets only

4. **Both parameters are provided** (e.g., `asset_types=["Crypto"]`, `asset_tickers=["GOOG"]`):
- OR logic: An asset is included if it matches any specified asset type OR any specified ticker
- Example: If portfolio has GOOG (Stock), AAPL (Stock), BTC-USD (Crypto), and filters are
`asset_types=["Crypto"]`, `asset_tickers=["GOOG"]`:
- Included: GOOG (matches ticker), BTC-USD (matches asset_type)
- Excluded: AAPL (matches neither)
- Allocations sum to 100% of the filtered assets only

**Important Notes**:

- Asset types are normalized using `validate_asset_type` for consistency
(e.g., "stock" → "Stock", "crypto" → "Crypto")
- When filters are provided, allocations are calculated against the filtered asset list only,
not the entire portfolio
- This means if you filter to only Crypto assets, their allocations will sum to 100% of
the Crypto portion, not 100% of the entire portfolio
- Empty filter results return an empty dictionary

**Examples**:

.. code-block:: python

# Get allocations for all assets (no filtering)
allocations = portfolio.get_all_allocations(prices)

# Get allocations for only Stock and ETF assets
allocations = portfolio.get_all_allocations(prices, asset_types=["Stock", "ETF"])

# Get allocations for specific tickers
allocations = portfolio.get_all_allocations(prices, asset_tickers=["GOOG", "AAPL"])

# Get allocations for Crypto assets OR specific tickers (OR logic)
allocations = portfolio.get_all_allocations(
prices,
asset_types=["Crypto"],
asset_tickers=["GOOG", "VOO"]
)
# This includes: all Crypto assets + GOOG + VOO (even if GOOG/VOO are not Crypto)

**Arguments**:

- `prices` - Dictionary mapping Asset to current price (None if unavailable)
- `asset_types` - Optional list of asset types to filter by (e.g., ["Stock", "ETF", "Crypto"]).
  Uses OR logic - asset is included if it matches any specified type.
- `asset_tickers` - Optional list of ticker symbols to filter by (e.g., ["GOOG", "AAPL"]).
  Uses OR logic - asset is included if it matches any specified ticker.
  

**Returns**:

  Dictionary mapping Asset to Decimal percentage allocation (2 decimal places)
  When filters are provided, only includes filtered assets and allocations sum to 100% of filtered assets.

<a id="wpm.portfolio.SimplePortfolio.get_all_trades"></a>

#### get\_all\_trades

```python
def get_all_trades() -> List[Trade]
```

Get all trades in the portfolio.

**Returns**:

  List of all trades

<a id="wpm.portfolio.SimplePortfolio.get_assets"></a>

#### get\_assets

```python
def get_assets() -> Dict[str, Asset]
```

Get all unique assets in the portfolio.

Returns a lightweight mapping without triggering any calculations.
This is updated automatically when trades are added.

**Returns**:

  Dictionary mapping ticker to Asset object

<a id="wpm.portfolio.SimplePortfolio.get_asset_trades"></a>

#### get\_asset\_trades

```python
def get_asset_trades(ticker: str,
                     start_date: Optional[date] = None,
                     end_date: Optional[date] = None) -> List[Trade]
```

Get all trades for a specified asset (ticker) within the portfolio.

**Arguments**:

- `ticker` - Asset ticker symbol to filter trades by
- `start_date` - Optional start date for date range filter (inclusive).
  If not specified, includes trades from the very beginning.
- `end_date` - Optional end date for date range filter (inclusive).
  If not specified, includes trades to the very end.
  

**Returns**:

  List of Trade objects matching the ticker and date range
  (includes both Buy and Sell trades)

<a id="wpm.portfolio.SimplePortfolio.clone"></a>

#### clone

```python
def clone(start_date: Optional[date] = None,
          end_date: Optional[date] = None,
          _skip_end_date_validation: bool = False) -> "SimplePortfolio"
```

Create a deep copy of the portfolio.

**Arguments**:

- `start_date` - Optional start date for filtering trades (inclusive).
  Must be within portfolio's date range if provided.
- `end_date` - Optional end date for filtering trades (inclusive).
  Must be within portfolio's date range if provided.
- `_skip_end_date_validation` - Internal flag to skip end_date validation
  when cloning sub-portfolios in composite portfolios.
  

**Returns**:

  New SimplePortfolio instance with cloned trades
  

**Raises**:

- `PortfolioError` - If date range is outside portfolio's date range

<a id="wpm.portfolio.SimplePortfolio.start_date"></a>

#### start\_date

```python
@property
def start_date() -> Optional[date]
```

Get the earliest trade date in the portfolio.

**Returns**:

  Earliest trade date, or None if no trades exist

<a id="wpm.portfolio.SimplePortfolio.end_date"></a>

#### end\_date

```python
@property
def end_date() -> Optional[date]
```

Get the most recent trade date in the portfolio.

**Returns**:

  Most recent trade date, or None if no trades exist

<a id="wpm.portfolio.CompositePortfolio"></a>

## CompositePortfolio Objects

```python
class CompositePortfolio(Portfolio)
```

Portfolio containing sub-portfolios.

<a id="wpm.portfolio.CompositePortfolio.__init__"></a>

#### \_\_init\_\_

```python
def __init__(name: str, is_historical: bool = False)
```

Initialize a composite portfolio.

**Arguments**:

- `name` - Portfolio name
- `is_historical` - Whether this is a historical portfolio (default: False)

<a id="wpm.portfolio.CompositePortfolio.add_sub_portfolio"></a>

#### add\_sub\_portfolio

```python
def add_sub_portfolio(portfolio: Portfolio) -> None
```

Add a sub-portfolio to this composite portfolio.

**Arguments**:

- `portfolio` - Portfolio to add as sub-portfolio
  

**Raises**:

- `PortfolioError` - If portfolio name already exists, portfolio is invalid,
  or is_historical flags don't match

<a id="wpm.portfolio.CompositePortfolio.get_sub_portfolios"></a>

#### get\_sub\_portfolios

```python
def get_sub_portfolios() -> Dict[str, "Portfolio"]
```

Get a copy of all sub-portfolios.

**Returns**:

  Dictionary mapping sub-portfolio name to Portfolio instance

<a id="wpm.portfolio.CompositePortfolio.get_positions"></a>

#### get\_positions

```python
def get_positions(
        asset_type: Optional[str] = None,
        tickers: Optional[List[str]] = None) -> Dict[Asset, Position]
```

Get all positions aggregated from sub-portfolios.

**Arguments**:

- `asset_type` - Optional asset type to filter by (e.g., "Stock", "ETF", "Crypto")
- `tickers` - Optional list of ticker symbols to filter by
  

**Returns**:

  Dictionary mapping Asset to aggregated Position objects

<a id="wpm.portfolio.CompositePortfolio.get_total_cost_basis"></a>

#### get\_total\_cost\_basis

```python
def get_total_cost_basis() -> float
```

Calculate total cost basis aggregated from sub-portfolios.

**Returns**:

  Total cost basis in USD

<a id="wpm.portfolio.CompositePortfolio.get_total_market_value"></a>

#### get\_total\_market\_value

```python
def get_total_market_value(prices: Dict[Asset, Optional[float]]) -> float
```

Calculate total market value aggregated from sub-portfolios.

**Arguments**:

- `prices` - Dictionary mapping Asset to current price (None if unavailable)
  

**Returns**:

  Total market value in USD

<a id="wpm.portfolio.CompositePortfolio.get_total_unrealized_pnl"></a>

#### get\_total\_unrealized\_pnl

```python
def get_total_unrealized_pnl(prices: Dict[Asset, Optional[float]]) -> float
```

Calculate total unrealized profit/loss aggregated from sub-portfolios.

**Arguments**:

- `prices` - Dictionary mapping Asset to current price (None if unavailable)
  

**Returns**:

  Total unrealized profit/loss in USD

<a id="wpm.portfolio.CompositePortfolio.get_asset_lots"></a>

#### get\_asset\_lots

```python
def get_asset_lots(
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        brokers: Optional[List[str]] = None,
        prices: Optional[Dict[Asset, Optional[float]]] = None) -> List[Lot]
```

Get all lots for a specified asset (ticker) within the portfolio.

Aggregates lots from all sub-portfolios.

**Arguments**:

- `ticker` - Asset ticker symbol to filter lots by
- `start_date` - Optional start date for date range filter (inclusive).
  If not specified, includes lots from the very beginning.
- `end_date` - Optional end date for date range filter (inclusive).
  If not specified, includes lots to the very end.
- `brokers` - Optional list of broker names to filter by.
  If not specified, includes lots from all brokers.
- `prices` - Optional dictionary mapping Asset to current price for P/L calculations
  

**Returns**:

  List of Lot objects for the ticker (aggregated from all sub-portfolios)

<a id="wpm.portfolio.CompositePortfolio.get_asset_positions_by_broker"></a>

#### get\_asset\_positions\_by\_broker

```python
def get_asset_positions_by_broker(ticker: str) -> Dict[str, Position]
```

Get positions grouped by broker for a specified asset (ticker).

Returns a dictionary mapping broker names to Position objects for the specified ticker.
Aggregates positions across all sub-portfolios for the same broker.
This encapsulates broker grouping and position calculation logic.

**Arguments**:

- `ticker` - Asset ticker symbol to get broker positions for
  

**Returns**:

  Dictionary mapping broker names to Position objects for the ticker.
  Returns empty dictionary if ticker not found or no positions exist.
  Brokers are sorted alphabetically.

<a id="wpm.portfolio.CompositePortfolio.get_total_realized_pnl"></a>

#### get\_total\_realized\_pnl

```python
def get_total_realized_pnl() -> float
```

Calculate total realized profit/loss aggregated from sub-portfolios.

Derives from lots' realized P/L.

**Returns**:

  Total realized profit/loss in USD

<a id="wpm.portfolio.CompositePortfolio.get_asset_realized_pnl"></a>

#### get\_asset\_realized\_pnl

```python
def get_asset_realized_pnl(ticker: str,
                           brokers: Optional[List[str]] = None) -> float
```

Calculate realized profit/loss for a specific asset position.

Aggregates realized P/L from all sub-portfolios.

**Arguments**:

- `ticker` - Asset ticker symbol
- `brokers` - Optional list of broker names to filter by.
  

**Returns**:

  Realized profit/loss in USD for the specified asset

<a id="wpm.portfolio.CompositePortfolio.get_asset_allocation"></a>

#### get\_asset\_allocation

```python
def get_asset_allocation(asset: Asset,
                         prices: Dict[Asset, Optional[float]]) -> Decimal
```

Get percentage allocation of a specific asset position.

The percentage is calculated as (asset market value / total portfolio market value) * 100.
Uses Decimal for precision and rounds to 2 decimal places.
For composite portfolios, aggregates positions across all sub-portfolios.

**Arguments**:

- `asset` - Asset to get allocation for
- `prices` - Dictionary mapping Asset to current price (None if unavailable)
  

**Returns**:

  Percentage allocation as Decimal rounded to 2 decimal places (0.00 if asset not in portfolio,
  missing price, or zero total market value)

<a id="wpm.portfolio.CompositePortfolio.get_all_allocations"></a>

#### get\_all\_allocations

```python
def get_all_allocations(
        prices: Dict[Asset, Optional[float]],
        asset_types: Optional[List[str]] = None,
        asset_tickers: Optional[List[str]] = None) -> Dict[Asset, Decimal]
```

Get percentage allocations for all asset positions in the portfolio.

The percentage for each asset is calculated as (asset market value / total portfolio market value) * 100.
Uses Decimal for precision and rounds to 2 decimal places. All allocations should sum to 100.00.
For composite portfolios, aggregates positions across all sub-portfolios.

When filters are provided, allocations are calculated against the filtered asset list only
(sum to 100% of filtered assets, not the entire portfolio).

**Filter Logic**:

The filtering uses OR logic between `asset_types` and `asset_tickers`. An asset is included
if it matches any specified asset type OR any specified ticker. The behavior depends on which
parameters are provided:

1. **Both parameters are None** (default):
- All assets in the portfolio are included
- Allocations sum to 100% of the entire portfolio
- This is the backward compatible behavior

2. **Only `asset_types` is provided** (e.g., `asset_types=["Stock", "ETF"]`):
- Only assets whose `asset_type` matches one of the specified types are included
- Example: If portfolio has GOOG (Stock), BTC-USD (Crypto), and VOO (ETF), and
`asset_types=["Stock", "ETF"]`:
- Included: GOOG (Stock), VOO (ETF)
- Excluded: BTC-USD (Crypto)
- Allocations sum to 100% of the filtered assets only

3. **Only `asset_tickers` is provided** (e.g., `asset_tickers=["GOOG", "AAPL"]`):
- Only assets whose ticker matches one of the specified tickers are included
- Example: If portfolio has GOOG, AAPL, MSFT, and `asset_tickers=["GOOG", "AAPL"]`:
- Included: GOOG, AAPL
- Excluded: MSFT
- Allocations sum to 100% of the filtered assets only

4. **Both parameters are provided** (e.g., `asset_types=["Crypto"]`, `asset_tickers=["GOOG"]`):
- OR logic: An asset is included if it matches any specified asset type OR any specified ticker
- Example: If portfolio has GOOG (Stock), AAPL (Stock), BTC-USD (Crypto), and filters are
`asset_types=["Crypto"]`, `asset_tickers=["GOOG"]`:
- Included: GOOG (matches ticker), BTC-USD (matches asset_type)
- Excluded: AAPL (matches neither)
- Allocations sum to 100% of the filtered assets only

**Important Notes**:

- Asset types are normalized using `validate_asset_type` for consistency
(e.g., "stock" → "Stock", "crypto" → "Crypto")
- When filters are provided, allocations are calculated against the filtered asset list only,
not the entire portfolio
- This means if you filter to only Crypto assets, their allocations will sum to 100% of
the Crypto portion, not 100% of the entire portfolio
- Empty filter results return an empty dictionary
- For composite portfolios, filtering is applied after aggregating positions across all sub-portfolios

**Examples**:

.. code-block:: python

# Get allocations for all assets (no filtering)
allocations = composite.get_all_allocations(prices)

# Get allocations for only Stock and ETF assets
allocations = composite.get_all_allocations(prices, asset_types=["Stock", "ETF"])

# Get allocations for specific tickers
allocations = composite.get_all_allocations(prices, asset_tickers=["GOOG", "AAPL"])

# Get allocations for Crypto assets OR specific tickers (OR logic)
allocations = composite.get_all_allocations(
prices,
asset_types=["Crypto"],
asset_tickers=["GOOG", "VOO"]
)
# This includes: all Crypto assets + GOOG + VOO (even if GOOG/VOO are not Crypto)

**Arguments**:

- `prices` - Dictionary mapping Asset to current price (None if unavailable)
- `asset_types` - Optional list of asset types to filter by (e.g., ["Stock", "ETF", "Crypto"]).
  Uses OR logic - asset is included if it matches any specified type.
- `asset_tickers` - Optional list of ticker symbols to filter by (e.g., ["GOOG", "AAPL"]).
  Uses OR logic - asset is included if it matches any specified ticker.
  

**Returns**:

  Dictionary mapping Asset to Decimal percentage allocation (2 decimal places)
  When filters are provided, only includes filtered assets and allocations sum to 100% of filtered assets.

<a id="wpm.portfolio.CompositePortfolio.get_all_trades"></a>

#### get\_all\_trades

```python
def get_all_trades() -> List[Trade]
```

Get all trades from all sub-portfolios.

**Returns**:

  List of all trades from sub-portfolios

<a id="wpm.portfolio.CompositePortfolio.get_assets"></a>

#### get\_assets

```python
def get_assets() -> Dict[str, Asset]
```

Get all unique assets across all sub-portfolios.

Returns a lightweight mapping without triggering any calculations.
Aggregates assets from all sub-portfolios.

**Returns**:

  Dictionary mapping ticker to Asset object

<a id="wpm.portfolio.CompositePortfolio.get_asset_trades"></a>

#### get\_asset\_trades

```python
def get_asset_trades(ticker: str,
                     start_date: Optional[date] = None,
                     end_date: Optional[date] = None) -> List[Trade]
```

Get all trades for a specified asset (ticker) within the portfolio.

Aggregates asset trades from all sub-portfolios.

**Arguments**:

- `ticker` - Asset ticker symbol to filter trades by
- `start_date` - Optional start date for date range filter (inclusive).
  If not specified, includes trades from the very beginning.
- `end_date` - Optional end date for date range filter (inclusive).
  If not specified, includes trades to the very end.
  

**Returns**:

  List of Trade objects matching the ticker and date range
  (includes both Buy and Sell trades)

<a id="wpm.portfolio.CompositePortfolio.start_date"></a>

#### start\_date

```python
@property
def start_date() -> Optional[date]
```

Get the earliest start_date of all sub-portfolios.

**Returns**:

  Earliest start_date, or None if no sub-portfolios exist

<a id="wpm.portfolio.CompositePortfolio.end_date"></a>

#### end\_date

```python
@property
def end_date() -> Optional[date]
```

Get the most recent end_date of all sub-portfolios.

**Returns**:

  Most recent end_date, or None if no sub-portfolios exist

<a id="wpm.portfolio.CompositePortfolio.clone"></a>

#### clone

```python
def clone(start_date: Optional[date] = None,
          end_date: Optional[date] = None,
          _skip_end_date_validation: bool = False) -> "CompositePortfolio"
```

Create a deep copy of the portfolio.

**Arguments**:

- `start_date` - Optional start date for filtering sub-portfolios (inclusive).
  Must be within portfolio's date range if provided.
- `end_date` - Optional end date for filtering sub-portfolios (inclusive).
  Must be within portfolio's date range if provided.
- `_skip_end_date_validation` - Internal flag to skip end_date validation
  when cloning sub-portfolios in composite portfolios.
  

**Returns**:

  New CompositePortfolio instance with cloned sub-portfolios
  

**Raises**:

- `PortfolioError` - If date range is outside portfolio's date range

<a id="wpm.portfolio.fetch_price_map"></a>

#### fetch\_price\_map

```python
def fetch_price_map(
        portfolio: Portfolio,
        price_service: "PriceService",
        target_date: Optional[date] = None) -> Dict[Asset, Optional[float]]
```

Fetch prices for all assets in portfolio and return a price map.

Extracts assets from portfolio positions, groups them by asset type for
batch processing, and fetches prices via PriceService. For historical portfolios,
uses historical prices. Handles exceptions gracefully by setting None for assets
that fail to fetch.

**Arguments**:

- `portfolio` - Portfolio containing assets (SimplePortfolio or CompositePortfolio)
- `price_service` - Price service for retrieving prices
- `target_date` - Optional target date for historical prices. If None and portfolio
  is historical, uses portfolio.end_date
  

**Returns**:

  Dictionary mapping Asset to Optional[float] price (None if price unavailable)

<a id="wpm.portfolio.generate_historical_snapshots"></a>

#### generate\_historical\_snapshots

```python
def generate_historical_snapshots(portfolio: Portfolio, start_date: date,
                                  end_date: date) -> List[Portfolio]
```

Generate historical snapshots of a portfolio for each date in range.

Creates a clone of the portfolio for each date from start_date to end_date
(inclusive), where each snapshot represents the portfolio state as of that date.

**Arguments**:

- `portfolio` - Portfolio to generate snapshots for
- `start_date` - Start date for snapshot generation (inclusive)
- `end_date` - End date for snapshot generation (inclusive)
  

**Returns**:

  List of Portfolio clones, one for each date in the range
  

**Raises**:

- `PortfolioError` - If date range is invalid or outside portfolio's date range

<a id="wpm.portfolio.get_historical_performance"></a>

#### get\_historical\_performance

```python
def get_historical_performance(
        portfolio: Portfolio,
        price_service: "PriceService",
        start_date: date,
        end_date: date,
        brokers: Optional[List[str]] = None) -> List[PortfolioHistoryPoint]
```

Get historical performance of a portfolio over a date range.

Returns a list of history points, one for each day from start_date to end_date
(inclusive). Each history point contains the total market value of the portfolio
and asset positions (quantity * historical price) for each asset on that date.

For assets that exist in the final portfolio but were purchased after the start date,
history points before the asset purchase will show a position of 0.0. For composite
portfolios, asset positions from sub-portfolios with the same ticker are merged.

This implementation calculates historical performance by filtering trades directly
instead of creating portfolio snapshots, and fetches all prices upfront in batch
for better performance.

**Arguments**:

- `portfolio` - Portfolio to analyze (SimplePortfolio or CompositePortfolio)
- `price_service` - Price service for retrieving historical prices
- `start_date` - Start date for performance tracking (inclusive)
- `end_date` - End date for performance tracking (inclusive)
- `brokers` - Optional list of broker names to filter by. If provided, only trades
  from specified brokers are included in position calculations.
  

**Returns**:

  List of PortfolioHistoryPoint objects, one for each day from start_date to end_date
  

**Raises**:

- `PortfolioError` - If date range is invalid or outside portfolio's date range
- `ValueError` - If historical prices cannot be retrieved for any required assets

<a id="wpm.portfolio.get_historical_allocations"></a>

#### get\_historical\_allocations

```python
def get_historical_allocations(
        portfolio: Portfolio,
        price_service: "PriceService",
        start_date: date,
        end_date: date,
        brokers: Optional[List[str]] = None) -> List[Dict[Asset, Decimal]]
```

Get historical percentage allocations of asset positions over a date range.

Returns a list of allocation dictionaries, one for each day from start_date to end_date
(inclusive). Each dictionary maps Asset to Decimal percentage allocation (2 decimal places).
Allocations are calculated as (asset position value / total portfolio market value) * 100.

This function leverages `get_historical_performance()` to reuse batch price retrieval
for efficiency.

**Arguments**:

- `portfolio` - Portfolio to analyze (SimplePortfolio or CompositePortfolio)
- `price_service` - Price service for retrieving historical prices
- `start_date` - Start date for allocation tracking (inclusive)
- `end_date` - End date for allocation tracking (inclusive)
- `brokers` - Optional list of broker names to filter by. If provided, only trades
  from specified brokers are included in allocation calculations.
  

**Returns**:

  List of dictionaries, one per date, mapping Asset to Decimal percentage allocation
  

**Raises**:

- `PortfolioError` - If date range is invalid or outside portfolio's date range
- `ValueError` - If historical prices cannot be retrieved for any required assets

<a id="wpm.portfolio.get_positions_with_allocations"></a>

#### get\_positions\_with\_allocations

```python
def get_positions_with_allocations(
    portfolio: Portfolio,
    prices: Dict[Asset, Optional[float]],
    asset_types: Optional[List[str]] = None,
    asset_tickers: Optional[List[str]] = None
) -> Dict[Asset, Tuple[Position, Decimal]]
```

Get positions and their percentage allocations combined in a single dictionary.

This utility function combines results from `get_positions()` and `get_all_allocations()`
for convenience. When filters are provided, only filtered assets are included and allocations
are calculated against the filtered asset list only (sum to 100% of filtered assets).

**Filter Logic**:

The filtering uses OR logic between `asset_types` and `asset_tickers`. An asset is included
if it matches any specified asset type OR any specified ticker. The behavior depends on which
parameters are provided:

1. **Both parameters are None** (default):
- All assets in the portfolio are included
- Allocations sum to 100% of the entire portfolio
- This is the backward compatible behavior

2. **Only `asset_types` is provided** (e.g., `asset_types=["Stock", "ETF"]`):
- Only assets whose `asset_type` matches one of the specified types are included
- Allocations sum to 100% of the filtered assets only

3. **Only `asset_tickers` is provided** (e.g., `asset_tickers=["GOOG", "AAPL"]`):
- Only assets whose ticker matches one of the specified tickers are included
- Allocations sum to 100% of the filtered assets only

4. **Both parameters are provided** (e.g., `asset_types=["Crypto"]`, `asset_tickers=["GOOG"]`):
- OR logic: An asset is included if it matches any specified asset type OR any specified ticker
- Example: If portfolio has GOOG (Stock), AAPL (Stock), BTC-USD (Crypto), and filters are
`asset_types=["Crypto"]`, `asset_tickers=["GOOG"]`:
- Included: GOOG (matches ticker), BTC-USD (matches asset_type)
- Excluded: AAPL (matches neither)
- Allocations sum to 100% of the filtered assets only

**Important Notes**:

- Asset types are normalized using `validate_asset_type` for consistency
- When filters are provided, allocations are calculated against the filtered asset list only,
not the entire portfolio
- Empty filter results return an empty dictionary

**Examples**:

.. code-block:: python

# Get positions and allocations for all assets (no filtering)
result = get_positions_with_allocations(portfolio, prices)

# Get positions and allocations for only Stock and ETF assets
result = get_positions_with_allocations(portfolio, prices, asset_types=["Stock", "ETF"])

# Get positions and allocations for specific tickers
result = get_positions_with_allocations(portfolio, prices, asset_tickers=["GOOG", "AAPL"])

# Get positions and allocations for Crypto assets OR specific tickers (OR logic)
result = get_positions_with_allocations(
portfolio,
prices,
asset_types=["Crypto"],
asset_tickers=["GOOG", "VOO"]
)

**Arguments**:

- `portfolio` - Portfolio to analyze (SimplePortfolio or CompositePortfolio)
- `prices` - Dictionary mapping Asset to current price (None if unavailable)
- `asset_types` - Optional list of asset types to filter by (e.g., ["Stock", "ETF", "Crypto"]).
  Uses OR logic - asset is included if it matches any specified type.
- `asset_tickers` - Optional list of ticker symbols to filter by (e.g., ["GOOG", "AAPL"]).
  Uses OR logic - asset is included if it matches any specified ticker.
  

**Returns**:

  Dictionary mapping Asset to tuple of (Position, allocation_percentage)
  Only includes assets that have both a position and an allocation (and match filters if provided)

<a id="wpm.portfolio.get_historical_positions_with_allocations"></a>

#### get\_historical\_positions\_with\_allocations

```python
def get_historical_positions_with_allocations(
    portfolio: Portfolio,
    price_service: "PriceService",
    start_date: date,
    end_date: date,
    asset_types: Optional[List[str]] = None,
    asset_tickers: Optional[List[str]] = None
) -> List[Dict[Asset, Tuple[float, Decimal]]]
```

Get historical positions and their percentage allocations combined.

This utility function combines results from `get_historical_performance()` and
`get_historical_allocations()` for convenience. Returns position values (floats)
and allocation percentages (Decimals) for each date in the range.

When filters are provided, only filtered assets are included for each date and allocations
are calculated against the filtered asset list only (sum to 100% of filtered assets for each date).

**Filter Logic**:

The filtering uses OR logic between `asset_types` and `asset_tickers`. An asset is included
if it matches any specified asset type OR any specified ticker. The behavior depends on which
parameters are provided:

1. **Both parameters are None** (default):
- All assets in the portfolio are included for each date
- Allocations sum to 100% of the entire portfolio for each date
- This is the backward compatible behavior

2. **Only `asset_types` is provided** (e.g., `asset_types=["Stock", "ETF"]`):
- Only assets whose `asset_type` matches one of the specified types are included
- Filter is applied consistently across all dates in the range
- Allocations sum to 100% of the filtered assets only for each date

3. **Only `asset_tickers` is provided** (e.g., `asset_tickers=["GOOG", "AAPL"]`):
- Only assets whose ticker matches one of the specified tickers are included
- Filter is applied consistently across all dates in the range
- Allocations sum to 100% of the filtered assets only for each date

4. **Both parameters are provided** (e.g., `asset_types=["Crypto"]`, `asset_tickers=["GOOG"]`):
- OR logic: An asset is included if it matches any specified asset type OR any specified ticker
- Example: If portfolio has GOOG (Stock), AAPL (Stock), BTC-USD (Crypto), and filters are
`asset_types=["Crypto"]`, `asset_tickers=["GOOG"]`:
- Included: GOOG (matches ticker), BTC-USD (matches asset_type)
- Excluded: AAPL (matches neither)
- Filter is applied consistently across all dates in the range
- Allocations sum to 100% of the filtered assets only for each date

**Important Notes**:

- Asset types are normalized using `validate_asset_type` for consistency
- When filters are provided, allocations are calculated against the filtered asset list only,
not the entire portfolio
- Filter is applied consistently across all dates in the range
- Empty filter results return an empty list of dictionaries

**Examples**:

.. code-block:: python

# Get historical positions and allocations for all assets (no filtering)
result = get_historical_positions_with_allocations(
portfolio, price_service, start_date, end_date
)

# Get historical positions and allocations for only Stock and ETF assets
result = get_historical_positions_with_allocations(
portfolio, price_service, start_date, end_date,
asset_types=["Stock", "ETF"]
)

# Get historical positions and allocations for specific tickers
result = get_historical_positions_with_allocations(
portfolio, price_service, start_date, end_date,
asset_tickers=["GOOG", "AAPL"]
)

# Get historical positions and allocations for Crypto assets OR specific tickers (OR logic)
result = get_historical_positions_with_allocations(
portfolio, price_service, start_date, end_date,
asset_types=["Crypto"],
asset_tickers=["GOOG", "VOO"]
)

**Arguments**:

- `portfolio` - Portfolio to analyze (SimplePortfolio or CompositePortfolio)
- `price_service` - Price service for retrieving historical prices
- `start_date` - Start date for tracking (inclusive)
- `end_date` - End date for tracking (inclusive)
- `asset_types` - Optional list of asset types to filter by (e.g., ["Stock", "ETF", "Crypto"]).
  Uses OR logic - asset is included if it matches any specified type.
- `asset_tickers` - Optional list of ticker symbols to filter by (e.g., ["GOOG", "AAPL"]).
  Uses OR logic - asset is included if it matches any specified ticker.
  

**Returns**:

  List of dictionaries, one per date, mapping Asset to tuple of
  (position_value, allocation_percentage)
  Only includes assets that appear in both position values and allocations (and match filters if provided)
  

**Raises**:

- `PortfolioError` - If date range is invalid or outside portfolio's date range
- `ValueError` - If historical prices cannot be retrieved for any required assets

<a id="wpm.pricing.service"></a>

# wpm.pricing.service

Service that orchestrates price retrieval with caching and rate limiting.

<a id="wpm.pricing.service.PriceService"></a>

## PriceService Objects

```python
class PriceService()
```

Service that orchestrates price retrieval with caching and rate limiting.

<a id="wpm.pricing.service.PriceService.__init__"></a>

#### \_\_init\_\_

```python
def __init__(cache_file: Optional[Path] = None,
             historical_cache_file: Optional[Path] = None,
             rate_limit_per_minute: int = 60,
             currency_service: CurrencyService = None)
```

Initialize price service.

**Arguments**:

- `cache_file` - Path to cache file (default: Config.CACHE_FILE)
- `historical_cache_file` - Path to historical cache file (default: Config.HISTORICAL_CACHE_FILE)
- `rate_limit_per_minute` - Rate limit for API calls per minute
- `currency_service` - CurrencyService instance (default: creates new instance)

<a id="wpm.pricing.service.PriceService.get_retriever"></a>

#### get\_retriever

```python
def get_retriever(asset_type: str) -> PriceRetriever
```

Get appropriate price retriever for asset type.

**Arguments**:

- `asset_type` - Asset type
  

**Returns**:

  PriceRetriever instance
  

**Raises**:

- `ValueError` - If asset type is not supported

<a id="wpm.pricing.service.PriceService.get_stock_retriever"></a>

#### get\_stock\_retriever

```python
def get_stock_retriever() -> PriceRetriever
```

Get the stock/ETF retriever instance.

**Returns**:

  YahooFinanceRetriever instance for stocks and ETFs

<a id="wpm.pricing.service.PriceService.detect_currency"></a>

#### detect\_currency

```python
def detect_currency(ticker: str) -> str
```

Detect currency from ticker symbol.

**Arguments**:

- `ticker` - Ticker symbol (e.g., "2800.HK", "GOOG")
  

**Returns**:

  Currency code (e.g., "HKD", "USD")

<a id="wpm.pricing.service.PriceService.get_price"></a>

#### get\_price

```python
def get_price(ticker: str,
              asset_type: str,
              in_native_currency: bool = False) -> float
```

Get current price for an asset (checks cache first).

**Arguments**:

- `ticker` - Asset ticker symbol
- `asset_type` - Asset type ("Stock", "ETF", or "Crypto")
- `in_native_currency` - If True, return price in native currency; if False, return USD (default)
  

**Returns**:

  Current price in USD (or native currency if in_native_currency=True)

<a id="wpm.pricing.service.PriceService.get_prices"></a>

#### get\_prices

```python
def get_prices(tickers: List[str],
               asset_type: str,
               in_native_currency: bool = False) -> Dict[str, float]
```

Batch price retrieval with rate limiting and batch API calls.

**Arguments**:

- `tickers` - List of asset ticker symbols
- `asset_type` - Asset type for all tickers
- `in_native_currency` - If True, return prices in native currency; if False, return USD (default)
  

**Returns**:

  Dictionary mapping ticker to price (in USD or native currency)
  

**Raises**:

- `ValueError` - If no price data can be obtained for a ticker (no API response and no cache)

<a id="wpm.pricing.service.PriceService.get_historical_price"></a>

#### get\_historical\_price

```python
def get_historical_price(ticker: str,
                         asset_type: str,
                         target_date: date,
                         in_native_currency: bool = False) -> float
```

Get historical price for an asset on a specific date.

**Arguments**:

- `ticker` - Asset ticker symbol
- `asset_type` - Asset type ("Stock", "ETF", or "Crypto")
- `target_date` - Target date (inclusive). Returns most recent price available up to this date
- `in_native_currency` - If True, return price in native currency; if False, return USD (default)
  

**Returns**:

  Historical price in USD (or native currency if in_native_currency=True)
  

**Raises**:

- `ValueError` - If price cannot be retrieved

<a id="wpm.pricing.service.PriceService.get_historical_prices"></a>

#### get\_historical\_prices

```python
def get_historical_prices(
        tickers: List[str],
        asset_type: str,
        start_date: date,
        end_date: date,
        in_native_currency: bool = False) -> Dict[str, Dict[date, float]]
```

Get historical prices for multiple assets over a date range.

Returns prices for all dates in the range (start_date to end_date, inclusive).

**Arguments**:

- `tickers` - List of asset ticker symbols
- `asset_type` - Asset type for all tickers
- `start_date` - Start date (inclusive)
- `end_date` - End date (inclusive)
- `in_native_currency` - If True, return prices in native currency; if False, return USD (default)
  

**Returns**:

  Dictionary mapping ticker to dictionary mapping date to price (in USD or native currency)
  

**Raises**:

- `ValueError` - If no price data can be obtained for any ticker

<a id="wpm.pricing.coingecko"></a>

# wpm.pricing.coingecko

CoinGecko price retriever implementation.

<a id="wpm.pricing.coingecko.CoinGeckoRetriever"></a>

## CoinGeckoRetriever Objects

```python
class CoinGeckoRetriever(PriceRetriever)
```

Price retriever using CoinGecko API for cryptocurrencies.

<a id="wpm.pricing.coingecko.CoinGeckoRetriever.metadata_supported"></a>

#### metadata\_supported

```python
@property
def metadata_supported() -> bool
```

Whether this retriever supports metadata retrieval.

**Returns**:

  False - CoinGecko retriever does not support metadata retrieval

<a id="wpm.pricing.coingecko.CoinGeckoRetriever.__init__"></a>

#### \_\_init\_\_

```python
def __init__(api_key: Optional[str] = None, is_demo: Optional[bool] = None)
```

Initialize CoinGecko API client.

**Arguments**:

- `api_key` - Optional API key for CoinGecko API. If not provided, uses
  Config.COINGECKO_API_KEY. If that is also None, uses free tier.
- `is_demo` - Optional flag to indicate if API key is a demo key. If not provided,
  uses Config.COINGECKO_API_IS_DEMO.

<a id="wpm.pricing.coingecko.CoinGeckoRetriever.get_price"></a>

#### get\_price

```python
def get_price(ticker: str, asset_type: str) -> float
```

Get current price from CoinGecko.

**Arguments**:

- `ticker` - Crypto ticker symbol
- `asset_type` - Asset type (should be "Crypto")
  

**Returns**:

  Current price in USD
  

**Raises**:

- `ValueError` - If price cannot be retrieved

<a id="wpm.pricing.coingecko.CoinGeckoRetriever.get_prices"></a>

#### get\_prices

```python
def get_prices(tickers: List[str], asset_type: str) -> Dict[str, float]
```

Get current prices from CoinGecko for multiple tickers in a single batch request.

**Arguments**:

- `tickers` - List of crypto ticker symbols
- `asset_type` - Asset type (should be "Crypto")
  

**Returns**:

  Dictionary mapping ticker to price. Only includes successfully retrieved prices.

<a id="wpm.pricing.coingecko.CoinGeckoRetriever.get_historical_prices"></a>

#### get\_historical\_prices

```python
def get_historical_prices(
        ticker: Union[str, List[str]], asset_type: str, start_date: date,
        end_date: date) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]
```

Get historical prices from CoinGecko over a date range.

Note: CoinGecko doesn't support multiple tickers in the same API call with date ranges,
so this method only handles a single ticker. When a list is provided, raises ValueError.

**Arguments**:

- `ticker` - Crypto ticker symbol (str) or list of ticker symbols (List[str])
- `asset_type` - Asset type (should be "Crypto")
- `start_date` - Start date (inclusive)
- `end_date` - End date (inclusive)
  

**Returns**:

  If ticker is str: DataFrame with date index and price column (USD)
  If ticker is List[str]: Not supported, raises ValueError
  

**Raises**:

- `ValueError` - If prices cannot be retrieved, or if multiple tickers are provided

<a id="wpm.pricing.coingecko.CoinGeckoRetriever.get_metadata"></a>

#### get\_metadata

```python
def get_metadata(ticker: str, asset_type: str) -> Optional[Dict[str, Any]]
```

Get metadata for an asset.

**Arguments**:

- `ticker` - Asset ticker symbol
- `asset_type` - Asset type (unused)
  

**Returns**:

  Never returns (always raises NotImplementedError)
  

**Raises**:

- `NotImplementedError` - CoinGecko does not support metadata retrieval

<a id="wpm.pricing.yahoo"></a>

# wpm.pricing.yahoo

Yahoo Finance price retriever implementation.

<a id="wpm.pricing.yahoo.YahooFinanceRetriever"></a>

## YahooFinanceRetriever Objects

```python
class YahooFinanceRetriever(PriceRetriever)
```

Price retriever using yfinance for stocks and ETFs.

<a id="wpm.pricing.yahoo.YahooFinanceRetriever.metadata_supported"></a>

#### metadata\_supported

```python
@property
def metadata_supported() -> bool
```

Whether this retriever supports metadata retrieval.

**Returns**:

  True - Yahoo Finance retriever supports metadata retrieval

<a id="wpm.pricing.yahoo.YahooFinanceRetriever.__init__"></a>

#### \_\_init\_\_

```python
def __init__(currency_service: CurrencyService = None)
```

Initialize Yahoo Finance retriever.

**Arguments**:

- `currency_service` - CurrencyService instance (default: creates new instance)

<a id="wpm.pricing.yahoo.YahooFinanceRetriever.get_price"></a>

#### get\_price

```python
def get_price(ticker: str, asset_type: str) -> float
```

Get current price from Yahoo Finance in native currency.

During trading hours: tries currentPrice or regularMarketPrice from ticker.info first,
falls back to Close from historical data if unavailable.
Outside trading hours: uses Close from historical data.

**Arguments**:

- `ticker` - Stock/ETF ticker symbol
- `asset_type` - Asset type (should be "Stock" or "ETF")
  

**Returns**:

  Current price in native currency (not USD)
  

**Raises**:

- `ValueError` - If price cannot be retrieved

<a id="wpm.pricing.yahoo.YahooFinanceRetriever.get_prices"></a>

#### get\_prices

```python
def get_prices(tickers: List[str], asset_type: str) -> Dict[str, float]
```

Get current prices from Yahoo Finance for multiple tickers in a single batch request.

Prices are returned in native currency (not USD).

During trading hours: tries currentPrice or regularMarketPrice from ticker.info for each ticker,
falls back to Close from batch download if unavailable.
Outside trading hours: uses Close from batch download.

**Arguments**:

- `tickers` - List of stock/ETF ticker symbols
- `asset_type` - Asset type (should be "Stock" or "ETF")
  

**Returns**:

  Dictionary mapping ticker to price in native currency. Only includes successfully retrieved prices.

<a id="wpm.pricing.yahoo.YahooFinanceRetriever.get_historical_prices"></a>

#### get\_historical\_prices

```python
def get_historical_prices(
        ticker: Union[str, List[str]], asset_type: str, start_date: date,
        end_date: date) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]
```

Get historical prices from Yahoo Finance over a date range.

Supports both single ticker and batch ticker fetching.

**Arguments**:

- `ticker` - Stock/ETF/Crypto ticker symbol (str) or list of ticker symbols (List[str])
- `asset_type` - Asset type (should be "Stock", "ETF", or "Crypto")
- `start_date` - Start date (inclusive)
- `end_date` - End date (inclusive)
  

**Returns**:

  If ticker is str: DataFrame with date index and price column (native currency, USD for crypto)
  If ticker is List[str]: Dictionary mapping ticker to DataFrame with date index and price column
  

**Raises**:

- `ValueError` - If prices cannot be retrieved

<a id="wpm.pricing.yahoo.YahooFinanceRetriever.get_metadata"></a>

#### get\_metadata

```python
def get_metadata(ticker: str, asset_type: str) -> Optional[Dict[str, Any]]
```

Get metadata for an asset.

**Arguments**:

- `ticker` - Asset ticker symbol
- `asset_type` - Asset type ("Stock", "ETF", or "Crypto")
  

**Returns**:

  Metadata dictionary with keys: name, sector, industry, country, market_cap, category.
  Returns None if retrieval fails.

<a id="wpm.pricing.rate_limiter"></a>

# wpm.pricing.rate\_limiter

Rate limiting utility for API calls.

<a id="wpm.pricing.rate_limiter.RateLimiter"></a>

## RateLimiter Objects

```python
class RateLimiter()
```

Rate limiting utility for API calls.

<a id="wpm.pricing.rate_limiter.RateLimiter.__init__"></a>

#### \_\_init\_\_

```python
def __init__(max_calls_per_minute: int = 60)
```

Initialize rate limiter.

**Arguments**:

- `max_calls_per_minute` - Maximum number of API calls per minute

<a id="wpm.pricing.rate_limiter.RateLimiter.wait_if_needed"></a>

#### wait\_if\_needed

```python
def wait_if_needed() -> None
```

Wait if rate limit would be exceeded.

<a id="wpm.pricing.cache"></a>

# wpm.pricing.cache

Manages persistent Parquet-based price cache.

<a id="wpm.pricing.cache.CacheValidityStatus"></a>

## CacheValidityStatus Objects

```python
class CacheValidityStatus(Enum)
```

Cache validity status enumeration.

<a id="wpm.pricing.cache.CacheValidity"></a>

## CacheValidity Objects

```python
@dataclass
class CacheValidity()
```

Cache validity status and stale entries.

**Attributes**:

- `status` - The validity status of the cache
- `stale_entries` - List of stale cache entries, each containing:
  - ticker: str
  - asset_type: str
  - price: float
  - timestamp: datetime

<a id="wpm.pricing.cache.PriceCache"></a>

## PriceCache Objects

```python
class PriceCache()
```

Manages persistent Parquet-based price cache.

<a id="wpm.pricing.cache.PriceCache.__init__"></a>

#### \_\_init\_\_

```python
def __init__(cache_file: Optional[Path] = None)
```

Initialize price cache.

**Arguments**:

- `cache_file` - Path to cache file (default: Config.CACHE_FILE)

<a id="wpm.pricing.cache.PriceCache.get_cached_price"></a>

#### get\_cached\_price

```python
def get_cached_price(ticker: str, asset_type: str) -> Optional[float]
```

Get cached USD price if valid.

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
  

**Returns**:

  Cached USD price if valid, None otherwise

<a id="wpm.pricing.cache.PriceCache.get_cached_price_native"></a>

#### get\_cached\_price\_native

```python
def get_cached_price_native(ticker: str, asset_type: str) -> Optional[float]
```

Get cached native currency price if valid.

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
  

**Returns**:

  Cached native currency price if valid, None otherwise

<a id="wpm.pricing.cache.PriceCache.get_stale_cached_price"></a>

#### get\_stale\_cached\_price

```python
def get_stale_cached_price(ticker: str, asset_type: str) -> Optional[float]
```

Get cached USD price even if it's expired/invalid (stale).

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
  

**Returns**:

  Cached USD price if entry exists (even if stale), None if no cache entry exists at all

<a id="wpm.pricing.cache.PriceCache.get_stale_cached_price_native"></a>

#### get\_stale\_cached\_price\_native

```python
def get_stale_cached_price_native(ticker: str,
                                  asset_type: str) -> Optional[float]
```

Get cached native currency price even if it's expired/invalid (stale).

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
  

**Returns**:

  Cached native currency price if entry exists (even if stale), None if no cache entry exists at all

<a id="wpm.pricing.cache.PriceCache.set_cached_price"></a>

#### set\_cached\_price

```python
def set_cached_price(ticker: str,
                     asset_type: str,
                     price: float,
                     native_price: float,
                     native_currency: str,
                     timestamp: Optional[datetime] = None) -> None
```

Set cached price (both USD and native currency).

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
- `price` - USD price to cache
- `native_price` - Native currency price to cache
- `native_currency` - Native currency code (e.g., "HKD", "USD")
- `timestamp` - Timestamp (default: current time)

<a id="wpm.pricing.cache.PriceCache.get_cache_validity"></a>

#### get\_cache\_validity

```python
def get_cache_validity(tickers: Optional[List[str]] = None) -> CacheValidity
```

Get cache validity status.

**Arguments**:

- `tickers` - Optional list of tickers to check. If None, checks all entries.
  

**Returns**:

  CacheValidity object with status and stale entries

<a id="wpm.pricing"></a>

# wpm.pricing

Market price data retrieval module with caching and rate limiting.

<a id="wpm.pricing.historical_cache"></a>

# wpm.pricing.historical\_cache

Manages persistent Parquet-based historical price cache.

<a id="wpm.pricing.historical_cache.HistoricalPriceCache"></a>

## HistoricalPriceCache Objects

```python
class HistoricalPriceCache()
```

Manages persistent Parquet-based historical price cache.

Stores daily prices for date ranges per asset. Historical cache entries
are always valid (no expiration).

<a id="wpm.pricing.historical_cache.HistoricalPriceCache.__init__"></a>

#### \_\_init\_\_

```python
def __init__(cache_file: Optional[Path] = None)
```

Initialize historical price cache.

**Arguments**:

- `cache_file` - Path to cache file (default: Config.HISTORICAL_CACHE_FILE)

<a id="wpm.pricing.historical_cache.HistoricalPriceCache.get_cached_prices"></a>

#### get\_cached\_prices

```python
def get_cached_prices(ticker: str, asset_type: str, start_date: date,
                      end_date: date) -> Optional[pd.DataFrame]
```

Get cached prices for a date range.

Returns DataFrame only if cache has complete coverage for the requested range.

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
- `start_date` - Start date (inclusive)
- `end_date` - End date (inclusive)
  

**Returns**:

  DataFrame with date index and price column if cache has full coverage,
  None otherwise

<a id="wpm.pricing.historical_cache.HistoricalPriceCache.get_cached_price"></a>

#### get\_cached\_price

```python
def get_cached_price(ticker: str, asset_type: str,
                     target_date: date) -> Optional[float]
```

Get cached price for a specific date (most recent available up to target_date).

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
- `target_date` - Target date (inclusive)
  

**Returns**:

  Cached price if available, None otherwise

<a id="wpm.pricing.historical_cache.HistoricalPriceCache.set_cached_prices"></a>

#### set\_cached\_prices

```python
def set_cached_prices(ticker: str,
                      asset_type: str,
                      prices_df: pd.DataFrame,
                      native_prices_df: Optional[pd.DataFrame] = None,
                      native_currency: str = "USD") -> None
```

Store daily prices for a date range.

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type
- `prices_df` - DataFrame with date index and price column (USD prices)
- `native_prices_df` - Optional DataFrame with date index and native_price column
- `native_currency` - Native currency code (default: "USD")

<a id="wpm.pricing.historical_cache.HistoricalPriceCache.clear_asset"></a>

#### clear\_asset

```python
def clear_asset(ticker: str, asset_type: str) -> None
```

Clear all cached prices for a specific asset.

**Arguments**:

- `ticker` - Asset ticker
- `asset_type` - Asset type

<a id="wpm.pricing.historical_cache.HistoricalPriceCache.clear_all"></a>

#### clear\_all

```python
def clear_all() -> None
```

Clear entire historical cache.

<a id="wpm.pricing.base"></a>

# wpm.pricing.base

Base class for price retrievers.

<a id="wpm.pricing.base.PriceRetriever"></a>

## PriceRetriever Objects

```python
class PriceRetriever(ABC)
```

Abstract base class for price retrievers.

<a id="wpm.pricing.base.PriceRetriever.metadata_supported"></a>

#### metadata\_supported

```python
@property
@abstractmethod
def metadata_supported() -> bool
```

Whether this retriever supports metadata retrieval.

**Returns**:

  True if metadata retrieval is supported, False otherwise

<a id="wpm.pricing.base.PriceRetriever.get_price"></a>

#### get\_price

```python
@abstractmethod
def get_price(ticker: str, asset_type: str) -> float
```

Get current price for an asset.

**Arguments**:

- `ticker` - Asset ticker symbol
- `asset_type` - Asset type ("Stock", "ETF", or "Crypto")
  

**Returns**:

  Current price in USD
  

**Raises**:

- `ValueError` - If price cannot be retrieved

<a id="wpm.pricing.base.PriceRetriever.get_prices"></a>

#### get\_prices

```python
@abstractmethod
def get_prices(tickers: List[str], asset_type: str) -> Dict[str, float]
```

Get current prices for multiple assets in a single batch request.

**Arguments**:

- `tickers` - List of asset ticker symbols
- `asset_type` - Asset type for all tickers ("Stock", "ETF", or "Crypto")
  

**Returns**:

  Dictionary mapping ticker to price. Only includes successfully retrieved prices.
  Tickers that fail are omitted from the result (caller should handle fallback).

<a id="wpm.pricing.base.PriceRetriever.get_historical_prices"></a>

#### get\_historical\_prices

```python
@abstractmethod
def get_historical_prices(
        ticker: Union[str, List[str]], asset_type: str, start_date: date,
        end_date: date) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]
```

Get historical prices for an asset or multiple assets over a date range.

**Arguments**:

- `ticker` - Asset ticker symbol (str) or list of ticker symbols (List[str])
- `asset_type` - Asset type ("Stock", "ETF", or "Crypto")
- `start_date` - Start date (inclusive)
- `end_date` - End date (inclusive)
  

**Returns**:

  If ticker is str: DataFrame with date index and price column (native currency)
  If ticker is List[str]: Dictionary mapping ticker to DataFrame with date index and price column (native currency)
  

**Raises**:

- `ValueError` - If prices cannot be retrieved

<a id="wpm.pricing.base.PriceRetriever.get_metadata"></a>

#### get\_metadata

```python
def get_metadata(ticker: str, asset_type: str) -> Optional[Dict[str, Any]]
```

Get metadata for an asset.

**Arguments**:

- `ticker` - Asset ticker symbol
- `asset_type` - Asset type ("Stock", "ETF", or "Crypto")
  

**Returns**:

  Metadata dictionary with keys: name, sector, industry, country, market_cap, category.
  Returns None if retrieval fails.
  

**Raises**:

- `NotImplementedError` - If metadata_supported is False

