import pandas_market_calendars as mcal
import pytz
from datetime import datetime, time

# Create NYSE calendar instance (handles holidays, early closes, etc.)
nyse = mcal.get_calendar('NYSE')

# Hong Kong timezone (your local time)
HK_TZ = pytz.timezone('Asia/Hong_Kong')

# US Eastern Time
ET_TZ = pytz.timezone('US/Eastern')

# Regular trading hours in ET
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)

def is_us_market_open(now_hk: datetime = None) -> bool:
    """
    Returns True if the US market (NYSE) is currently open for regular trading hours.
    Accounts for weekends, official holidays, and early closes automatically.
    """
    if now_hk is None:
        now_hk = datetime.now(HK_TZ)
    
    # Convert to US/Eastern
    now_et = now_hk.astimezone(ET_TZ)
    now_et_date = now_et.date()
    current_time_et = now_et.time()
    
    # Get the trading schedule for today
    schedule = nyse.schedule(start_date=now_et_date, end_date=now_et_date)
    
    if schedule.empty:
        # No trading session today (holiday or weekend)
        return False
    
    market_open_et = schedule.loc[now_et_date, 'market_open'].time()
    market_close_et = schedule.loc[now_et_date, 'market_close'].time()
    
    return market_open_et <= current_time_et < market_close_et

# Example integration into your previous periodic updater
def periodic_price_update(interval_minutes: int = 5):
    while True:
        now_hk = datetime.now(HK_TZ)
        print(f"\n[{now_hk.strftime('%Y-%m-%d %H:%M:%S %Z')}] Fetching prices...")
        
        prices = fetch_current_prices(TICKERS)
        print("Current US stock prices (USD):")
        for ticker, price in prices.items():
            print(f"  {ticker}: ${price}")
        
        if is_us_market_open(now_hk):
            sleep_seconds = interval_minutes * 60
            print(f"Market is OPEN → next update in {interval_minutes} minutes")
        else:
            # Sleep long when closed; in production, calculate time to next open
            sleep_seconds = 3600 * 8  # e.g., check again in 8 hours
            print("Market is CLOSED → next update later")
        
        time.sleep(sleep_seconds)