
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import logging
import datetime
from src.data.alpaca import obtener_datos_alpaca
from src.strategies.patterns.velas import detectar_patron
from src.core.config import CRYPTO_ATR_SL, CRYPTO_ATR_TP

logger = logging.getLogger(__name__)

class CryptoAnalyzer:
    """
    Profile: SCALPING (Score >= 55, Risk 1.0%)
    Target: Many frequent operations with small profits.
    """

    def __init__(self, symbol='BTC/USD', capital=10000.0, risk_per_trade=0.015):
        self.symbol = symbol.upper()
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.df_5m = None
        self.df_15m = None
        self.df_1h = None

    def fetch_data(self):
        """Obtiene datos multi-timeframe (5m, 15m, 1h)."""
        try:
            self.df_5m = obtener_datos_alpaca(self.symbol, limit=200, timeframe='5Min')
            self.df_15m = obtener_datos_alpaca(self.symbol, limit=200, timeframe='15Min')
            self.df_1h = obtener_datos_alpaca(self.symbol, limit=100, timeframe='1Hour')
            
            if self.df_5m is None or self.df_15m is None or self.df_1h is None:
                return False
            return True
        except Exception as e:
            logger.error(f"Error fetching Scalping Crypto data: {e}")
            return False

    def analyze(self):
        if not self.fetch_data():
            return {"error": "Insufficient data"}

        # 1. ANÁLISIS TOP-DOWN
        # Macro (1h proxy)
        self.df_1h.ta.ema(length=200, append=True)
        macro_trend = "bull" if self.df_1h['close'].iloc[-1] > self.df_1h['EMA_200'].iloc[-1] else "neutral"
        
        # 5m Signal Layer (Scalping)
        df = self.df_5m
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

        if macro_trend == "bull":
            score += 2
            reasons.append("Macro Trend Bullish")
        
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

        # Scalping Threshold (Reduced for more frequency)
        signal = "LONG" if score >= 5.5 else "HOLD"

        # 3. GESTIÓN (Basado en configuración central)
        entry_price = float(last['close'])
        atr = last['ATRr_14']
        
        # Stop inicial y Take Profits basados en CRYPTO_ATR_SL y CRYPTO_ATR_TP
        stop_loss = entry_price - (atr * CRYPTO_ATR_SL) if signal == "LONG" else entry_price + (atr * CRYPTO_ATR_SL)
        tp1_dist = atr * CRYPTO_ATR_TP
        tp1 = entry_price + tp1_dist if signal == "LONG" else entry_price - tp1_dist
        tp2 = entry_price + (tp1_dist * 1.5) if signal == "LONG" else entry_price - (tp1_dist * 1.5)

        return {
            "signal": signal,
            "ticker": self.symbol,
            "macro_trend": macro_trend,
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
    analyzer = CryptoAnalyzer('BTC/USD')
    print(analyzer.analyze())
