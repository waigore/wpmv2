import yfinance as yf

# List of tickers you want to track
tickers_list = ["AAPL", "GOOGL", "TSLA", "MSFT"]

# Create a Tickers object
tickers_data = yf.Tickers(' '.join(tickers_list))

# Iterate through the tickers to get the current price
prices = {}
for ticker_symbol, ticker_object in tickers_data.tickers.items():
    # Fetch the current price from the info dictionary
    price = ticker_object.info.get('currentPrice')
    if price is None:
        price = ticker_object.info.get('regularMarketPrice')

    if price is not None:
        prices[ticker_symbol] = price
    else:
        prices[ticker_symbol] = "Price not found"

print("Current Prices:")
for symbol, price_val in prices.items():
    print(f"{symbol}: {price_val}")

