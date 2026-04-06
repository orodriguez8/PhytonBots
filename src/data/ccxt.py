import ccxt
import pandas as pd
import time
from src.core.config import CCXT_API_KEY, CCXT_SECRET_KEY, CCXT_TESTNET, CCXT_EXCHANGE_ID
from src.core.health import get_circuit_breaker_status, record_success, record_failure

def _get_exchange():
    """
    Inicializa el exchange configurado via CCXT.
    Soporta modo Futures para Binance si se solicita.
    """
    params = {
        'apiKey': CCXT_API_KEY,
        'secret': CCXT_SECRET_KEY,
        'enableRateLimit': True,
    }

    # Si es Binance, configuramos para operar en FUTUROS (permite SHORT)
    if 'binance' in CCXT_EXCHANGE_ID.lower():
        params['options'] = {'defaultType': 'future'}

    exchange_cls = getattr(ccxt, CCXT_EXCHANGE_ID, None)
    if exchange_cls is None:
        raise ValueError(f"Exchange CCXT no soportado: {CCXT_EXCHANGE_ID}")

    exchange = exchange_cls(params)

    if CCXT_TESTNET and getattr(exchange, 'urls', None) and exchange.urls.get('test'):
        exchange.set_sandbox_mode(True)

    return exchange

def obtener_datos_ccxt(symbol='BTC/USDC', timeframe='1h', limit=100):
    """
    Obtiene velas OHLCV respetando el Circuit Breaker.
    """
    if get_circuit_breaker_status():
        return None

    try:
        # En Coinbase el par suele ser /USDC o /USD
        if '/' not in symbol:
            symbol = f"{symbol[:3]}/{symbol[3:]}" if len(symbol) == 6 else symbol
            if 'USDT' in symbol:
                symbol = symbol.replace('USDT', 'USDC') # Coinbase prefiere USDC o USD
            elif 'USD' in symbol:
                symbol = symbol.replace('USD', '/USD')

        exchange = _get_exchange()
        
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception:
            # Reintentar con símbolo estándar si falla (Binance Futures usa BTC/USDT)
            if 'binance' in CCXT_EXCHANGE_ID.lower():
                symbol = symbol.replace('/USD', '/USDT')
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            else:
                raise

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        record_success()
        return df
    except Exception as e:
        print(f"Error obteniendo datos de CCXT-{CCXT_EXCHANGE_ID} ({symbol}): {e}")
        record_failure()
        return None

if __name__ == "__main__":
    # Prueba rápida
    df = obtener_datos_ccxt('BTC/USD', '1h', 10)
    if df is not None:
        print(df.head())
