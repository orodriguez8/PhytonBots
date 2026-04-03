import os, sys
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
import datetime

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

def test_crypto_feed():
    key = os.getenv('ALPACA_API_KEY')
    sec = os.getenv('ALPACA_SECRET_KEY')
    base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    api = tradeapi.REST(key, sec, base, api_version='v2')
    
    start_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).isoformat()
    
    # Try different combinations
    tests = [
        ('BTCUSD', '1Hour', {}),
        ('BTCUSD', '1Hour', {'feed': 'crypto'}),
        ('BTCUSD', '1Hour', {'feed': 'us_crypto'}),
        ('BTC/USD', '1Min', {}),
        ('BTC/USD', '1Hour', {}),
    ]
    
    for sym, tf, extra in tests:
        try:
            print(f"Testing {sym} | {tf} | {extra} ...")
            bars = api.get_bars(sym, tf, start=start_date, limit=5, **extra).df
            if bars.empty:
                print(f"   -> EMPTY")
            else:
                print(f"   -> {len(bars)} bars found.")
        except Exception as e:
            print(f"   -> ERROR: {e}")

if __name__ == "__main__":
    test_crypto_feed()
