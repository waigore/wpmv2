# Data Models

## Asset

Represents a financial asset identifier.

**Fields:**
- `ticker` (str, required): Asset ticker symbol (e.g., "BTC-USD", "GOOG", "IAU")
  - Validation: Non-empty string, alphanumeric with hyphens/underscores allowed
- `asset_type` (str, required): Type of asset - one of "Stock", "ETF", or "Crypto"
  - Validation: Must be one of the allowed values (case-insensitive, normalized to title case)

**Methods:**
- `__eq__()`: Equality comparison based on ticker and asset_type
- `__hash__()`: Hashable for use in sets/dictionaries

## Trade

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

## Position

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

## Lot

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

## Portfolio

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

## PortfolioHistoryPoint

Represents a portfolio state at a specific point in time, used for historical performance tracking.

**Fields:**
- `date` (date, required): The date this history point represents
  - Validation: Valid date object
- `total_market_value` (float, required): Total market value of the portfolio on this date
  - Validation: Non-negative number
- `asset_positions` (Dict[str, float], required): Dictionary mapping ticker symbols to position values (quantity * historical price)
  - Validation: Dictionary with string keys (tickers) and non-negative float values
  - Assets that exist in the final portfolio but weren't purchased by this date have position value of 0.0
  - For composite portfolios, positions from sub-portfolios with the same ticker are merged (summed)

**Usage Notes:**
- Used by `get_historical_performance()` function to represent portfolio state at each date in a date range
- Asset positions dictionary includes all assets from the final portfolio state, ensuring consistent tracking even for assets purchased after the start date
- For composite portfolios, asset positions from sub-portfolios are automatically merged by ticker

## Price Cache Entry

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

