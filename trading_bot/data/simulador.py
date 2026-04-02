
# =============================================================================
# MÓDULO: GENERACIÓN DE DATOS OHLCV SIMULADOS
# =============================================================================
# Genera velas OHLCV (Open, High, Low, Close, Volume) con tendencia y
# volatilidad realistas usando movimiento browniano geométrico.
#
# En producción, sustituye generar_datos() por la carga de datos reales:
#   - pd.read_csv('datos.csv')
#   - CCXT (criptomonedas)
#   - MetaTrader 5 (forex/CFDs)
#   - Interactive Brokers (acciones)
# =============================================================================

import numpy as np
import pandas as pd
from config import (
    N_VELAS, PRECIO_INICIAL, TENDENCIA, VOLATILIDAD, SEMILLA_ALEATORIA
)


def generar_datos(n_velas: int = N_VELAS,
                  precio_inicial: float = PRECIO_INICIAL,
                  tendencia: float = TENDENCIA,
                  volatilidad: float = VOLATILIDAD,
                  semilla: int = SEMILLA_ALEATORIA) -> pd.DataFrame:
    """
    Genera un DataFrame OHLCV simulado y realista.

    Técnica: Movimiento Browniano Geométrico (GBM) con superposición de
    ciclos sinusoidales para imitar los ciclos naturales del mercado.

    Args:
        n_velas       : Número de velas a generar
        precio_inicial: Precio de cierre de la primera vela
        tendencia     : Drift por vela (positivo = alcista)
        volatilidad   : Desviación estándar de los retornos por vela
        semilla       : Semilla para reproducibilidad

    Returns:
        DataFrame con índice de fechas y columnas: open, high, low, close, volume
    """
    np.random.seed(semilla)

    # Retornos con tendencia + ruido gaussiano
    retornos = np.random.normal(tendencia, volatilidad, n_velas)

    # Añadir dos ciclos de mercado para hacer los datos más realistas
    ciclo_largo  = 0.002 * np.sin(np.linspace(0,  4 * np.pi, n_velas))
    ciclo_corto  = 0.001 * np.sin(np.linspace(0, 12 * np.pi, n_velas))
    retornos += ciclo_largo + ciclo_corto

    # Precios de cierre acumulando los retornos logarítmicos
    cierres = precio_inicial * np.exp(np.cumsum(retornos))

    opens   = np.zeros(n_velas)
    highs   = np.zeros(n_velas)
    lows    = np.zeros(n_velas)
    volumes = np.zeros(n_velas)

    opens[0] = precio_inicial

    for i in range(n_velas):
        # El open es el cierre anterior con un pequeño gap de apertura
        if i > 0:
            gap = np.random.normal(0, volatilidad * 0.3)
            opens[i] = cierres[i - 1] * (1 + gap)

        # High y Low dependen del rango natural de esa vela
        rango = abs(np.random.normal(0, volatilidad * 1.5))
        highs[i] = max(opens[i], cierres[i]) * (1 + rango)
        lows[i]  = min(opens[i], cierres[i]) * (1 - rango)

        # El volumen es mayor en movimientos más grandes (correlación real)
        vol_base = 100_000
        factor   = 1 + abs(retornos[i]) / volatilidad * 2
        volumes[i] = vol_base * factor * np.random.uniform(0.5, 1.5)

    fechas = pd.date_range(end=pd.Timestamp.now(), periods=n_velas, freq='1h')
    return pd.DataFrame(
        {'open': opens, 'high': highs, 'low': lows,
         'close': cierres, 'volume': volumes},
        index=fechas
    )
