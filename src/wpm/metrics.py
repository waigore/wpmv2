"""Portfolio metrics and breakdown generation."""

import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from wpm.models import Asset, Portfolio, Position, Trade

logger = logging.getLogger(__name__)


def calculate_portfolio_metrics(portfolio: Portfolio) -> Dict:
    """Calculate comprehensive portfolio metrics.

    Args:
        portfolio: Portfolio to analyze

    Returns:
        Dictionary containing portfolio metrics
    """
    logger.info(f"Calculating portfolio metrics for '{portfolio.name}'")

    positions = portfolio.get_positions()
    total_cost_basis = portfolio.get_total_cost_basis()

    metrics = {
        "portfolio_name": portfolio.name,
        "cost_basis_method": "fifo",
        "total_cost_basis": total_cost_basis,
        "position_count": len(positions),
        "positions": positions,
    }

    logger.debug(
        f"Metrics calculated: {len(positions)} positions, "
        f"total cost basis: ${total_cost_basis:.2f}"
    )

    logger.info("Portfolio metrics calculation completed")
    return metrics


def breakdown_by_asset_type(portfolio: Portfolio) -> Dict[str, Dict]:
    """Generate breakdown grouped by asset type.

    Args:
        portfolio: Portfolio to analyze

    Returns:
        Dictionary mapping asset type to aggregated metrics
    """
    logger.info(f"Generating breakdown by asset type for '{portfolio.name}'")

    positions = portfolio.get_positions()
    breakdown: Dict[str, Dict] = defaultdict(
        lambda: {"positions": [], "total_quantity": Decimal('0'), "total_cost_basis": 0.0}
    )

    for asset, position in positions.items():
        asset_type = asset.asset_type
        breakdown[asset_type]["positions"].append(position)
        breakdown[asset_type]["total_quantity"] += position.quantity
        breakdown[asset_type]["total_cost_basis"] += position.cost_basis

        logger.debug(
            f"Added {asset.ticker} ({asset_type}): "
            f"quantity={position.quantity}, cost_basis=${position.cost_basis:.2f}"
        )

    result = dict(breakdown)
    logger.info(f"Breakdown by asset type completed: {len(result)} asset types")
    return result


def breakdown_by_ticker(portfolio: Portfolio) -> Dict[str, Position]:
    """Generate breakdown grouped by ticker.

    Args:
        portfolio: Portfolio to analyze

    Returns:
        Dictionary mapping ticker to Position object
    """
    logger.info(f"Generating breakdown by ticker for '{portfolio.name}'")

    positions = portfolio.get_positions()
    breakdown: Dict[str, Position] = {}

    for asset, position in positions.items():
        breakdown[asset.ticker] = position
        logger.debug(
            f"Added {asset.ticker}: quantity={position.quantity}, "
            f"cost_basis=${position.cost_basis:.2f}"
        )

    logger.info(f"Breakdown by ticker completed: {len(breakdown)} tickers")
    return breakdown


def breakdown_by_purchase_period(
    portfolio: Portfolio, period: str = "month"
) -> Dict[str, Dict]:
    """Generate breakdown grouped by purchase period.

    Args:
        portfolio: Portfolio to analyze
        period: Time period grouping ("month", "quarter", or "year")

    Returns:
        Dictionary mapping period string to aggregated metrics
    """
    logger.info(
        f"Generating breakdown by purchase period ({period}) for '{portfolio.name}'"
    )

    if period not in ("month", "quarter", "year"):
        raise ValueError(f"Period must be 'month', 'quarter', or 'year', got '{period}'")

    trades = portfolio.get_all_trades()
    buy_trades = [t for t in trades if t.is_buy()]

    breakdown: Dict[str, Dict] = defaultdict(
        lambda: {"trades": [], "total_quantity": Decimal('0'), "total_cost_basis": 0.0}
    )

    for trade in buy_trades:
        trade_date = trade.date

        if period == "month":
            period_key = trade_date.strftime("%Y-%m")
        elif period == "quarter":
            quarter = (trade_date.month - 1) // 3 + 1
            period_key = f"{trade_date.year}-Q{quarter}"
        else:
            period_key = str(trade_date.year)

        breakdown[period_key]["trades"].append(trade)
        breakdown[period_key]["total_quantity"] += trade.quantity
        breakdown[period_key]["total_cost_basis"] += trade.total_value

        logger.debug(
            f"Added trade to period {period_key}: {trade.asset.ticker} "
            f"{trade.quantity} @ ${trade.price}"
        )

    result = dict(breakdown)
    logger.info(f"Breakdown by purchase period completed: {len(result)} periods")
    return result


def breakdown_by_broker(portfolio: Portfolio) -> Dict[str, Dict]:
    """Generate breakdown grouped by broker.

    Args:
        portfolio: Portfolio to analyze

    Returns:
        Dictionary mapping broker name to aggregated metrics
    """
    logger.info(f"Generating breakdown by broker for '{portfolio.name}'")

    trades = portfolio.get_all_trades()
    breakdown: Dict[str, Dict] = defaultdict(
        lambda: {
            "trades": [],
            "total_quantity": defaultdict(lambda: Decimal('0')),
            "total_cost_basis": 0.0,
        }
    )

    for trade in trades:
        broker = trade.broker
        breakdown[broker]["trades"].append(trade)
        breakdown[broker]["total_quantity"][trade.asset.ticker] += trade.quantity
        breakdown[broker]["total_cost_basis"] += trade.total_value

        logger.debug(
            f"Added trade to broker {broker}: {trade.asset.ticker} "
            f"{trade.action} {trade.quantity} @ ${trade.price}"
        )

    result = {broker: dict(metrics) for broker, metrics in breakdown.items()}
    logger.info(f"Breakdown by broker completed: {len(result)} brokers")
    return result


def calculate_market_value(
    portfolio: Portfolio, prices: Dict[Asset, float]
) -> float:
    """Calculate current market value of portfolio.

    Args:
        portfolio: Portfolio to analyze
        prices: Dictionary mapping Asset to current price

    Returns:
        Total market value in USD
    """
    logger.info(f"Calculating market value for '{portfolio.name}'")

    positions = portfolio.get_positions()
    total_market_value = 0.0

    for asset, position in positions.items():
        if asset not in prices:
            logger.warning(f"No price available for {asset.ticker}, skipping")
            continue

        price = prices[asset]
        # Convert Decimal quantity to float for market value calculation
        market_value = float(position.quantity) * price
        total_market_value += market_value

        logger.debug(
            f"{asset.ticker}: {position.quantity} * ${price:.2f} = ${market_value:.2f}"
        )

    logger.info(f"Market value calculation completed: ${total_market_value:.2f}")
    return total_market_value

