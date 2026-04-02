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
    
    # Alpaca Free Tier (IEX) vs Crypto
    is_crypto = 'USD' in symbol or '/' in symbol
    
    api = tradeapi.REST(key, secret, base, api_version='v2')
    
    try:
        start_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Para el feed de Crypto en la API gratuita, NO se debe pasar feed='crypto' en get_bars
        # Se descarga directamente. Para stocks, usamos 'iex' para evitar el error de suscripción
        if is_crypto:
            bars = api.get_bars(symbol, '1Hour', start=start_date, limit=limit).df
        else:
            bars = api.get_bars(symbol, '1Hour', start=start_date, limit=limit, feed='iex').df
            
        if bars.empty:
            logger.warning(f"⚠️ No hay datos para {symbol} en Alpaca.")
            return None
            
        df = bars[['open', 'high', 'low', 'close', 'volume']].copy()
        return df.tail(limit)
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo datos de Alpaca para {symbol}: {e}")
        return None
