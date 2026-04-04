import os, sys, requests, json
from dotenv import load_dotenv

load_dotenv()

def test_direct_api():
    key = os.getenv('ALPACA_API_KEY')
    sec = os.getenv('ALPACA_SECRET_KEY')
    
    # Alpaca Market Data V2 Crypto
    url = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
    params = {
        "symbols": "BTC/USD",
        "timeframe": "1Hour",
        "limit": 5
    }
    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": sec
    }
    
    r = requests.get(url, params=params, headers=headers)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        print(f"Data: {json.dumps(r.json(), indent=2)}")
    else:
        print(f"Error: {r.text}")

if __name__ == "__main__":
    test_direct_api()
