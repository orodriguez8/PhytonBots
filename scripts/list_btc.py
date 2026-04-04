import os, sys
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi

load_dotenv()

def list_all_crypto():
    key = os.getenv('ALPACA_API_KEY')
    sec = os.getenv('ALPACA_SECRET_KEY')
    base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    api = tradeapi.REST(key, sec, base, api_version='v2')
    
    assets = api.list_assets(asset_class='crypto')
    for a in assets:
        if 'BTC' in a.symbol:
            print(f"[{a.symbol}] Status: {a.status}")

if __name__ == "__main__":
    list_all_crypto()
