"""CoinGecko price retriever implementation."""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Union

import pandas as pd
from pycoingecko import CoinGeckoAPI

from wpm.config import Config
from wpm.pricing.base import PriceRetriever

logger = logging.getLogger(__name__)


class CoinGeckoRetriever(PriceRetriever):
    """Price retriever using CoinGecko API for cryptocurrencies."""

    def __init__(self, api_key: Optional[str] = None, is_demo: Optional[bool] = None):
        """Initialize CoinGecko API client.
        
        Args:
            api_key: Optional API key for CoinGecko API. If not provided, uses
                    Config.COINGECKO_API_KEY. If that is also None, uses free tier.
            is_demo: Optional flag to indicate if API key is a demo key. If not provided,
                    uses Config.COINGECKO_API_IS_DEMO.
        """
        api_key = api_key or Config.COINGECKO_API_KEY
        is_demo = is_demo if is_demo is not None else Config.COINGECKO_API_IS_DEMO
        
        if api_key:
            if is_demo:
                # Use demo API key with regular API endpoint (api.coingecko.com)
                self.client = CoinGeckoAPI(demo_api_key=api_key)
            else:
                # Use regular API key with pro API endpoint (pro-api.coingecko.com)
                self.client = CoinGeckoAPI(api_key=api_key)
        else:
            # Free tier - no API key
            self.client = CoinGeckoAPI()

    def _get_coin_id(self, ticker: str) -> str:
        """Convert ticker to CoinGecko coin ID.

        Args:
            ticker: Crypto ticker (e.g., "BTC-USD")

        Returns:
            CoinGecko coin ID (e.g., "bitcoin")
        """
        ticker_lower = ticker.lower().replace("-usd", "").replace("_usd", "")

        coin_map = {
            "btc": "bitcoin",
            "eth": "ethereum",
            "ada": "cardano",
            "dot": "polkadot",
            "sol": "solana",
            "matic": "matic-network",
            "avax": "avalanche-2",
        }

        return coin_map.get(ticker_lower, ticker_lower)

    def get_price(self, ticker: str, asset_type: str) -> float:
        """Get current price from CoinGecko.

        Args:
            ticker: Crypto ticker symbol
            asset_type: Asset type (should be "Crypto")

        Returns:
            Current price in USD

        Raises:
            ValueError: If price cannot be retrieved
        """
        logger.debug(f"Fetching price from CoinGecko for {ticker} ({asset_type})")

        try:
            coin_id = self._get_coin_id(ticker)
            data = self.client.get_price(ids=coin_id, vs_currencies="usd")

            if not data or coin_id not in data:
                raise ValueError(f"No price data available for {ticker}")

            price = data[coin_id]["usd"]

            if price <= 0:
                raise ValueError(f"Invalid price data for {ticker}")

            logger.debug(f"Retrieved price for {ticker}: ${price:.2f}")
            return float(price)

        except Exception as e:
            raise ValueError(f"Error fetching price for {ticker} from CoinGecko: {str(e)}") from e

    def _extract_price_from_coin_data(self, coin_data: Dict, ticker: str) -> Optional[float]:
        """Extract price from coin data dictionary.

        Args:
            coin_data: Dictionary with coin price data
            ticker: Ticker symbol for logging

        Returns:
            Price if valid, None otherwise
        """
        price = coin_data.get("usd")
        if not price or price <= 0:
            logger.warning(f"Invalid price data for {ticker}")
            return None

        price_float = float(price)
        logger.debug(f"Retrieved price for {ticker}: ${price_float:.2f}")
        return price_float

    def get_prices(self, tickers: List[str], asset_type: str) -> Dict[str, float]:
        """Get current prices from CoinGecko for multiple tickers in a single batch request.

        Args:
            tickers: List of crypto ticker symbols
            asset_type: Asset type (should be "Crypto")

        Returns:
            Dictionary mapping ticker to price. Only includes successfully retrieved prices.
        """
        logger.debug(f"Batch fetching prices from CoinGecko for {len(tickers)} {asset_type} assets")

        if not tickers:
            return {}

        try:
            # Convert all tickers to coin IDs and maintain mapping
            coin_id_to_ticker: Dict[str, str] = {}
            coin_ids: List[str] = []

            for ticker in tickers:
                coin_id = self._get_coin_id(ticker)
                coin_id_to_ticker[coin_id] = ticker
                coin_ids.append(coin_id)

            # Batch API call with comma-separated coin IDs
            data = self.client.get_price(ids=",".join(coin_ids), vs_currencies="usd")

            if not data:
                logger.warning(f"No price data available for any of the requested tickers: {tickers}")
                return {}

            # Map results back to original tickers
            prices: Dict[str, float] = {}
            for coin_id, ticker in coin_id_to_ticker.items():
                try:
                    if coin_id not in data:
                        logger.warning(f"No price data available for {ticker} (coin_id: {coin_id})")
                        continue

                    coin_data = data[coin_id]
                    price = self._extract_price_from_coin_data(coin_data, ticker)
                    if price is not None:
                        prices[ticker] = price
                except Exception as e:
                    logger.warning(f"Error processing price for {ticker}: {str(e)}")

            return prices

        except Exception as e:
            logger.warning(f"Error in batch price retrieval from CoinGecko: {str(e)}")
            return {}

    def get_historical_prices(
        self, ticker: Union[str, List[str]], asset_type: str, start_date: date, end_date: date
    ) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """Get historical prices from CoinGecko over a date range.

        Note: CoinGecko doesn't support multiple tickers in the same API call with date ranges,
        so this method only handles a single ticker. When a list is provided, raises ValueError.

        Args:
            ticker: Crypto ticker symbol (str) or list of ticker symbols (List[str])
            asset_type: Asset type (should be "Crypto")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            If ticker is str: DataFrame with date index and price column (USD)
            If ticker is List[str]: Not supported, raises ValueError

        Raises:
            ValueError: If prices cannot be retrieved, or if multiple tickers are provided
        """
        # CoinGecko doesn't support batch historical fetching
        if isinstance(ticker, list):
            if len(ticker) == 0:
                return {}
            if len(ticker) > 1:
                raise ValueError(
                    f"CoinGecko doesn't support batch historical price fetching for multiple tickers. "
                    f"Provided {len(ticker)} tickers: {ticker}"
                )
            # Single ticker in list - extract it
            ticker = ticker[0]

        # Handle single ticker (backward compatibility)
        return self._get_historical_prices_single(ticker, asset_type, start_date, end_date)

    def _get_historical_prices_single(
        self, ticker: str, asset_type: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """Get historical prices for a single ticker (internal helper).

        Args:
            ticker: Crypto ticker symbol
            asset_type: Asset type (should be "Crypto")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            DataFrame with date index and price column (USD)

        Raises:
            ValueError: If prices cannot be retrieved
        """
        logger.debug(
            f"Fetching historical prices from CoinGecko for {ticker} ({asset_type}) "
            f"from {start_date} to {end_date}"
        )

        try:
            coin_id = self._get_coin_id(ticker)

            # Convert dates to timestamps (Unix seconds)
            # Start at beginning of start_date
            start_dt = datetime.combine(start_date, datetime.min.time())
            start_ts = int(start_dt.timestamp())
            
            # End at end of end_date (23:59:59)
            end_dt = datetime.combine(end_date, datetime.max.time())
            # Add 86399 seconds (23:59:59) to make end_date inclusive
            end_ts = int(end_dt.timestamp()) + 86399

            # Use pycoingecko library method (automatically handles API key authentication)
            # The library's get_coin_market_chart_range_by_id() method handles API keys via extra_params
            data = self.client.get_coin_market_chart_range_by_id(
                id=coin_id,
                vs_currency="usd",
                from_timestamp=start_ts,
                to_timestamp=end_ts
            )

            if not data or "prices" not in data:
                raise ValueError(f"No historical price data available for {ticker}")

            # prices = [[timestamp_ms, price], ...]
            prices_list = data["prices"]
            if not prices_list:
                raise ValueError(f"No price data in response for {ticker}")

            # Convert to DataFrame
            df = pd.DataFrame(prices_list, columns=["timestamp", "price"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df["price"] = df["price"].astype(float)

            # Resample to daily (take last price of each day)
            df = df.resample("D").last()

            # Forward fill to handle missing days
            date_range = pd.date_range(start=start_date, end=end_date, freq="D")
            df = df.reindex(date_range, method="ffill")

            # Rename index to "date" for consistency
            df.index.name = "date"

            logger.debug(
                f"Retrieved {len(df)} historical prices for {ticker} "
                f"from {start_date} to {end_date}"
            )

            return df

        except Exception as e:
            raise ValueError(
                f"Error fetching historical prices for {ticker} from CoinGecko: {str(e)}"
            ) from e

