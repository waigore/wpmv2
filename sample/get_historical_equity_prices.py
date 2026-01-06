import yfinance as yf
import pandas as pd
from datetime import datetime

def fetch_stock_prices(
    start_date: str,   # "YYYY-MM-DD"
    end_date: str | None = None,  # Optional, defaults to today (2026-01-06)
    tickers: list[str] | None = None
) -> pd.DataFrame:
    """
    Fetches daily adjusted close prices for your US stocks and ETFs.
    Returns DataFrame with Date index and one column per ticker.
    """
    # Your unique equity/ETF tickers from the uploaded CSV
    default_tickers = ["ASST", "BMNR", "COIN", "GOOG", "HOOD", "IAU"]
    
    tickers_to_use = tickers or default_tickers
    
    # If no end_date provided, use today
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Fetching prices for {tickers_to_use} from {start_date} to {end_date}...")
    
    # Batch download - most efficient way
    data = yf.download(
        tickers=tickers_to_use,
        start=start_date,
        end=end_date,
        progress=False,          # Clean output in backend
        auto_adjust=True,        # Directly gives 'Close' as adjusted close
        actions=False            # We don't need dividends/splits separately
    )
    
    # When multiple tickers, yfinance returns MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        prices = data['Close']      # Extract only the Close (adjusted) level
    else:
        prices = data[['Close']]    # Single ticker case
        prices.columns = tickers_to_use
    
    # Rename columns to match your internal ticker format if needed
    prices.columns = [col.strip() for col in prices.columns]
    
    # Forward fill any missing trading days (e.g., holidays) - common for daily valuation
    prices = prices.ffill()
    
    # Optional: drop rows with all NaN (early dates before any ticker existed)
    prices = prices.dropna(how='all')
    
    print(f"Retrieved {len(prices)} trading days.")
    return prices.round(2)

# Example usage - covers your entire stock trade history
stock_prices = fetch_stock_prices(
    start_date="2024-05-01",   # Earliest IAU trade
    end_date="2026-01-06"     # Today
)

print(stock_prices.tail(10))  # Show most recent prices