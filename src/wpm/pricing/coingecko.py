"""CoinGecko price retriever implementation."""

import logging
from typing import Dict, List, Optional

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

