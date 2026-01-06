"""Base class for price retrievers."""

from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, List

import pandas as pd


class PriceRetriever(ABC):
    """Abstract base class for price retrievers."""

    @abstractmethod
    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get current price for an asset.

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type ("Stock", "ETF", or "Crypto")

        Returns:
            Current price in USD

        Raises:
            ValueError: If price cannot be retrieved
        """
        pass

    @abstractmethod
    def get_prices(self, tickers: List[str], asset_type: str) -> Dict[str, float]:
        """Get current prices for multiple assets in a single batch request.

        Args:
            tickers: List of asset ticker symbols
            asset_type: Asset type for all tickers ("Stock", "ETF", or "Crypto")

        Returns:
            Dictionary mapping ticker to price. Only includes successfully retrieved prices.
            Tickers that fail are omitted from the result (caller should handle fallback).
        """
        pass

    @abstractmethod
    def get_historical_prices(
        self, ticker: str, asset_type: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Get historical prices for an asset over a date range.

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type ("Stock", "ETF", or "Crypto")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            DataFrame with date index and price column (native currency)

        Raises:
            ValueError: If prices cannot be retrieved
        """
        pass

