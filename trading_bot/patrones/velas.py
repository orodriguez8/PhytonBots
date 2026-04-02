
# =============================================================================
# MÓDULO: DETECCIÓN DE PATRONES DE VELAS JAPONESAS
# =============================================================================
# Las velas japonesas revelan la psicología del mercado en cada periodo.
# Este módulo detecta los patrones de reversión más importantes.
#
# Patrones implementados:
#   🕯️ Doji           → Indecisión (cuerpo casi inexistente)
#   🔨 Martillo        → Reversión alcista (mecha inferior larga)
#   🔨 Martillo Inv.   → Reversión alcista (mecha superior larga, vela alcista)
#   💫 Estrella Fugaz  → Reversión bajista (mecha superior larga, vela bajista)
#   🟢 Engulfing Alc.  → Vela alcista que envuelve la vela bajista anterior
#   🔴 Engulfing Baj.  → Vela bajista que envuelve la vela alcista anterior
#   📌 Pin Bar Alcista → Mecha inferior ≥ 70% del rango
#   📌 Pin Bar Bajista → Mecha superior ≥ 70% del rango
# =============================================================================

import pandas as pd


def detectar_patron(datos: pd.DataFrame, indice: int = -1) -> str:
    """
    Analiza la vela en la posición indicada y devuelve el patrón detectado.

    Args:
        datos : DataFrame OHLCV
        indice: Posición de la vela a analizar (-1 = última)

    Returns:
        String con el nombre del patrón detectado o 'Sin patrón relevante'
    """
    # Normalizar el índice negativo a un índice positivo
    idx = len(datos) - 1 if indice == -1 else indice
    if idx < 1:
        return "Datos insuficientes para detectar patrón"

    # ── Vela actual ──────────────────────────────────────────────────────────
    o = datos['open'].iloc[idx]
    h = datos['high'].iloc[idx]
    l = datos['low'].iloc[idx]
    c = datos['close'].iloc[idx]

    cuerpo          = abs(c - o)
    rango_total     = h - l
    mecha_superior  = h - max(o, c)
    mecha_inferior  = min(o, c) - l
    es_alcista      = c > o

    if rango_total == 0:
        return "Sin patrón relevante"

    # ── Vela anterior (necesaria para Engulfing) ─────────────────────────────
    o_ant = datos['open'].iloc[idx - 1]
    c_ant = datos['close'].iloc[idx - 1]
    cuerpo_ant     = abs(c_ant - o_ant)
    es_alcista_ant = c_ant > o_ant

    # ── DOJI ─────────────────────────────────────────────────────────────────
    # Cuerpo < 10% del rango total → compradores y vendedores empatados
    if cuerpo / rango_total < 0.10:
        return "🕯️ Doji (Indecisión)"

    # ── MARTILLO ──────────────────────────────────────────────────────────────
    # Cuerpo en la parte superior de la vela, mecha inferior larga.
    # Señal alcista cuando aparece al final de una tendencia bajista.
    if (mecha_inferior >= 2 * cuerpo and
            mecha_superior < cuerpo * 0.5 and
            cuerpo / rango_total < 0.4):
        return "🔨 Martillo (Señal Alcista)"

    # ── MARTILLO INVERTIDO / ESTRELLA FUGAZ ──────────────────────────────────
    # Cuerpo en la parte inferior de la vela, mecha superior larga.
    if (mecha_superior >= 2 * cuerpo and
            mecha_inferior < cuerpo * 0.5 and
            cuerpo / rango_total < 0.4):
        if es_alcista:
            return "🔨 Martillo Invertido (Señal Alcista)"
        else:
            return "💫 Estrella Fugaz (Señal Bajista)"

    # ── PIN BAR ───────────────────────────────────────────────────────────────
    # La mecha domina el 70% o más del rango total → fuerte rechazo de precio
    if mecha_inferior / rango_total >= 0.70:
        return "📌 Pin Bar Alcista (Rechazo de Mínimos)"
    if mecha_superior / rango_total >= 0.70:
        return "📌 Pin Bar Bajista (Rechazo de Máximos)"

    # ── ENGULFING ALCISTA ─────────────────────────────────────────────────────
    # Vela alcista que envuelve por completo la vela bajista anterior.
    # Muestra que los compradores tomaron el control tras una vela bajista.
    if (es_alcista and not es_alcista_ant and
            o < c_ant and c > o_ant and
            cuerpo > cuerpo_ant):
        return "🟢 Engulfing Alcista (Fuerte Señal de Compra)"

    # ── ENGULFING BAJISTA ─────────────────────────────────────────────────────
    # Vela bajista que envuelve por completo la vela alcista anterior.
    if (not es_alcista and es_alcista_ant and
            o > c_ant and c < o_ant and
            cuerpo > cuerpo_ant):
        return "🔴 Engulfing Bajista (Fuerte Señal de Venta)"

    return "Sin patrón relevante"
