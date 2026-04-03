import os, sys
from dotenv import load_dotenv
import pandas as pd
import alpaca_trade_api as tradeapi
import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def test_crypto_symbols():
    key = os.getenv('ALPACA_API_KEY')
    sec = os.getenv('ALPACA_SECRET_KEY')
    base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    
    api = tradeapi.REST(key, sec, base, api_version='v2')
    start_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
    
    symbols = ['BTCUSD', 'BTC/USD', 'ETHUSD', 'ETH/USD']
    for sym in symbols:
        try:
            bars = api.get_bars(sym, '1Hour', start=start_date, limit=5).df
            if bars.empty:
                print(f"[WARN] {sym}: Empty")
            else:
                print(f"[OK] {sym}: {len(bars)} bars")
        except Exception as e:
            print(f"[FAIL] {sym}: {e}")

if __name__ == "__main__":
    test_crypto_symbols()
