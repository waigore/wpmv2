import yfinance as yf
import pandas as pd

tickers = ["GOOG", "COIN", "HOOD", "IAU", "ASST", "BMNR",
           "BTC-USD", "ETH-USD", "SOL-USD", "LINK-USD", "SUI20947-USD"]  # use correct Sui ticker

metadata = {}

for t in tickers:
    try:
        info = yf.Ticker(t).info
        metadata[t] = {
            "name":        info.get("longName") or info.get("shortName") or info.get("name") or t,
            "type":        info.get("quoteType", "unknown"),
            "currency":    info.get("currency", "N/A"),
            "market_cap":  info.get("marketCap") or info.get("totalAssets"),
            "sector":      info.get("sector", "N/A"),
            "industry":    info.get("industry", "N/A"),
            "country":     info.get("country", "N/A"),
            "category":    info.get("category", "N/A"),           # useful for ETFs
        }
    except Exception as e:
        metadata[t] = {"error": str(e)}

# Nice table view
df = pd.DataFrame.from_dict(metadata, orient="index")
print(df.round(0))   # market cap usually huge number → round for readability