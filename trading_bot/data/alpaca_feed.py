
import os
import pandas as pd
import alpaca_trade_api as tradeapi
import datetime

def obtener_datos_alpaca(symbol: str = None, limit: int = 300):
    key    = os.getenv('ALPACA_API_KEY')
    secret = os.getenv('ALPACA_SECRET_KEY')
    base   = os.getenv('ALPACA_BASE_URL')
    symbol = symbol or os.getenv('ALPACA_SYMBOL', 'AAPL')
    
    api = tradeapi.REST(key, secret, base, api_version='v2')
    
    try:
        # Formato de fecha RFC3339 exacto (sin milisegundos) para Alpaca
        start_date = (datetime.datetime.now() - datetime.timedelta(days=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        try:
             # Canal gratuito 'iex' para cuentas Demo/Paper
             bars = api.get_bars(symbol, '1Hour', start=start_date, limit=limit, feed='iex').df
             if bars.empty:
                  bars = api.get_bars(symbol, '1Hour', start=start_date, limit=limit).df
        except:
             bars = api.get_bars(symbol, '1Hour', start=start_date, limit=limit).df
             
        if bars.empty:
            raise ValueError(f"Sin datos de {symbol} en Alpaca. Prueba con 'AAPL'.")
            
        df = bars[['open', 'high', 'low', 'close', 'volume']].copy()
        return df.tail(limit)
        
    except Exception as e:
        print(f"Error Alpaca Data: {e}")
        # Intento final con Apple sin parámetros complejos
        try:
             return api.get_bars('AAPL', '1Hour', limit=limit).df[['open', 'high', 'low', 'close', 'volume']]
        except:
             raise e
