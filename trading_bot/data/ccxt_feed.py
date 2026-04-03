import ccxt
import pandas as pd
import time
from ..config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET

def _get_exchange():
    """
    Inicializa el exchange de Binance via CCXT.
    """
    exchange = ccxt.binance({
        'apiKey': BINANCE_API_KEY,
        'secret': BINANCE_SECRET_KEY,
        'enableRateLimit': True,
    })
    
    if BINANCE_TESTNET:
        exchange.set_sandbox_mode(True)
        
    return exchange

def obtener_datos_ccxt(symbol='BTC/USDT', timeframe='1h', limit=100):
    """
    Obtiene velas OHLCV de Binance y las devuelve como un DataFrame de Pandas.
    """
    try:
        # Normalizar símbolo para Binance (ej: BTCUSD -> BTC/USDT)
        if '/' not in symbol:
            symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) == 6 else symbol
            if 'USD' in symbol and 'USDT' not in symbol:
                symbol = symbol.replace('USD', '/USDT')

        exchange = _get_exchange()
        
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
    except Exception as e:
        print(f"Error obteniendo datos de CCXT ({symbol}): {e}")
        return None

if __name__ == "__main__":
    # Prueba rápida
    df = obtener_datos_ccxt('BTC/USDT', '1h', 10)
    if df is not None:
        print(df.head())
