"""Cache utilities for WPM library."""

from collections import OrderedDict
from typing import Dict, List, Optional, TypeVar, Generic

from wpm.models import Trade

T = TypeVar('T')


class LRUCache(Generic[T]):
    """Simple LRU cache implementation using OrderedDict.

    Provides thread-safe-like operations for single-threaded use cases.
    For multi-threaded scenarios, external synchronization would be needed.
    """

    def __init__(self, maxsize: int = 128):
        """Initialize LRU cache.

        Args:
            maxsize: Maximum number of entries in the cache
        """
        self._cache: OrderedDict = OrderedDict()
        self._maxsize = maxsize

    def get(self, key) -> Optional[T]:
        """Get value from cache, moving it to end (most recently used).

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key, value: T) -> None:
        """Set value in cache, implementing LRU eviction if needed.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = value
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return number of entries in cache."""
        return len(self._cache)


def trades_to_cache_key(trades: List[Trade]) -> tuple:
    """Convert trades list to hashable tuple for cache key.

    Args:
        trades: List of Trade objects

    Returns:
        Hashable tuple representation of trades
    """
    return tuple(
        (
            t.date,
            t.asset.ticker,
            t.asset.asset_type,
            t.action,
            t.broker,
            t.quantity,
            t.price,
            t.split_adjustment_factor,
        )
        for t in sorted(trades, key=lambda t: (t.date, id(t)))
    )


def trades_to_cache_key_with_filters(
    trades: List[Trade], asset_type: Optional[str] = None, tickers: Optional[List[str]] = None
) -> tuple:
    """Convert trades list and filters to hashable tuple for cache key.

    Args:
        trades: List of Trade objects
        asset_type: Optional asset type filter
        tickers: Optional tickers filter

    Returns:
        Hashable tuple representation
    """
    trades_key = trades_to_cache_key(trades)
    tickers_key = tuple(sorted(tickers)) if tickers else None
    return (trades_key, asset_type, tickers_key)

