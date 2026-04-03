import os, sys
from dotenv import load_dotenv
import logging

# Mock logging for the import to work without errors if needed, 
# although we already have it in the file.
logging.basicConfig(level=logging.INFO)

# Set path to include trading_bot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trading_bot.data.alpaca_feed import obtener_datos_alpaca

load_dotenv()

def verify_new_feed():
    symbols = ['AAPL', 'BTCUSD', 'ETHUSD', 'AVAXUSD']
    for s in symbols:
        print(f"Checking {s}...")
        df = obtener_datos_alpaca(s, limit=5)
        if df is not None:
            print(f"   [OK] {s}: {len(df)} rows. Last Close: {df['close'].iloc[-1]}")
        else:
            print(f"   [FAIL] {s}: No data.")

if __name__ == "__main__":
    verify_new_feed()
