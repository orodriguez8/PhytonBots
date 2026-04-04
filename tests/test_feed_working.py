import os, sys
from dotenv import load_dotenv
import pandas as pd
import alpaca_trade_api as tradeapi
import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def test_working_symbols():
    key = os.getenv('ALPACA_API_KEY')
    sec = os.getenv('ALPACA_SECRET_KEY')
    base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    
    api = tradeapi.REST(key, sec, base, api_version='v2')
    start_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).isoformat()
    
    symbols = ['AAPL', 'TSLA', 'AVAXUSD', 'LTCUSD']
    for sym in symbols:
        try:
            extra = {'feed': 'iex'} if 'USD' not in sym else {}
            bars = api.get_bars(sym, '1Hour', start=start_date, limit=10, **extra).df
            if bars.empty:
                print(f"[WARN] {sym}: Empty")
            else:
                print(f"[OK] {sym}: {len(bars)} bars, Close: {bars['close'].iloc[-1]}")
        except Exception as e:
            print(f"[FAIL] {sym}: {e}")

if __name__ == "__main__":
    test_working_symbols()
