import yfinance as yf
import pandas as pd

def get_cumulative_split_factor(ticker_symbol, trade_date, current_date=None):
    ticker = yf.Ticker(ticker_symbol)
    splits = ticker.splits
    
    # Filter splits that occurred after the trade date
    if current_date is None:
        current_date = pd.Timestamp.now()
    relevant_splits = splits[(splits.index > trade_date) & (splits.index <= current_date)]
    
    # Cumulative factor: product of all split ratios after the trade
    cumulative_factor = relevant_splits.prod() if not relevant_splits.empty else 1.0
    return cumulative_factor