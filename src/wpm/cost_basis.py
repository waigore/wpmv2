"""Cost basis calculation methods (FIFO)."""

import logging
from collections import deque
from decimal import Decimal
from typing import Dict, List, Tuple

from wpm.cache_utils import LRUCache, trades_to_cache_key
from wpm.models import Asset, Lot, Position, Trade, ValidationError

logger = logging.getLogger(__name__)

# LRU cache for lot calculations (since we need Trade objects which aren't hashable)
_lots_cache: LRUCache[Dict[Asset, List[Lot]]] = LRUCache(maxsize=128)


def _calculate_lots_from_trades_impl(trades: List[Trade]) -> Dict[Asset, List[Lot]]:
    """Calculate lots from trades using FIFO method (internal implementation).

    Sell trades must match against buy lots from the same broker. If a sell trade
    cannot find a matching buy lot from the same broker, a ValidationError is raised.

    Args:
        trades: List of trades to process

    Returns:
        Dictionary mapping Asset to list of Lot objects
    """
    logger.debug(f"Calculating lots from {len(trades)} trades")

    # Dictionary to store lots for each asset
    lots_by_asset: Dict[Asset, List[Lot]] = {}
    # Dictionary to store FIFO queues for each asset-broker combination (deque of Lot objects)
    # Key is (Asset, broker) tuple to enforce broker matching
    fifo_lots: Dict[Tuple[Asset, str], deque] = {}

    # Sort trades chronologically
    sorted_trades = sorted(trades, key=lambda t: t.date)

    for trade in sorted_trades:
        asset = trade.asset

        if trade.is_buy():
            logger.debug(
                f"Processing buy: {trade.adjusted_quantity} @ ${trade.adjusted_price:.2f} "
                f"(original: {trade.quantity} @ ${trade.price:.2f}, factor: {trade.split_adjustment_factor}) "
                f"from broker {trade.broker}"
            )
            # Create a new lot from the buy trade using adjusted values
            lot = Lot(
                purchase_date=trade.date,
                purchase_price=trade.adjusted_price,
                original_quantity=trade.adjusted_quantity,
                remaining_quantity=trade.adjusted_quantity,
                cost_basis=float(trade.adjusted_quantity) * trade.adjusted_price,
                asset=asset,
                broker=trade.broker,
                matched_sells=[],
            )
            # Use (asset, broker) as key to maintain separate FIFO queues per broker
            lot_key = (asset, trade.broker)
            if lot_key not in fifo_lots:
                fifo_lots[lot_key] = deque()
            if asset not in lots_by_asset:
                lots_by_asset[asset] = []
            
            fifo_lots[lot_key].append(lot)
            lots_by_asset[asset].append(lot)
        else:
            logger.debug(
                f"Processing sell: {trade.adjusted_quantity} @ ${trade.adjusted_price:.2f} "
                f"(original: {trade.quantity} @ ${trade.price:.2f}, factor: {trade.split_adjustment_factor}) "
                f"from broker {trade.broker}"
            )
            remaining_sell_quantity = trade.adjusted_quantity

            # Match sell only against lots from the same broker
            lot_key = (asset, trade.broker)
            
            # Check if there are any lots available for this broker
            if lot_key not in fifo_lots or not fifo_lots[lot_key]:
                raise ValidationError(
                    f"Cannot sell {remaining_sell_quantity} units from broker '{trade.broker}' when no matching buy lots exist for that broker"
                )

            # Calculate total available quantity only from lots matching the sell's broker
            total_available = sum(lot.remaining_quantity for lot in fifo_lots[lot_key])

            # Check if we're trying to sell more than available
            if remaining_sell_quantity > total_available:
                raise ValidationError(
                    f"Cannot sell {remaining_sell_quantity} units from broker '{trade.broker}' when only {total_available} are available for that broker"
                )

            # Match sell against lots using FIFO (only from the same broker)
            while remaining_sell_quantity > 0 and fifo_lots[lot_key]:
                oldest_lot = fifo_lots[lot_key][0]

                if oldest_lot.remaining_quantity <= remaining_sell_quantity:
                    # Entire lot is consumed
                    consumed_quantity = oldest_lot.remaining_quantity
                    oldest_lot.remaining_quantity = Decimal('0')
                    oldest_lot.matched_sells.append((trade, consumed_quantity))
                    fifo_lots[lot_key].popleft()
                else:
                    # Partial lot consumption
                    consumed_quantity = remaining_sell_quantity
                    oldest_lot.remaining_quantity -= consumed_quantity
                    oldest_lot.matched_sells.append((trade, consumed_quantity))

                remaining_sell_quantity -= consumed_quantity

                logger.debug(
                    f"Matched {consumed_quantity} units from lot @ ${oldest_lot.purchase_price} (broker: {oldest_lot.broker})"
                )

    logger.debug(
        f"Lot calculation completed. Lots calculated for {len(lots_by_asset)} assets"
    )
    return lots_by_asset


def calculate_lots_from_trades(trades: List[Trade]) -> Dict[Asset, List[Lot]]:
    """Calculate lots from trades using FIFO method.

    Uses LRU caching to avoid recalculating lots for the same set of trades.

    Sell trades must match against buy lots from the same broker. If a sell trade
    cannot find a matching buy lot from the same broker, a ValidationError is raised.

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

