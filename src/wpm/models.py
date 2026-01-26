"""Core data models for the WPM library."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from wpm.utils import validate_asset_type, validate_ticker


class ValidationError(ValueError):
    """Raised when validation of input data fails."""

    pass


class PortfolioError(ValueError):
    """Raised when portfolio operations are invalid."""

    pass


@dataclass(frozen=True, eq=True)
class Asset:
    """Represents a financial asset with ticker and type."""

    ticker: str
    asset_type: str

    def __post_init__(self):
        """Validate asset fields after initialization."""
        if not self.ticker or not isinstance(self.ticker, str):
            raise ValidationError("Ticker must be a non-empty string")

        try:
            validate_ticker(self.ticker)
        except ValueError as e:
            raise ValidationError(str(e)) from e

        if not self.asset_type or not isinstance(self.asset_type, str):
            raise ValidationError("Asset type must be a non-empty string")

        try:
            normalized_type = validate_asset_type(self.asset_type)
            object.__setattr__(self, "asset_type", normalized_type)
        except ValueError as e:
            raise ValidationError(str(e)) from e

    def __hash__(self):
        """Make Asset hashable for use in sets/dictionaries."""
        return hash((self.ticker, self.asset_type))


@dataclass
class Trade:
    """Represents a single buy or sell transaction."""

    date: date
    asset: Asset
    action: str
    broker: str
    order_instruction: Optional[str] = None
    trade_type: Optional[str] = None
    currency: str = "USD"
    price: float = field(default=0.0)  # Price in USD (accounting currency)
    price_native: float = field(default=0.0)  # Price in native currency
    quantity: Decimal = field(default_factory=lambda: Decimal('0'))

    def __post_init__(self):
        """Validate trade fields after initialization."""
        if not isinstance(self.date, date):
            raise ValidationError("Date must be a date object")

        today = date.today()
        if self.date > today:
            raise ValidationError("Trade date cannot be in the future")

        if not isinstance(self.asset, Asset):
            raise ValidationError("Asset must be an Asset object")

        if not self.action or not isinstance(self.action, str):
            raise ValidationError("Action must be a non-empty string")

        normalized_action = self.action.strip().title()
        if normalized_action not in ("Buy", "Sell"):
            raise ValidationError(f"Action must be 'Buy' or 'Sell', got '{self.action}'")
        object.__setattr__(self, "action", normalized_action)

        if not self.broker or not isinstance(self.broker, str):
            raise ValidationError("Broker must be a non-empty string")

        if not self.currency or not isinstance(self.currency, str):
            raise ValidationError("Currency must be a non-empty string")

        if self.order_instruction is not None:
            if not isinstance(self.order_instruction, str) or not self.order_instruction.strip():
                raise ValidationError("Order instruction must be a non-empty string if provided")

        if self.trade_type is not None:
            if not isinstance(self.trade_type, str) or not self.trade_type.strip():
                raise ValidationError("Trade type must be a non-empty string if provided")

        if not isinstance(self.price, (int, float)) or self.price <= 0:
            raise ValidationError("Price must be a positive number greater than 0")

        if not isinstance(self.price_native, (int, float)) or self.price_native <= 0:
            raise ValidationError("Price native must be a positive number greater than 0")

        # Ensure price_native matches price when currency is USD
        if self.currency == "USD" and abs(self.price - self.price_native) > 0.0001:
            raise ValidationError(
                f"When currency is USD, price_native ({self.price_native}) must equal price ({self.price})"
            )

        # Convert quantity to Decimal if it's a float or int
        if isinstance(self.quantity, (int, float)):
            quantity_decimal = Decimal(str(self.quantity))
            object.__setattr__(self, "quantity", quantity_decimal)
        elif not isinstance(self.quantity, Decimal):
            raise ValidationError("Quantity must be a Decimal, int, or float")
        
        if self.quantity <= 0:
            raise ValidationError("Quantity must be a positive number greater than 0")

    @property
    def total_value(self) -> float:
        """Calculate total value of the trade (price * quantity)."""
        return float(self.quantity) * self.price

    def is_buy(self) -> bool:
        """Check if trade is a buy transaction."""
        return self.action == "Buy"

    def is_sell(self) -> bool:
        """Check if trade is a sell transaction."""
        return self.action == "Sell"


@dataclass
class Lot:
    """Represents a purchase record (lot) for an asset with FIFO sell matching."""

    purchase_date: date
    purchase_price: float
    original_quantity: Decimal
    remaining_quantity: Decimal
    cost_basis: float
    asset: Asset
    broker: str
    matched_sells: List[Tuple[Trade, Decimal]] = field(default_factory=list)

    def __post_init__(self):
        """Validate lot fields after initialization."""
        if not isinstance(self.purchase_date, date):
            raise ValidationError("Purchase date must be a date object")

        if not isinstance(self.purchase_price, (int, float)) or self.purchase_price <= 0:
            raise ValidationError("Purchase price must be a positive number greater than 0")

        # Convert quantities to Decimal if needed
        if isinstance(self.original_quantity, (int, float)):
            original_quantity_decimal = Decimal(str(self.original_quantity))
            object.__setattr__(self, "original_quantity", original_quantity_decimal)
        elif not isinstance(self.original_quantity, Decimal):
            raise ValidationError("Original quantity must be a Decimal, int, or float")

        if isinstance(self.remaining_quantity, (int, float)):
            remaining_quantity_decimal = Decimal(str(self.remaining_quantity))
            object.__setattr__(self, "remaining_quantity", remaining_quantity_decimal)
        elif not isinstance(self.remaining_quantity, Decimal):
            raise ValidationError("Remaining quantity must be a Decimal, int, or float")

        if self.original_quantity <= 0:
            raise ValidationError("Original quantity must be a positive number greater than 0")

        if self.remaining_quantity < 0:
            raise ValidationError("Remaining quantity must be a non-negative number")

        if self.remaining_quantity > self.original_quantity:
            raise ValidationError("Remaining quantity cannot exceed original quantity")

        if not isinstance(self.cost_basis, (int, float)) or self.cost_basis < 0:
            raise ValidationError("Cost basis must be a non-negative number")

        if not isinstance(self.asset, Asset):
            raise ValidationError("Asset must be an Asset object")

        if not self.broker or not isinstance(self.broker, str):
            raise ValidationError("Broker must be a non-empty string")

        # Validate matched_sells
        if not isinstance(self.matched_sells, list):
            raise ValidationError("Matched sells must be a list")
        for sell_trade, quantity_sold in self.matched_sells:
            if not isinstance(sell_trade, Trade):
                raise ValidationError("Matched sell must contain a Trade object")
            if not isinstance(quantity_sold, Decimal):
                if isinstance(quantity_sold, (int, float)):
                    quantity_sold = Decimal(str(quantity_sold))
                else:
                    raise ValidationError("Quantity sold must be a Decimal, int, or float")
            if quantity_sold <= 0:
                raise ValidationError("Quantity sold must be a positive number")

    def get_realized_pnl(self) -> float:
        """Calculate realized profit/loss from matched sells.

        Returns:
            Realized P/L in USD (sum of (sell_price - purchase_price) * quantity_sold for all matched sells)
        """
        realized_pnl = 0.0
        for sell_trade, quantity_sold in self.matched_sells:
            pnl_per_unit = sell_trade.price - self.purchase_price
            realized_pnl += float(quantity_sold) * pnl_per_unit
        return realized_pnl

    def get_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized profit/loss for remaining quantity.

        Args:
            current_price: Current market price per unit

        Returns:
            Unrealized P/L in USD ((current_price - purchase_price) * remaining_quantity)
        """
        if current_price is None:
            return 0.0
        pnl_per_unit = current_price - self.purchase_price
        return float(self.remaining_quantity) * pnl_per_unit

    def get_total_pnl(self, current_price: Optional[float]) -> float:
        """Calculate total profit/loss (realized + unrealized).

        Args:
            current_price: Current market price per unit (None if unavailable)

        Returns:
            Total P/L in USD (realized P/L + unrealized P/L)
        """
        return self.get_realized_pnl() + self.get_unrealized_pnl(current_price or 0.0)


