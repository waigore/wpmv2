"""Stock split data retrieval and adjustment factor calculation."""

import logging
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def compute_cumulative_split_factor_from_splits(
    splits: pd.Series,
    trade_date: date,
    current_date: Optional[date] = None,
) -> Decimal:
    """Compute cumulative split adjustment factor from an existing splits Series.

    Pure function: no I/O, no cache access. Use with pre-fetched split data to
    avoid repeated service/cache calls (e.g. one get_splits per ticker at import).

    The factor is the product of all split ratios for splits that occurred
    strictly after trade_date and up to current_date (inclusive).

    Args:
        splits: pandas Series with date index and split ratio values (e.g. from
            SplitService.get_splits). Can be unfiltered or pre-filtered by date.
        trade_date: Date of the trade (splits after this date are included).
        current_date: Optional end date; only splits on or before this date are
            included. If None, all splits after trade_date are included.

    Returns:
        Decimal cumulative factor (default Decimal('1.0') if no relevant splits).
    """
    if splits is None or splits.empty:
        return Decimal('1.0')
    split_dates = pd.Series([ts.date() for ts in splits.index], index=splits.index)
    mask = split_dates > trade_date
    if current_date is not None:
        mask = mask & (split_dates <= current_date)
    relevant_splits = splits[mask]
    if relevant_splits.empty:
        return Decimal('1.0')
    return Decimal(str(float(relevant_splits.prod())))


class SplitService:
    """Service for retrieving stock split data and calculating adjustment factors."""

    def __init__(self):
        """Initialize SplitService with internal cache for split data."""
        # Cache for split data: ticker -> pd.Series of splits
        self._split_cache: Dict[str, pd.Series] = {}

    def _filter_splits_by_date(
        self,
        splits: pd.Series,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.Series:
        """Apply start_date/end_date filter to a splits Series (in place logic)."""
        if splits is None or splits.empty:
            return splits.copy() if splits is not None else pd.Series(dtype=float)
        if start_date is None and end_date is None:
            return splits.copy()
        split_dates = pd.Series([ts.date() for ts in splits.index], index=splits.index)
        out = splits
        if start_date is not None:
            out = out[split_dates >= start_date]
            split_dates = split_dates[split_dates >= start_date]
        if end_date is not None:
            out = out[split_dates <= end_date]
        return out

    def get_splits(
        self,
        tickers: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, pd.Series]:
        """Get raw split data from yfinance for a batch of tickers.

        Retrieval (cache and yfinance) is done in one batch to avoid N+1 calls.
        Each requested ticker appears exactly once in the returned dict; on
        fetch error or no data, that ticker gets an empty Series.

        Args:
            tickers: List of Stock/ETF ticker symbols
            start_date: Optional start date to filter splits (inclusive)
            end_date: Optional end date to filter splits (inclusive)

        Returns:
            Dict mapping each ticker to a pandas Series with date index and
            split ratio values. Empty list returns {}.

        Note:
            Split ratios are stored as-is from yfinance:
            - Forward split (2:1) = 2.0
            - Reverse split (1:2) = 0.5
        """
        if not tickers:
            return {}

        # Partition into cached vs uncached
        result: Dict[str, pd.Series] = {}
        uncached: List[str] = []
        for t in tickers:
            if t in self._split_cache:
                result[t] = self._filter_splits_by_date(
                    self._split_cache[t], start_date, end_date
                )
            else:
                uncached.append(t)

        if not uncached:
            return result

        # One batch fetch for all uncached tickers via yf.Tickers
        logger.debug(f"Batch fetching split data from yfinance for {len(uncached)} tickers")
        try:
            tickers_obj = yf.Tickers(" ".join(uncached))
            # yfinance Tickers is untyped; use getattr to avoid assuming a stable public API.
            tickers_dict = getattr(tickers_obj, "tickers", None)
            for t in uncached:
                try:
                    ticker_obj = tickers_dict.get(t) if tickers_dict is not None else None
                    raw = ticker_obj.splits if ticker_obj is not None else None
                    if raw is None or not isinstance(raw, pd.Series):
                        raw = pd.Series(dtype=float)
                    if not raw.empty:
                        self._split_cache[t] = raw
                        logger.debug(f"Cached {len(raw)} splits for {t}")
                    else:
                        self._split_cache[t] = pd.Series(dtype=float)
                        logger.debug(f"No splits found for {t}")
                    result[t] = self._filter_splits_by_date(raw, start_date, end_date)
                except Exception as e:
                    logger.warning(f"Failed to fetch splits for {t}: {e}")
                    self._split_cache[t] = pd.Series(dtype=float)
                    result[t] = pd.Series(dtype=float)
        except Exception as e:
            logger.warning(f"Batch fetch splits failed: {e}. Failing each uncached ticker.")
            for t in uncached:
                if t not in result:
                    self._split_cache[t] = pd.Series(dtype=float)
                    result[t] = pd.Series(dtype=float)

        return result

    def get_cumulative_split_factor(
        self, ticker: str, trade_date: date, current_date: Optional[date] = None
    ) -> Decimal:
        """Calculate cumulative split adjustment factor for a trade.

        The factor represents the cumulative effect of all splits that occurred
        after the trade date and up to the current date.

        Args:
            ticker: Stock/ETF ticker symbol
            trade_date: Date of the trade (splits after this date are included)
            current_date: Optional end date for split calculation (default: today).
                         For historical portfolios, use the portfolio's end_date.

        Returns:
            Decimal representing cumulative split factor:
            - Factor > 1.0: Forward splits occurred (e.g., 2.0 for 2:1 split)
            - Factor < 1.0: Reverse splits occurred (e.g., 0.5 for 1:2 reverse split)
            - Factor = 1.0: No splits occurred (default)

        Note:
            For crypto assets, always returns Decimal('1.0') as crypto doesn't have splits.
            Caller should check asset type before calling this method.
        """
        try:
            splits_map = self.get_splits([ticker], start_date=trade_date, end_date=current_date)
            splits = splits_map.get(ticker, pd.Series(dtype=float))
            factor_decimal = compute_cumulative_split_factor_from_splits(
                splits, trade_date, current_date
            )
            if factor_decimal != Decimal('1.0'):
                logger.debug(
                    f"Calculated cumulative split factor for {ticker}: {factor_decimal}"
                )
            return factor_decimal
        except Exception as e:
            logger.warning(
                f"Error calculating split factor for {ticker} (trade_date={trade_date}): {e}. "
                f"Using default factor 1.0"
            )
            return Decimal('1.0')

    def clear_cache(self) -> None:
        """Clear the internal split data cache.

        Useful for testing or if split data needs to be refreshed.
        """
        self._split_cache.clear()
        logger.debug("Cleared split data cache")
