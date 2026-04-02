
# =============================================================================
# MÓDULO: RSI (Relative Strength Index - Índice de Fuerza Relativa)
# =============================================================================
# El RSI mide la velocidad y magnitud de los movimientos de precio.
# Oscila entre 0 y 100:
#   RSI < 30 → Zona de sobreventa  (precio posiblemente muy barato → señal LONG)
#   RSI > 70 → Zona de sobrecompra (precio posiblemente muy caro  → señal SHORT)
#   RSI ≈ 50 → Equilibrio entre compradores y vendedores
#
# Cálculo:
#   RS  = Media de subidas / Media de bajadas (en N periodos)
#   RSI = 100 - (100 / (1 + RS))
# =============================================================================

import pandas as pd
from config import PERIODO_RSI, RSI_SOBREVENTA, RSI_SOBRECOMPRA


def calcular_rsi(datos: pd.DataFrame, periodo: int = PERIODO_RSI) -> pd.Series:
    """
    Calcula el RSI usando medias móviles exponenciales (método de Wilder).

    Args:
        datos  : DataFrame OHLCV
        periodo: Número de periodos (por defecto 14)

    Returns:
        Serie con valores RSI entre 0 y 100
    """
    delta = datos['close'].diff()

    # Separar movimientos positivos (ganancias) y negativos (pérdidas)
    ganancias = delta.where(delta > 0, 0.0)
    perdidas  = -delta.where(delta < 0, 0.0)

    # Suavizado exponencial (método de Wilder = EWM con com = periodo - 1)
    media_ganancias = ganancias.ewm(com=periodo - 1, adjust=False).mean()
    media_perdidas  = perdidas.ewm(com=periodo - 1, adjust=False).mean()

    rs  = media_ganancias / media_perdidas
    rsi = 100 - (100 / (1 + rs))
    return rsi


def zona_rsi(valor: float) -> str:
    """
    Devuelve una etiqueta descriptiva según el valor del RSI.

    Args:
        valor: Valor numérico del RSI

    Returns:
        Etiqueta de zona: 'Sobrecompra', 'Sobreventa' o 'Neutral'
    """
    if valor > RSI_SOBRECOMPRA:
        return f"🔴 Sobrecompra ({valor:.1f})"
    elif valor < RSI_SOBREVENTA:
        return f"🟢 Sobreventa ({valor:.1f})"
    else:
        return f"⚪ Neutral ({valor:.1f})"
