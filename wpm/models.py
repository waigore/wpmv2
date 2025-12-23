"""Core data models for the WPM library."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

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
    order_type: Optional[str] = None
    price: float = field(default=0.0)
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

        if self.order_type is not None:
            if not isinstance(self.order_type, str) or not self.order_type.strip():
                raise ValidationError("Order type must be a non-empty string if provided")

        if not isinstance(self.price, (int, float)) or self.price <= 0:
            raise ValidationError("Price must be a positive number greater than 0")

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

        if self.cost_basis_method not in ("fifo", "average"):
            raise ValidationError("Cost basis method must be 'fifo' or 'average'")

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

    def __init__(self, name: str):
        """Initialize portfolio with a name."""
        if not name or not isinstance(name, str):
            raise ValidationError("Portfolio name must be a non-empty string")
        self.name = name

    @abstractmethod
    def get_positions(self) -> dict[Asset, "Position"]:
        """Get all positions in the portfolio."""
        pass

    @abstractmethod
    def get_total_cost_basis(self) -> float:
        """Calculate total cost basis for the portfolio."""
        pass

    @abstractmethod
    def get_all_trades(self) -> list[Trade]:
        """Get all trades in the portfolio (including sub-portfolios)."""
        pass

    def get_position(self, asset: Asset) -> Optional["Position"]:
        """Get position for a specific asset."""
        positions = self.get_positions()
        return positions.get(asset)

