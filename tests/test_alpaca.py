
import os
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
import pandas as pd
from datetime import datetime, timedelta

load_dotenv()

def test_alpaca():
    key    = os.getenv('ALPACA_API_KEY')
    secret = os.getenv('ALPACA_SECRET_KEY')
    base   = os.getenv('ALPACA_BASE_URL')
    
    # Probamos con AAPL que es más estable en Paper
    symbol = "AAPL"
    
    print(f"Testing Alpaca with {symbol}")
    
    try:
        api = tradeapi.REST(key, secret, base, api_version='v2')
        acc = api.get_account()
        print(f"Cuenta OK. Equity: {acc.equity}")
        
        # Probar datos
        # Para Paper free tier, a veces el feed 'sip' no funciona. 
        # Intentamos con 'iex' que es el gratuito de prueba.
        try:
            bars = api.get_bars(symbol, '1Hour', limit=20, feed='iex').df
        except:
             bars = api.get_bars(symbol, '1Hour', limit=20).df

        print(f"Datos recibidos ({len(bars)} filas):")
        if not bars.empty:
            print(bars.tail(3))
        else:
            print("Vacío. Probando con BTCUSD...")
            bars = api.get_bars("BTCUSD", '1Hour', limit=20, feed='crypto').df
            print(f"BTCUSD: {len(bars)} filas.")
            if not bars.empty: print(bars.tail(3))
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_alpaca()
