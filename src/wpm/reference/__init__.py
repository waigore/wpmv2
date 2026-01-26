"""Reference portfolio module for creating baseline comparison portfolios."""

from wpm.reference.fetcher import DefaultHistoricalPriceFetcher, HistoricalPriceFetcher
from wpm.reference.portfolio import create_reference_portfolio
from wpm.reference.strategy import BuyAndHoldStrategy, ReferenceStrategy

__all__ = [
    "ReferenceStrategy",
    "BuyAndHoldStrategy",
    "create_reference_portfolio",
    "HistoricalPriceFetcher",
    "DefaultHistoricalPriceFetcher",
]
