
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
        # ESTRATEGIA ACCIONES — SISTEMA EXPERTO DE ANÁLISIS TÉCNICO
        # Scoring 0-10 | Umbral >= 7
        # =========================================================================
        score_long  = 0
        score_short = 0

        # Adquirir indicadores extendidos si existen
        adx  = indicadores.get('adx', pd.Series(0, index=datos.index)).iloc[-1]
        vwap = indicadores.get('vwap', datos['close']).iloc[-1]
        obv  = indicadores.get('obv', pd.Series(0, index=datos.index)).iloc[-1]
        
        # 1. TENDENCIA ALINEADA TF MÚLTIPLE: +2
        # (Proxy: EMA50 > EMA200 y Precio > EMA200)
        macro_alcista = e50 > e200 and p > e200
        macro_bajista = e50 < e200 and p < e200
        
        if macro_alcista:
            score_long += 2
            long_confs.append("✅ Tendencia MTF Alineada (+2)")
        elif macro_bajista:
            score_short += 2
            short_confs.append("🔴 Tendencia MTF Alineada (+2)")

        # 2. VWAP COMO SOPORTE/RESISTENCIA: +1.5
        if p > vwap and macro_alcista:
            score_long += 1.5
            long_confs.append("✅ Precio sobre VWAP/Soporte (+1.5)")
        elif p < vwap and macro_bajista:
            score_short += 1.5
            short_confs.append("🔴 Precio bajo VWAP/Resistencia (+1.5)")

        # 3. RSI EN ZONA ÓPTIMA: +1.5
        # Alcista: 45-65 | Bajista: 35-55
        if 45 <= rsi <= 65:
            score_long += 1.5
            long_confs.append(f"✅ RSI Zona Óptima ({rsi:.1f}) (+1.5)")
        elif 35 <= rsi <= 55:
            score_short += 1.5
            short_confs.append(f"🔴 RSI Zona Óptima ({rsi:.1f}) (+1.5)")

        # 4. MACD ALINEADO: +1
        if hist > 0 and hist > hist_previo:
            score_long += 1
            long_confs.append("✅ MACD Alineado y en Expansión (+1)")
        elif hist < 0 and hist < hist_previo:
            score_short += 1
            short_confs.append("🔴 MACD Alineado y en Expansión (+1)")

        # 5. VOLUMEN CONFIRMA: +1.5
        if vol > vol_med * 1.2:
            score_long += 1.5
            score_short += 1.5
            long_confs.append("✅ Volumen Confirmado (>1.2x) (+1.5)")
            short_confs.append("🔴 Volumen Confirmado (>1.2x) (+1.5)")

        # 6. DIVERGENCIA FAVORABLE: +1.5 (Simplificada: RSI vs Precio)
        if rsi > indicadores['rsi'].iloc[-2] and p < prev_close:
            score_long += 1.5
            long_confs.append("✅ Divergencia Alcista Detectada (+1.5)")
        elif rsi < indicadores['rsi'].iloc[-2] and p > prev_close:
            score_short += 1.5
            short_confs.append("🔴 Divergencia Bajista Detectada (+1.5)")

        # 7. PATRÓN DE VELAS: +1 (Momento histórico vs previo)
        if abs(hist) > abs(hist_previo) * 1.1:
            score_long += 1
            score_short += 1
            long_confs.append("✅ Patrón de Impulso Confirmado (+1)")
            short_confs.append("🔴 Patrón de Impulso Confirmado (+1)")

        # Inyectamos el score en el resultado para el bot
        long_confs.append(f"TOTAL SCORE: {score_long}/10")
        short_confs.append(f"TOTAL SCORE: {score_short}/10")
        
        final_long = score_long
        final_short = score_short

    else:
        # =========================================================================
        # ESTRATEGIA CRIPTO — SISTEMA EXPERTO (SOLO LONG)
        # Scoring 0-10 | Umbral >= 7.5
        # =========================================================================
        score_long = 0
        
        # Indicadores requeridos
        e9   = indicadores.get('ema_9', p)
        e21  = indicadores.get('ema_21', p)
        adx  = indicadores.get('adx', pd.Series(0, index=datos.index)).iloc[-1]
        vwap = indicadores.get('vwap', datos['close']).iloc[-1]
        
        # 1. BTC EN TENDENCIA FAVORABLE (Proxy: e50 > e200 en 15m como indicador de mercado)
        if e50 > e200:
            score_long += 2
            long_confs.append("✅ BTC/Mercado en Tendencia Favorable (+2)")
        
        # 2. TRIPLE EMA ALINEADA (9 > 21 > 50): +1.5
        if e9.iloc[-1] > e21.iloc[-1] > e50:
            score_long += 1.5
            long_confs.append("✅ Triple EMA Alcista Alineada (+1.5)")

        # 3. RSI EN ZONA ÓPTIMA + SIN DIVERGENCIA ADVERSA: +1.5
        # Zona TREND: 45-60
        if 45 <= rsi <= 60:
            score_long += 1.5
            long_confs.append(f"✅ RSI en Zona de Momentum ({rsi:.1f}) (+1.5)")

        # 4. MACD ALINEADO: +1
        if hist > 0 and hist > hist_previo:
            score_long += 1
            long_confs.append("✅ MACD Alcista en Expansión (+1)")

        # 5. VOLUMEN CONFIRMA: +1.5
        if vol > vol_med * 1.4:
            score_long += 1.5
            long_confs.append("✅ Volumen de Ruptura Confirmado (+1.5)")

        # 6. PATRÓN DE VELAS / PULLBACK (+1 / +1.5)
        # Pullback a EMA21
        if p <= e21.iloc[-1] * 1.002 and p >= e21.iloc[-1] * 0.998:
            score_long += 1.5
            long_confs.append("✅ Pullback a EMA21 Confirmado (+1.5)")

        # 7. ZONA TÉCNICA RELEVANTE: +1.5
        if p > vwap:
            score_long += 1.5
            long_confs.append("✅ Confluencia sobre VWAP (+1.5)")

        # MODO DE MERCADO (ADX)
        regime = "TREND" if adx > 25 else "MEAN_REV" if adx < 20 else "HYBRID"
        long_confs.append(f"🔍 Régimen detectado: {regime} (ADX: {adx:.1f})")
        long_confs.append(f"TOTAL SCORE: {score_long}/10")
        
        final_long = score_long
        final_short = 0

    return {
        'long':        long_confs,
        'short':       short_confs,
        'total_long':  final_long,
        'total_short': final_short,
    }
