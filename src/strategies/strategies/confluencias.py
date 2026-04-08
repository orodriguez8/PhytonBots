
# =============================================================================
# MÓDULO: CONTEO DE CONFLUENCIAS (Motor de Señales v3 - Anti-Pérdidas)
# =============================================================================
import pandas as pd
from src.core.config import RSI_SOBREVENTA, RSI_SOBRECOMPRA

def contar_confluencias(datos: pd.DataFrame, indicadores: dict, is_crypto: bool = False) -> dict:
    """
    Evalúa condiciones de alta probabilidad separando la lógica de Acciones vs Cripto.
    """
    long_confs  = []
    short_confs = []

    p    = datos['close'].iloc[-1]
    e20  = indicadores['ema_20'].iloc[-1]
    e50  = indicadores['ema_50'].iloc[-1]
    e200 = indicadores['ema_200'].iloc[-1]
    rsi  = indicadores['rsi'].iloc[-1]
    macd = indicadores['macd'].iloc[-1]
    sig  = indicadores['macd_signal'].iloc[-1]
    hist = indicadores['macd_histogram'].iloc[-1]
    atr  = indicadores['atr'].iloc[-1]

    bb_sup  = indicadores['bb_superior'].iloc[-1]
    bb_inf  = indicadores['bb_inferior'].iloc[-1]
    vol     = datos['volume'].iloc[-1]
    vol_med = indicadores['volumen_medio'].iloc[-1]

    try:
        hist_previo = indicadores['macd_histogram'].iloc[-2]
        prev_close  = datos['close'].iloc[-2]
    except Exception:
        hist_previo = hist
        prev_close  = p

    if not is_crypto:
        # =========================================================================
        # ESTRATEGIA ACCIONES — Trend Following Disciplinado
        # Objetivo: Evitar operar contra la tendencia primaria.
        # 5 condiciones disponibles. MIN_CONFLUENCIAS = 3 para ejecutar.
        # =========================================================================

        # ── LONG ──────────────────────────────────────────────────────────────────

        # 1. FILTRO MACRO: Tendencia principal alcista (Golden Cross en vigor)
        if e50 > e200:
            long_confs.append("✅ Macro Alcista: EMA50 > EMA200 (Golden Cross activo)")

        # 2. ESTRUCTURA: Precio por encima de EMA20 y EMA50 (momentum alcista)
        if p > e20 and p > e50:
            long_confs.append("✅ Estructura: Precio sobre EMA20 y EMA50")

        # 3. RSI: En zona de momentum sano, sin sobrecompra extrema
        if 45 <= rsi <= 72:
            long_confs.append(f"✅ RSI en zona alcista sana: {rsi:.1f}")

        # 4. MACD: Histograma positivo y en expansión
        if hist > 0 and hist > hist_previo:
            long_confs.append("✅ MACD: Momentum alcista en expansion")

        # 5. VOLUMEN: Confirmación de volumen sobre la media
        if vol > vol_med * 0.9:
            long_confs.append("✅ Volumen: Por encima del 90% de la media")

        # ── SHORT ─────────────────────────────────────────────────────────────────

        # 1. FILTRO MACRO: Tendencia principal bajista (Death Cross)
        if e50 < e200:
            short_confs.append("🔴 Macro Bajista: EMA50 < EMA200 (Death Cross activo)")

        # 2. ESTRUCTURA: Precio debajo de EMA20 y EMA50
        if p < e20 and p < e50:
            short_confs.append("🔴 Estructura: Precio bajo EMA20 y EMA50")

        # 3. RSI: En zona bajista sin sobreventa extrema
        if 28 <= rsi <= 55:
            short_confs.append(f"🔴 RSI en canal bajista: {rsi:.1f}")

        # 4. MACD: Histograma negativo y en contraccion
        if hist < 0 and hist < hist_previo:
            short_confs.append("🔴 MACD: Momentum bajista en expansion")

        # 5. VOLUMEN: Presión vendedora confirmada
        if vol > vol_med * 0.9:
            short_confs.append("🔴 Volumen: Presion vendedora confirmada")

    else:
        # =========================================================================
        # ESTRATEGIA CRIPTO — Mean Reversion Conservadora con Filtro Macro
        # Objetivo: Solo comprar pullbacks en tendencia alcista. NUNCA contra tendencia.
        # Long-only (Alpaca no permite short en crypto).
        # 5 condiciones. MIN_CONFLUENCIAS = 3 para ejecutar.
        # =========================================================================

        # ── FILTRO MACRO OBLIGATORIO: EMA200 como filtro de tendencia primaria ───
        # Si el precio está bajo la EMA200 = bear market primario = NO operar.
        macro_alcista = p > e200

        if macro_alcista:
            long_confs.append("✅ Macro: Precio sobre EMA200 (Tendencia primaria alcista)")

            # 1. PULLBACK A ZONA DE VALOR: EMA20 o BB inferior
            en_zona_pullback = (p <= e20 * 1.005) or (p <= bb_inf * 1.02)
            if en_zona_pullback:
                long_confs.append("✅ Estructura: Pullback a soporte (EMA20 / BB inferior)")

            # 2. RSI: Sobreventa relativa (momentum agotado en la corrección)
            if rsi < 50:
                long_confs.append(f"✅ RSI en sobreventa relativa: {rsi:.1f}")

            # 3. MACD: Señal de rebote (histograma mejorando)
            if (hist > hist_previo) or (macd > sig and hist > -0.5 * abs(hist_previo + 0.0001)):
                long_confs.append("✅ MACD: Señal de rebote / inercia positiva")

            # 4. VOLUMEN: Confirmacion (no operar en silencio de mercado)
            if vol > vol_med * 0.8:
                long_confs.append("✅ Volumen: Actividad suficiente para confirmar movimiento")

    return {
        'long':        long_confs,
        'short':       short_confs,
        'total_long':  len(long_confs),
        'total_short': len(short_confs),
    }
