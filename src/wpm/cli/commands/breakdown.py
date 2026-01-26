"""Breakdown command handler."""

import logging
from typing import Dict, List, Optional

from wpm.metrics import (
    breakdown_by_asset_type,
    breakdown_by_broker,
    breakdown_by_purchase_period,
    breakdown_by_ticker,
)
from wpm.models import Portfolio
from wpm.portfolio import CompositePortfolio

from ..formatters import (
    format_breakdown_asset_type,
    format_breakdown_broker,
    format_breakdown_purchase_period,
    format_breakdown_ticker,
)

logger = logging.getLogger(__name__)


def _execute_breakdown(portfolio: Portfolio, breakdown_type: str) -> Optional[Dict]:
    """Execute breakdown calculation based on type.

    Args:
        portfolio: Portfolio to analyze
        breakdown_type: Type of breakdown to perform

    Returns:
        Breakdown data dictionary, or None if invalid type or no data
    """
    if breakdown_type == "asset_type":
        return breakdown_by_asset_type(portfolio)
    if breakdown_type == "ticker":
        return breakdown_by_ticker(portfolio)
    if breakdown_type == "purchase_period":
        return breakdown_by_purchase_period(portfolio, period="month")
    if breakdown_type == "broker":
        return breakdown_by_broker(portfolio)

    print(
        f"Invalid breakdown type '{breakdown_type}'. "
        f"Valid types: asset_type, ticker, purchase_period, broker"
    )
    return None


def _format_breakdown(breakdown: Dict, breakdown_type: str) -> None:
    """Format and display breakdown data.

    Args:
        breakdown: Breakdown data dictionary
        breakdown_type: Type of breakdown
    """
    if breakdown_type == "asset_type":
        format_breakdown_asset_type(breakdown)
    elif breakdown_type == "ticker":
        format_breakdown_ticker(breakdown)
    elif breakdown_type == "purchase_period":
        format_breakdown_purchase_period(breakdown)
    elif breakdown_type == "broker":
        format_breakdown_broker(breakdown)


def cmd_breakdown(composite: CompositePortfolio, args: List[str]) -> None:
    """Handle 'breakdown [<name>] <by>' command.

    Args:
        composite: Composite portfolio
        args: Command arguments (optional portfolio name, required breakdown type)
    """
    if len(args) < 1:
        print("Error: Breakdown type required. Valid types: asset_type, ticker, purchase_period, broker")
        return

    # Determine if first arg is portfolio name or breakdown type
    breakdown_type = args[-1]
    portfolio_name = None

    if len(args) == 2:
        # First arg is portfolio name, second is breakdown type
        portfolio_name = args[0]
        breakdown_type = args[1]

    # Get portfolio to use
    portfolio = composite
    if portfolio_name:
        sub_portfolios = composite.get_sub_portfolios()
        if portfolio_name not in sub_portfolios:
            print(f"Portfolio '{portfolio_name}' not found.")
            return
        portfolio = sub_portfolios[portfolio_name]

    # Route to appropriate breakdown function
    try:
        breakdown = _execute_breakdown(portfolio, breakdown_type)
        if breakdown is None:
            print("No data available for breakdown.")
            return

        _format_breakdown(breakdown, breakdown_type)
    except Exception as e:
        logger.error(f"Error generating breakdown: {e}", exc_info=True)
        print("No data available for breakdown.")
