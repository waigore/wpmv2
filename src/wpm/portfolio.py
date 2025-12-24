"""Portfolio class implementation with aggregation logic."""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from wpm.cost_basis import calculate_average_cost_basis, calculate_fifo_cost_basis
from wpm.models import Asset, Portfolio, Position, PortfolioError, Trade

logger = logging.getLogger(__name__)


class SimplePortfolio(Portfolio):
    """Portfolio containing direct asset positions (trades)."""

    def __init__(self, name: str, cost_basis_method: str = "fifo"):
        """Initialize a simple portfolio.

        Args:
            name: Portfolio name
            cost_basis_method: Cost basis calculation method ("fifo" or "average")
        """
        super().__init__(name)

        if cost_basis_method not in ("fifo", "average"):
            raise PortfolioError("Cost basis method must be 'fifo' or 'average'")

        self.cost_basis_method = cost_basis_method
        self._trades: List[Trade] = []

        logger.info(
            f"Created SimplePortfolio '{name}' with cost_basis_method='{cost_basis_method}'"
        )

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to the portfolio.

        Args:
            trade: Trade to add
        """
        if not isinstance(trade, Trade):
            raise PortfolioError("Trade must be a Trade object")

        self._trades.append(trade)
        logger.info(f"Added trade to portfolio '{self.name}': {trade.asset.ticker} {trade.action}")

    def get_positions(self) -> Dict[Asset, Position]:
        """Get all positions in the portfolio.

        Returns:
            Dictionary mapping Asset to Position objects
        """
        if not self._trades:
            return {}

        if self.cost_basis_method == "fifo":
            positions = calculate_fifo_cost_basis(self._trades)
        else:
            positions = calculate_average_cost_basis(self._trades)

        logger.debug(
            f"Calculated {len(positions)} positions for portfolio '{self.name}'"
        )
        return positions

    def get_total_cost_basis(self) -> float:
        """Calculate total cost basis for the portfolio.

        Returns:
            Total cost basis in USD
        """
        positions = self.get_positions()
        total = sum(position.cost_basis for position in positions.values())
        return total

    def get_all_trades(self) -> List[Trade]:
        """Get all trades in the portfolio.

        Returns:
            List of all trades
        """
        return self._trades.copy()


class CompositePortfolio(Portfolio):
    """Portfolio containing sub-portfolios."""

    def __init__(self, name: str):
        """Initialize a composite portfolio.

        Args:
            name: Portfolio name
        """
        super().__init__(name)
        self._sub_portfolios: Dict[str, Portfolio] = {}

        logger.info(f"Created CompositePortfolio '{name}'")

    def add_sub_portfolio(self, portfolio: Portfolio) -> None:
        """Add a sub-portfolio to this composite portfolio.

        Args:
            portfolio: Portfolio to add as sub-portfolio

        Raises:
            PortfolioError: If portfolio name already exists or portfolio is invalid
        """
        if not isinstance(portfolio, Portfolio):
            raise PortfolioError("Sub-portfolio must be a Portfolio object")

        if portfolio.name in self._sub_portfolios:
            raise PortfolioError(
                f"Sub-portfolio with name '{portfolio.name}' already exists"
            )

        self._sub_portfolios[portfolio.name] = portfolio
        logger.info(
            f"Added sub-portfolio '{portfolio.name}' to composite portfolio '{self.name}'"
        )

    def get_positions(self) -> Dict[Asset, Position]:
        """Get all positions aggregated from sub-portfolios.

        Returns:
            Dictionary mapping Asset to aggregated Position objects
        """
        aggregated_positions: Dict[Asset, Position] = {}

        for sub_portfolio in self._sub_portfolios.values():
            sub_positions = sub_portfolio.get_positions()

            for asset, position in sub_positions.items():
                if asset not in aggregated_positions:
                    aggregated_positions[asset] = Position(
                        asset=asset,
                        quantity=Decimal('0'),
                        cost_basis=0.0,
                        cost_basis_method=position.cost_basis_method,
                    )

                existing = aggregated_positions[asset]
                aggregated_positions[asset] = Position(
                    asset=asset,
                    quantity=existing.quantity + position.quantity,
                    cost_basis=existing.cost_basis + position.cost_basis,
                    cost_basis_method=position.cost_basis_method,
                )

                logger.debug(
                    f"Aggregated position for {asset.ticker}: "
                    f"quantity={aggregated_positions[asset].quantity}, "
                    f"cost_basis=${aggregated_positions[asset].cost_basis:.2f}"
                )

        return aggregated_positions

    def get_total_cost_basis(self) -> float:
        """Calculate total cost basis aggregated from sub-portfolios.

        Returns:
            Total cost basis in USD
        """
        total = sum(
            sub_portfolio.get_total_cost_basis()
            for sub_portfolio in self._sub_portfolios.values()
        )
        return total

    def get_all_trades(self) -> List[Trade]:
        """Get all trades from all sub-portfolios.

        Returns:
            List of all trades from sub-portfolios
        """
        all_trades: List[Trade] = []
        for sub_portfolio in self._sub_portfolios.values():
            all_trades.extend(sub_portfolio.get_all_trades())
        return all_trades

