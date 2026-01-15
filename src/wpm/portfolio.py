"""Portfolio class implementation with aggregation logic."""

import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from wpm.cache_utils import LRUCache, trades_to_cache_key_with_filters
from wpm.cost_basis import calculate_fifo_cost_basis, calculate_lots_from_trades
from wpm.models import Asset, Lot, Portfolio, PortfolioHistoryPoint, Position, PortfolioError, Trade
from wpm.utils import validate_asset_type

if TYPE_CHECKING:
    from wpm.pricing import PriceService

logger = logging.getLogger(__name__)

# LRU caches for portfolio calculations
_positions_cache: LRUCache[Dict[Asset, Position]] = LRUCache(maxsize=128)
_cost_basis_cache: LRUCache[float] = LRUCache(maxsize=128)


class SimplePortfolio(Portfolio):
    """Portfolio containing direct asset positions (trades)."""

    def __init__(self, name: str, is_historical: bool = False):
        """Initialize a simple portfolio.

        Args:
            name: Portfolio name
            is_historical: Whether this is a historical portfolio (default: False)
        """
        super().__init__(name, is_historical=is_historical)

        self._trades: List[Trade] = []
        self._assets: Dict[str, Asset] = {}  # Lightweight asset cache

        logger.info(f"Created SimplePortfolio '{name}' (is_historical={is_historical})")

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to the portfolio.

        Args:
            trade: Trade to add
        """
        if not isinstance(trade, Trade):
            raise PortfolioError("Trade must be a Trade object")

        self._trades.append(trade)
        # Update asset cache
        self._assets[trade.asset.ticker] = trade.asset
        logger.info(f"Added trade to portfolio '{self.name}': {trade.asset.ticker} {trade.action}")

    def get_positions(
        self, asset_type: Optional[str] = None, tickers: Optional[List[str]] = None
    ) -> Dict[Asset, Position]:
        """Get all positions in the portfolio.

        Uses LRU caching to avoid recalculating positions for the same trades.

        Args:
            asset_type: Optional asset type to filter by (e.g., "Stock", "ETF", "Crypto")
            tickers: Optional list of ticker symbols to filter by

        Returns:
            Dictionary mapping Asset to Position objects
        """
        if not self._trades:
            return {}

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

        # Create cache key
        cache_key = trades_to_cache_key_with_filters(self._trades, normalized_asset_type, tickers)

        # Check cache
        cached_positions = _positions_cache.get(cache_key)
        if cached_positions is not None:
            logger.debug("Cache hit for positions calculation")
            return cached_positions

        # Cache miss - calculate positions
        logger.debug("Cache miss for positions calculation")
        positions = calculate_fifo_cost_basis(self._trades)

        logger.debug(
            f"Calculated {len(positions)} positions for portfolio '{self.name}'"
        )

        # Apply filtering if parameters are provided
        if normalized_asset_type is not None or tickers is not None:
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
            positions = filtered_positions

        # Store in cache (LRU eviction handled automatically)
        _positions_cache.set(cache_key, positions)

        return positions

    def get_total_cost_basis(self) -> float:
        """Calculate total cost basis for the portfolio.

        Uses LRU caching to avoid recalculating for the same trades.

        Returns:
            Total cost basis in USD
        """
        if not self._trades:
            return 0.0

        # Create cache key (no filters for cost basis)
        cache_key = trades_to_cache_key_with_filters(self._trades, None, None)

        # Check cache
        cached_cost_basis = _cost_basis_cache.get(cache_key)
        if cached_cost_basis is not None:
            logger.debug("Cache hit for cost basis calculation")
            return cached_cost_basis

        # Cache miss - calculate cost basis
        logger.debug("Cache miss for cost basis calculation")
        positions = self.get_positions()
        total = sum(position.cost_basis for position in positions.values())

        # Store in cache (LRU eviction handled automatically)
        _cost_basis_cache.set(cache_key, total)

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

    def get_asset_lots(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        prices: Optional[Dict[Asset, Optional[float]]] = None,
    ) -> List[Lot]:
        """Get all lots for a specified asset (ticker) within the portfolio.

        Args:
            ticker: Asset ticker symbol to filter lots by
            start_date: Optional start date for date range filter (inclusive).
                If not specified, includes lots from the very beginning.
            end_date: Optional end date for date range filter (inclusive).
                If not specified, includes lots to the very end.
            prices: Optional dictionary mapping Asset to current price for P/L calculations

        Returns:
            List of Lot objects for the ticker
        """
        logger.info(
            f"Getting asset lots for ticker '{ticker}' "
            f"(start_date={start_date}, end_date={end_date}) in portfolio '{self.name}'"
        )

        # Filter trades by ticker and date range
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

        if not filtered_trades:
            logger.info(
                f"No trades found for ticker '{ticker}' "
                f"in portfolio '{self.name}'"
            )
            return []

        # Calculate lots from filtered trades (benefits from caching)
        lots_by_asset = calculate_lots_from_trades(filtered_trades)

        # Get lots for this asset
        asset = Asset(ticker=ticker, asset_type=filtered_trades[0].asset.asset_type)
        lots = lots_by_asset.get(asset, [])

        logger.info(
            f"Found {len(lots)} lots for ticker '{ticker}' "
            f"in portfolio '{self.name}'"
        )

        return lots

    def get_total_realized_pnl(self, prices: Dict[Asset, Optional[float]]) -> float:
        """Calculate total realized profit/loss for the portfolio.

        Derives from lots' realized P/L.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable).
                Note: Realized P/L doesn't actually depend on current prices, but included
                for consistency with other P/L methods.

        Returns:
            Total realized profit/loss in USD
        """
        if not self._trades:
            return 0.0

        # Calculate lots from all trades (benefits from caching)
        lots_by_asset = calculate_lots_from_trades(self._trades)

        # Sum realized P/L from all lots
        total_realized_pnl = 0.0
        for lots in lots_by_asset.values():
            for lot in lots:
                total_realized_pnl += lot.get_realized_pnl()

        return total_realized_pnl

    def get_asset_allocation(
        self, asset: Asset, prices: Dict[Asset, Optional[float]]
    ) -> Decimal:
        """Get percentage allocation of a specific asset position.

        The percentage is calculated as (asset market value / total portfolio market value) * 100.
        Uses Decimal for precision and rounds to 2 decimal places.

        Args:
            asset: Asset to get allocation for
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Percentage allocation as Decimal rounded to 2 decimal places (0.00 if asset not in portfolio,
            missing price, or zero total market value)
        """
        positions = self.get_positions()
        
        # Guard clause: asset not in portfolio
        if asset not in positions:
            return Decimal('0.00')
        
        position = positions[asset]
        
        # Guard clause: no quantity
        if position.quantity == 0:
            return Decimal('0.00')
        
        # Guard clause: missing price
        if asset not in prices or prices[asset] is None:
            logger.debug(f"No price available for {asset.ticker}, returning 0.00 allocation")
            return Decimal('0.00')
        
        # Calculate asset market value
        price = Decimal(str(prices[asset]))
        asset_market_value = position.quantity * price
        
        # Calculate total portfolio market value
        total_market_value = Decimal(str(self.get_total_market_value(prices)))
        
        # Guard clause: zero total market value
        if total_market_value == 0:
            return Decimal('0.00')
        
        # Calculate percentage: (asset_market_value / total_market_value) * 100
        allocation = (asset_market_value / total_market_value) * Decimal('100')
        
        # Round to 2 decimal places
        allocation = allocation.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        logger.debug(
            f"Allocation for {asset.ticker}: {asset_market_value} / {total_market_value} * 100 = {allocation}%"
        )
        
        return allocation

    def get_all_allocations(
        self, prices: Dict[Asset, Optional[float]]
    ) -> Dict[Asset, Decimal]:
        """Get percentage allocations for all asset positions in the portfolio.

        The percentage for each asset is calculated as (asset market value / total portfolio market value) * 100.
        Uses Decimal for precision and rounds to 2 decimal places. All allocations should sum to 100.00.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Dictionary mapping Asset to Decimal percentage allocation (2 decimal places)
        """
        positions = self.get_positions()
        
        # Guard clause: empty portfolio
        if not positions:
            return {}
        
        allocations: Dict[Asset, Decimal] = {}
        
        # Calculate allocation for each asset with a position
        for asset in positions.keys():
            allocation = self.get_asset_allocation(asset, prices)
            allocations[asset] = allocation
        
        # Verify allocations sum to 100.00 (within rounding tolerance)
        total_allocation = sum(allocations.values())
        expected_total = Decimal('100.00')
        tolerance = Decimal('0.01')
        
        if abs(total_allocation - expected_total) > tolerance:
            logger.warning(
                f"Portfolio allocations sum to {total_allocation}%, expected 100.00% "
                f"(difference: {abs(total_allocation - expected_total)}%)"
            )
        else:
            logger.debug(f"Portfolio allocations sum to {total_allocation}%")
        
        return allocations

    def get_all_trades(self) -> List[Trade]:
        """Get all trades in the portfolio.

        Returns:
            List of all trades
        """
        return self._trades.copy()

    def get_assets(self) -> Dict[str, Asset]:
        """Get all unique assets in the portfolio.

        Returns a lightweight mapping without triggering any calculations.
        This is updated automatically when trades are added.

        Returns:
            Dictionary mapping ticker to Asset object
        """
        return self._assets.copy()  # Return copy to prevent external modification

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

    def clone(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        _skip_end_date_validation: bool = False,
    ) -> "SimplePortfolio":
        """Create a deep copy of the portfolio.

        Args:
            start_date: Optional start date for filtering trades (inclusive).
                Must be within portfolio's date range if provided.
            end_date: Optional end date for filtering trades (inclusive).
                Must be within portfolio's date range if provided.
            _skip_end_date_validation: Internal flag to skip end_date validation
                when cloning sub-portfolios in composite portfolios.

        Returns:
            New SimplePortfolio instance with cloned trades

        Raises:
            PortfolioError: If date range is outside portfolio's date range
        """
        # Create new portfolio with same name and is_historical flag
        cloned_portfolio = SimplePortfolio(name=self.name, is_historical=self.is_historical)

        # Helper function to clone a trade
        def _clone_trade(trade: Trade) -> None:
            cloned_trade = Trade(
                date=trade.date,
                asset=trade.asset,  # Asset is frozen/immutable, can reuse
                action=trade.action,
                broker=trade.broker,
                order_instruction=trade.order_instruction,
                trade_type=trade.trade_type,
                currency=trade.currency,
                price=trade.price,
                price_native=trade.price_native,
                quantity=trade.quantity,
            )
            cloned_portfolio.add_trade(cloned_trade)

        # If no date filtering, clone all trades
        if start_date is None and end_date is None:
            for trade in self._trades:
                _clone_trade(trade)
            logger.info(
                f"Cloned portfolio '{self.name}' "
                f"(start_date={start_date}, end_date={end_date}, "
                f"trades={len(cloned_portfolio._trades)})"
            )
            return cloned_portfolio

        # Validate date range - use guard clauses
        if start_date is not None and end_date is not None and start_date > end_date:
            raise PortfolioError(
                f"start_date {start_date} is after end_date {end_date}"
            )

        # Validate date range is within portfolio's date range (if portfolio has trades)
        if self._trades:
            portfolio_start = self.start_date
            portfolio_end = self.end_date

            # Validate start_date
            if start_date is not None and portfolio_start is not None and start_date < portfolio_start:
                raise PortfolioError(
                    f"start_date {start_date} is before portfolio's start_date {portfolio_start}"
                )

            # For end_date validation: we validate strictly for direct cloning.
            # When cloning sub-portfolios in composite portfolios, we skip this validation
            # to allow composite date ranges that extend beyond individual sub-portfolio ranges.
            if (
                end_date is not None
                and portfolio_end is not None
                and not _skip_end_date_validation
                and end_date > portfolio_end
            ):
                raise PortfolioError(
                    f"end_date {end_date} is after portfolio's end_date {portfolio_end}"
                )

        # Filter and clone trades within date range
        for trade in self._trades:
            # Filter by start_date if provided
            if start_date is not None and trade.date < start_date:
                continue

            # Filter by end_date if provided
            if end_date is not None and trade.date > end_date:
                continue

            _clone_trade(trade)

        logger.info(
            f"Cloned portfolio '{self.name}' "
            f"(start_date={start_date}, end_date={end_date}, "
            f"trades={len(cloned_portfolio._trades)})"
        )

        return cloned_portfolio

    @property
    def start_date(self) -> Optional[date]:
        """Get the earliest trade date in the portfolio.

        Returns:
            Earliest trade date, or None if no trades exist
        """
        if not self._trades:
            return None
        return min(trade.date for trade in self._trades)

    @property
    def end_date(self) -> Optional[date]:
        """Get the most recent trade date in the portfolio.

        Returns:
            Most recent trade date, or None if no trades exist
        """
        if not self._trades:
            return None
        return max(trade.date for trade in self._trades)


class CompositePortfolio(Portfolio):
    """Portfolio containing sub-portfolios."""

    def __init__(self, name: str, is_historical: bool = False):
        """Initialize a composite portfolio.

        Args:
            name: Portfolio name
            is_historical: Whether this is a historical portfolio (default: False)
        """
        super().__init__(name, is_historical=is_historical)
        self._sub_portfolios: Dict[str, Portfolio] = {}

        logger.info(f"Created CompositePortfolio '{name}' (is_historical={is_historical})")

    def add_sub_portfolio(self, portfolio: Portfolio) -> None:
        """Add a sub-portfolio to this composite portfolio.

        Args:
            portfolio: Portfolio to add as sub-portfolio

        Raises:
            PortfolioError: If portfolio name already exists, portfolio is invalid,
                           or is_historical flags don't match
        """
        if not isinstance(portfolio, Portfolio):
            raise PortfolioError("Sub-portfolio must be a Portfolio object")

        if portfolio.name in self._sub_portfolios:
            raise PortfolioError(
                f"Sub-portfolio with name '{portfolio.name}' already exists"
            )

        # Validate that is_historical flags match
        if portfolio.is_historical != self.is_historical:
            raise PortfolioError(
                f"Sub-portfolio '{portfolio.name}' has is_historical={portfolio.is_historical}, "
                f"but composite portfolio has is_historical={self.is_historical}. "
                f"All sub-portfolios must have identical is_historical flags."
            )

        self._sub_portfolios[portfolio.name] = portfolio
        logger.info(
            f"Added sub-portfolio '{portfolio.name}' to composite portfolio '{self.name}'"
        )

    def get_sub_portfolios(self) -> Dict[str, "Portfolio"]:
        """Get a copy of all sub-portfolios.

        Returns:
            Dictionary mapping sub-portfolio name to Portfolio instance
        """
        return self._sub_portfolios.copy()

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

    def get_asset_lots(
        self,
        ticker: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        prices: Optional[Dict[Asset, Optional[float]]] = None,
    ) -> List[Lot]:
        """Get all lots for a specified asset (ticker) within the portfolio.

        Aggregates lots from all sub-portfolios.

        Args:
            ticker: Asset ticker symbol to filter lots by
            start_date: Optional start date for date range filter (inclusive).
                If not specified, includes lots from the very beginning.
            end_date: Optional end date for date range filter (inclusive).
                If not specified, includes lots to the very end.
            prices: Optional dictionary mapping Asset to current price for P/L calculations

        Returns:
            List of Lot objects for the ticker (aggregated from all sub-portfolios)
        """
        logger.info(
            f"Getting asset lots for ticker '{ticker}' "
            f"(start_date={start_date}, end_date={end_date}) in composite portfolio '{self.name}'"
        )

        all_lots: List[Lot] = []
        for sub_portfolio in self._sub_portfolios.values():
            sub_lots = sub_portfolio.get_asset_lots(ticker, start_date, end_date, prices)
            all_lots.extend(sub_lots)

        logger.info(
            f"Found {len(all_lots)} lots for ticker '{ticker}' "
            f"in composite portfolio '{self.name}'"
        )

        return all_lots

    def get_total_realized_pnl(self, prices: Dict[Asset, Optional[float]]) -> float:
        """Calculate total realized profit/loss aggregated from sub-portfolios.

        Derives from lots' realized P/L.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable).
                Note: Realized P/L doesn't actually depend on current prices, but included
                for consistency with other P/L methods.

        Returns:
            Total realized profit/loss in USD
        """
        total = sum(
            sub_portfolio.get_total_realized_pnl(prices)
            for sub_portfolio in self._sub_portfolios.values()
        )
        return total

    def get_asset_allocation(
        self, asset: Asset, prices: Dict[Asset, Optional[float]]
    ) -> Decimal:
        """Get percentage allocation of a specific asset position.

        The percentage is calculated as (asset market value / total portfolio market value) * 100.
        Uses Decimal for precision and rounds to 2 decimal places.
        For composite portfolios, aggregates positions across all sub-portfolios.

        Args:
            asset: Asset to get allocation for
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Percentage allocation as Decimal rounded to 2 decimal places (0.00 if asset not in portfolio,
            missing price, or zero total market value)
        """
        positions = self.get_positions()
        
        # Guard clause: asset not in portfolio
        if asset not in positions:
            return Decimal('0.00')
        
        position = positions[asset]
        
        # Guard clause: no quantity
        if position.quantity == 0:
            return Decimal('0.00')
        
        # Guard clause: missing price
        if asset not in prices or prices[asset] is None:
            logger.debug(f"No price available for {asset.ticker}, returning 0.00 allocation")
            return Decimal('0.00')
        
        # Calculate asset market value
        price = Decimal(str(prices[asset]))
        asset_market_value = position.quantity * price
        
        # Calculate total portfolio market value
        total_market_value = Decimal(str(self.get_total_market_value(prices)))
        
        # Guard clause: zero total market value
        if total_market_value == 0:
            return Decimal('0.00')
        
        # Calculate percentage: (asset_market_value / total_market_value) * 100
        allocation = (asset_market_value / total_market_value) * Decimal('100')
        
        # Round to 2 decimal places
        allocation = allocation.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        logger.debug(
            f"Allocation for {asset.ticker}: {asset_market_value} / {total_market_value} * 100 = {allocation}%"
        )
        
        return allocation

    def get_all_allocations(
        self, prices: Dict[Asset, Optional[float]]
    ) -> Dict[Asset, Decimal]:
        """Get percentage allocations for all asset positions in the portfolio.

        The percentage for each asset is calculated as (asset market value / total portfolio market value) * 100.
        Uses Decimal for precision and rounds to 2 decimal places. All allocations should sum to 100.00.
        For composite portfolios, aggregates positions across all sub-portfolios.

        Args:
            prices: Dictionary mapping Asset to current price (None if unavailable)

        Returns:
            Dictionary mapping Asset to Decimal percentage allocation (2 decimal places)
        """
        positions = self.get_positions()
        
        # Guard clause: empty portfolio
        if not positions:
            return {}
        
        allocations: Dict[Asset, Decimal] = {}
        
        # Calculate allocation for each asset with a position
        for asset in positions.keys():
            allocation = self.get_asset_allocation(asset, prices)
            allocations[asset] = allocation
        
        # Verify allocations sum to 100.00 (within rounding tolerance)
        total_allocation = sum(allocations.values())
        expected_total = Decimal('100.00')
        tolerance = Decimal('0.01')
        
        if abs(total_allocation - expected_total) > tolerance:
            logger.warning(
                f"Portfolio allocations sum to {total_allocation}%, expected 100.00% "
                f"(difference: {abs(total_allocation - expected_total)}%)"
            )
        else:
            logger.debug(f"Portfolio allocations sum to {total_allocation}%")
        
        return allocations

    def get_all_trades(self) -> List[Trade]:
        """Get all trades from all sub-portfolios.

        Returns:
            List of all trades from sub-portfolios
        """
        all_trades: List[Trade] = []
        for sub_portfolio in self._sub_portfolios.values():
            all_trades.extend(sub_portfolio.get_all_trades())
        return all_trades

    def get_assets(self) -> Dict[str, Asset]:
        """Get all unique assets across all sub-portfolios.

        Returns a lightweight mapping without triggering any calculations.
        Aggregates assets from all sub-portfolios.

        Returns:
            Dictionary mapping ticker to Asset object
        """
        assets: Dict[str, Asset] = {}
        for sub_portfolio in self._sub_portfolios.values():
            sub_assets = sub_portfolio.get_assets()
            # Merge: if same ticker exists, keep first one (assets are same for same ticker)
            for ticker, asset in sub_assets.items():
                if ticker not in assets:
                    assets[ticker] = asset
        return assets

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

    @property
    def start_date(self) -> Optional[date]:
        """Get the earliest start_date of all sub-portfolios.

        Returns:
            Earliest start_date, or None if no sub-portfolios exist
        """
        if not self._sub_portfolios:
            return None
        
        start_dates = [
            sub_portfolio.start_date
            for sub_portfolio in self._sub_portfolios.values()
            if sub_portfolio.start_date is not None
        ]
        
        if not start_dates:
            return None
        
        return min(start_dates)

    @property
    def end_date(self) -> Optional[date]:
        """Get the most recent end_date of all sub-portfolios.

        Returns:
            Most recent end_date, or None if no sub-portfolios exist
        """
        if not self._sub_portfolios:
            return None
        
        end_dates = [
            sub_portfolio.end_date
            for sub_portfolio in self._sub_portfolios.values()
            if sub_portfolio.end_date is not None
        ]
        
        if not end_dates:
            return None
        
        return max(end_dates)

    def clone(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        _skip_end_date_validation: bool = False,
    ) -> "CompositePortfolio":
        """Create a deep copy of the portfolio.

        Args:
            start_date: Optional start date for filtering sub-portfolios (inclusive).
                Must be within portfolio's date range if provided.
            end_date: Optional end date for filtering sub-portfolios (inclusive).
                Must be within portfolio's date range if provided.
            _skip_end_date_validation: Internal flag to skip end_date validation
                when cloning sub-portfolios in composite portfolios.

        Returns:
            New CompositePortfolio instance with cloned sub-portfolios

        Raises:
            PortfolioError: If date range is outside portfolio's date range
        """
        # Create new portfolio with same name and is_historical flag
        cloned_portfolio = CompositePortfolio(name=self.name, is_historical=self.is_historical)

        # Validate date range if portfolio has sub-portfolios - use guard clauses
        if self._sub_portfolios:
            portfolio_start = self.start_date
            portfolio_end = self.end_date

            # Validate start_date
            if start_date is not None and (portfolio_start is None or start_date < portfolio_start):
                raise PortfolioError(
                    f"start_date {start_date} is before portfolio's start_date {portfolio_start}"
                )

            # Skip end_date validation if _skip_end_date_validation is True
            # (e.g., when cloning for historical performance calculation)
            if (
                end_date is not None
                and not _skip_end_date_validation
                and (portfolio_end is None or end_date > portfolio_end)
            ):
                raise PortfolioError(
                    f"end_date {end_date} is after portfolio's end_date {portfolio_end}"
                )

            # Validate date range consistency
            if start_date is not None and end_date is not None and start_date > end_date:
                raise PortfolioError(
                    f"start_date {start_date} is after end_date {end_date}"
                )

        # Recursively clone all sub-portfolios
        # Skip end_date validation for sub-portfolios to allow composite date ranges
        # that extend beyond individual sub-portfolio ranges
        for sub_portfolio in self._sub_portfolios.values():
            # Pass _skip_end_date_validation to nested composites as well
            if isinstance(sub_portfolio, CompositePortfolio):
                cloned_sub = sub_portfolio.clone(
                    start_date=start_date,
                    end_date=end_date,
                    _skip_end_date_validation=True,
                )
            else:
                cloned_sub = sub_portfolio.clone(
                    start_date=start_date,
                    end_date=end_date,
                    _skip_end_date_validation=True,
                )
            cloned_portfolio.add_sub_portfolio(cloned_sub)

        logger.info(
            f"Cloned composite portfolio '{self.name}' "
            f"(start_date={start_date}, end_date={end_date}, "
            f"sub_portfolios={len(cloned_portfolio._sub_portfolios)})"
        )

        return cloned_portfolio


def fetch_price_map(
    portfolio: Portfolio,
    price_service: "PriceService",
    target_date: Optional[date] = None,
) -> Dict[Asset, Optional[float]]:
    """Fetch prices for all assets in portfolio and return a price map.

    Extracts assets from portfolio positions, groups them by asset type for
    batch processing, and fetches prices via PriceService. For historical portfolios,
    uses historical prices. Handles exceptions gracefully by setting None for assets
    that fail to fetch.

    Args:
        portfolio: Portfolio containing assets (SimplePortfolio or CompositePortfolio)
        price_service: Price service for retrieving prices
        target_date: Optional target date for historical prices. If None and portfolio
                    is historical, uses portfolio.end_date

    Returns:
        Dictionary mapping Asset to Optional[float] price (None if price unavailable)
    """
    positions = portfolio.get_positions()
    assets = list(positions.keys())

    if not assets:
        logger.debug("No assets found in portfolio, returning empty price map")
        return {}

    # Determine if we should use historical prices
    use_historical = portfolio.is_historical
    if use_historical and target_date is None:
        target_date = portfolio.end_date
        if target_date is None:
            logger.warning(
                f"Historical portfolio '{portfolio.name}' has no end_date, "
                f"cannot fetch historical prices"
            )
            use_historical = False

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
            if use_historical and target_date is not None:
                # Use historical prices
                # For historical prices, we need start_date and end_date
                # Use portfolio dates if available, otherwise use target_date for both
                start_date = portfolio.start_date if portfolio.start_date is not None else target_date
                end_date = target_date

                logger.debug(
                    f"Fetching historical prices for {asset_type} assets "
                    f"from {start_date} to {end_date}"
                )
                prices = price_service.get_historical_prices(
                    tickers, asset_type, start_date, end_date
                )
            else:
                # Use current prices
                prices = price_service.get_prices(tickers, asset_type)
                # Current prices return Dict[str, float]
                for asset in asset_list:
                    ticker = asset.ticker
                    price_map[asset] = prices.get(ticker)
                continue

            # Map tickers back to assets (historical prices)
            # prices is Dict[str, Dict[date, float]], extract price for end_date
            for asset in asset_list:
                ticker = asset.ticker
                if ticker in prices:
                    ticker_prices = prices[ticker]
                    # Find price for end_date (or most recent available up to end_date)
                    if end_date in ticker_prices:
                        price_map[asset] = ticker_prices[end_date]
                    else:
                        # Find most recent date <= end_date
                        available_dates = [d for d in ticker_prices.keys() if d <= end_date]
                        if available_dates:
                            most_recent_date = max(available_dates)
                            price_map[asset] = ticker_prices[most_recent_date]
                        else:
                            price_map[asset] = None
                else:
                    price_map[asset] = None
        except Exception as e:
            logger.warning(
                f"Price retrieval failed for {asset_type} assets: {e}"
            )
            # Set None for all assets of this type
            for asset in asset_list:
                price_map[asset] = None

    return price_map


def generate_historical_snapshots(
    portfolio: Portfolio,
    start_date: date,
    end_date: date,
) -> List[Portfolio]:
    """Generate historical snapshots of a portfolio for each date in range.

    Creates a clone of the portfolio for each date from start_date to end_date
    (inclusive), where each snapshot represents the portfolio state as of that date.

    Args:
        portfolio: Portfolio to generate snapshots for
        start_date: Start date for snapshot generation (inclusive)
        end_date: End date for snapshot generation (inclusive)

    Returns:
        List of Portfolio clones, one for each date in the range

    Raises:
        PortfolioError: If date range is invalid or outside portfolio's date range
    """
    # Validate date range
    if start_date > end_date:
        raise PortfolioError(
            f"start_date {start_date} is after end_date {end_date}"
        )

    # Validate date range is within portfolio's date range (if portfolio has date range)
    portfolio_start = portfolio.start_date
    portfolio_end = portfolio.end_date

    if portfolio_start is not None and start_date < portfolio_start:
        raise PortfolioError(
            f"start_date {start_date} is before portfolio's start_date {portfolio_start}"
        )

    if portfolio_end is not None and end_date > portfolio_end:
        raise PortfolioError(
            f"end_date {end_date} is after portfolio's end_date {portfolio_end}"
        )

    # Generate snapshots for each date in range
    snapshots: List[Portfolio] = []
    current_date = start_date

    while current_date <= end_date:
        # Clone portfolio with end_date set to current_date
        snapshot = portfolio.clone(start_date=None, end_date=current_date)
        snapshots.append(snapshot)
        current_date += timedelta(days=1)

    logger.info(
        f"Generated {len(snapshots)} historical snapshots for portfolio '{portfolio.name}' "
        f"from {start_date} to {end_date}"
    )

    return snapshots
def get_historical_performance(
    portfolio: Portfolio,
    price_service: "PriceService",
    start_date: date,
    end_date: date,
) -> List[PortfolioHistoryPoint]:
    """Get historical performance of a portfolio over a date range.

    Returns a list of history points, one for each day from start_date to end_date
    (inclusive). Each history point contains the total market value of the portfolio
    and asset positions (quantity * historical price) for each asset on that date.

    For assets that exist in the final portfolio but were purchased after the start date,
    history points before the asset purchase will show a position of 0.0. For composite
    portfolios, asset positions from sub-portfolios with the same ticker are merged.

    This implementation calculates historical performance by filtering trades directly
    instead of creating portfolio snapshots, and fetches all prices upfront in batch
    for better performance.

    Args:
        portfolio: Portfolio to analyze (SimplePortfolio or CompositePortfolio)
        price_service: Price service for retrieving historical prices
        start_date: Start date for performance tracking (inclusive)
        end_date: End date for performance tracking (inclusive)

    Returns:
        List of PortfolioHistoryPoint objects, one for each day from start_date to end_date

    Raises:
        PortfolioError: If date range is invalid or outside portfolio's date range
        ValueError: If historical prices cannot be retrieved for any required assets
    """
    logger.info(
        f"Calculating historical performance for portfolio '{portfolio.name}' "
        f"from {start_date} to {end_date}"
    )

    # Validate date range
    if start_date > end_date:
        raise PortfolioError(
            f"start_date {start_date} is after end_date {end_date}"
        )

    # Get all assets that exist in the final portfolio state
    # This ensures we track all assets even if they weren't purchased by start_date
    final_positions = portfolio.get_positions()
    all_assets = list(final_positions.keys())

    # Note: We allow flexible date ranges:
    # - start_date can be before portfolio_start (assets will show 0.0 positions before purchase)
    # - end_date can be after portfolio_end (we can calculate performance for dates after trades,
    #   showing current positions as of those dates)
    # This allows users to analyze performance across any date range, even extending beyond
    # the portfolio's actual trade date range

    # Create a mapping of asset to ticker for quick lookup
    asset_to_ticker = {asset: asset.ticker for asset in all_assets}

    # Group assets by asset type for efficient batch price fetching
    assets_by_type: Dict[str, List[Asset]] = {}
    for asset in all_assets:
        asset_type = asset.asset_type
        if asset_type not in assets_by_type:
            assets_by_type[asset_type] = []
        assets_by_type[asset_type].append(asset)

    # Get all trades once (works for both SimplePortfolio and CompositePortfolio)
    all_trades = portfolio.get_all_trades()

    # Fetch all prices upfront for the entire date range (batch fetch by asset type)
    # Structure: Dict[asset_type, Dict[ticker, Dict[date, price]]]
    all_prices_by_type: Dict[str, Dict[str, Dict[date, float]]] = {}

    for asset_type, asset_list in assets_by_type.items():
        tickers = [asset.ticker for asset in asset_list]
        if not tickers:
            continue
        
        try:
            # Fetch prices for entire date range in a single batch call
            prices = price_service.get_historical_prices(
                tickers, asset_type, start_date, end_date
            )
            all_prices_by_type[asset_type] = prices
        except ValueError as e:
            logger.error(
                f"Failed to retrieve historical prices for {asset_type} assets "
                f"from {start_date} to {end_date}: {e}"
            )
            raise ValueError(
                f"Historical prices unavailable for {asset_type} assets from {start_date} to {end_date}: {e}"
            ) from e

    # Generate history points for each date in range
    history_points: List[PortfolioHistoryPoint] = []
    current_date = start_date

    while current_date <= end_date:
        # Filter trades directly by date (instead of cloning portfolio)
        # Only include trades up to and including current_date
        filtered_trades = [t for t in all_trades if t.date <= current_date]

        # Calculate positions from filtered trades using calculate_fifo_cost_basis
        # This avoids creating portfolio snapshots
        snapshot_positions = calculate_fifo_cost_basis(filtered_trades)

        # Initialize asset positions dictionary with all assets from final portfolio
        # This ensures all assets are present even if not purchased by current_date
        asset_positions: Dict[str, float] = {
            asset_to_ticker[asset]: 0.0 for asset in all_assets
        }

        # Look up prices from pre-fetched data
        prices_by_ticker: Dict[str, float] = {}

        # Look up prices for all assets with positions on current_date
        # Iterate through assets with positions directly to ensure we get prices for all of them
        for asset in all_assets:
            if asset in snapshot_positions and snapshot_positions[asset].quantity > 0:
                asset_type = asset.asset_type
                ticker = asset_to_ticker[asset]
                
                # Skip if we already have a price for this ticker (in case of duplicates)
                if ticker in prices_by_ticker:
                    continue
                
                # Get prices for this asset type from pre-fetched data
                if asset_type not in all_prices_by_type:
                    continue

                type_prices = all_prices_by_type[asset_type]
                
                if ticker in type_prices:
                    ticker_prices = type_prices[ticker]

                    # Find price for current_date (or most recent available up to current_date)
                    if current_date in ticker_prices:
                        prices_by_ticker[ticker] = ticker_prices[current_date]
                    else:
                        # Find most recent date <= current_date
                        available_dates = [d for d in ticker_prices.keys() if d <= current_date]
                        if available_dates:
                            most_recent_date = max(available_dates)
                            prices_by_ticker[ticker] = ticker_prices[most_recent_date]

        # Check if all required prices were retrieved (only for assets with positions)
        missing_prices = []
        for asset in all_assets:
            # Only require prices for assets that have positions on this date
            if asset in snapshot_positions and snapshot_positions[asset].quantity > 0:
                ticker = asset_to_ticker[asset]
                if ticker not in prices_by_ticker:
                    missing_prices.append(ticker)

        if missing_prices:
            raise ValueError(
                f"Historical prices unavailable for tickers on {current_date}: {', '.join(missing_prices)}"
            )

        # Calculate asset positions: quantity * price for each asset
        total_market_value = 0.0
        asset_prices: Dict[str, float] = {}

        for asset in all_assets:
            ticker = asset_to_ticker[asset]
            position = snapshot_positions.get(asset)

            if position is not None and position.quantity > 0:
                # Asset has a position in the snapshot
                price = prices_by_ticker.get(ticker)
                if price is None:
                    continue
                position_value = float(position.quantity) * price
                asset_positions[ticker] = position_value
                asset_prices[ticker] = price
                total_market_value += position_value
            else:
                # Asset not yet purchased or fully sold - position already set to 0.0
                asset_positions[ticker] = 0.0
                # Include price even if position is 0 (for consistency, use price from prices_by_ticker if available)
                if ticker in prices_by_ticker:
                    asset_prices[ticker] = prices_by_ticker[ticker]

        # For composite portfolios, calculate_fifo_cost_basis correctly merges positions
        # for the same asset across all trades (from all sub-portfolios), since it groups
        # by Asset (ticker + asset_type). This is functionally equivalent to get_positions()
        # on a cloned CompositePortfolio.

        # Create history point
        history_point = PortfolioHistoryPoint(
            date=current_date,
            total_market_value=total_market_value,
            asset_positions=asset_positions.copy(),
            prices=asset_prices.copy(),
        )
        history_points.append(history_point)

        # Move to next day
        current_date += timedelta(days=1)

    logger.info(
        f"Generated {len(history_points)} history points for portfolio '{portfolio.name}' "
        f"from {start_date} to {end_date}"
    )

    return history_points


def get_historical_allocations(
    portfolio: Portfolio,
    price_service: "PriceService",
    start_date: date,
    end_date: date,
) -> List[Dict[Asset, Decimal]]:
    """Get historical percentage allocations of asset positions over a date range.

    Returns a list of allocation dictionaries, one for each day from start_date to end_date
    (inclusive). Each dictionary maps Asset to Decimal percentage allocation (2 decimal places).
    Allocations are calculated as (asset position value / total portfolio market value) * 100.

    This function leverages `get_historical_performance()` to reuse batch price retrieval
    for efficiency.

    Args:
        portfolio: Portfolio to analyze (SimplePortfolio or CompositePortfolio)
        price_service: Price service for retrieving historical prices
        start_date: Start date for allocation tracking (inclusive)
        end_date: End date for allocation tracking (inclusive)

    Returns:
        List of dictionaries, one per date, mapping Asset to Decimal percentage allocation

    Raises:
        PortfolioError: If date range is invalid or outside portfolio's date range
        ValueError: If historical prices cannot be retrieved for any required assets
    """
    logger.info(
        f"Calculating historical allocations for portfolio '{portfolio.name}' "
        f"from {start_date} to {end_date}"
    )

    # Get historical performance data (reuses batch price retrieval)
    history_points = get_historical_performance(portfolio, price_service, start_date, end_date)

    # Get final portfolio positions to establish ticker-to-Asset mapping
    final_positions = portfolio.get_positions()
    ticker_to_asset: Dict[str, Asset] = {asset.ticker: asset for asset in final_positions.keys()}

    # Calculate allocations for each history point
    allocations_list: List[Dict[Asset, Decimal]] = []
    
    for history_point in history_points:
        allocations: Dict[Asset, Decimal] = {}
        total_market_value = Decimal(str(history_point.total_market_value))
        
        # Guard clause: zero total market value
        if total_market_value == 0:
            # Return empty allocations for all assets
            for asset in final_positions.keys():
                allocations[asset] = Decimal('0.00')
            allocations_list.append(allocations)
            continue
        
        # Calculate allocation for each asset
        for ticker, position_value in history_point.asset_positions.items():
            # Map ticker to Asset object
            if ticker not in ticker_to_asset:
                logger.debug(f"Ticker {ticker} not found in final positions, skipping")
                continue
            
            asset = ticker_to_asset[ticker]
            position_value_decimal = Decimal(str(position_value))
            
            # Calculate percentage: (position_value / total_market_value) * 100
            allocation = (position_value_decimal / total_market_value) * Decimal('100')
            
            # Round to 2 decimal places
            allocation = allocation.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            allocations[asset] = allocation
        
        # Ensure all assets from final portfolio are included (set to 0.00 if not present)
        for asset in final_positions.keys():
            if asset not in allocations:
                allocations[asset] = Decimal('0.00')
        
        allocations_list.append(allocations)
    
    logger.info(
        f"Generated {len(allocations_list)} allocation dictionaries for portfolio '{portfolio.name}' "
        f"from {start_date} to {end_date}"
    )
    
    return allocations_list


def get_positions_with_allocations(
    portfolio: Portfolio,
    prices: Dict[Asset, Optional[float]],
) -> Dict[Asset, Tuple[Position, Decimal]]:
    """Get positions and their percentage allocations combined in a single dictionary.

    This utility function combines results from `get_positions()` and `get_all_allocations()`
    for convenience.

    Args:
        portfolio: Portfolio to analyze (SimplePortfolio or CompositePortfolio)
        prices: Dictionary mapping Asset to current price (None if unavailable)

    Returns:
        Dictionary mapping Asset to tuple of (Position, allocation_percentage)
        Only includes assets that have both a position and an allocation
    """
    positions = portfolio.get_positions()
    allocations = portfolio.get_all_allocations(prices)
    
    # Combine positions and allocations
    result: Dict[Asset, Tuple[Position, Decimal]] = {}
    
    for asset in positions.keys():
        if asset in allocations:
            result[asset] = (positions[asset], allocations[asset])
    
    logger.debug(
        f"Combined {len(result)} positions with allocations for portfolio '{portfolio.name}'"
    )
    
    return result


def get_historical_positions_with_allocations(
    portfolio: Portfolio,
    price_service: "PriceService",
    start_date: date,
    end_date: date,
) -> List[Dict[Asset, Tuple[float, Decimal]]]:
    """Get historical positions and their percentage allocations combined.

    This utility function combines results from `get_historical_performance()` and
    `get_historical_allocations()` for convenience. Returns position values (floats)
    and allocation percentages (Decimals) for each date in the range.

    Args:
        portfolio: Portfolio to analyze (SimplePortfolio or CompositePortfolio)
        price_service: Price service for retrieving historical prices
        start_date: Start date for tracking (inclusive)
        end_date: End date for tracking (inclusive)

    Returns:
        List of dictionaries, one per date, mapping Asset to tuple of
        (position_value, allocation_percentage)
        Only includes assets that appear in both position values and allocations

    Raises:
        PortfolioError: If date range is invalid or outside portfolio's date range
        ValueError: If historical prices cannot be retrieved for any required assets
    """
    # Get historical performance and allocations (reuses batch price retrieval)
    history_points = get_historical_performance(portfolio, price_service, start_date, end_date)
    allocations_list = get_historical_allocations(portfolio, price_service, start_date, end_date)
    
    # Get final portfolio positions to establish ticker-to-Asset mapping
    final_positions = portfolio.get_positions()
    ticker_to_asset: Dict[str, Asset] = {asset.ticker: asset for asset in final_positions.keys()}
    
    # Combine position values and allocations for each date
    result: List[Dict[Asset, Tuple[float, Decimal]]] = []
    
    for i, history_point in enumerate(history_points):
        allocations = allocations_list[i]
        combined: Dict[Asset, Tuple[float, Decimal]] = {}
        
        # Combine position values (from history_point.asset_positions) with allocations
        for ticker, position_value in history_point.asset_positions.items():
            # Map ticker to Asset object
            if ticker not in ticker_to_asset:
                logger.debug(f"Ticker {ticker} not found in final positions, skipping")
                continue
            
            asset = ticker_to_asset[ticker]
            
            # Only include if asset has an allocation
            if asset in allocations:
                combined[asset] = (position_value, allocations[asset])
        
        result.append(combined)
    
    logger.debug(
        f"Combined {len(result)} historical position/allocation dictionaries for portfolio '{portfolio.name}' "
        f"from {start_date} to {end_date}"
    )
    
    return result

