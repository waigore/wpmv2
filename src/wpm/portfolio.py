"""Portfolio class implementation with aggregation logic."""

import logging
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from wpm.cost_basis import calculate_average_cost_basis, calculate_fifo_cost_basis
from wpm.models import Asset, Portfolio, Position, PortfolioError, Trade
from wpm.utils import validate_asset_type

if TYPE_CHECKING:
    from wpm.pricing import PriceService

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

    def get_positions(
        self, asset_type: Optional[str] = None, tickers: Optional[List[str]] = None
    ) -> Dict[Asset, Position]:
        """Get all positions in the portfolio.

        Args:
            asset_type: Optional asset type to filter by (e.g., "Stock", "ETF", "Crypto")
            tickers: Optional list of ticker symbols to filter by

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

        # Apply filtering if parameters are provided
        if asset_type is not None or tickers is not None:
            # Normalize asset_type if provided
            normalized_asset_type = None
            if asset_type is not None:
                try:
                    normalized_asset_type = validate_asset_type(asset_type)
                except ValueError:
                    # Invalid asset type - no positions will match
                    logger.debug(
                        f"Invalid asset_type filter '{asset_type}', returning empty results"
                    )
                    return {}

            filtered_positions: Dict[Asset, Position] = {}
            for asset, position in positions.items():
                # Check asset_type filter
                if normalized_asset_type is not None and asset.asset_type != normalized_asset_type:
                    continue
                # Check tickers filter
                if tickers is not None and asset.ticker not in tickers:
                    continue
                # Both filters passed (or one was None), include this position
                filtered_positions[asset] = position

            logger.debug(
                f"Filtered positions: {len(filtered_positions)} of {len(positions)} "
                f"positions match filters (asset_type={normalized_asset_type or asset_type}, tickers={tickers})"
            )
            return filtered_positions

        return positions

    def get_total_cost_basis(self) -> float:
        """Calculate total cost basis for the portfolio.

        Returns:
            Total cost basis in USD
        """
        positions = self.get_positions()
        total = sum(position.cost_basis for position in positions.values())
        return total

    def get_total_market_value(self, prices: Dict[Asset, Optional[float]]) -> float:
        """Calculate total market value for the portfolio.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Total market value in USD
        """
        positions = self.get_positions()
        total_market_value = 0.0

        for asset, position in positions.items():
            if asset not in prices or prices[asset] is None:
                logger.debug(f"No price available for {asset.ticker}, skipping")
                continue

            price = prices[asset]
            # Convert Decimal quantity to float for market value calculation
            market_value = float(position.quantity) * price
            total_market_value += market_value

            logger.debug(
                f"{asset.ticker}: {position.quantity} * ${price:.2f} = ${market_value:.2f}"
            )

        return total_market_value

    def get_total_unrealized_pnl(self, prices: Dict[Asset, Optional[float]]) -> float:
        """Calculate total unrealized profit/loss for the portfolio.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Total unrealized profit/loss in USD (market_value - cost_basis)
        """
        market_value = self.get_total_market_value(prices)
        cost_basis = self.get_total_cost_basis()
        return market_value - cost_basis

    def get_all_trades(self) -> List[Trade]:
        """Get all trades in the portfolio.

        Returns:
            List of all trades
        """
        return self._trades.copy()

    def get_asset_trades(
        self, ticker: str, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Trade]:
        """Get all trades for a specified asset (ticker) within the portfolio.

        Args:
            ticker: Asset ticker symbol to filter trades by
            start_date: Optional start date for date range filter (inclusive).
                If not specified, includes trades from the very beginning.
            end_date: Optional end date for date range filter (inclusive).
                If not specified, includes trades to the very end.

        Returns:
            List of Trade objects matching the ticker and date range
            (includes both Buy and Sell trades)
        """
        logger.info(
            f"Getting asset trades for ticker '{ticker}' "
            f"(start_date={start_date}, end_date={end_date}) in portfolio '{self.name}'"
        )

        filtered_trades: List[Trade] = []
        for trade in self._trades:
            # Filter by ticker
            if trade.asset.ticker != ticker:
                continue

            # Filter by start_date if provided
            if start_date is not None and trade.date < start_date:
                continue

            # Filter by end_date if provided
            if end_date is not None and trade.date > end_date:
                continue

            filtered_trades.append(trade)

        logger.info(
            f"Found {len(filtered_trades)} trades for ticker '{ticker}' "
            f"in portfolio '{self.name}'"
        )

        return filtered_trades


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

    def get_positions(
        self, asset_type: Optional[str] = None, tickers: Optional[List[str]] = None
    ) -> Dict[Asset, Position]:
        """Get all positions aggregated from sub-portfolios.

        Args:
            asset_type: Optional asset type to filter by (e.g., "Stock", "ETF", "Crypto")
            tickers: Optional list of ticker symbols to filter by

        Returns:
            Dictionary mapping Asset to aggregated Position objects
        """
        aggregated_positions: Dict[Asset, Position] = {}

        for sub_portfolio in self._sub_portfolios.values():
            sub_positions = sub_portfolio.get_positions(
                asset_type=asset_type, tickers=tickers
            )

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

    def get_total_market_value(self, prices: Dict[Asset, Optional[float]]) -> float:
        """Calculate total market value aggregated from sub-portfolios.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Total market value in USD
        """
        total = sum(
            sub_portfolio.get_total_market_value(prices)
            for sub_portfolio in self._sub_portfolios.values()
        )
        return total

    def get_total_unrealized_pnl(self, prices: Dict[Asset, Optional[float]]) -> float:
        """Calculate total unrealized profit/loss aggregated from sub-portfolios.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Total unrealized profit/loss in USD
        """
        total = sum(
            sub_portfolio.get_total_unrealized_pnl(prices)
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

    def get_asset_trades(
        self, ticker: str, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[Trade]:
        """Get all trades for a specified asset (ticker) within the portfolio.

        Aggregates asset trades from all sub-portfolios.

        Args:
            ticker: Asset ticker symbol to filter trades by
            start_date: Optional start date for date range filter (inclusive).
                If not specified, includes trades from the very beginning.
            end_date: Optional end date for date range filter (inclusive).
                If not specified, includes trades to the very end.

        Returns:
            List of Trade objects matching the ticker and date range
            (includes both Buy and Sell trades)
        """
        logger.info(
            f"Getting asset trades for ticker '{ticker}' "
            f"(start_date={start_date}, end_date={end_date}) in composite portfolio '{self.name}'"
        )

        all_trades: List[Trade] = []
        for sub_portfolio in self._sub_portfolios.values():
            sub_trades = sub_portfolio.get_asset_trades(ticker, start_date, end_date)
            all_trades.extend(sub_trades)

        logger.info(
            f"Found {len(all_trades)} trades for ticker '{ticker}' "
            f"in composite portfolio '{self.name}'"
        )

        return all_trades


def fetch_price_map(
    portfolio: Portfolio, price_service: "PriceService"
) -> Dict[Asset, Optional[float]]:
    """Fetch prices for all assets in portfolio and return a price map.

    Extracts assets from portfolio positions, groups them by asset type for
    batch processing, and fetches prices via PriceService. Handles exceptions
    gracefully by setting None for assets that fail to fetch.

    Args:
        portfolio: Portfolio containing assets (SimplePortfolio or CompositePortfolio)
        price_service: Price service for retrieving prices

    Returns:
        Dictionary mapping Asset to Optional[float] price (None if price unavailable)
    """
    positions = portfolio.get_positions()
    assets = list(positions.keys())

    if not assets:
        logger.debug("No assets found in portfolio, returning empty price map")
        return {}

    # Group assets by asset_type for batch processing
    assets_by_type: Dict[str, List[Asset]] = {}
    for asset in assets:
        asset_type = asset.asset_type
        if asset_type not in assets_by_type:
            assets_by_type[asset_type] = []
        assets_by_type[asset_type].append(asset)

    # Fetch prices in batches by asset type
    price_map: Dict[Asset, Optional[float]] = {}
    for asset_type, asset_list in assets_by_type.items():
        tickers = [asset.ticker for asset in asset_list]
        try:
            prices = price_service.get_prices(tickers, asset_type)
            # Map tickers back to assets
            for asset in asset_list:
                price_map[asset] = prices.get(asset.ticker)
        except Exception as e:
            logger.warning(
                f"Price retrieval failed for {asset_type} assets: {e}"
            )
            # Set None for all assets of this type
            for asset in asset_list:
                price_map[asset] = None

    return price_map