@dataclass
class Position:
    """Represents current holdings for a specific asset within a portfolio."""

    asset: Asset
    quantity: Decimal
    cost_basis: float
    cost_basis_method: str

    def __post_init__(self):
        """Validate position fields after initialization."""
        if not isinstance(self.asset, Asset):
            raise ValidationError("Asset must be an Asset object")

        # Convert quantity to Decimal if it's a float or int
        if isinstance(self.quantity, (int, float)):
            quantity_decimal = Decimal(str(self.quantity))
            object.__setattr__(self, "quantity", quantity_decimal)
        elif not isinstance(self.quantity, Decimal):
            raise ValidationError("Quantity must be a Decimal, int, or float")
        
        if self.quantity < 0:
            raise ValidationError("Quantity must be a non-negative number")

        if not isinstance(self.cost_basis, (int, float)) or self.cost_basis < 0:
            raise ValidationError("Cost basis must be a non-negative number")

        if self.cost_basis_method != "fifo":
            raise ValidationError("Cost basis method must be 'fifo'")

    def get_average_cost(self) -> float:
        """Calculate average cost per unit."""
        if self.quantity == 0:
            return 0.0
        return self.cost_basis / float(self.quantity)

    @property
    def average_cost(self) -> float:
        """Average cost per unit (computed property)."""
        return self.get_average_cost()


