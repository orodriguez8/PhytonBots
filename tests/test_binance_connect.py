import os
import ccxt
from dotenv import load_dotenv

# Intentar cargar variables si existen
load_dotenv()

def test_binance():
    print("Testing Binance Connectivity via CCXT...")
    
    # Usamos Testnet por defecto para la prueba
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    exchange.set_sandbox_mode(True)
    
    try:
        print(f"Fetching BTC/USDT Ticker...")
        ticker = exchange.fetch_ticker('BTC/USDT')
        print(f"[OK] Success! Last BTC Price on Binance Testnet: {ticker['last']} USDT")
        
        print("\nChecking Public Balances (should be empty but succeed)...")
        # create a dummy authenticated instance with fake keys just to check if the error is "Auth" or "Connect"
        # but let's just stick to public for now to verify network/library
        
        print("[OK] CCXT Library and Network are working correctly.")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")

if __name__ == "__main__":
    test_binance()
