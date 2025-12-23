"""Cost basis calculation methods (FIFO and Average Cost)."""

import logging
from collections import deque
from decimal import Decimal
from typing import Dict, List

from wpm.models import Asset, Position, Trade

logger = logging.getLogger(__name__)


def calculate_fifo_cost_basis(trades: List[Trade]) -> Dict[Asset, Position]:
    """Calculate positions using FIFO (First In, First Out) method.

    Args:
        trades: List of trades to process

    Returns:
        Dictionary mapping Asset to Position objects
    """
    logger.info(f"Starting FIFO cost basis calculation for {len(trades)} trades")

    # Dictionary to store FIFO queues for each asset (deque of (quantity, price) tuples)
    fifo_queues: Dict[Asset, deque] = {}
    # Dictionary to store current positions
    positions: Dict[Asset, Position] = {}

    for trade in trades:
        asset = trade.asset

        if asset not in fifo_queues:
            fifo_queues[asset] = deque()
            positions[asset] = Position(
                asset=asset,
                quantity=Decimal('0'),
                cost_basis=0.0,
                cost_basis_method="fifo",
            )

        if trade.is_buy():
            logger.debug(f"Processing buy: {trade.quantity} @ ${trade.price}")
            fifo_queues[asset].append((trade.quantity, trade.price))

            current_position = positions[asset]
            positions[asset] = Position(
                asset=asset,
                quantity=current_position.quantity + trade.quantity,
                cost_basis=current_position.cost_basis + trade.total_value,
                cost_basis_method="fifo",
            )
        else:
            logger.debug(f"Processing sell: {trade.quantity} @ ${trade.price}")
            remaining_sell_quantity = trade.quantity

            current_position = positions[asset]
            remaining_cost_basis = current_position.cost_basis

            while remaining_sell_quantity > 0 and fifo_queues[asset]:
                oldest_buy_quantity, oldest_buy_price = fifo_queues[asset][0]

                if oldest_buy_quantity <= remaining_sell_quantity:
                    consumed_quantity = oldest_buy_quantity
                    fifo_queues[asset].popleft()
                else:
                    consumed_quantity = remaining_sell_quantity
                    fifo_queues[asset][0] = (
                        oldest_buy_quantity - consumed_quantity,
                        oldest_buy_price,
                    )

                # Convert Decimal quantity to float for cost basis calculation
                cost_basis_consumed = float(consumed_quantity) * oldest_buy_price
                remaining_cost_basis -= cost_basis_consumed
                remaining_sell_quantity -= consumed_quantity

                logger.debug(
                    f"Matched {consumed_quantity} units from buy @ ${oldest_buy_price}"
                )

            positions[asset] = Position(
                asset=asset,
                quantity=current_position.quantity - trade.quantity,
                cost_basis=remaining_cost_basis,
                cost_basis_method="fifo",
            )

    logger.info(
        f"FIFO calculation completed. Positions calculated for {len(positions)} assets"
    )
    return positions


def calculate_average_cost_basis(trades: List[Trade]) -> Dict[Asset, Position]:
    """Calculate positions using Average Cost method.

    Args:
        trades: List of trades to process

    Returns:
        Dictionary mapping Asset to Position objects
    """
    logger.info(
        f"Starting Average Cost basis calculation for {len(trades)} trades"
    )

    positions: Dict[Asset, Position] = {}

    for trade in trades:
        asset = trade.asset

        if asset not in positions:
            positions[asset] = Position(
                asset=asset,
                quantity=Decimal('0'),
                cost_basis=0.0,
                cost_basis_method="average",
            )

        current_position = positions[asset]

        if trade.is_buy():
            logger.debug(f"Processing buy: {trade.quantity} @ ${trade.price}")
            total_quantity = current_position.quantity + trade.quantity
            total_cost_basis = current_position.cost_basis + trade.total_value

            positions[asset] = Position(
                asset=asset,
                quantity=total_quantity,
                cost_basis=total_cost_basis,
                cost_basis_method="average",
            )
        else:
            logger.debug(f"Processing sell: {trade.quantity} @ ${trade.price}")

            if current_position.quantity == 0:
                logger.warning(
                    f"Sell transaction for {asset.ticker} with no existing position"
                )
                continue

            average_cost = current_position.get_average_cost()
            # Convert Decimal quantity to float for cost basis calculation
            cost_basis_to_remove = float(trade.quantity) * average_cost

            remaining_quantity = current_position.quantity - trade.quantity
            remaining_cost_basis = current_position.cost_basis - cost_basis_to_remove

            positions[asset] = Position(
                asset=asset,
                quantity=remaining_quantity,
                cost_basis=remaining_cost_basis,
                cost_basis_method="average",
            )

    logger.info(
        f"Average Cost calculation completed. Positions calculated for {len(positions)} assets"
    )
    return positions

