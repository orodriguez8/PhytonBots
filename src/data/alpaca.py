
import os
import pandas as pd
import datetime
import logging
import backoff
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY

logger = logging.getLogger(__name__)

@backoff.on_exception(backoff.expo, Exception, max_tries=5, giveup=lambda e: not any(x in str(e) for x in ["429", "SSL", "connection", "ConnectionPool", "Timeout"]))
def obtener_datos_alpaca(symbol: str = 'BTC/USD', limit: int = 300, timeframe: str = '1Hour'):
    """
    Fetch bar data from Alpaca using alpaca-py SDK.
    """
    is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])
    norm_sym = symbol.replace('/', '').upper()
    
    # Timeframe mapping
    tf_map = {
        '1Min': TimeFrame.Minute,
        '15Min': TimeFrame(15, TimeFrame.Minute),
        '1Hour': TimeFrame.Hour,
        '1Day': TimeFrame.Day
    }
    tf = tf_map.get(timeframe, TimeFrame.Hour)

    now = datetime.datetime.now(datetime.timezone.utc)
    # Buffers to ensure we get enough bars (especially for stocks)
    buffer_days = 4 if not is_crypto else 1
    if timeframe == '1Day':
        start_time = now - datetime.timedelta(days=(limit * buffer_days) + 30)
    elif timeframe == '1Hour':
        start_time = now - datetime.timedelta(days=(limit // 6 * buffer_days) + 7)
    elif timeframe == '15Min':
        start_time = now - datetime.timedelta(days=(limit // 24 * buffer_days) + 3)
    else:
        start_time = now - datetime.timedelta(days=limit * buffer_days)

    try:
        if not is_crypto:
            client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
            req = StockBarsRequest(
                symbol_or_symbols=norm_sym,
                timeframe=tf,
                start=start_time,
                end=now,
                feed='iex' # Use 'sip' for paid plans
            )
            bars = client.get_stock_bars(req)
        else:
            client = CryptoHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
            # alpaca-py likes BTC/USD format for many things but let's ensure it's correct
            fetch_sym = symbol if '/' in symbol else symbol.replace('USD', '/USD').replace('USDT', '/USDT').replace('USDC', '/USDC')
            req = CryptoBarsRequest(
                symbol_or_symbols=fetch_sym,
                timeframe=tf,
                start=start_time,
                end=now
            )
            bars = client.get_crypto_bars(req)

        df = bars.df
        if df is None or df.empty:
            return None
            
        # Clear MultiIndex if present
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(norm_sym if not is_crypto else fetch_sym, level='symbol')
            
        return df[['open', 'high', 'low', 'close', 'volume']].tail(limit)

    except Exception as e:
        logger.error(f"❌ Exception fetching Alpaca data for {symbol}: {e}")
        return None
