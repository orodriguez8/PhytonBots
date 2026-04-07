
import os
import sys

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), 'src')))

try:
    # Try importing the client
    # First, need to set environment variables if not set, or let it read .env
    from dotenv import load_dotenv
    load_dotenv()

    from src.execution.alpaca_client import obtener_historial_cartera, obtener_cuenta
    from src.core.config import ALPACA_BASE_URL, ALPACA_API_KEY
    
    print(f"Base URL: {ALPACA_BASE_URL}")
    print(f"API Key: {ALPACA_API_KEY[:5]}...")
    
    print("\n1. Testing Account...")
    acc = obtener_cuenta()
    if acc:
        print(f"Account Success! Equity: {acc['nav']}")
    else:
        print("Account Failed (unauthorized or other error).")

    print("\n2. Testing Performance History (1D, 5Min)...")
    data = obtener_historial_cartera('1D', '5Min')
    print(f"Results: {len(data)} items")
    if data:
        print(f"Sample data: {data[0]}")
    else:
        print("Empty data returned.")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
