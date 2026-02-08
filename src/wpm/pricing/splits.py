"""Stock split data retrieval and adjustment factor calculation."""

import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from wpm.config import Config

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
    """Service for retrieving stock split data and calculating adjustment factors.

    Uses a file-based Parquet cache with daily validity. Cache is valid when:
    - File mtime is on the same calendar day as now
    - All requested tickers are present in the cache

    If cache is invalid or any ticker is missing, a full batch fetch from yfinance
    is performed and the cache is refreshed.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize SplitService with file-based cache.

        Args:
            cache_file: Path to Parquet cache file (default: Config.SPLIT_CACHE_FILE)
        """
        self.cache_file = cache_file or Config.SPLIT_CACHE_FILE
        self._split_cache: Dict[str, pd.Series] = {}
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        cache_dir = self.cache_file.parent
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created cache directory: {cache_dir}")

    def _load_from_file(self) -> None:
        """Load split cache from Parquet file into _split_cache."""
        if not self.cache_file.exists():
            logger.debug("Split cache file does not exist")
            self._split_cache = {}
            return

        try:
            df = pd.read_parquet(self.cache_file)
            if df.empty:
                self._split_cache = {}
                return

            if "split_date" in df.columns:
                df["split_date"] = pd.to_datetime(df["split_date"]).dt.date

            self._split_cache = {}
            for ticker in df["ticker"].unique():
                ticker_df = df[df["ticker"] == ticker]
                if ticker_df.empty:
                    self._split_cache[ticker] = pd.Series(dtype=float)
                else:
                    dates = pd.to_datetime(ticker_df["split_date"])
                    series = pd.Series(
                        ticker_df["split_ratio"].values,
                        index=dates,
                    )
                    self._split_cache[ticker] = series

            logger.info(
                f"Loaded split cache from {self.cache_file} with {len(self._split_cache)} tickers"
            )
        except Exception as e:
            logger.warning(f"Error loading split cache: {e}. Starting with empty cache.")
            self._split_cache = {}

    def _save_to_file(self) -> None:
        """Save _split_cache to Parquet file."""
        if not self._split_cache:
            return

        rows = []
        for ticker, series in self._split_cache.items():
            if series is not None and not series.empty:
                for ts, ratio in series.items():
                    d = ts.date() if isinstance(ts, pd.Timestamp) else ts
                    rows.append({"ticker": ticker, "split_date": d, "split_ratio": float(ratio)})

        if not rows:
            return

        try:
            df = pd.DataFrame(rows)
            df.to_parquet(self.cache_file, index=False)
            logger.debug(f"Saved split cache to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Error saving split cache: {e}")

    def _is_cache_valid_for_tickers(self, tickers: List[str]) -> bool:
        """Check if file cache is valid for the requested tickers.

        Valid when: file exists, mtime is today, and all tickers are in cache.
        """
        if not tickers:
            return True
        if not self.cache_file.exists():
            return False
        mtime = datetime.fromtimestamp(self.cache_file.stat().st_mtime)
        if mtime.date() != date.today():
            return False
        if not self._split_cache:
            self._load_from_file()
        return all(t in self._split_cache for t in tickers)

    def ensure_splits_loaded(self, tickers: List[str]) -> None:
        """Ensure split data is loaded for all tickers.

        Call once at import start. At most one file load or yfinance fetch per run.
        If cache is valid and has all tickers, loads from file. Otherwise batch
        fetches from yfinance and saves to file.

        Args:
            tickers: List of Stock/ETF ticker symbols
        """
        if not tickers:
            return

        if self._is_cache_valid_for_tickers(tickers):
            logger.debug(
                f"Split cache valid for {len(tickers)} tickers, using cached data"
            )
            return

        logger.info(
            f"Split cache invalid or missing tickers, batch fetching from yfinance for {len(tickers)} tickers"
        )
        self._fetch_and_cache(tickers)

    def _fetch_and_cache(self, tickers: List[str]) -> None:
        """Batch fetch from yfinance and update cache and file."""
        try:
            tickers_obj = yf.Tickers(" ".join(tickers))
            # yfinance Tickers: optional .tickers attr; getattr used for third-party API.
            tickers_dict = getattr(tickers_obj, "tickers", None)
            for t in tickers:
                try:
                    ticker_obj = tickers_dict.get(t) if tickers_dict else None
                    raw = ticker_obj.splits if ticker_obj else None
                    if raw is None or not isinstance(raw, pd.Series):
                        raw = pd.Series(dtype=float)
                    self._split_cache[t] = raw if not raw.empty else pd.Series(dtype=float)
                except Exception as e:
                    logger.warning(f"Failed to fetch splits for {t}: {e}")
                    self._split_cache[t] = pd.Series(dtype=float)
            self._save_to_file()
        except Exception as e:
            logger.warning(f"Batch fetch splits failed: {e}")
            for t in tickers:
                if t not in self._split_cache:
                    self._split_cache[t] = pd.Series(dtype=float)

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
        """Get raw split data for a batch of tickers.

        Uses in-memory cache if all tickers are present. If any ticker is missing,
        triggers a refresh (batch fetch from yfinance, update cache, save file).

        Args:
            tickers: List of Stock/ETF ticker symbols
            start_date: Optional start date to filter splits (inclusive)
            end_date: Optional end date to filter splits (inclusive)

        Returns:
            Dict mapping each ticker to a pandas Series with date index and
            split ratio values. Empty list returns {}.
        """
        if not tickers:
            return {}

        missing = [t for t in tickers if t not in self._split_cache]
        if missing:
            if not self._split_cache and self.cache_file.exists():
                self._load_from_file()
                missing = [t for t in tickers if t not in self._split_cache]
            if missing:
                self._fetch_and_cache(list(set(tickers)))

        result: Dict[str, pd.Series] = {}
        for t in tickers:
            series = self._split_cache.get(t, pd.Series(dtype=float))
            result[t] = self._filter_splits_by_date(series, start_date, end_date)
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
