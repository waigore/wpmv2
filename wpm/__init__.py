"""WPM (Wealth Portfolio Manager) Library."""

from wpm.cost_basis import (
    calculate_average_cost_basis,
    calculate_fifo_cost_basis,
)
from wpm.importer import import_trades_from_csv
from wpm.metrics import (
    breakdown_by_asset_type,
    breakdown_by_broker,
    breakdown_by_purchase_period,
    breakdown_by_ticker,
    calculate_market_value,
    calculate_portfolio_metrics,
)
from wpm.models import Asset, Portfolio, Position, Trade
from wpm.portfolio import CompositePortfolio, SimplePortfolio
from wpm.pricing import PriceRetriever, PriceService
from wpm.utils import setup_logging

__all__ = [
    # Core models
    "Asset",
    "Trade",
    "Position",
    "Portfolio",
    # Portfolio classes
    "SimplePortfolio",
    "CompositePortfolio",
    # Import
    "import_trades_from_csv",
    # Cost basis
    "calculate_fifo_cost_basis",
    "calculate_average_cost_basis",
    # Pricing
    "PriceService",
    "PriceRetriever",
    # Metrics
    "calculate_portfolio_metrics",
    "breakdown_by_asset_type",
    "breakdown_by_ticker",
    "breakdown_by_purchase_period",
    "breakdown_by_broker",
    "calculate_market_value",
    # Utils
    "setup_logging",
]
