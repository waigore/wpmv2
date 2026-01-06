# Adjusted for correct Sui ticker
crypto_tickers = ["BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "SUI20947-USD"]  # Use this for yfinance

data = yf.download(crypto_tickers, start="2025-05-01", end="2026-01-06", progress=False)
prices = data['Adj Close'].ffill().round(2)