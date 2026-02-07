"""Portfolio metrics and breakdown generation."""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from wpm.cost_basis import calculate_lots_from_trades
from wpm.models import Asset, Portfolio, PortfolioHistoryPoint, Position, Trade
from wpm.portfolio import _calculate_percentage_return_from_lots

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
        breakdown[period_key]["total_quantity"] += trade.adjusted_quantity
        breakdown[period_key]["total_cost_basis"] += trade.total_value

        logger.debug(
            f"Added trade to period {period_key}: {trade.asset.ticker} "
            f"{trade.adjusted_quantity} @ ${trade.adjusted_price:.2f} "
            f"(original: {trade.quantity} @ ${trade.price:.2f}, factor: {trade.split_adjustment_factor})"
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
        breakdown[broker]["total_quantity"][trade.asset.ticker] += trade.adjusted_quantity
        breakdown[broker]["total_cost_basis"] += trade.total_value

        logger.debug(
            f"Added trade to broker {broker}: {trade.asset.ticker} "
            f"{trade.action} {trade.adjusted_quantity} @ ${trade.adjusted_price:.2f} "
            f"(original: {trade.quantity} @ ${trade.price:.2f}, factor: {trade.split_adjustment_factor})"
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


def calculate_unrealized_pnl_percentage(
    portfolio: Portfolio,
    price_map: Dict[Asset, Optional[float]],
    target_date: Optional[date] = None,
) -> Optional[float]:
    """Calculate unrealized P/L percentage return.
    
    Formula: (unrealized_pnl / cost_basis_of_remaining_lots) * 100
    
    Uses _calculate_percentage_return_from_lots which calculates percentage return
    from lots (unrealized P/L / cost basis).
    
    Args:
        portfolio: Portfolio to calculate percentage for
        price_map: Dictionary mapping Asset to current/historical price (None if unavailable)
        target_date: Optional date to filter trades up to (for historical calculations)
    
    Returns:
        Percentage return as float, or None if cost basis is 0 or prices unavailable
    """
    # Get all trades from portfolio
    all_trades = portfolio.get_all_trades()
    
    # Filter trades up to target_date if provided
    if target_date is not None:
        filtered_trades = [t for t in all_trades if t.date <= target_date]
    else:
        filtered_trades = all_trades
    
    if not filtered_trades:
        return None
    
    # Convert price_map (Dict[Asset, Optional[float]]) to prices_by_ticker (Dict[str, float])
    # Only include assets that have valid prices
    prices_by_ticker: Dict[str, float] = {}
    for asset, price in price_map.items():
        if price is not None:
            prices_by_ticker[asset.ticker] = price
    
    if not prices_by_ticker:
        return None
    
    # Use existing function to calculate percentage return
    try:
        percentage = _calculate_percentage_return_from_lots(
            filtered_trades, prices_by_ticker, ticker_filter=None
        )
        return percentage
    except (ValueError, ZeroDivisionError):
        return None


def calculate_realized_pnl_percentage(
    portfolio: Portfolio,
    target_date: Optional[date] = None,
) -> Optional[float]:
    """Calculate realized P/L percentage return.
    
    Formula: (realized_pnl / cost_basis_of_sold_lots) * 100
    
    Args:
        portfolio: Portfolio to calculate percentage for
        target_date: Optional date to filter trades up to (for historical calculations)
    
    Returns:
        Percentage return as float, or None if cost basis of sold lots is 0
    """
    # Get all trades from portfolio
    all_trades = portfolio.get_all_trades()
    
    # Filter trades up to target_date if provided
    if target_date is not None:
        filtered_trades = [t for t in all_trades if t.date <= target_date]
    else:
        filtered_trades = all_trades
    
    if not filtered_trades:
        return None
    
    # Calculate lots from filtered trades
    lots_by_asset = calculate_lots_from_trades(filtered_trades)
    
    # Calculate cost basis of sold lots and realized P/L
    # Since we filtered trades by target_date, the lots already only contain matched_sells up to target_date
    total_cost_basis_of_sold_lots = 0.0
    total_realized_pnl = 0.0
    
    for asset, lots in lots_by_asset.items():
        for lot in lots:
            # Calculate cost basis of sold lots: sum(purchase_price * quantity_sold) for all matched_sells
            # matched_sells are already filtered by target_date since we filtered trades before calculating lots
            for sell_trade, quantity_sold in lot.matched_sells:
                cost_basis_sold = float(quantity_sold) * lot.purchase_price
                total_cost_basis_of_sold_lots += cost_basis_sold
            
            # Get realized P/L from this lot
            # Since lots are calculated from filtered trades, get_realized_pnl() already returns filtered P/L
            realized_pnl = lot.get_realized_pnl()
            total_realized_pnl += realized_pnl
    
    # Calculate percentage return: (realized_pnl / cost_basis_of_sold_lots) * 100
    if total_cost_basis_of_sold_lots == 0:
        return None
    
    return (total_realized_pnl / total_cost_basis_of_sold_lots) * 100


def format_weekly_performance_summary(history_points: List[PortfolioHistoryPoint]) -> None:
    """Display weekly performance summary from history points.

    Groups history points by calendar week (Monday-Sunday) and displays
    weekly totals (date range and total_market_value).

    Args:
        history_points: List of PortfolioHistoryPoint objects to summarize
    """
    if not history_points:
        print("No history points to display.")
        return

    # Group history points by calendar week
    # Week starts on Monday (weekday 0) and ends on Sunday (weekday 6)
    weekly_groups: Dict[date, List[PortfolioHistoryPoint]] = defaultdict(list)

    for point in history_points:
        # Calculate the Monday of the week for this date
        # weekday() returns 0 for Monday, 6 for Sunday
        days_since_monday = point.date.weekday()
        week_start = point.date - timedelta(days=days_since_monday)
        weekly_groups[week_start].append(point)

    # Sort weeks by start date
    sorted_weeks = sorted(weekly_groups.items())

    print("Weekly Performance Summary:")
    print()  # Blank line

    # Helper function to format currency (avoid circular import)
    def _format_currency(value: float) -> str:
        return f"${value:,.2f}"

    for week_start, week_points in sorted_weeks:
        # Get week end (Sunday)
        week_end = week_start + timedelta(days=6)

        # Sort points within week by date
        week_points.sort(key=lambda p: p.date)

        # Display week range and total market value with percentage return
        # Use the last day's value for the week (or average if preferred)
        # For simplicity, use the last day's value in the week
        last_point = week_points[-1]
        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")

        # Format percentage return with 2 decimal places and + sign for positive returns
        percentage_str = f"{last_point.percentage_return:+.2f}%"
        print(
            f"Week of {week_start_str} to {week_end_str}: "
            f"{_format_currency(last_point.total_market_value)} ({percentage_str})"
        )

