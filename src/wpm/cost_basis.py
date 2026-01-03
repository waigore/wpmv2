"""Cost basis calculation methods (FIFO)."""

import logging
from collections import deque
from decimal import Decimal
from typing import Dict, List

from wpm.cache_utils import LRUCache, trades_to_cache_key
from wpm.models import Asset, Lot, Position, Trade, ValidationError

logger = logging.getLogger(__name__)

# LRU cache for lot calculations (since we need Trade objects which aren't hashable)
_lots_cache: LRUCache[Dict[Asset, List[Lot]]] = LRUCache(maxsize=128)


def _calculate_lots_from_trades_impl(trades: List[Trade]) -> Dict[Asset, List[Lot]]:
    """Calculate lots from trades using FIFO method (internal implementation).

    Args:
        trades: List of trades to process

    Returns:
        Dictionary mapping Asset to list of Lot objects
    """
    logger.debug(f"Calculating lots from {len(trades)} trades")

    # Dictionary to store lots for each asset
    lots_by_asset: Dict[Asset, List[Lot]] = {}
    # Dictionary to store FIFO queues for each asset (deque of Lot objects)
    fifo_lots: Dict[Asset, deque] = {}

    # Sort trades chronologically
    sorted_trades = sorted(trades, key=lambda t: t.date)

    for trade in sorted_trades:
        asset = trade.asset

        if asset not in fifo_lots:
            fifo_lots[asset] = deque()
            lots_by_asset[asset] = []

        if trade.is_buy():
            logger.debug(f"Processing buy: {trade.quantity} @ ${trade.price}")
            # Create a new lot from the buy trade
            lot = Lot(
                purchase_date=trade.date,
                purchase_price=trade.price,
                original_quantity=trade.quantity,
                remaining_quantity=trade.quantity,
                cost_basis=float(trade.quantity) * trade.price,
                asset=asset,
                matched_sells=[],
            )
            fifo_lots[asset].append(lot)
            lots_by_asset[asset].append(lot)
        else:
            logger.debug(f"Processing sell: {trade.quantity} @ ${trade.price}")
            remaining_sell_quantity = trade.quantity

            # Calculate total available quantity
            total_available = sum(lot.remaining_quantity for lot in fifo_lots[asset])

            # Check if we're trying to sell more than available
            if remaining_sell_quantity > total_available:
                raise ValidationError(
                    f"Cannot sell {remaining_sell_quantity} units when only {total_available} are available"
                )

            # Match sell against lots using FIFO
            while remaining_sell_quantity > 0 and fifo_lots[asset]:
                oldest_lot = fifo_lots[asset][0]

                if oldest_lot.remaining_quantity <= remaining_sell_quantity:
                    # Entire lot is consumed
                    consumed_quantity = oldest_lot.remaining_quantity
                    oldest_lot.remaining_quantity = Decimal('0')
                    oldest_lot.matched_sells.append((trade, consumed_quantity))
                    fifo_lots[asset].popleft()
                else:
                    # Partial lot consumption
                    consumed_quantity = remaining_sell_quantity
                    oldest_lot.remaining_quantity -= consumed_quantity
                    oldest_lot.matched_sells.append((trade, consumed_quantity))

                remaining_sell_quantity -= consumed_quantity

                logger.debug(
                    f"Matched {consumed_quantity} units from lot @ ${oldest_lot.purchase_price}"
                )

    logger.debug(
        f"Lot calculation completed. Lots calculated for {len(lots_by_asset)} assets"
    )
    return lots_by_asset


def calculate_lots_from_trades(trades: List[Trade]) -> Dict[Asset, List[Lot]]:
    """Calculate lots from trades using FIFO method.

    Uses LRU caching to avoid recalculating lots for the same set of trades.

    Args:
        trades: List of trades to process

    Returns:
        Dictionary mapping Asset to list of Lot objects
    """
    if not trades:
        return {}

    # Convert trades to cache key
    trades_key = trades_to_cache_key(trades)

    # Check cache
    cached_lots = _lots_cache.get(trades_key)
    if cached_lots is not None:
        logger.debug("Cache hit for lot calculation")
        # Note: Lot objects contain Trade references, so we need to be careful
        # For now, we'll return the cached result directly since lots are
        # typically not mutated after creation
        return cached_lots

    # Cache miss - calculate lots
    logger.debug("Cache miss for lot calculation")
    lots = _calculate_lots_from_trades_impl(trades)

    # Store in cache (LRU eviction handled automatically)
    _lots_cache.set(trades_key, lots)

    return lots


def calculate_fifo_cost_basis(trades: List[Trade]) -> Dict[Asset, Position]:
    """Calculate positions using FIFO (First In, First Out) method.

    Now derives positions from lots internally for consistency.

    Args:
        trades: List of trades to process

    Returns:
        Dictionary mapping Asset to Position objects
    """
    logger.info(f"Starting FIFO cost basis calculation for {len(trades)} trades")

    # Calculate lots from trades (benefits from caching)
    lots_by_asset = calculate_lots_from_trades(trades)

    # Aggregate lots into positions
    positions: Dict[Asset, Position] = {}

    for asset, lots in lots_by_asset.items():
        total_quantity = Decimal('0')
        total_cost_basis = 0.0

        for lot in lots:
            # Only count remaining quantity in cost basis
            total_quantity += lot.remaining_quantity
            total_cost_basis += float(lot.remaining_quantity) * lot.purchase_price

        positions[asset] = Position(
            asset=asset,
            quantity=total_quantity,
            cost_basis=total_cost_basis,
            cost_basis_method="fifo",
        )

    logger.info(
        f"FIFO calculation completed. Positions calculated for {len(positions)} assets"
    )
    return positions

