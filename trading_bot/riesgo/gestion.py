
# =============================================================================
# MÓDULO: GESTIÓN DE RIESGO
# =============================================================================
# La gestión de riesgo es la parte más importante de cualquier estrategia.
# Un buen trader puede ganar sólo el 40% de sus operaciones y ser rentable
# si el ratio Riesgo:Beneficio es lo suficientemente favorable.
#
# Principios aplicados en este módulo:
#   1. Stop Loss dinámico basado en ATR (se adapta a la volatilidad actual)
#   2. Take Profit con ratio 1:2 (ganar el doble de lo que se arriesga)
#   3. Nunca arriesgar más del 2% del capital total por operación
#   4. Tamaño de posición calculado automáticamente según el riesgo definido
# =============================================================================

from config import (
    CAPITAL_INICIAL, RIESGO_POR_OPERACION,
    MULTIPLICADOR_ATR_SL, MULTIPLICADOR_ATR_TP
)


def calcular_gestion_riesgo(direccion: str,
                              precio_entrada: float,
                              atr: float,
                              capital: float = CAPITAL_INICIAL,
                              mult_sl: float  = MULTIPLICADOR_ATR_SL,
                              mult_tp: float  = MULTIPLICADOR_ATR_TP,
                              riesgo: float   = RIESGO_POR_OPERACION) -> dict:
    """
    Calcula el stop loss, take profit y tamaño de posición para una operación.

    Fórmulas:
        LONG:
            Stop Loss   = entrada - (ATR × mult_sl)
            Take Profit = entrada + (ATR × mult_tp)
        SHORT:
            Stop Loss   = entrada + (ATR × mult_sl)
            Take Profit = entrada - (ATR × mult_tp)

        Riesgo por unidad   = |entrada - stop_loss|
        Capital en riesgo   = capital_total × riesgo_por_operacion
        Tamaño de posición  = capital_en_riesgo / riesgo_por_unidad

    Args:
        direccion     : 'LONG' o 'SHORT'
        precio_entrada: Precio al que se ejecuta la entrada
        atr           : Valor actual del ATR
        capital       : Capital total disponible
        mult_sl       : Multiplicador del ATR para el Stop Loss
        mult_tp       : Multiplicador del ATR para el Take Profit
        riesgo        : Fracción del capital a arriesgar (ej: 0.02 = 2%)

    Returns:
        Diccionario con la gestión completa de la operación, o {} si la
        dirección no es válida.
    """
    if direccion == 'LONG':
        stop_loss   = precio_entrada - (atr * mult_sl)
        take_profit = precio_entrada + (atr * mult_tp)
    elif direccion == 'SHORT':
        stop_loss   = precio_entrada + (atr * mult_sl)
        take_profit = precio_entrada - (atr * mult_tp)
    else:
        return {}

    riesgo_por_unidad   = abs(precio_entrada - stop_loss)
    capital_en_riesgo   = capital * riesgo
    tamano_posicion     = capital_en_riesgo / riesgo_por_unidad
    beneficio_potencial = abs(take_profit - precio_entrada)
    ratio_riesgo        = beneficio_potencial / riesgo_por_unidad
    valor_posicion      = tamano_posicion * precio_entrada

    return {
        'direccion':          direccion,
        'precio_entrada':     precio_entrada,
        'stop_loss':          stop_loss,
        'take_profit':        take_profit,
        'atr':                atr,
        'riesgo_por_unidad':  riesgo_por_unidad,
        'capital_total':      capital,
        'capital_en_riesgo':  capital_en_riesgo,
        'tamano_posicion':    tamano_posicion,
        'valor_posicion':     valor_posicion,
        'ratio_riesgo':       ratio_riesgo,
    }
