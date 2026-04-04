
# =============================================================================
# MÓDULO: CONTEO DE CONFLUENCIAS (Motor de Señales Mejorado para Auto-Trading)
# =============================================================================
import pandas as pd
from src.core.config import RSI_SOBREVENTA, RSI_SOBRECOMPRA

def contar_confluencias(datos: pd.DataFrame, indicadores: dict) -> dict:
    """
    Evalúa condiciones de alta probabilidad para trading automático.
    """
    long_confs  = []
    short_confs = []

    # -- Datos actuales --
    p   = datos['close'].iloc[-1]
    e20 = indicadores['ema_20'].iloc[-1]
    e50 = indicadores['ema_50'].iloc[-1]
    e200 = indicadores['ema_200'].iloc[-1]
    rsi = indicadores['rsi'].iloc[-1]
    macd = indicadores['macd'].iloc[-1]
    sig  = indicadores['macd_signal'].iloc[-1]
    hist = indicadores['macd_histogram'].iloc[-1]
    
    # 1. TENDENCIA MAESTRA (Filtro Principal)
    tendencia_alcista = p > e200 and e50 > e200
    tendencia_bajista = p < e200 and e50 < e200
    
    if tendencia_alcista:
        long_confs.append("Tendencia Alcista Confirmada (Precio > EMA 200)")
    if tendencia_bajista:
        short_confs.append("Tendencia Bajista Confirmada (Precio < EMA 200)")
        
    # 2. MOMENTUM (EMAs Rápidas)
    if e20 > e50:
        long_confs.append("Cruce de EMA 20/50 Alcista (Momentum)")
    if e20 < e50:
        short_confs.append("Cruce de EMA 20/50 Bajista (Momentum)")

    # 3. MACD ALINEADO
    if macd > sig and hist > 0:
        long_confs.append("MACD Alcista (Histograma > 0)")
    if macd < sig and hist < 0:
        short_confs.append("MACD Bajista (Histograma < 0)")
        
    # 4. RSI (Filtro de Extremos)
    # No queremos comprar si ya está muy estirado
    if rsi < 65 and rsi > 45 and p > e20: # Pullback alcista
        long_confs.append("RSI en zona de continuacion alcista")
    if rsi > 35 and rsi < 55 and p < e20: # Pullback bajista
        short_confs.append("RSI en zona de continuacion bajista")
        
    # Zona de Reversion (Solo si hay tendencia clara)
    if rsi < RSI_SOBREVENTA:
        long_confs.append("Sobreventa extrema detectada")
    if rsi > RSI_SOBRECOMPRA:
        short_confs.append("Sobrecompra extrema detectada")

    # 5. VOLUMEN (Confirmacion Institucional)
    vol_act = datos['volume'].iloc[-1]
    vol_med = indicadores['volumen_medio'].iloc[-1]
    if vol_act > vol_med * 1.5:
        long_confs.append("Volumen Inusualmente Alto (Anomalia)")
        short_confs.append("Volumen Inusualmente Alto (Anomalia)")

    return {
        'long':        long_confs,
        'short':       short_confs,
        'total_long':  len(long_confs),
        'total_short': len(short_confs),
    }
