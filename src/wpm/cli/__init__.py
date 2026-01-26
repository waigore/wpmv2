"""CLI module for WPM (Wealth Portfolio Manager).

This package provides the command-line interface for WPM.
"""

# Backward compatibility: Export main() for entry point
from .main import main

# Backward compatibility: Export all tested functions
from .args import parse_brokers, parse_from_date, parse_up_to_date
from .commands import asset, breakdown, portfolio
from .formatters import (
    format_historical_asset_line,
    format_market_cap,
    format_position_line,
)

# Export command handlers for backward compatibility
cmd_show_all = portfolio.cmd_show_all
cmd_show_portfolio = portfolio.cmd_show_portfolio
cmd_show_asset = asset.cmd_show_asset
cmd_metadata = asset.cmd_metadata

# Export calculation functions from metrics (moved from CLI)
from wpm.metrics import (
    calculate_realized_pnl_percentage,
    calculate_unrealized_pnl_percentage,
    format_weekly_performance_summary,
)

# Export _display_weekly_summary as alias for format_weekly_performance_summary
# (for backward compatibility with tests)
_display_weekly_summary = format_weekly_performance_summary

# Export _display_totals_section for backward compatibility
_display_totals_section = portfolio._display_totals_section

# Export portfolio functions for backward compatibility (used in tests for patching)
from wpm.portfolio import (
    fetch_price_map,
    get_historical_allocations,
    get_historical_performance,
)

__all__ = [
    # Entry point
    "main",
    # Argument parsing
    "parse_up_to_date",
    "parse_from_date",
    "parse_brokers",
    # Command handlers
    "cmd_show_all",
    "cmd_show_portfolio",
    "cmd_show_asset",
    "cmd_metadata",
    # Formatters
    "format_historical_asset_line",
    "format_position_line",
    "format_market_cap",
    # Metrics (moved from CLI)
    "calculate_unrealized_pnl_percentage",
    "calculate_realized_pnl_percentage",
    "format_weekly_performance_summary",
    "_display_weekly_summary",  # Alias for backward compatibility
    "_display_totals_section",
    # Portfolio functions exported for backward compatibility (used in tests)
    "fetch_price_map",
    "get_historical_performance",
    "get_historical_allocations",
]
