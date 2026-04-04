
# =============================================================================
# MÓDULO: MACD (Moving Average Convergence Divergence)
# =============================================================================
# El MACD detecta cambios en la fuerza, dirección y momentum de la tendencia.
# Componentes:
#   Línea MACD  = EMA(12) - EMA(26)
#   Señal       = EMA(9) de la línea MACD
#   Histograma  = MACD - Señal  (mide la divergencia entre ambas)
#
# Señales clave:
#   → MACD cruza la señal al alza: momentum alcista
#   → MACD cruza la señal a la baja: momentum bajista
#   → Histograma positivo y creciendo: tendencia alcista fuerte
# =============================================================================

import pandas as pd
from src.core.config import MACD_RAPIDO, MACD_LENTO, MACD_SIGNAL


def calcular_macd(datos: pd.DataFrame,
                  rapido: int = MACD_RAPIDO,
                  lento: int  = MACD_LENTO,
                  signal: int = MACD_SIGNAL) -> dict:
    """
    Calcula el indicador MACD completo: línea MACD, señal e histograma.

    Args:
        datos : DataFrame OHLCV
        rapido: Periodo de la EMA rápida (por defecto 12)
        lento : Periodo de la EMA lenta (por defecto 26)
        signal: Periodo de la línea de señal (por defecto 9)

    Returns:
        Diccionario con:
            'macd'      → Línea MACD
            'signal'    → Línea de señal
            'histogram' → Histograma (diferencia MACD - señal)
    """
    ema_rapida  = datos['close'].ewm(span=rapido, adjust=False).mean()
    ema_lenta   = datos['close'].ewm(span=lento,  adjust=False).mean()
    linea_macd  = ema_rapida - ema_lenta
    linea_signal = linea_macd.ewm(span=signal, adjust=False).mean()
    histograma  = linea_macd - linea_signal

    return {
        'macd':      linea_macd,
        'signal':    linea_signal,
        'histogram': histograma,
    }


def hay_cruce_alza(macd: pd.Series, signal: pd.Series) -> bool:
    """
    Detecta si el MACD acaba de cruzar la señal al alza en la última vela.
    (Vela anterior: MACD < señal → Vela actual: MACD > señal)

    Args:
        macd  : Serie de la línea MACD
        signal: Serie de la línea de señal

    Returns:
        True si hay cruce alcista en la última vela
    """
    return (macd.iloc[-2] < signal.iloc[-2]) and (macd.iloc[-1] > signal.iloc[-1])


def hay_cruce_baja(macd: pd.Series, signal: pd.Series) -> bool:
    """
    Detecta si el MACD acaba de cruzar la señal a la baja en la última vela.

    Args:
        macd  : Serie de la línea MACD
        signal: Serie de la línea de señal

    Returns:
        True si hay cruce bajista en la última vela
    """
    return (macd.iloc[-2] > signal.iloc[-2]) and (macd.iloc[-1] < signal.iloc[-1])
