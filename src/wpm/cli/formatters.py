"""Formatting functions for CLI output."""

from datetime import date
from decimal import Decimal
from typing import Dict, Optional

from wpm.models import Lot, Position, PortfolioHistoryPoint


def format_currency(value: float) -> str:
    """Format currency value with $ prefix and 2 decimal places.

    Args:
        value: Currency value to format

    Returns:
        Formatted string (e.g., "$1,234.56")
    """
    return f"${value:,.2f}"


def format_unrealized_pnl(value: float) -> str:
    """Format unrealized P/L with + prefix for profit, - for loss.

    Args:
        value: Unrealized P/L value to format

    Returns:
        Formatted string with sign prefix (e.g., "+$1,234.56" or "-$1,234.56")
    """
    if value >= 0:
        return f"+{format_currency(value)}"
    else:
        # value is negative, format_currency will handle the - sign
        return format_currency(value)


def format_quantity(value) -> str:
    """Format quantity value appropriately.

    Handles Decimal and float values, rounding to 8 decimal places
    (standard for crypto precision) and removes trailing zeros.

    Args:
        value: Quantity value to format (Decimal or float)

    Returns:
        Formatted string (integer if whole number, decimal otherwise)
    """
    # Convert Decimal to float for formatting
    if isinstance(value, Decimal):
        float_value = float(value)
    else:
        float_value = float(value)
    
    # Round to 8 decimal places to handle floating point precision issues
    rounded = round(float_value, 8)
    
    # If it's effectively a whole number after rounding, return as integer
    if abs(rounded - round(rounded)) < 1e-10:
        return str(int(round(rounded)))
    
    # Format with up to 8 decimal places and strip trailing zeros
    formatted = f"{rounded:.8f}".rstrip('0').rstrip('.')
    return formatted


def format_position_line(
    position: Position,
    price: Optional[float],
    is_historical: bool = False,
    end_date: Optional[date] = None,
    allocation: Optional[Decimal] = None,
) -> str:
    """Format a position line for display.

    Args:
        position: Position to format
        price: Current or historical price (None if unavailable)
        is_historical: Whether this is a historical portfolio
        end_date: End date for historical portfolios (used in label)
        allocation: Optional allocation percentage (Decimal, None if unavailable)

    Returns:
        Formatted position line
    """
    asset = position.asset
    ticker = asset.ticker
    asset_type = asset.asset_type
    quantity = format_quantity(position.quantity)
    avg_cost = format_currency(position.get_average_cost())
    cost_basis = format_currency(position.cost_basis)

    # Determine value label
    if is_historical and end_date is not None:
        value_label = f"Historical Value ({end_date.strftime('%Y-%m-%d')})"
    else:
        value_label = "Current Value"

    # Format allocation if available
    allocation_str = ""
    if allocation is not None and price is not None:
        allocation_str = f" | Allocation: {allocation:.2f}%"

    if price is not None:
        # Convert Decimal quantity to float for market value calculation
        market_value = float(position.quantity) * price
        market_value_str = format_currency(market_value)
        price_str = format_currency(price)
        return (
            f"{ticker} ({asset_type}): {quantity} @ {avg_cost} = {cost_basis} | "
            f"{value_label} = {market_value_str} @ {price_str}{allocation_str}"
        )

    return (
        f"{ticker} ({asset_type}): {quantity} @ {avg_cost} = {cost_basis} | "
        f"{value_label} = N/A"
    )


def format_historical_asset_line(
    history_point: PortfolioHistoryPoint,
    ticker: str,
    asset_type: str,
    allocation: Optional[Decimal] = None,
    percentage_return: Optional[float] = None,
) -> str:
    """Format a simplified line for historical asset positions.

    Args:
        history_point: History point containing position and price data
        ticker: Asset ticker symbol
        asset_type: Asset type (e.g., "Stock", "ETF", "Crypto")
        allocation: Optional allocation percentage (Decimal, None if unavailable)
        percentage_return: Optional percentage return for this asset (float, None if unavailable)

    Returns:
        Formatted string: YYYY-MM-DD: Ticker (Asset Type): Quantity = Position Value @ Price | Allocation: XX.XX% | Return: XX.XX%
    """
    date_str = history_point.date.strftime("%Y-%m-%d")
    position_value = history_point.asset_positions.get(ticker, 0.0)
    position_value_str = format_currency(position_value)
    price = history_point.prices.get(ticker)
    quantity = history_point.quantities.get(ticker)

    # Format quantity
    if quantity is not None:
        quantity_str = format_quantity(Decimal(str(quantity)))
    else:
        quantity_str = "N/A"

    # Format allocation if available
    allocation_str = ""
    if allocation is not None:
        allocation_str = f" | Allocation: {allocation:.2f}%"

    # Format percentage return if available
    return_str = ""
    if percentage_return is not None:
        return_str = f" | Return: {percentage_return:.2f}%"

    if price is not None:
        price_str = format_currency(price)
        return f"{date_str}: {ticker} ({asset_type}): {quantity_str} = {position_value_str} @ {price_str}{allocation_str}{return_str}"

    return f"{date_str}: {ticker} ({asset_type}): {quantity_str} = {position_value_str} @ N/A{allocation_str}{return_str}"


