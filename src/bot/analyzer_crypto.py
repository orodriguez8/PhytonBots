
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import logging
import datetime
from src.data.alpaca import obtener_datos_alpaca
from src.strategies.patterns.velas import detectar_patron

logger = logging.getLogger(__name__)

class CryptoExpertAnalyzer:
    """
    Sistema experto de análisis técnico para trading algorítmico de Crypto.
    SOLO LONG (Alpaca API).
    """

    def __init__(self, symbol='BTC/USD', capital=10000.0, risk_per_trade=0.015):
        self.symbol = symbol.upper()
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.df_15m = None
        self.df_1h = None
        self.df_4h = None

    def fetch_data(self):
        """Obtiene datos multi-timeframe (15m, 1h, 4h)."""
        try:
            self.df_15m = obtener_datos_alpaca(self.symbol, limit=200, timeframe='15Min')
            self.df_1h = obtener_datos_alpaca(self.symbol, limit=200, timeframe='1Hour')
            self.df_4h = obtener_datos_alpaca(self.symbol, limit=100, timeframe='1Hour') # Alpaca no da 4h directo, agrupamos o usamos 1h
            
            if self.df_15m is None or self.df_1h is None or self.df_4h is None:
                return False
            return True
        except Exception as e:
            logger.error(f"Error fetching Crypto data: {e}")
            return False

    def analyze(self):
        if not self.fetch_data():
            return {"error": "Insufficient data"}

        # 1. ANÁLISIS TOP-DOWN
        # Macro (4h/1h proxy)
        self.df_1h.ta.ema(length=200, append=True)
        btc_macro = "bull" if self.df_1h['close'].iloc[-1] > self.df_1h['EMA_200'].iloc[-1] else "neutral"
        
        # 15m Signal Layer
        df = self.df_15m
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        df.ta.adx(length=14, append=True)
        df.ta.vwap(append=True)
        df.ta.bbands(append=True)
        df.ta.atr(append=True)
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        adx_val = last['ADX_14']
        regime = "TREND" if adx_val > 25 else "MEAN_REV" if adx_val < 20 else "HYBRID"

        # 2. SISTEMA DE PUNTUACIÓN (0-10)
        score = 0
        reasons = []

        if btc_macro == "bull":
            score += 2
            reasons.append("BTC Macro Bullish")
        
        # Triple EMA alineada
        if last['EMA_9'] > last['EMA_21'] > last['EMA_50']:
            score += 1.5
            reasons.append("Triple EMA Alignment")
            
        # RSI Optima
        if 45 <= last['RSI_14'] <= 60:
            score += 1.5
            reasons.append("RSI in Momentum Zone")
            
        # MACD
        if last['MACDh_12_26_9'] > prev['MACDh_12_26_9'] and last['MACDh_12_26_9'] > 0:
            score += 1
            reasons.append("MACD Bullish Expansion")
            
        # Vol
        vol_ma = df['volume'].rolling(20).mean().iloc[-1]
        if last['volume'] > vol_ma * 1.4:
            score += 1.5
            reasons.append("Volume Confirmation (>1.4x)")
            
        # Velas
        pattern = detectar_patron(df)
        if "Alcista" in pattern:
            score += 1
            reasons.append(f"Candlestick Pattern: {pattern}")
            
        # Tech Zone
        if last['close'] > last['VWAP_D']:
            score += 1.5
            reasons.append("Above VWAP Support")

        signal = "LONG" if score >= 7.5 else "HOLD"

        # 3. GESTIÓN
        entry_price = float(last['close'])
        atr = last['ATRr_14']
        
        # Stop inicial: Estructura
        stop_loss = entry_price - (atr * 2.0)
        tp1 = entry_price + (atr * 2.5)
        tp2 = entry_price + (atr * 4.0)

        return {
            "signal": signal,
            "ticker": self.symbol,
            "btc_macro": btc_macro,
            "regime": regime,
            "entry_price": round(entry_price, 4),
            "entry_2_price": round(entry_price * 1.002, 4),
            "stop_loss": round(stop_loss, 4),
            "take_profit_1": round(tp1, 4),
            "take_profit_2": round(tp2, 4),
            "score": float(score),
            "position_size_pct": self.risk_per_trade * 100,
            "confidence": round(score / 10, 2),
            "reason": ", ".join(reasons),
            "invalidation": "Price drops below EMA 200 or RSI bearish divergence"
        }

if __name__ == "__main__":
    analyzer = CryptoExpertAnalyzer('BTC/USD')
    print(analyzer.analyze())
