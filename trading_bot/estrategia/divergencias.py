
# =============================================================================
# MÓDULO: DETECCIÓN DE DIVERGENCIAS RSI vs PRECIO
# =============================================================================
# Una divergencia ocurre cuando el precio y el RSI se mueven en direcciones
# opuestas. Es una de las señales de reversión más potentes del análisis técnico.
#
# DIVERGENCIA ALCISTA:
#   Precio hace un mínimo MÁS BAJO → pero RSI hace un mínimo MÁS ALTO
#   → Los vendedores pierden fuerza → posible reversión al alza
#
# DIVERGENCIA BAJISTA:
#   Precio hace un máximo MÁS ALTO → pero RSI hace un máximo MÁS BAJO
#   → Los compradores pierden fuerza → posible reversión a la baja
# =============================================================================

import pandas as pd


def detectar_divergencia_alcista(datos: pd.DataFrame,
                                  rsi: pd.Series,
                                  ventana: int = 10) -> bool:
    """
    Detecta si hay una divergencia alcista entre el precio de cierre y el RSI
    en las últimas N velas.

    Args:
        datos  : DataFrame OHLCV
        rsi    : Serie con valores del RSI
        ventana: Número de velas hacia atrás donde buscar divergencia

    Returns:
        True si se detecta divergencia alcista
    """
    precios_ventana = datos['close'].iloc[-ventana:]
    rsi_ventana     = rsi.iloc[-ventana:]

    # Mínimo de precio en la ventana y el RSI en ese momento
    idx_min_precio        = precios_ventana.idxmin()
    rsi_en_minimo_precio  = rsi_ventana.loc[idx_min_precio]

    # Precio y RSI actuales (última vela)
    precio_actual = datos['close'].iloc[-1]
    rsi_actual    = rsi.iloc[-1]

    # Divergencia: precio más bajo que su mínimo, pero RSI más alto que el RSI en ese mínimo
    return precio_actual < precios_ventana.min() and rsi_actual > rsi_en_minimo_precio


def detectar_divergencia_bajista(datos: pd.DataFrame,
                                  rsi: pd.Series,
                                  ventana: int = 10) -> bool:
    """
    Detecta si hay una divergencia bajista entre el precio de cierre y el RSI
    en las últimas N velas.

    Args:
        datos  : DataFrame OHLCV
        rsi    : Serie con valores del RSI
        ventana: Número de velas hacia atrás donde buscar divergencia

    Returns:
        True si se detecta divergencia bajista
    """
    precios_ventana = datos['close'].iloc[-ventana:]
    rsi_ventana     = rsi.iloc[-ventana:]

    # Máximo de precio en la ventana y el RSI en ese momento
    idx_max_precio        = precios_ventana.idxmax()
    rsi_en_maximo_precio  = rsi_ventana.loc[idx_max_precio]

    # Precio y RSI actuales (última vela)
    precio_actual = datos['close'].iloc[-1]
    rsi_actual    = rsi.iloc[-1]

    # Divergencia: precio más alto que su máximo, pero RSI más bajo que el RSI en ese máximo
    return precio_actual > precios_ventana.max() and rsi_actual < rsi_en_maximo_precio
