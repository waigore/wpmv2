"""Yahoo Finance price retriever implementation."""

import logging
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from wpm.pricing.base import PriceRetriever

logger = logging.getLogger(__name__)


class YahooFinanceRetriever(PriceRetriever):
    """Price retriever using yfinance for stocks and ETFs."""

    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get current price from Yahoo Finance.

        Args:
            ticker: Stock/ETF ticker symbol
            asset_type: Asset type (should be "Stock" or "ETF")

        Returns:
            Current price in USD

        Raises:
            ValueError: If price cannot be retrieved
        """
        logger.debug(f"Fetching price from Yahoo Finance for {ticker} ({asset_type})")

        try:
            ticker_obj = yf.Ticker(ticker)
            data = ticker_obj.history(period="1d", interval="1m")

            if data.empty:
                raise ValueError(f"No price data available for {ticker}")

            latest_price = data["Close"].iloc[-1]

            if pd.isna(latest_price) or latest_price <= 0:
                raise ValueError(f"Invalid price data for {ticker}")

            logger.debug(f"Retrieved price for {ticker}: ${latest_price:.2f}")
            return float(latest_price)

        except Exception as e:
            raise ValueError(f"Error fetching price for {ticker} from Yahoo Finance: {str(e)}") from e

    def _extract_price_from_ticker_data(self, ticker_data: pd.DataFrame, ticker: str) -> Optional[float]:
        """Extract price from ticker data DataFrame.

        Args:
            ticker_data: DataFrame with price data for a ticker
            ticker: Ticker symbol for logging

        Returns:
            Price if valid, None otherwise
        """
        if "Close" not in ticker_data.columns or ticker_data.empty:
            logger.warning(f"No Close price data available for {ticker}")
            return None

        latest_price = ticker_data["Close"].iloc[-1]
        if pd.isna(latest_price) or latest_price <= 0:
            logger.warning(f"Invalid price data for {ticker}")
            return None

        price = float(latest_price)
        logger.debug(f"Retrieved price for {ticker}: ${price:.2f}")
        return price

    def _process_multiindex_data(self, data: pd.DataFrame, tickers: List[str]) -> Dict[str, float]:
        """Process MultiIndex DataFrame from yfinance batch download.

        Args:
            data: DataFrame with MultiIndex columns
            tickers: List of ticker symbols

        Returns:
            Dictionary mapping ticker to price
        """
        prices: Dict[str, float] = {}

        for ticker in tickers:
            try:
                if ticker not in data.columns.levels[0]:
                    logger.warning(f"No price data available for {ticker}")
                    continue

                ticker_data = data[ticker]
                price = self._extract_price_from_ticker_data(ticker_data, ticker)
                if price is not None:
                    prices[ticker] = price
            except Exception as e:
                logger.warning(f"Error processing price for {ticker}: {str(e)}")

        return prices

    def _process_single_ticker_data(self, data: pd.DataFrame, ticker: str) -> Dict[str, float]:
        """Process single ticker DataFrame from yfinance download.

        Args:
            data: DataFrame with single-level columns
            ticker: Ticker symbol

        Returns:
            Dictionary mapping ticker to price
        """
        prices: Dict[str, float] = {}

        if not ticker:
            return prices

        try:
            price = self._extract_price_from_ticker_data(data, ticker)
            if price is not None:
                prices[ticker] = price
        except Exception as e:
            logger.warning(f"Error processing price for {ticker}: {str(e)}")

        return prices

    def get_prices(self, tickers: List[str], asset_type: str) -> Dict[str, float]:
        """Get current prices from Yahoo Finance for multiple tickers in a single batch request.

        Args:
            tickers: List of stock/ETF ticker symbols
            asset_type: Asset type (should be "Stock" or "ETF")

        Returns:
            Dictionary mapping ticker to price. Only includes successfully retrieved prices.
        """
        logger.debug(f"Batch fetching prices from Yahoo Finance for {len(tickers)} {asset_type} assets")

        if not tickers:
            return {}

        try:
            # Use yf.download for batch retrieval
            data = yf.download(tickers, period="1d", interval="1m", group_by="ticker", progress=False)

            if data.empty:
                logger.warning(f"No price data available for any of the requested tickers: {tickers}")
                return {}

            # Check if we have MultiIndex columns (multiple tickers) or single level (one ticker)
            has_multiindex = isinstance(data.columns, pd.MultiIndex)

            if has_multiindex:
                return self._process_multiindex_data(data, tickers)

            # Single ticker: columns are single level
            ticker = tickers[0]
            return self._process_single_ticker_data(data, ticker)

        except Exception as e:
            logger.warning(f"Error in batch price retrieval from Yahoo Finance: {str(e)}")
            return {}

