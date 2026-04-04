
import pandas as pd
import numpy as np
import pandas_ta as ta
import requests
import logging
import datetime
from src.data.alpaca import obtener_datos_alpaca

logger = logging.getLogger(__name__)

class CryptoAnalyzer:
    """
    Expert Quantitative Technical Analysis Bot for Crypto (LONG positions only).
    Profile: CONSERVATIVE (Score >= 80, Risk 2.5%)
    """

    def __init__(self, symbol='BTC/USD', capital=10000.0, risk_per_trade=0.025):
        self.symbol = symbol
        self.capital = capital
        self.risk_per_trade = risk_per_trade
        self.df_15m = None
        self.df_1h = None
        self.score = 0
        self.confluences = []
        self.results = {}

    def fetch_data(self):
        """Fetches 15min and 1h data from Alpaca."""
        self.df_15m = obtener_datos_alpaca(self.symbol, limit=500, timeframe='15Min')
        self.df_1h = obtener_datos_alpaca(self.symbol, limit=500, timeframe='1Hour')
        
        if self.df_15m is None or self.df_1h is None or self.df_15m.empty or self.df_1h.empty:
            return False
        return True

    def get_fear_and_greed(self):
        """Fetches the Fear & Greed Index."""
        try:
            r = requests.get("https://api.alternative.me/fng/", timeout=5)
            if r.status_code == 200:
                data = r.json()
                return int(data['data'][0]['value'])
        except Exception as e:
            logger.error(f"Error fetching F&G: {e}")
        return 50 # Neutral fallback

    def get_btc_dominance(self):
        """
        Placeholder for BTC Dominance. 
        In a real scenario, this would fetch from CoinGecko or a specific data provider.
        """
        # For the sake of the bot logic, we'll return a static/simulated value 
        # or try to fetch it if a known API is available.
        return 50.0 

    def analyze(self):
        if not self.fetch_data():
            return self._no_trade_response("Insufficient data")

        # --- LAYER 1: MACRO TREND (1h) ---
        self.df_1h.ta.ema(length=200, append=True)
        last_1h = self.df_1h.iloc[-1]
        prev_1h = self.df_1h.iloc[-2]
        
        price_1h = last_1h['close']
        ema200_1h = last_1h['EMA_200']
        
        # Structure HH/HL check (simplified)
        recent_lows = self.df_1h['low'].tail(20).rolling(window=5).min()
        recent_highs = self.df_1h['high'].tail(20).rolling(window=5).max()
        uptrend_structure = last_1h['close'] > prev_1h['close'] # Basic check

        macro_bullish = price_1h > ema200_1h
        if not macro_bullish and price_1h < ema200_1h * 0.98: # Strict filter
             return self._no_trade_response("Macro trend is bearish (Price < EMA 200 1h)")

        # --- LAYER 2: MOMENTUM & ENTRY (15min) ---
        df = self.df_15m
        df.ta.ema(length=9, append=True)
        df.ta.ema(length=21, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.vwap(append=True)
        df.ta.obv(append=True)
        df['vol_ema20'] = df['volume'].rolling(20).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # ADX for Market Regime
        adx = df.ta.adx(length=14)
        current_adx = adx['ADX_14'].iloc[-1] if adx is not None else 0
        market_regime = "trending" if current_adx > 25 else "ranging"

        # Scoring Logic
        score = 0
        reasons = []

        # 1. Trend Confirmation (30 pts)
        trend_pts = 0
        if last['close'] > last['EMA_200']: trend_pts += 10
        if last['EMA_9'] > last['EMA_21'] > last['EMA_50']: trend_pts += 10
        if last['close'] > last['EMA_50']: trend_pts += 10
        score += trend_pts
        if trend_pts >= 20: reasons.append("Strong bullish EMA alignment")

        # 2. Momentum (25 pts)
        mom_pts = 0
        if last['RSI_14'] > 50 and last['RSI_14'] < 70: mom_pts += 10
        if last['MACD_12_26_9'] > last['MACDs_12_26_9']: mom_pts += 10
        if last['volume'] > last['vol_ema20']: mom_pts += 5
        score += mom_pts
        if mom_pts >= 15: reasons.append("Positive momentum (RSI/MACD)")

        # 3. Value Zone (20 pts)
        val_pts = 0
        if last['close'] > last['VWAP_D']: val_pts += 5
        
        # Fibonacci Retracement (Last 100 bars swing)
        swing_high = df['high'].tail(100).max()
        swing_low = df['low'].tail(100).min()
        range_fib = swing_high - swing_low
        fib_618 = swing_low + (0.618 * range_fib)
        fib_500 = swing_low + (0.500 * range_fib)
        
        # Near key fib level? (within 0.5%)
        if abs(last['close'] - fib_618) / last['close'] < 0.005: 
            val_pts += 10
            reasons.append("Price at 0.618 Fibonacci level")
        elif abs(last['close'] - fib_500) / last['close'] < 0.005:
            val_pts += 5
            reasons.append("Price at 0.500 Fibonacci level")

        # Near BB lower band?
        if last['close'] < last['BBL_20_2.0'] * 1.01: val_pts += 5
        
        score += val_pts
        if val_pts >= 10 and "Fibonacci" not in reasons: reasons.append("Price in value zone (VWAP/Fib/BB)")

        # 4. Patterns & Divergences (15 pts)
        pat_pts = 0
        # RSI Divergence (Very basic: price lower low, RSI higher low over 10 bars)
        if last['close'] < prev['close'] and last['RSI_14'] > prev['RSI_14'] and last['RSI_14'] < 40:
            pat_pts += 10
            reasons.append("Potential Bullish Divergence (RSI)")
            
        # Candlesticks
        body = abs(last['close'] - last['open'])
        wick_low = min(last['open'], last['close']) - last['low']
        if wick_low > body * 2: # Hammer-like
            pat_pts += 10
            reasons.append("Bullish Hammer detected")
        elif last['close'] > prev['open'] and prev['close'] < prev['open'] and (last['close'] - last['open']) > (prev['open'] - prev['close']):
            pat_pts += 10
            reasons.append("Bullish Engulfing detected")
        
        score += min(pat_pts, 15)

        # 5. Market Context (10 pts)
        fng = self.get_fear_and_greed()
        ctx_pts = 0
        if fng < 40: ctx_pts += 10 # Buy fear
        elif fng < 60: ctx_pts += 5
        score += ctx_pts
        if ctx_pts >= 5: reasons.append(f"F&G Index: {fng} (Opportunities)")

        # --- SAFETY FILTERS ---
        if fng > 80: return self._no_trade_response("Fear & Greed Index > 80 (Too Greedy)")
        if last['RSI_14'] > 75: return self._no_trade_response("RSI 15m Overbought (>75)")
        if last_1h['RSI_14'] > 75: return self._no_trade_response("RSI 1h Overbought (>75)")
        if last['volume'] < last['vol_ema20'] * 0.7: return self._no_trade_response("Low volume (<70% avg)")
        
        # Conservative Spread Filter (0.3%) 
        # Since we don't have orderbook in bars, we'll simulate or add a placeholder
        # In a real scenario, this would check 'bid' and 'ask' prices.
        spread_pct = 0.001 # Simulated 0.1%
        if spread_pct > 0.003: return self._no_trade_response("Spread too high (>0.3%)")
        
        # Final Decision
        signal = "NO_TRADE"
        if score >= 80:
            signal = "LONG"
        elif score >= 70:
            signal = "WAIT"
            reasons.append("Score above 70, waiting for more confluence (Min 80 for CONSERVATIVE)")

        # Position Management
        entry_price = float(last['close'])
        atr = float(last['ATRr_14'])
        stop_loss = entry_price - (1.5 * atr)
        
        # Targets based on R:R 2:1, 3:1, 5:1
        tp1 = entry_price + (2 * (entry_price - stop_loss))
        tp2 = entry_price + (3 * (entry_price - stop_loss))
        tp3 = entry_price + (5 * (entry_price - stop_loss))
        
        rr = (tp1 - entry_price) / (entry_price - stop_loss) if (entry_price - stop_loss) != 0 else 0
        
        # Position sizing: Risk 2.5% of capital on SL
        risk_amount = self.capital * self.risk_per_trade
        sl_distance = entry_price - stop_loss
        if sl_distance > 0:
            qty = risk_amount / sl_distance
            pos_size_pct = (qty * entry_price / self.capital) * 100
        else:
            pos_size_pct = 0

        response = {
            "symbol": self.symbol,
            "signal": signal,
            "confidence_score": int(score),
            "entry_price": round(entry_price, 4),
            "stop_loss": round(stop_loss, 4),
            "take_profit_1": round(tp1, 4),
            "take_profit_2": round(tp2, 4),
            "take_profit_3": round(tp3, 4),
            "position_size_pct": round(pos_size_pct, 2),
            "risk_reward_ratio": round(rr, 2),
            "timeframe": "15min",
            "market_regime": market_regime,
            "key_reasons": reasons,
            "invalidation_conditions": ["Price breaks below EMA 200 (1h)", "RSI div bearish", "Volume drop > 50%"],
            "hold_duration_estimate": "4h - 12h",
            "urgency": "immediate" if score >= 85 else "next_candle" if score >= 75 else "monitor"
        }

        return response

    def _no_trade_response(self, reason):
        return {
            "symbol": self.symbol,
            "signal": "NO_TRADE",
            "confidence_score": 0,
            "entry_price": 0,
            "stop_loss": 0,
            "take_profit_1": 0,
            "take_profit_2": 0,
            "take_profit_3": 0,
            "position_size_pct": 0,
            "risk_reward_ratio": 0,
            "timeframe": "15min",
            "market_regime": "unknown",
            "key_reasons": [reason],
            "invalidation_conditions": [],
            "hold_duration_estimate": "N/A",
            "urgency": "monitor"
        }

if __name__ == "__main__":
    analyzer = CryptoAnalyzer('BTC/USD')
    result = analyzer.analyze()
    import json
    print(json.dumps(result, indent=2))
