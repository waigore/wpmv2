"""Yahoo Finance price retriever implementation."""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import pytz
import yfinance as yf

from wpm.currency import CurrencyService
from wpm.pricing.base import PriceRetriever
from wpm.utils import is_within_trading_hours

logger = logging.getLogger(__name__)


class YahooFinanceRetriever(PriceRetriever):
    """Price retriever using yfinance for stocks and ETFs."""

    # Crypto ticker mapping for yfinance
    # Some crypto tickers have different names in yfinance
    _CRYPTO_TICKER_MAP = {
        "SUI-USD": "SUI20947-USD",
        # Add more mappings as needed
    }

    @property
    def metadata_supported(self) -> bool:
        """Whether this retriever supports metadata retrieval.

        Returns:
            True - Yahoo Finance retriever supports metadata retrieval
        """
        return True

    def __init__(self, currency_service: CurrencyService = None):
        """Initialize Yahoo Finance retriever.

        Args:
            currency_service: CurrencyService instance (default: creates new instance)
        """
        self.currency_service = currency_service or CurrencyService()

    def _map_crypto_ticker(self, ticker: str) -> str:
        """Map crypto ticker to yfinance ticker format.
        
        Args:
            ticker: Original crypto ticker (e.g., "SUI-USD")
        
        Returns:
            yfinance ticker (e.g., "SUI20947-USD") or original if no mapping exists
        """
        return self._CRYPTO_TICKER_MAP.get(ticker, ticker)

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
                native_price = self._extract_realtime_price(ticker_obj, ticker, asset_type)
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

    def _extract_realtime_price(self, ticker_obj: yf.Ticker, ticker: str, asset_type: str = "Stock") -> Optional[float]:
        """Extract real-time price from ticker.info dict.

        Args:
            ticker_obj: yfinance Ticker object
            ticker: Ticker symbol for logging
            asset_type: Asset type (unused, kept for compatibility)

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

    def _extract_prices_from_dataframe(
        self, data: pd.DataFrame, yfinance_ticker: str, ticker: str
    ) -> pd.Series:
        """Extract price series from DataFrame using guard clauses to avoid nested conditionals.

        Args:
            data: DataFrame from yf.download (may have MultiIndex or single-level columns)
            yfinance_ticker: Ticker symbol as used in yfinance
            ticker: Original ticker symbol for error messages

        Returns:
            Price series (pd.Series)

        Raises:
            ValueError: If no Close price data is available
        """
        # Handle MultiIndex columns (crypto data often has structure like [('Close', 'BTC-USD'), ...])
        if not isinstance(data.columns, pd.MultiIndex):
            # Single column case - use guard clauses
            if "Close" in data.columns:
                return data["Close"]
            if "Adj Close" in data.columns:
                return data["Adj Close"]
            raise ValueError(f"No Close price data available for {ticker}")

        # MultiIndex case - check if ticker is in level 1 (Ticker level)
        if yfinance_ticker in data.columns.levels[1]:
            if ('Adj Close', yfinance_ticker) in data.columns:
                return data[('Adj Close', yfinance_ticker)]
            if ('Close', yfinance_ticker) in data.columns:
                return data[('Close', yfinance_ticker)]
            raise ValueError(f"No Close price data available for {ticker}. Available columns: {data.columns}")

        # Check if ticker is in level 0 (Price level) - less common but possible
        if yfinance_ticker in data.columns.levels[0]:
            ticker_data = data[yfinance_ticker]
            if "Close" in ticker_data.columns:
                return ticker_data["Close"]
            if "Adj Close" in ticker_data.columns:
                return ticker_data["Adj Close"]
            raise ValueError(f"No Close price data available for {ticker}. Available columns: {data.columns}")

        # Ticker not found in either level
        raise ValueError(f"No Close price data available for {ticker}. Available columns: {data.columns}")

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

    def _process_historical_multiindex_data(
        self, data: pd.DataFrame, tickers: List[str], start_date: date, end_date: date
    ) -> Dict[str, pd.DataFrame]:
        """Process MultiIndex DataFrame from yfinance batch historical download.

        Args:
            data: DataFrame with MultiIndex columns (group_by='ticker')
            tickers: List of ticker symbols
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Dictionary mapping ticker to DataFrame with date index and price column
        """
        result: Dict[str, pd.DataFrame] = {}

        for ticker in tickers:
            try:
                if ticker not in data.columns.levels[0]:
                    logger.warning(f"No historical price data available for {ticker}")
                    continue

                ticker_data = data[ticker]
                if ticker_data.empty:
                    logger.warning(f"No historical price data for {ticker}")
                    continue

                # Extract Close prices (or Adj Close if available)
                if "Close" in ticker_data.columns:
                    prices = ticker_data["Close"]
                elif "Adj Close" in ticker_data.columns:
                    prices = ticker_data["Adj Close"]
                else:
                    logger.warning(f"No Close price data available for {ticker}")
                    continue

                # Convert to DataFrame with date index
                result_df = pd.DataFrame({"price": prices})
                result_df.index.name = "date"

                # Forward fill to handle missing trading days
                date_range = pd.date_range(start=start_date, end=end_date, freq="D")
                result_df = result_df.reindex(date_range, method="ffill")

                result[ticker] = result_df

                logger.debug(
                    f"Retrieved {len(result_df)} historical prices for {ticker} "
                    f"from {start_date} to {end_date}"
                )
            except Exception as e:
                logger.warning(f"Error processing historical prices for {ticker}: {str(e)}")

        return result

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
                    price = self._extract_realtime_price(ticker_obj, ticker, asset_type)
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

    def get_historical_prices(
        self, ticker: Union[str, List[str]], asset_type: str, start_date: date, end_date: date
    ) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """Get historical prices from Yahoo Finance over a date range.

        Supports both single ticker and batch ticker fetching.

        Args:
            ticker: Stock/ETF/Crypto ticker symbol (str) or list of ticker symbols (List[str])
            asset_type: Asset type (should be "Stock", "ETF", or "Crypto")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            If ticker is str: DataFrame with date index and price column (native currency, USD for crypto)
            If ticker is List[str]: Dictionary mapping ticker to DataFrame with date index and price column

        Raises:
            ValueError: If prices cannot be retrieved
        """
        # Handle single ticker (backward compatibility)
        if isinstance(ticker, str):
            return self._get_historical_prices_single(ticker, asset_type, start_date, end_date)

        # Handle batch tickers
        if not ticker:
            return {}

        logger.debug(
            f"Batch fetching historical prices from Yahoo Finance for {len(ticker)} {asset_type} assets "
            f"from {start_date} to {end_date}"
        )

        try:
            # Map crypto tickers to yfinance format if needed
            yfinance_tickers = []
            ticker_mapping: Dict[str, str] = {}  # Maps yfinance ticker to original ticker
            for orig_ticker in ticker:
                if asset_type == "Crypto":
                    yfinance_ticker = self._map_crypto_ticker(orig_ticker)
                    if yfinance_ticker != orig_ticker:
                        logger.debug(f"Mapped crypto ticker {orig_ticker} to {yfinance_ticker} for yfinance")
                    # Store mapping: yfinance_ticker -> orig_ticker
                    ticker_mapping[yfinance_ticker] = orig_ticker
                    yfinance_tickers.append(yfinance_ticker)
                else:
                    yfinance_tickers.append(orig_ticker)
                    ticker_mapping[orig_ticker] = orig_ticker

            # Use yf.download with start and end dates, group_by='ticker' for batch
            data = yf.download(
                yfinance_tickers,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
                actions=False,
                group_by="ticker",
            )

            # Handle case where yf.download returns None
            if data is None:
                raise ValueError(f"No historical price data available for tickers: {ticker}")

            if data.empty:
                raise ValueError(f"No historical price data available for tickers: {ticker}")

            # Process MultiIndex DataFrame with group_by='ticker'
            result = self._process_historical_multiindex_data(data, yfinance_tickers, start_date, end_date)

            # Map back to original tickers if crypto mapping was used
            # ticker_mapping maps yfinance_ticker -> orig_ticker
            if asset_type == "Crypto" and ticker_mapping:
                mapped_result: Dict[str, pd.DataFrame] = {}
                for yf_ticker, df in result.items():
                    # Look up original ticker for this yfinance ticker
                    orig_ticker = ticker_mapping.get(yf_ticker, yf_ticker)
                    mapped_result[orig_ticker] = df
                result = mapped_result

            return result

        except Exception as e:
            raise ValueError(
                f"Error fetching historical prices for tickers {ticker} from Yahoo Finance: {str(e)}"
            ) from e

    def _get_historical_prices_single(
        self, ticker: str, asset_type: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Get historical prices for a single ticker (internal helper).

        Args:
            ticker: Stock/ETF/Crypto ticker symbol
            asset_type: Asset type (should be "Stock", "ETF", or "Crypto")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            DataFrame with date index and price column (native currency, USD for crypto)

        Raises:
            ValueError: If prices cannot be retrieved
        """
        logger.debug(
            f"Fetching historical prices from Yahoo Finance for {ticker} ({asset_type}) "
            f"from {start_date} to {end_date}"
        )

        try:
            # Map crypto ticker to yfinance format if needed
            yfinance_ticker = ticker
            if asset_type == "Crypto":
                yfinance_ticker = self._map_crypto_ticker(ticker)
                if yfinance_ticker != ticker:
                    logger.debug(f"Mapped crypto ticker {ticker} to {yfinance_ticker} for yfinance")

            # Use yf.download with start and end dates
            data = yf.download(
                yfinance_ticker,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
                actions=False,
            )

            # Handle case where yf.download returns None
            if data is None:
                raise ValueError(f"No historical price data available for {ticker}")

            if data.empty:
                raise ValueError(f"No historical price data available for {ticker}")

            # Extract Close prices (adjusted close when auto_adjust=True)
            # yf.download can return different structures depending on the data
            prices = self._extract_prices_from_dataframe(data, yfinance_ticker, ticker)

            # Convert to DataFrame with date index
            result_df = pd.DataFrame({"price": prices})
            result_df.index.name = "date"

            # Forward fill to handle missing trading days
            date_range = pd.date_range(start=start_date, end=end_date, freq="D")
            result_df = result_df.reindex(date_range, method="ffill")

            logger.debug(
                f"Retrieved {len(result_df)} historical prices for {ticker} "
                f"from {start_date} to {end_date}"
            )

            return result_df

        except Exception as e:
            raise ValueError(
                f"Error fetching historical prices for {ticker} from Yahoo Finance: {str(e)}"
            ) from e

    def _extract_metadata_from_info(
        self, info: Dict[str, Any], ticker: str, asset_type: str
    ) -> Dict[str, Any]:
        """Extract and normalize metadata from yfinance .info dict.

        Args:
            info: yfinance .info dictionary
            ticker: Asset ticker (for fallback)
            asset_type: Asset type

        Returns:
            Normalized metadata dictionary
        """
        metadata: Dict[str, Any] = {}

        # Name: longName or shortName or name or ticker (fallback)
        metadata["name"] = (
            info.get("longName")
            or info.get("shortName")
            or info.get("name")
            or ticker
        )

        # Sector, industry, country (equities only, fallback to "N/A")
        if asset_type in ("Stock", "ETF"):
            metadata["sector"] = info.get("sector", "N/A")
            metadata["industry"] = info.get("industry", "N/A")
            metadata["country"] = info.get("country", "N/A")
        else:
            metadata["sector"] = "N/A"
            metadata["industry"] = "N/A"
            metadata["country"] = "N/A"

        # Market cap: marketCap or totalAssets or None (fallback)
        metadata["market_cap"] = info.get("marketCap") or info.get("totalAssets")

        # Category: category or "unknown" (fallback)
        metadata["category"] = info.get("category", "unknown")

        return metadata

    def get_metadata(self, ticker: str, asset_type: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an asset.

        Args:
            ticker: Asset ticker symbol
            asset_type: Asset type ("Stock", "ETF", or "Crypto")

        Returns:
            Metadata dictionary with keys: name, sector, industry, country, market_cap, category.
            Returns None if retrieval fails.
        """
        logger.debug(f"Retrieving metadata for {ticker} ({asset_type})")

        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            if not info or len(info) == 0:
                logger.warning(f"No metadata available for {ticker} ({asset_type})")
                return None

            metadata = self._extract_metadata_from_info(info, ticker, asset_type)
            logger.debug(f"Retrieved metadata for {ticker} ({asset_type})")
            return metadata

        except Exception as e:
            logger.warning(f"Error fetching metadata for {ticker} ({asset_type}): {e}")
            return None
