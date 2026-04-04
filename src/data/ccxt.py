import ccxt
import pandas as pd
import time
from src.core.config import CCXT_API_KEY, CCXT_SECRET_KEY, CCXT_TESTNET, CCXT_EXCHANGE_ID

def _get_exchange():
    """
    Inicializa el exchange configurado via CCXT.
    """
    exchange_cls = getattr(ccxt, CCXT_EXCHANGE_ID, None)
    if exchange_cls is None:
        raise ValueError(f"Exchange CCXT no soportado: {CCXT_EXCHANGE_ID}")

    exchange = exchange_cls({
        'apiKey': CCXT_API_KEY,
        'secret': CCXT_SECRET_KEY,
        'enableRateLimit': True,
    })

    if CCXT_TESTNET and getattr(exchange, 'urls', None) and exchange.urls.get('test'):
        exchange.set_sandbox_mode(True)

    return exchange

def obtener_datos_ccxt(symbol='BTC/USDC', timeframe='1h', limit=100):
    """
    Obtiene velas OHLCV del exchange configurado y las devuelve como DataFrame.
    """
    try:
        # En Coinbase el par suele ser /USDC o /USD
        if '/' not in symbol:
            symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) == 6 else symbol
            if 'USDT' in symbol:
                symbol = symbol.replace('USDT', 'USDC') # Coinbase prefiere USDC o USD
            elif 'USD' in symbol:
                symbol = symbol.replace('USD', '/USD')

        exchange = _get_exchange()
        
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        return df
    except Exception as e:
        print(f"Error obteniendo datos de CCXT-{CCXT_EXCHANGE_ID} ({symbol}): {e}")
        return None

if __name__ == "__main__":
    # Prueba rápida
    df = obtener_datos_ccxt('BTC/USD', '1h', 10)
    if df is not None:
        print(df.head())
