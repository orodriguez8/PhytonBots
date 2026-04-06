
# =============================================================================
# MÓDULO: CONTEO DE CONFLUENCIAS (Motor de Señales Mejorado para Auto-Trading)
# =============================================================================
import pandas as pd
from src.core.config import RSI_SOBREVENTA, RSI_SOBRECOMPRA

def contar_confluencias(datos: pd.DataFrame, indicadores: dict, is_crypto: bool = False) -> dict:
    """
    Evalúa condiciones de alta probabilidad separando la lógica de Acciones vs Cripto.
    """
    long_confs  = []
    short_confs = []

    p   = datos['close'].iloc[-1]
    e20 = indicadores['ema_20'].iloc[-1]
    e50 = indicadores['ema_50'].iloc[-1]
    e200 = indicadores['ema_200'].iloc[-1]
    rsi = indicadores['rsi'].iloc[-1]
    macd = indicadores['macd'].iloc[-1]
    sig  = indicadores['macd_signal'].iloc[-1]
    hist = indicadores['macd_histogram'].iloc[-1]
    
    bb_sup = indicadores['bb_superior'].iloc[-1]
    bb_inf = indicadores['bb_inferior'].iloc[-1]
    
    try:
        hist_previo = indicadores['macd_histogram'].iloc[-2]
    except:
        hist_previo = hist

    if not is_crypto:
        # =========================================================================
        # ESTRATEGIA ACCIONES (Asimétrica Trend Following)
        # =========================================================================
        if e50 > e200 and e20 > e50:
            long_confs.append("Filtro Macro: Full Tendencia Alcista (Doble confirmación)")
            
        if p > e20 and p < bb_sup * 0.995: 
            long_confs.append("Filtro Estructural: Flotando sobre EMA 20 pero con recorrido hacia arriba")

        if 45 <= rsi <= 65:
            long_confs.append("Filtro Fuerza: RSI en canal alcista sano y sin sobrecompra")
            
        if hist > 0 and macd > sig:
            long_confs.append("Disparador Momentum: MACD en ciclo pleno de expansión alcista")

        # Cortos en Acciones
        if e50 < e200 and e20 < e50:
            short_confs.append("Filtro Macro: Full Tendencia Bajista (Doble confirmación)")

        if p < e20 and p > bb_inf * 1.005:
            short_confs.append("Filtro Estructural: Debajo de EMA 20 pero con recorrido hacia abajo")

        if 35 <= rsi <= 55:
            short_confs.append("Filtro Fuerza: RSI en canal bajista sano y sin sobreventa")

        if hist < 0 and macd < sig:
            short_confs.append("Disparador Momentum: MACD en ciclo pleno de contracción bajista")

    else:
        # =========================================================================
        # ESTRATEGIA CRIPTO ULTRA-AGRESIVA (Market Inhaler)
        # Maximiza la actividad buscando entrar en casi cualquier corrección.
        # =========================================================================
        
        # 1. Filtro Bollinger: (Tolerancia 1.5% sobre la banda inferior)
        if p <= bb_inf * 1.015:
            long_confs.append("Disparador Fuerte: Precio en zona baja del canal de Bollinger")
            
        # 2. Descuento Mínimo Intradiario
        if p < e20 * 0.998: # Solo un 0.2% de descuento es suficiente para ser agresivo
            long_confs.append("Filtro Estructural: Micro-pullback sobre media de 20h")

        # 3. Fuerza Exhausta (RSI < 55)
        if rsi < 55:
            long_confs.append("Filtro Agotamiento: RSI por debajo del nivel neutral")
            
        # 4. DISPARADOR DE REBOTE (Inercia positiva)
        if hist > hist_previo or macd > sig:
            long_confs.append("Disparador Momentum: MACD con inercia favorable")
            
        # Cortos deshabilitados
        pass

    return {
        'long':        long_confs,
        'short':       short_confs,
        'total_long':  len(long_confs),
        'total_short': len(short_confs),
    }
