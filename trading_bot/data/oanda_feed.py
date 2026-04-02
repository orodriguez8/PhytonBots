
# =============================================================================
# MÓDULO: DATOS EN TIEMPO REAL VÍA OANDA API v20
# =============================================================================
# Reemplaza al simulador con datos reales de Oanda.
# Requiere que OANDA_API_KEY y OANDA_ACCOUNT_ID estén en el archivo .env
# =============================================================================

import os
import pandas as pd
import oandapyV20
import oandapyV20.endpoints.instruments as instruments

from config import OANDA_INSTRUMENT, OANDA_GRANULARITY, N_VELAS


def _get_client() -> oandapyV20.API:
    """Crea y devuelve un cliente de la API de Oanda."""
    api_key = os.getenv('OANDA_API_KEY')
    environment = os.getenv('OANDA_ENVIRONMENT', 'practice')  # 'practice' = demo
    if not api_key:
        raise ValueError("OANDA_API_KEY no encontrada. Revisa tu archivo .env")
    return oandapyV20.API(access_token=api_key, environment=environment)


def obtener_datos_oanda(n_velas: int = N_VELAS,
                        instrumento: str = None,
                        granularidad: str = None) -> pd.DataFrame:
    """
    Descarga las últimas n_velas velas OHLCV del instrumento indicado desde Oanda.

    Args:
        n_velas      : Número de velas a descargar (máx. 5000 por petición)
        instrumento  : Par de divisas. Ej: 'EUR_USD', 'GBP_USD', 'US30_USD'
        granularidad : Temporalidad. Ej: 'H1', 'M15', 'D'

    Returns:
        DataFrame con columnas: open, high, low, close, volume
        e índice de tipo DatetimeIndex (UTC)
    """
    instrumento  = instrumento  or os.getenv('OANDA_INSTRUMENT', OANDA_INSTRUMENT)
    granularidad = granularidad or os.getenv('OANDA_GRANULARITY', OANDA_GRANULARITY)

    client = _get_client()

    params = {
        'count':       str(n_velas),
        'granularity': granularidad,
        'price':       'M',   # Mid prices (punto medio bid/ask)
    }

    req = instruments.InstrumentsCandles(instrument=instrumento, params=params)
    client.request(req)

    candles = req.response.get('candles', [])

    rows = []
    for c in candles:
        # Omitir velas incompletas (la vela actual aún está formándose)
        if not c.get('complete', True):
            continue
        rows.append({
            'time':   pd.Timestamp(c['time']),
            'open':   float(c['mid']['o']),
            'high':   float(c['mid']['h']),
            'low':    float(c['mid']['l']),
            'close':  float(c['mid']['c']),
            'volume': int(c['volume']),
        })

    if not rows:
        raise ValueError(f"Oanda no devolvió velas para {instrumento} ({granularidad})")

    df = pd.DataFrame(rows).set_index('time')
    df.index = pd.to_datetime(df.index, utc=True)
    return df
