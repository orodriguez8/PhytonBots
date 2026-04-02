import os
import pandas as pd
import alpaca_trade_api as tradeapi
import datetime
import logging

logger = logging.getLogger(__name__)

def obtener_datos_alpaca(symbol: str = 'AAPL', limit: int = 300):
    key    = os.getenv('ALPACA_API_KEY')
    secret = os.getenv('ALPACA_SECRET_KEY')
    base   = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    
    # Alpaca requiere feeds específicos para crypto o stocks
    is_crypto = 'USD' in symbol or '/' in symbol
    feed = 'crypto' if is_crypto else 'iex'
    
    api = tradeapi.REST(key, secret, base, api_version='v2')
    
    try:
        # Fechas ajustadas para asegurar que haya datos en fin de semana (crypto) o laborables (stocks)
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Obtención de barras con feed específico
        bars = api.get_bars(symbol, '1Hour', start=start_date, limit=limit, feed=feed).df
        
        if bars.empty:
            # Reintento sin el parámetro feed por si no está soportado en la cuenta
            bars = api.get_bars(symbol, '1Hour', start=start_date, limit=limit).df
            
        if bars.empty:
            logger.warning(f"⚠️ No hay datos para {symbol} en Alpaca.")
            return None
            
        df = bars[['open', 'high', 'low', 'close', 'volume']].copy()
        return df.tail(limit)
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo datos de Alpaca para {symbol}: {e}")
        return None
