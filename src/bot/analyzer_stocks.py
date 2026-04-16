
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
import logging
import datetime
from src.data.alpaca import obtener_datos_alpaca
from src.strategies.patterns.velas import detectar_patron
from src.core.config import ALPACA_API_KEY, STOCK_ATR_SL, STOCK_ATR_TP

logger = logging.getLogger(__name__)

class StockAnalyzer:
    """
    Sistema experto de análisis técnico para trading algorítmico con Alpaca API.
    Opera en acciones con capacidad de long y short.
    """

    def __init__(self, symbol='AAPL', capital=10000.0, risk_per_trade=0.01):
        self.symbol = symbol.upper()
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.df_15m = None
        self.df_1h = None
        self.df_daily = None

    def fetch_data(self):
        """Obtiene datos multi-timeframe de Alpaca."""
        try:
            self.df_15m = obtener_datos_alpaca(self.symbol, limit=200, timeframe='15Min')
            self.df_1h = obtener_datos_alpaca(self.symbol, limit=200, timeframe='1Hour')
            self.df_daily = obtener_datos_alpaca(self.symbol, limit=50, timeframe='1Day')
            
            if self.df_15m is None or self.df_1h is None or self.df_daily is None:
                return False
            return not (self.df_15m.empty or self.df_1h.empty or self.df_daily.empty)
        except Exception as e:
            logger.error(f"Error fetching MTF data for {self.symbol}: {e}")
            return False

    def get_daily_poc(self):
        """Calcula el POC (Point of Control) del día anterior de forma simplificada."""
        if self.df_daily is None or len(self.df_daily) < 2:
            return None
        # Usamos la vela diaria anterior. Un POC real requiere datos de ticks/1min, 
        # pero para intraday podemos aproximar con el Pivot Point o el nivel de mayor volumen si tuviéramos barras menores.
        # Aquí usaremos el (H+L+C)/3 de ayer como proxy de nivel de valor si no hay datos de perfil.
        yesterday = self.df_daily.iloc[-2]
        return (yesterday['high'] + yesterday['low'] + yesterday['close']) / 3

    def detect_divergence(self, df):
        """Detecta divergencias RSI básicas."""
        if len(df) < 20: return False
        
        # Últimos 10 periodos
        current_rsi = df['RSI_14'].iloc[-1]
        prev_rsi = df['RSI_14'].iloc[-10:-1].min()
        
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-10:-1].min()
        
        # Bullish divergence: Price lower low, RSI higher low
        if current_price < prev_price and current_rsi > prev_rsi and current_rsi < 40:
            return "bullish"
        
        # Bearish divergence: Price higher high, RSI lower high
        max_rsi = df['RSI_14'].iloc[-10:-1].max()
        max_price = df['close'].iloc[-10:-1].max()
        if current_price > max_price and current_rsi < max_rsi and current_rsi > 60:
            return "bearish"
            
        return None

    def analyze(self):
        if not self.fetch_data():
            return {"error": "Insufficient data"}

        # 1. ANÁLISIS MULTI-TIMEFRAME
        # Diario: Sesgo
        self.df_daily.ta.ema(length=20, append=True)
        last_d = self.df_daily.iloc[-1]
        daily_bias = "bull" if last_d['close'] > last_d['EMA_20'] else "bear"
        
        # 1h: Estructura
        self.df_1h.ta.ema(length=50, append=True)
        last_1h = self.df_1h.iloc[-1]
        h1_bias = "bull" if last_1h['close'] > last_1h['EMA_50'] else "bear"

        # 15m: Señal precisa e Indicadores Core
        df = self.df_15m
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        df.ta.bbands(append=True)
        df.ta.adx(append=True)
        df.ta.vwap(append=True)
        
        # OBV + Vol Relative
        df.ta.obv(append=True)
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['rel_vol'] = df['volume'] / df['vol_ma']

        last = df.iloc[-1]
        prev = df.iloc[-2]
        poc_yesterday = self.get_daily_poc()

        # 2. SISTEMA DE PUNTUACIÓN (0-10)
        score = 0
        reasons = []

        # Tendencia alineada TF múltiple: +2
        if daily_bias == "bull" and h1_bias == "bull" and last['EMA_50'] > last['EMA_200']:
            score += 2
            reasons.append("MTF Trend Alignment (D/1h/15m)")
        elif daily_bias == "bear" and h1_bias == "bear" and last['EMA_50'] < last['EMA_200']:
            score += 2
            reasons.append("MTF Trend Alignment (D/1h/15m)")

        # VWAP como soporte/resistencia: +1.5
        vwap = last['VWAP_D']
        if (daily_bias == "bull" and last['close'] > vwap) or (daily_bias == "bear" and last['close'] < vwap):
            score += 1.5
            reasons.append("VWAP Confirmation")

        # RSI en zona óptima: +1.5
        rsi = last['RSI_14']
        if (daily_bias == "bull" and 45 < rsi < 65) or (daily_bias == "bear" and 35 < rsi < 55):
            score += 1.5
            reasons.append(f"RSI Optima ({rsi:.1f})")

        # MACD alineado: +1
        macd_hist = last['MACDh_12_26_9']
        if (daily_bias == "bull" and macd_hist > 0) or (daily_bias == "bear" and macd_hist < 0):
            score += 1
            reasons.append("MACD Alignment")

        # Volumen confirma: +1.5
        if last['rel_vol'] > 1.2:
            score += 1.5
            reasons.append(f"Volume Spike (x{last['rel_vol']:.1f})")

        # Divergencia favorable: +1.5
        div = self.detect_divergence(df)
        if (daily_bias == "bull" and div == "bullish") or (daily_bias == "bear" and div == "bearish"):
            score += 1.5
            reasons.append(f"Divergence detected ({div})")

        # Patrón de velas: +1
        pattern = detectar_patron(df)
        if (daily_bias == "bull" and "Alcista" in pattern) or (daily_bias == "bear" and "Bajista" in pattern):
            score += 1
            reasons.append(f"Candlestick Pattern: {pattern}")

        # Regime detection (ADX)
        current_adx = last['ADX_14']
        regime = "trending" if current_adx > 25 else "ranging"

        # Signal Logic
        signal = "HOLD"
        if score >= 7:
            signal = "LONG" if daily_bias == "bull" else "SHORT"

        # 3. GESTIÓN DINÁMICA
        entry_price = float(last['close'])
        atr = df.ta.atr(length=14).iloc[-1]
        
        # Stop y TP basados en configuración central (STOCK_ATR_SL y STOCK_ATR_TP)
        sl_dist = max(atr * STOCK_ATR_SL, entry_price * 0.01) # Mínimo 1% de seguridad
        stop_loss = entry_price - sl_dist if signal == "LONG" else entry_price + sl_dist
        
        # Take Profit Primario (según STOCK_ATR_TP relativo al ATR)
        tp1_dist = atr * STOCK_ATR_TP
        tp1 = entry_price + tp1_dist if signal == "LONG" else entry_price - tp1_dist
        
        # Take Profit Secundario (1.5x del primario para tendencia extendida)
        tp2 = entry_price + (tp1_dist * 1.5) if signal == "LONG" else entry_price - (tp1_dist * 1.5)

        # Result construction
        result = {
            "signal": signal,
            "ticker": self.symbol,
            "timeframe_bias": {"daily": daily_bias, "1h": h1_bias},
            "entry_price": round(entry_price, 4),
            "stop_loss": round(stop_loss, 4),
            "take_profit_1": round(tp1, 4),
            "take_profit_2": round(tp2, 4),
            "score": float(score),
            "position_size_pct": self.risk_per_trade * 100,
            "confidence": round(score / 10, 2),
            "reason": ", ".join(reasons),
            "invalidation": "Price crosses VWAP against position" if signal != "HOLD" else "N/A"
        }

        return result

if __name__ == "__main__":
    analyzer = StockAnalyzer('AAPL')
    print(analyzer.analyze())
