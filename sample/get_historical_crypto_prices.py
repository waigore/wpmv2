import pandas as pd
import yfinance as yf
from datetime import date, timedelta

# Crypto ticker mapping for yfinance
# Some crypto tickers have different names in yfinance
CRYPTO_TICKER_MAP = {
    "SUI-USD": "SUI20947-USD",
    # Add more mappings as needed
}

def map_crypto_ticker(ticker: str) -> str:
    """Map crypto ticker to yfinance ticker format.
    
    Args:
        ticker: Original crypto ticker (e.g., "SUI-USD")
    
    Returns:
        yfinance ticker (e.g., "SUI20947-USD") or original if no mapping exists
    """
    return CRYPTO_TICKER_MAP.get(ticker, ticker)

def fetch_crypto_prices_yfinance(
    ticker: str,
    start_date: str,   # "YYYY-MM-DD"
    end_date: str,     # "YYYY-MM-DD", inclusive
) -> pd.DataFrame:
    """
    Returns a DataFrame with daily closing prices for a single crypto using yfinance.
    Index: datetime
    Column: price (USD)
    
    Args:
        ticker: Crypto ticker symbol (e.g., "BTC-USD")
        start_date: Start date in "YYYY-MM-DD" format
        end_date: End date in "YYYY-MM-DD" format (inclusive)
    
    Returns:
        DataFrame with date index and price column
    """
    # Map ticker to yfinance format if needed
    yfinance_ticker = map_crypto_ticker(ticker)
    
    try:
        # Use yfinance to download historical data
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
        
        # Extract Adj Close or Close prices
        # Handle both DataFrame and Series returns from yfinance
        prices = None
        
        if isinstance(data.columns, pd.MultiIndex):
            # MultiIndex case - crypto data often has structure like [('Close', 'BTC-USD'), ...]
            # Check if ticker is in level 1 (Ticker level)
            if yfinance_ticker in data.columns.levels[1]:
                # Try Adj Close first, then Close
                if ('Adj Close', yfinance_ticker) in data.columns:
                    prices = data[('Adj Close', yfinance_ticker)]
                elif ('Close', yfinance_ticker) in data.columns:
                    prices = data[('Close', yfinance_ticker)]
                else:
                    raise ValueError(f"No Close price data available for {ticker}. Available columns: {data.columns}")
            # Check if ticker is in level 0 (Price level) - less common but possible
            elif yfinance_ticker in data.columns.levels[0]:
                ticker_data = data[yfinance_ticker]
                if "Close" in ticker_data.columns:
                    prices = ticker_data["Close"]
                elif "Adj Close" in ticker_data.columns:
                    prices = ticker_data["Adj Close"]
            else:
                raise ValueError(f"No Close price data available for {ticker}. Available columns: {data.columns}")
        else:
            # Single column case
            if "Adj Close" in data.columns:
                prices = data["Adj Close"]
            elif "Close" in data.columns:
                prices = data["Close"]
            else:
                raise ValueError(f"No Close price data available for {ticker}. Available columns: {data.columns}")
        
        if prices is None:
            raise ValueError(f"No Close price data available for {ticker}")
        
        # Convert to DataFrame with date index
        result_df = pd.DataFrame({"price": prices})
        result_df.index.name = "date"
        
        # Forward fill to handle missing trading days
        date_range = pd.date_range(start=start_date, end=end_date, freq="D")
        result_df = result_df.reindex(date_range, method="ffill")
        
        return result_df
        
    except Exception as e:
        raise ValueError(f"Error fetching historical prices for {ticker} from yfinance: {str(e)}") from e


# Test with BTC first
if __name__ == "__main__":
    print("Testing BTC historical price retrieval with yfinance...")
    try:
        # Use a date range (yfinance supports longer ranges than CoinGecko free tier)
        end_date_obj = date.today()
        start_date_obj = end_date_obj - timedelta(days=30)  # Last 30 days
        
        btc_prices = fetch_crypto_prices_yfinance(
            ticker="BTC-USD",
            start_date=start_date_obj.strftime("%Y-%m-%d"),
            end_date=end_date_obj.strftime("%Y-%m-%d")
        )
        print(f"\nSuccessfully retrieved {len(btc_prices)} days of BTC prices")
        print("\nFirst 5 days:")
        print(btc_prices.head())
        print("\nLast 5 days:")
        print(btc_prices.tail())
        print(f"\nPrice range: ${btc_prices['price'].min():.2f} - ${btc_prices['price'].max():.2f}")
        
        # Test with SUI-USD to verify mapping
        print("\n\nTesting SUI-USD historical price retrieval with ticker mapping...")
        sui_prices = fetch_crypto_prices_yfinance(
            ticker="SUI-USD",
            start_date=start_date_obj.strftime("%Y-%m-%d"),
            end_date=end_date_obj.strftime("%Y-%m-%d")
        )
        print(f"\nSuccessfully retrieved {len(sui_prices)} days of SUI prices")
        print("\nFirst 5 days:")
        print(sui_prices.head())
        print("\nLast 5 days:")
        print(sui_prices.tail())
        print(f"\nPrice range: ${sui_prices['price'].min():.2f} - ${sui_prices['price'].max():.2f}")
    except Exception as e:
        print(f"Error: {e}")