import yfinance as yf

# Fetch the latest data for HKD to USD (ticker is 'HKDUSD=X')
data = yf.download('HKDUSD=X', period='1d', progress=False)
usd_rate = data['Close'].iloc[-1]  # Latest closing rate (1 HKD = X USD)

# Example conversion
hkd_amount = 100
usd_amount = hkd_amount * usd_rate
print(f"{hkd_amount} HKD is approximately {usd_amount:.2f} USD")