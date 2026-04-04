import os
import pandas as pd
import alpaca_trade_api as tradeapi
import datetime
import logging

logger = logging.getLogger(__name__)

from alpaca_trade_api.rest import TimeFrame
import requests, json
from trading_bot.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL

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
    
    try:
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
                start=(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).isoformat(), 
                limit=limit, 
                feed='iex'
            ).df
            if bars is None or bars.empty: return None
            df = bars[['open', 'high', 'low', 'close', 'volume']].copy()
            return df.tail(limit)
        else:
            # Crypto data via direct API
            fetch_sym = symbol if '/' in symbol else symbol.replace('USD', '/USD').replace('USDT', '/USDT').replace('USDC', '/USDC')
            url = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
            params = {
                "symbols": fetch_sym,
                "timeframe": timeframe, # Alpaca accepts "15Min", "1Hour"...
                "limit": limit
            }
            headers = {
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": secret
            }
            r = requests.get(url, params=params, headers=headers)
            if r.status_code == 200:
                data = r.json()
                bars_list = data.get('bars', {}).get(fetch_sym, [])
                if not bars_list: return None
                df = pd.DataFrame(bars_list)
                # Map Alpaca internal keys
                df = df.rename(columns={'t':'time', 'o':'open', 'h':'high', 'l':'low', 'c':'close', 'v':'volume'})
                df.index = pd.to_datetime(df['time'])
                return df[['open', 'high', 'low', 'close', 'volume']].tail(limit)
            else:
                logger.error(f"❌ API Error {symbol}: {r.status_code} {r.text}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Exception {symbol}: {e}")
        return None
