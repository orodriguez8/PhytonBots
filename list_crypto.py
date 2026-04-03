import os, sys
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi

load_dotenv()

def list_crypto_assets():
    key = os.getenv('ALPACA_API_KEY')
    sec = os.getenv('ALPACA_SECRET_KEY')
    base = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    api = tradeapi.REST(key, sec, base, api_version='v2')
    
    assets = api.list_assets(asset_class='crypto')
    print(f"Total crypto assets: {len(assets)}")
    for a in assets[:10]:
        print(f" - {a.symbol} ({a.status})")

if __name__ == "__main__":
    list_crypto_assets()