class Portfolio(ABC):
    """Abstract base class for portfolios."""

    def __init__(self, name: str, is_historical: bool = False):
        """Initialize portfolio with a name.

        Args:
            name: Portfolio name
            is_historical: Whether this is a historical portfolio (default: False)
        """
        if not name or not isinstance(name, str):
            raise ValidationError("Portfolio name must be a non-empty string")
        self.name = name
        self.is_historical = is_historical

    @abstractmethod
    def get_positions(
        self, asset_type: Optional[str] = None, tickers: Optional[List[str]] = None
    ) -> dict[Asset, "Position"]:
        """Get all positions in the portfolio.

        Args:
            asset_type: Optional asset type to filter by (e.g., "Stock", "ETF", "Crypto")
            tickers: Optional list of ticker symbols to filter by

        Returns:
            Dictionary mapping Asset to Position objects
        """
        pass

    @abstractmethod
    def get_total_cost_basis(self) -> float:
        """Calculate total cost basis for the portfolio."""
        pass

    @abstractmethod
    def get_all_trades(self) -> list[Trade]:
        """Get all trades in the portfolio (including sub-portfolios)."""
        pass

    @abstractmethod
    def get_assets(self) -> Dict[str, "Asset"]:
        """Get all unique assets in the portfolio (ticker -> Asset mapping).

        Returns a lightweight mapping without triggering any calculations.
        This is updated automatically when trades are added.

        Returns:
            Dictionary mapping ticker to Asset object
        """
        pass

    @abstractmethod
    def get_asset_trades(
        self, ticker: str, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Trade]:
        """Get all trades for a specified asset (ticker) within the portfolio.

        Args:
            ticker: Asset ticker symbol to filter trades by
            start_date: Optional start date for date range filter (inclusive).
                If not specified, includes trades from the very beginning.
            end_date: Optional end date for date range filter (inclusive).
                If not specified, includes trades to the very end.

        Returns:
            List of Trade objects matching the ticker and date range
            (includes both Buy and Sell trades)
        """
        pass

    @abstractmethod
    def get_total_market_value(self, prices: Dict[Asset, Optional[float]]) -> float:
        """Calculate total market value for the portfolio.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Total market value in USD
        """
        pass

    @abstractmethod
    def get_total_unrealized_pnl(self, prices: Dict[Asset, Optional[float]]) -> float:
        """Calculate total unrealized profit/loss for the portfolio.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Total unrealized profit/loss in USD (market_value - cost_basis)
        """
        pass

    @abstractmethod
    def get_asset_lots(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        brokers: Optional[List[str]] = None,
        prices: Optional[Dict[Asset, Optional[float]]] = None,
    ) -> List["Lot"]:
        """Get all lots for a specified asset (ticker) within the portfolio.

        Args:
            ticker: Asset ticker symbol to filter lots by
            start_date: Optional start date for date range filter (inclusive).
                If not specified, includes lots from the very beginning.
            end_date: Optional end date for date range filter (inclusive).
                If not specified, includes lots to the very end.
            brokers: Optional list of broker names to filter by.
                If not specified, includes lots from all brokers.
            prices: Optional dictionary mapping Asset to current price for P/L calculations

        Returns:
            List of Lot objects for the ticker
        """
        pass

    @abstractmethod
    def get_total_realized_pnl(self) -> float:
        """Calculate total realized profit/loss for the portfolio.

        Derives from lots' realized P/L.

        Returns:
            Total realized profit/loss in USD
        """
        pass

    @abstractmethod
    def get_asset_realized_pnl(
        self,
        ticker: str,
        brokers: Optional[List[str]] = None,
    ) -> float:
        """Calculate realized profit/loss for a specific asset position.

        Args:
            ticker: Asset ticker symbol
            brokers: Optional list of broker names to filter by.
                If not specified, includes lots from all brokers.

        Returns:
            Realized profit/loss in USD for the specified asset
        """
        pass

    @abstractmethod
    def clone(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> "Portfolio":
        """Create a deep copy of the portfolio.

        Args:
            start_date: Optional start date for filtering (inclusive).
                Must be within portfolio's date range if provided.
            end_date: Optional end date for filtering (inclusive).
                Must be within portfolio's date range if provided.

        Returns:
            New Portfolio instance with cloned data
        """
        pass

    @abstractmethod
    def get_asset_positions_by_broker(self, ticker: str) -> Dict[str, "Position"]:
        """Get positions grouped by broker for a specified asset (ticker).

        Returns a dictionary mapping broker names to Position objects for the specified ticker.
        This encapsulates broker grouping and position calculation logic.

        Args:
            ticker: Asset ticker symbol to get broker positions for

        Returns:
            Dictionary mapping broker names to Position objects for the ticker.
            Returns empty dictionary if ticker not found or no positions exist.
            Brokers are sorted alphabetically.
        """
        pass

    def get_position(self, asset: Asset) -> Optional["Position"]:
        """Get position for a specific asset."""
        positions = self.get_positions()
        return positions.get(asset)


@dataclass
class PortfolioHistoryPoint:
    """Represents a portfolio state at a specific point in time."""

    date: date
    total_market_value: float
    asset_positions: Dict[str, float]  # Maps ticker to position value (quantity * price)
    prices: Dict[str, float]  # Maps ticker to price on that date
    quantities: Dict[str, float]  # Maps ticker to quantity held on that date
    percentage_return: float  # Percentage return from start_date to this date

    def __post_init__(self):
        """Validate history point fields after initialization."""
        if not isinstance(self.date, date):
            raise ValidationError("Date must be a date object")

        if not isinstance(self.total_market_value, (int, float)) or self.total_market_value < 0:
            raise ValidationError("Total market value must be a non-negative number")

        if not isinstance(self.asset_positions, dict):
            raise ValidationError("Asset positions must be a dictionary")

        if not isinstance(self.prices, dict):
            raise ValidationError("Prices must be a dictionary")

        if not isinstance(self.quantities, dict):
            raise ValidationError("Quantities must be a dictionary")

        if not isinstance(self.percentage_return, (int, float)):
            raise ValidationError("Percentage return must be a number")

        for ticker, position_value in self.asset_positions.items():
            if not isinstance(ticker, str):
                raise ValidationError("Asset positions keys must be strings (tickers)")
            if not isinstance(position_value, (int, float)) or position_value < 0:
                raise ValidationError(
                    f"Asset position value for {ticker} must be a non-negative number"
                )

        for ticker, price in self.prices.items():
            if not isinstance(ticker, str):
                raise ValidationError("Prices keys must be strings (tickers)")
            if not isinstance(price, (int, float)) or price < 0:
                raise ValidationError(
                    f"Price for {ticker} must be a non-negative number"
                )

        for ticker, quantity in self.quantities.items():
            if not isinstance(ticker, str):
                raise ValidationError("Quantities keys must be strings (tickers)")
            if not isinstance(quantity, (int, float)) or quantity < 0:
                raise ValidationError(
                    f"Quantity for {ticker} must be a non-negative number"
                )
