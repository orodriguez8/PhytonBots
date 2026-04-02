
# =============================================================================
# MÓDULO: ATR (Average True Range - Rango Verdadero Promedio)
# =============================================================================
# El ATR mide la volatilidad del mercado teniendo en cuenta los gaps entre
# velas consecutivas (algo que el rango simple High-Low no considera).
#
# True Range (TR) es el mayor de:
#   1. High actual - Low actual
#   2. |High actual - Cierre anterior|
#   3. |Low actual  - Cierre anterior|
#
# ATR = Media exponencial del True Range en N periodos
#
# Uso en este bot:
#   Stop Loss  = precio_entrada ± (ATR × 1.5)
#   Take Profit = precio_entrada ± (ATR × 3.0)
#   → Stop loss dinámico que se adapta a la volatilidad del mercado
# =============================================================================

import pandas as pd
from config import PERIODO_ATR


def calcular_atr(datos: pd.DataFrame, periodo: int = PERIODO_ATR) -> pd.Series:
    """
    Calcula el ATR usando el método de media exponencial de Wilder.

    Args:
        datos  : DataFrame OHLCV
        periodo: Número de periodos (por defecto 14)

    Returns:
        Serie con los valores del ATR
    """
    cierre_anterior = datos['close'].shift(1)

    # Las tres medidas del True Range
    tr1 = datos['high'] - datos['low']                  # Rango de la vela
    tr2 = (datos['high'] - cierre_anterior).abs()       # Gap alcista
    tr3 = (datos['low']  - cierre_anterior).abs()       # Gap bajista

    # True Range = el mayor de los tres
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # ATR = media exponencial del True Range (suavizado de Wilder)
    atr = true_range.ewm(com=periodo - 1, adjust=False).mean()
    return atr