def _format_broker_breakdown(broker_positions: Dict[str, Position]) -> None:
    """Format broker breakdown section for display.

    Args:
        broker_positions: Dictionary mapping broker names to Position objects
    """
    if not broker_positions:
        return

    print()  # Blank line before breakdown
    print("Broker Breakdown:")

    for broker, position in broker_positions.items():
        quantity = format_quantity(position.quantity)
        avg_cost = format_currency(position.get_average_cost())
        cost_basis = format_currency(position.cost_basis)
        print(f"{broker}: {quantity} @ {avg_cost} = {cost_basis}")


def format_lot_line(lot: Lot, current_price: Optional[float]) -> str:
    """Format a lot line with matched sells for display.

    Args:
        lot: Lot to format
        current_price: Current price (None if unavailable)

    Returns:
        Multi-line formatted string (lot summary + matched sells if any)
    """
    # Format purchase date
    purchase_date_str = lot.purchase_date.strftime("%Y-%m-%d")
    
    # Format quantities and prices
    original_qty = format_quantity(lot.original_quantity)
    remaining_qty = format_quantity(lot.remaining_quantity)
    purchase_price_str = format_currency(lot.purchase_price)
    remaining_cost_basis = float(lot.remaining_quantity) * lot.purchase_price
    remaining_cost_basis_str = format_currency(remaining_cost_basis)
    
    # Calculate P/L
    realized_pnl = lot.get_realized_pnl()
    realized_pnl_str = format_unrealized_pnl(realized_pnl) if realized_pnl != 0.0 else format_currency(0.0)
    
    if current_price is not None:
        unrealized_pnl = lot.get_unrealized_pnl(current_price)
        total_pnl = lot.get_total_pnl(current_price)
        unrealized_pnl_str = format_unrealized_pnl(unrealized_pnl)
        total_pnl_str = format_unrealized_pnl(total_pnl)
    else:
        unrealized_pnl_str = "N/A"
        total_pnl_str = "N/A"
    
    # Build main lot line
    lot_line = (
        f"{purchase_date_str}: {original_qty} @ {purchase_price_str} | "
        f"Remaining: {remaining_qty} @ {purchase_price_str} = {remaining_cost_basis_str} | "
        f"Realized: {realized_pnl_str} | "
        f"Unrealized: {unrealized_pnl_str} | "
        f"Total: {total_pnl_str}"
    )
    
    # Add matched sells if any
    lines = [lot_line]
    if lot.matched_sells:
        # Sort matched sells by date (oldest first)
        sorted_sells = sorted(lot.matched_sells, key=lambda x: x[0].date)
        for sell_trade, quantity_sold in sorted_sells:
            sell_date_str = sell_trade.date.strftime("%Y-%m-%d")
            qty_sold_str = format_quantity(quantity_sold)
            sell_price_str = format_currency(sell_trade.price)
            lines.append(f"  Sold: {sell_date_str}, {qty_sold_str} @ {sell_price_str}")
    
    return "\n".join(lines)


def format_market_cap(value: Optional[float]) -> str:
    """Format market cap value for display.

    Args:
        value: Market cap value (can be None)

    Returns:
        Formatted string (e.g., "$1.23B", "$1,234.56M", or "N/A")
    """
    if value is None:
        return "N/A"
    
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    else:
        return f"${value:,.2f}"


def format_breakdown_asset_type(breakdown: Dict[str, Dict]) -> None:
    """Format breakdown by asset type for display.

    Args:
        breakdown: Breakdown dictionary from breakdown_by_asset_type
    """
    for asset_type, data in sorted(breakdown.items()):
        quantity = format_quantity(data["total_quantity"])
        cost_basis = format_currency(data["total_cost_basis"])
        print(f"{asset_type}: {quantity} @ {cost_basis}")


def format_breakdown_ticker(breakdown: Dict[str, Position]) -> None:
    """Format breakdown by ticker for display.

    Args:
        breakdown: Breakdown dictionary from breakdown_by_ticker
    """
    for ticker, position in sorted(breakdown.items()):
        quantity = format_quantity(position.quantity)
        cost_basis = format_currency(position.cost_basis)
        print(f"{ticker}: {quantity} @ {cost_basis}")


def format_breakdown_purchase_period(breakdown: Dict[str, Dict]) -> None:
    """Format breakdown by purchase period for display.

    Args:
        breakdown: Breakdown dictionary from breakdown_by_purchase_period
    """
    for period, data in sorted(breakdown.items()):
        quantity = format_quantity(data["total_quantity"])
        cost_basis = format_currency(data["total_cost_basis"])
        print(f"{period}: {quantity} @ {cost_basis}")


def format_breakdown_broker(breakdown: Dict[str, Dict]) -> None:
    """Format breakdown by broker for display.

    Args:
        breakdown: Breakdown dictionary from breakdown_by_broker
    """
    for broker, data in sorted(breakdown.items()):
        broker_output = f"{broker}:"
        asset_details = []

        # Format per-asset quantities
        total_quantity = data["total_quantity"]
        if isinstance(total_quantity, dict):
            for ticker, qty in sorted(total_quantity.items()):
                qty_str = format_quantity(qty)
                asset_details.append(f"{ticker}: {qty_str}")

        cost_basis = format_currency(data["total_cost_basis"])

        if asset_details:
            print(f"{broker_output} {', '.join(asset_details)}, Total: {cost_basis}")
        else:
            print(f"{broker_output} Total: {cost_basis}")
