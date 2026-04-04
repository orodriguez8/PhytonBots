import os, sys
from dotenv import load_dotenv
import pandas as pd
import alpaca_trade_api as tradeapi
import datetime

# Fix for Windows console encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()
from trading_bot.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL

def test_full():
    key = ALPACA_API_KEY
    sec = ALPACA_SECRET_KEY
    base = ALPACA_BASE_URL
    
    print(f"Key: {key[:5]}... | Sec: {sec[:5]}...")
    print(f"Base: {base}")
    
    if not key or not sec:
        print("[FAIL] Missing API keys.")
        return

    try:
        api = tradeapi.REST(key, sec, base, api_version='v2')
        acc = api.get_account()
        print(f"[OK] Account connected. Equity: {acc.equity}")
        
        pos = api.list_positions()
        print(f"[OK] Open positions: {len(pos)}")
        for p in pos:
            print(f"   - {p.symbol}: {p.qty} @ {p.avg_entry_price}")
            
        print("\nTesting Data (AAPL):")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%dT%H%M:%SZ')
        # Fix format for Alpaca datetime
        start_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).isoformat()
        
        try:
            bars = api.get_bars('AAPL', '1Hour', start=start_date, limit=10, feed='iex').df
            if bars.empty:
                print("[WARN] Stock data (IEX) empty.")
            else:
                print(f"[OK] Stock data ok: {len(bars)} bars.")
        except Exception as e_data:
            print(f"[FAIL] Stock data failed: {e_data}")
            
        print("\nTesting Data (BTCUSD):")
        try:
            bars_crypto = api.get_bars('BTCUSD', '1Hour', start=start_date, limit=10).df
            if bars_crypto.empty:
                print("[WARN] Crypto data empty.")
            else:
                print(f"[OK] Crypto data ok: {len(bars_crypto)} bars.")
        except Exception as e_crypto:
            print(f"[FAIL] Crypto data failed: {e_crypto}")
            
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    test_full()
