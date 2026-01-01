"""Yahoo Finance price retriever implementation."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import pytz
import yfinance as yf

from wpm.currency import CurrencyService
from wpm.pricing.base import PriceRetriever
from wpm.utils import is_within_trading_hours

logger = logging.getLogger(__name__)


class YahooFinanceRetriever(PriceRetriever):
    """Price retriever using yfinance for stocks and ETFs."""

    def __init__(self, currency_service: CurrencyService = None):
        """Initialize Yahoo Finance retriever.

        Args:
            currency_service: CurrencyService instance (default: creates new instance)
        """
        self.currency_service = currency_service or CurrencyService()

    def _detect_currency(self, ticker: str) -> str:
        """Detect currency from ticker suffix.

        Args:
            ticker: Ticker symbol (e.g., "2800.HK", "GOOG")

        Returns:
            Currency code (e.g., "HKD", "USD")
        """
        # Hong Kong stocks have .HK suffix
        if ticker.endswith(".HK"):
            return "HKD"

        # Default to USD for US stocks/ETFs
        return "USD"

    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get current price from Yahoo Finance in native currency.

        During trading hours: tries currentPrice or regularMarketPrice from ticker.info first,
        falls back to Close from historical data if unavailable.
        Outside trading hours: uses Close from historical data.

        Args:
            ticker: Stock/ETF ticker symbol
            asset_type: Asset type (should be "Stock" or "ETF")

        Returns:
            Current price in native currency (not USD)

        Raises:
            ValueError: If price cannot be retrieved
        """
        logger.debug(f"Fetching price from Yahoo Finance for {ticker} ({asset_type})")

        # Detect currency from ticker
        currency = self._detect_currency(ticker)
        logger.debug(f"Detected currency for {ticker}: {currency}")

        try:
            ticker_obj = yf.Ticker(ticker)
            now = datetime.now(pytz.UTC)
            in_trading_hours = is_within_trading_hours(now)

            native_price: Optional[float] = None

            # If within trading hours, try real-time prices first
            if in_trading_hours:
                native_price = self._extract_realtime_price(ticker_obj, ticker)
                if native_price is not None:
                    logger.debug(f"Retrieved real-time price for {ticker}: {native_price:.2f} {currency}")
                else:
                    # Fallback to Close if real-time prices unavailable
                    logger.debug(f"Real-time price unavailable for {ticker}, falling back to Close")

            # Use Close from historical data (outside hours or as fallback)
            if native_price is None:
                data = ticker_obj.history(period="1d", interval="1m")

                if data.empty:
                    raise ValueError(f"No price data available for {ticker}")

                # Find the last non-NaN Close price (some .HK tickers have NaN at the end)
                close_series = data["Close"].dropna()
                if close_series.empty:
                    raise ValueError(f"No valid Close price data available for {ticker}")

                latest_price = close_series.iloc[-1]

                if pd.isna(latest_price) or latest_price <= 0:
                    raise ValueError(f"Invalid price data for {ticker}")

                native_price = float(latest_price)
                logger.debug(f"Retrieved price for {ticker}: {native_price:.2f} {currency}")

            return native_price

        except Exception as e:
            raise ValueError(f"Error fetching price for {ticker} from Yahoo Finance: {str(e)}") from e

    def _extract_realtime_price(self, ticker_obj: yf.Ticker, ticker: str) -> Optional[float]:
        """Extract real-time price from ticker.info dict.

        Args:
            ticker_obj: yfinance Ticker object
            ticker: Ticker symbol for logging

        Returns:
            Price if valid, None otherwise
        """
        try:
            info = ticker_obj.info
            price = info.get('currentPrice')
            if price is None:
                price = info.get('regularMarketPrice')

            if price is not None and not pd.isna(price) and price > 0:
                return float(price)
        except Exception as e:
            logger.debug(f"Error extracting real-time price for {ticker}: {str(e)}")

        return None

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

        # Find the last non-NaN Close price (some .HK tickers have NaN at the end)
        close_series = ticker_data["Close"].dropna()
        if close_series.empty:
            logger.warning(f"No valid Close price data available for {ticker}")
            return None
        
        latest_price = close_series.iloc[-1]
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

    def get_prices(self, tickers: List[str], asset_type: str) -> Dict[str, float]:
        """Get current prices from Yahoo Finance for multiple tickers in a single batch request.

        Prices are returned in native currency (not USD).

        During trading hours: tries currentPrice or regularMarketPrice from ticker.info for each ticker,
        falls back to Close from batch download if unavailable.
        Outside trading hours: uses Close from batch download.

        Args:
            tickers: List of stock/ETF ticker symbols
            asset_type: Asset type (should be "Stock" or "ETF")

        Returns:
            Dictionary mapping ticker to price in native currency. Only includes successfully retrieved prices.
        """
        logger.debug(f"Batch fetching prices from Yahoo Finance for {len(tickers)} {asset_type} assets")

        if not tickers:
            return {}

        now = datetime.now(pytz.UTC)
        in_trading_hours = is_within_trading_hours(now)
        prices: Dict[str, float] = {}

        # If within trading hours, try real-time prices first
        if in_trading_hours:
            for ticker in tickers:
                try:
                    ticker_obj = yf.Ticker(ticker)
                    price = self._extract_realtime_price(ticker_obj, ticker)
                    if price is not None:
                        prices[ticker] = price
                except Exception as e:
                    logger.debug(f"Error fetching real-time price for {ticker}: {str(e)}")

        # Fetch Close prices for any tickers that don't have real-time prices
        uncached_tickers = [t for t in tickers if t not in prices]
        if uncached_tickers:
            try:
                # Use yf.download for batch retrieval
                data = yf.download(uncached_tickers, period="1d", interval="1m", group_by="ticker", progress=False)

                if not data.empty:
                    # yf.download with group_by="ticker" always returns MultiIndex columns, even for single ticker
                    close_prices = self._process_multiindex_data(data, uncached_tickers)
                    prices.update(close_prices)
                else:
                    logger.warning(f"No Close price data available for tickers: {uncached_tickers}")
            except Exception as e:
                logger.warning(f"Error in batch Close price retrieval from Yahoo Finance: {str(e)}")

        return prices

