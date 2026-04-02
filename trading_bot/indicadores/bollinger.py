
# =============================================================================
# MÓDULO: BANDAS DE BOLLINGER
# =============================================================================
# Las Bandas de Bollinger miden la volatilidad del mercado.
# Se construyen a partir de una media móvil simple (SMA) y su desviación std.
#
# Componentes:
#   Banda Media    = SMA(20) del precio de cierre
#   Banda Superior = Media + (2 × desviación estándar)
#   Banda Inferior = Media - (2 × desviación estándar)
#
# Interpretación:
#   Precio toca banda inferior → posible sobreventa   → señal LONG
#   Precio toca banda superior → posible sobrecompra  → señal SHORT
#   Bandas muy estrechas       → baja volatilidad → posible explosión inminente
# =============================================================================

import pandas as pd
from config import PERIODO_BOLLINGER, DESVIACIONES_BB


def calcular_bollinger(datos: pd.DataFrame,
                        periodo: int    = PERIODO_BOLLINGER,
                        desviaciones: float = DESVIACIONES_BB) -> dict:
    """
    Calcula las Bandas de Bollinger completas.

    Args:
        datos       : DataFrame OHLCV
        periodo     : Periodos de la media móvil (por defecto 20)
        desviaciones: Número de desviaciones estándar (por defecto 2.0)

    Returns:
        Diccionario con:
            'banda_media'    → SMA del precio de cierre
            'banda_superior' → Media + N desviaciones
            'banda_inferior' → Media - N desviaciones
            'ancho'          → Ancho relativo (volatilidad normalizada)
    """
    media      = datos['close'].rolling(window=periodo).mean()
    desviacion = datos['close'].rolling(window=periodo).std()

    superior = media + (desviaciones * desviacion)
    inferior = media - (desviaciones * desviacion)
    ancho    = (superior - inferior) / media   # Ancho relativo al precio

    return {
        'banda_media':    media,
        'banda_superior': superior,
        'banda_inferior': inferior,
        'ancho':          ancho,
    }


def posicion_en_banda(precio: float, superior: float, inferior: float) -> str:
    """
    Determina si el precio está tocando alguna banda.

    Args:
        precio  : Precio actual de cierre
        superior: Valor actual de la banda superior
        inferior: Valor actual de la banda inferior

    Returns:
        Etiqueta descriptiva de la posición del precio respecto a las bandas
    """
    tolerancia = 0.005  # 0.5% de margen para considerar "toca" la banda
    if precio <= inferior * (1 + tolerancia):
        return "🔵 Banda Inferior (posible sobreventa)"
    elif precio >= superior * (1 - tolerancia):
        return "🔴 Banda Superior (posible sobrecompra)"
    else:
        return "⚪ Dentro de las bandas"
