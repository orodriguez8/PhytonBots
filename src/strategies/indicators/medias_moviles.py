
# =============================================================================
# MÓDULO: MEDIAS MÓVILES EXPONENCIALES (EMA)
# =============================================================================
# La EMA da más peso a los precios recientes que la SMA.
# Se usa para identificar la tendencia en diferentes marcos temporales:
#   EMA 20  → Tendencia de corto plazo
#   EMA 50  → Tendencia de medio plazo
#   EMA 200 → Tendencia principal / filtro de dirección
# =============================================================================

import pandas as pd
from src.core.config import PERIODO_EMA_RAPIDA, PERIODO_EMA_MEDIA, PERIODO_EMA_LENTA


def calcular_ema(serie: pd.Series, periodo: int) -> pd.Series:
    """
    Calcula la Media Móvil Exponencial para cualquier serie y periodo.

    Fórmula:
        EMA(t) = precio(t) × k + EMA(t-1) × (1 - k)
        donde k = 2 / (periodo + 1)

    Args:
        serie  : Serie de precios (normalmente el cierre)
        periodo: Número de periodos

    Returns:
        Serie con los valores EMA
    """
    return serie.ewm(span=periodo, adjust=False).mean()


def calcular_emas(datos: pd.DataFrame) -> dict:
    """
    Calcula las EMAs principales (9, 21, 20, 50, 200) sobre el precio de cierre.

    Args:
        datos: DataFrame OHLCV

    Returns:
        Diccionario con las series de EMA
    """
    return {
        'ema_9':   calcular_ema(datos['close'], 9),
        'ema_21':  calcular_ema(datos['close'], 21),
        'ema_20':  calcular_ema(datos['close'], PERIODO_EMA_RAPIDA),
        'ema_50':  calcular_ema(datos['close'], PERIODO_EMA_MEDIA),
        'ema_200': calcular_ema(datos['close'], PERIODO_EMA_LENTA),
    }
