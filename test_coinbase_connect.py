import os
import ccxt
from dotenv import load_dotenv

# Cargar variables (.env)
load_dotenv()

def test_coinbase():
    print("Testing Coinbase Connectivity via CCXT...")
    
    # Coinbase Advanced Trade no requiere sandbox para obtener datos públicos
    exchange = ccxt.coinbase({
        'enableRateLimit': True,
    })
    
    try:
        print(f"Fetching BTC/USD Ticker from Coinbase...")
        ticker = exchange.fetch_ticker('BTC/USD')
        print(f"[OK] Success! Last BTC Price on Coinbase: {ticker['last']} USD")
        
        print("\nChecking Public Order Book...")
        order_book = exchange.fetch_order_book('BTC/USD', limit=5)
        print(f"[OK] Top Bid: {order_book['bids'][0][0]}")
        
        print("[OK] CCXT Library and Coinbase Networking are working from this location!")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")

if __name__ == "__main__":
    test_coinbase()
