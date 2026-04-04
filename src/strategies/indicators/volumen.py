
# =============================================================================
# MÓDULO: VOLUMEN MEDIO
# =============================================================================
# El volumen confirma la fuerza de un movimiento de precio.
# Un movimiento con volumen alto es más fiable que uno con volumen bajo.
#
# Uso en este bot:
#   Si el volumen actual > volumen medio × 1.2 → confirmación de señal
#   Se aplica igual a señales LONG y SHORT
# =============================================================================

import pandas as pd
from src.core.config import PERIODO_VOLUMEN


def calcular_volumen_medio(datos: pd.DataFrame,
                            periodo: int = PERIODO_VOLUMEN) -> pd.Series:
    """
    Calcula el volumen medio a través de una media móvil simple (SMA).

    Args:
        datos  : DataFrame OHLCV
        periodo: Número de velas para el promedio (por defecto 20)

    Returns:
        Serie con el volumen medio móvil
    """
    return datos['volume'].rolling(window=periodo).mean()


def volumen_es_significativo(volumen_actual: float,
                              volumen_medio: float,
                              factor: float = 1.2) -> bool:
    """
    Determina si el volumen de la vela actual está por encima del promedio.

    Args:
        volumen_actual: Volumen de la última vela
        volumen_medio : Volumen medio de los últimos N periodos
        factor        : Multiplicador del promedio (por defecto 1.2 = 20% superior)

    Returns:
        True si el volumen actual supera el umbral establecido
    """
    return volumen_actual > volumen_medio * factor
