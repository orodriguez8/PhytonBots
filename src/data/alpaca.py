import os
import pandas as pd
import alpaca_trade_api as tradeapi
import datetime
import logging

logger = logging.getLogger(__name__)

from alpaca_trade_api.rest import TimeFrame
import requests, json
from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL

def obtener_datos_alpaca(symbol: str = 'BTC/USD', limit: int = 300, timeframe: str = '1Hour'):
    """
    Fetch bar data from Alpaca. Supports stocks (IEX) and crypto.
    timeframe: '15Min', '1Hour', '1Day'...
    """
    key    = ALPACA_API_KEY
    secret = ALPACA_SECRET_KEY
    base   = ALPACA_BASE_URL
    
    # Normalize symbol
    is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])
    
    # Calculate start time ensuring we have enough bars (stocks only trade 6.5h/day)
    now = datetime.datetime.now(datetime.timezone.utc)
    # Conservativo: Asumimos que sólo hay unas 6 horas útiles por día de mercado para acciones (multiplicador x4)
    buffer = 4 if not is_crypto else 1 
    
    if timeframe == '1Day':
        start_time = (now - datetime.timedelta(days=(limit * buffer) + 30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    elif timeframe == '1Hour':
        start_time = (now - datetime.timedelta(days=(limit // 6 * buffer) + 7)).strftime('%Y-%m-%dT%H:%M:%SZ')
    elif timeframe == '15Min':
        start_time = (now - datetime.timedelta(days=(limit // 24 * buffer) + 3)).strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        start_time = (now - datetime.timedelta(days=limit * buffer)).strftime('%Y-%m-%dT%H:%M:%SZ')

    try:
        end_time = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        if not is_crypto:
            api = tradeapi.REST(key, secret, base, api_version='v2')
            # Stock data via library
            tf_map = {
                '1Min': TimeFrame.Minute,
                '15Min': TimeFrame(15, TimeFrame.Minute),
                '1Hour': TimeFrame.Hour,
                '1Day': TimeFrame.Day
            }
            
            bars = api.get_bars(
                symbol, 
                tf_map.get(timeframe, TimeFrame.Hour), 
                start=start_time,
                end=end_time,
                feed='iex'
            ).df
            
            if bars is None or bars.empty: return None
            df = bars[['open', 'high', 'low', 'close', 'volume']].copy()
            return df.tail(limit)
        else:
            # Crypto data via SDK para manejar paginación y límites grandes automáticamente
            api = tradeapi.REST(key, secret, base, api_version='v2')
            fetch_sym = symbol if '/' in symbol else symbol.replace('USD', '/USD').replace('USDT', '/USDT').replace('USDC', '/USDC')
            
            tf_map = {
                '1Min': tradeapi.TimeFrame.Minute,
                '15Min': tradeapi.TimeFrame(15, tradeapi.TimeFrame.Minute),
                '1Hour': tradeapi.TimeFrame.Hour,
                '1Day': tradeapi.TimeFrame.Day
            }
            
            bars = api.get_crypto_bars(
                fetch_sym, 
                tf_map.get(timeframe, tradeapi.TimeFrame.Hour),
                start=start_time,
                end=end_time
            ).df
            
            if bars is None or bars.empty: return None
            
            # Limpiar MultiIndex si existe (Alpaca suele devolverlo con el símbolo y timestamp)
            if hasattr(bars.index, 'levels'):
                bars = bars.xs(fetch_sym, level='symbol')
            
            df = bars[['open', 'high', 'low', 'close', 'volume']].copy()
            return df.tail(limit)
                
    except Exception as e:
        logger.error(f"❌ Exception {symbol}: {e}")
        return None
