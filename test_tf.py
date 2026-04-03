import os, sys
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import TimeFrame

load_dotenv()

def test_tf_object():
    key = os.getenv('ALPACA_API_KEY')
    sec = os.getenv('ALPACA_SECRET_KEY')
    base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    api = tradeapi.REST(key, sec, base, api_version='v2')
    
    # Try different symbols
    syms = ['BTCUSD', 'BTC/USD', 'ETHUSD', 'ETH/USD']
    for sym in syms:
        try:
            print(f"Testing {sym} with TimeFrame.Hour...")
            bars = api.get_bars(sym, TimeFrame.Hour, limit=5).df
            if bars.empty:
                print(f"   -> EMPTY")
            else:
                print(f"   -> SUCCESS: {len(bars)} bars")
        except Exception as e:
            print(f"   -> ERROR: {e}")

if __name__ == "__main__":
    test_tf_object()
