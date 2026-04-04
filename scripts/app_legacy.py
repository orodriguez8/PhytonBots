
# =============================================================================
# SERVIDOR WEB — app.py  (Integración Alpaca)
# =============================================================================
import sys
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import numpy as np
import io

# Forzar codificación UTF-8 para evitar errores en Windows con emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from bot.trading_bot import TradingBot
from config import (
    N_VELAS, PRECIO_INICIAL, TENDENCIA, VOLATILIDAD,
    SEMILLA_ALEATORIA, CAPITAL_INICIAL, RIESGO_POR_OPERACION,
    MIN_CONFLUENCIAS,
)

app = Flask(__name__, static_folder='dashboard', static_url_path='')
CORS(app)

# ── Detectar modo: Alpaca, Oanda o Simulador ─────────────────────────────────
ALPACA_ENABLED = bool(os.getenv('ALPACA_API_KEY'))
OANDA_ENABLED  = bool(os.getenv('OANDA_API_KEY')) and not ALPACA_ENABLED
AUTO_TRADING   = False # Interruptor de Seguridad Global

if ALPACA_ENABLED:
    MODO = 'ALPACA'
elif OANDA_ENABLED:
    MODO = 'OANDA'
else:
    MODO = 'SIMULADOR'

print(f"Modo detectado: {MODO}")

# ── Utilidad ─────────────────────────────────────────────────────────────────
def to_python(obj):
    if isinstance(obj, (np.integer,)):   return int(obj)
    if isinstance(obj, (np.floating,)):  return float(obj)
    if isinstance(obj, np.ndarray):      return obj.tolist()
    return obj

@app.route('/')
def index():
    return send_from_directory('dashboard', 'index.html')

@app.route('/api/status')
def api_status():
    return jsonify({
        'modo':         MODO,
        'auto_trading': AUTO_TRADING,
        'instrumento':  os.getenv('ALPACA_SYMBOL', 'AAPL') if ALPACA_ENABLED else os.getenv('OANDA_INSTRUMENT', 'EUR_USD') if OANDA_ENABLED else 'SIMULADO',
    })

@app.route('/api/toggle-auto', methods=['POST'])
def api_toggle_auto():
    global AUTO_TRADING
    AUTO_TRADING = not AUTO_TRADING
    return jsonify({'ok': True, 'auto_trading': AUTO_TRADING})

@app.route('/api/run')
def api_run():
    try:
        # 1. Obtener datos
        if ALPACA_ENABLED:
            from data.alpaca_feed import obtener_datos_alpaca
            symbol = os.getenv('ALPACA_SYMBOL', 'AAPL')
            datos  = obtener_datos_alpaca(symbol=symbol)
        elif OANDA_ENABLED:
            from data.oanda_feed import obtener_datos_oanda
            datos  = obtener_datos_oanda()
        else:
            from data.simulador import generar_datos
            datos = generar_datos()

        # 2. Ejecutar Bot
        bot = TradingBot(datos, CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS)
        bot.ejecutar()

        ind = bot.indicadores
        dec = bot.decision
        ges = dec.get('gestion') or {}

        # ── Función auxiliar para evitar errores con NaN en JSON ──────
        def safe_float(val, ndigits=5):
            if val is None or np.isnan(val): return None
            return round(float(val), ndigits)

        # 3. Formatear para Frontend (Lightweight Charts)
        candles = []
        for ts, row in datos.iterrows():
            # Algunos proveedores (Alpaca) devuelven el índice con zona horaria
            try:
                epoch = int(ts.timestamp())
            except:
                epoch = int(ts.value // 1e9)
            candles.append({
                'time':   epoch,
                'open':   safe_float(row['open']),
                'high':   safe_float(row['high']),
                'low':    safe_float(row['low']),
                'close':  safe_float(row['close']),
                'volume': int(row['volume']),
            })

        def series(s):
            res = []
            for ts, val in s.items():
                try:
                    epoch = int(ts.timestamp())
                except:
                    epoch = int(ts.value // 1e9)
                if val is not None and not np.isnan(val):
                    res.append({'time': epoch, 'value': safe_float(val)})
            return res

        payload = {
            'modo':    MODO,
            'candles': candles,
            'mercado': {
                'open':      safe_float(datos['open'].iloc[-1]),
                'close':     safe_float(datos['close'].iloc[-1]),
                'high':      safe_float(datos['high'].iloc[-1]),
                'low':       safe_float(datos['low'].iloc[-1]),
                'instrumento': os.getenv('ALPACA_SYMBOL', 'AAPL') if ALPACA_ENABLED else 'SIMULADO',
                'vol_ratio': safe_float(datos['volume'].iloc[-1] / ind['volumen_medio'].iloc[-1], 2) if 'volumen_medio' in ind else 1.0,
                'variacion': safe_float((datos['close'].iloc[-1] / datos['close'].iloc[0] - 1) * 100, 2),
            },
            'indicadores': {
                'ema_20':         safe_float(ind['ema_20'].iloc[-1]),
                'ema_50':         safe_float(ind['ema_50'].iloc[-1]),
                'ema_200':        safe_float(ind['ema_200'].iloc[-1]),
                'rsi':            safe_float(ind['rsi'].iloc[-1], 2),
                'macd':           safe_float(ind['macd'].iloc[-1]),
                'macd_histogram': safe_float(ind['macd_histogram'].iloc[-1]),
                'macd_signal':    safe_float(ind['macd_signal'].iloc[-1]),
                'bb_superior':    safe_float(ind['bb_superior'].iloc[-1]),
                'bb_media':       safe_float(ind['bb_media'].iloc[-1]),
                'bb_inferior':    safe_float(ind['bb_inferior'].iloc[-1]),
                'bb_ancho':       safe_float(ind['bb_ancho'].iloc[-1]),
                'atr':            safe_float(ind['atr'].iloc[-1]),
            },
            'series': {
                'ema_20':         series(ind['ema_20']),
                'ema_50':         series(ind['ema_50']),
                'ema_200':        series(ind['ema_200']),
                'rsi':            series(ind['rsi']),
                'macd':           series(ind['macd']),
                'macd_signal':    series(ind['macd_signal']),
                'macd_histogram': series(ind['macd_histogram']),
                'bb_superior':    series(ind['bb_superior']),
                'bb_inferior':    series(ind['bb_inferior']),
                'volume':         [{'time': c['time'], 'value': c['volume'], 'color': '#26a69a'} for c in candles],
            },
            'patron': bot.patron,
            'confluencias': {
                'long':        bot.confluencias_long,
                'short':       bot.confluencias_short,
                'total_long':  dec['total_long'] if 'total_long' in dec else 0,
                'total_short': dec['total_short'] if 'total_short' in dec else 0,
                'min':         MIN_CONFLUENCIAS,
            },
            'decision': dec,
            'gestion':  {k: safe_float(v) if isinstance(v, (float, np.floating)) else v for k, v in ges.items()} if ges else None,
        }

        # ── AUTO-EXECUTOR (Ejecución automática de órdenes) ─────────────────
        if AUTO_TRADING and dec['direccion'] != 'NEUTRAL':
            try:
                # 1. Comprobar posiciones abiertas (no queremos duplicar)
                if ALPACA_ENABLED:
                    from ejecucion.alpaca_orders import obtener_posiciones_abiertas, colocar_orden_mercado
                    pos = obtener_posiciones_abiertas()
                    if not any(p['instrumento'] == payload['mercado']['instrumento'] for p in pos):
                         print(f"[AUTO-TRADER] Ejecutando {dec['direccion']} en Alpaca...")
                         side = 'buy' if dec['direccion'] == 'LONG' else 'sell'
                         units = int(ges['tamano_posicion'] if ges else 10)
                         colocar_orden_mercado(payload['mercado']['instrumento'], units, side, ges.get('take_profit'), ges.get('stop_loss'))
            except Exception as ae:
                print(f"[AUTO-TRADER ERROR] {ae}")

        return jsonify(payload)
    except Exception as e:
        print(f"ERROR EN /api/run: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/account')
def api_account():
    try:
        if ALPACA_ENABLED:
            from ejecucion.alpaca_orders import obtener_cuenta, obtener_posiciones_abiertas
        elif OANDA_ENABLED:
            from ejecucion.ordenes import obtener_cuenta, obtener_posiciones_abiertas
        else:
            return jsonify({'error': 'Modo simulado'}), 400
            
        cuenta = obtener_cuenta()
        posiciones = obtener_posiciones_abiertas()
        return jsonify({'cuenta': cuenta, 'posiciones': posiciones})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/order', methods=['POST'])
def api_order():
    try:
        data = request.get_json()
        direccion = data['direccion']
        unidades  = int(data['unidades'])
        
        if ALPACA_ENABLED:
            from ejecucion.alpaca_orders import colocar_orden_mercado
            symbol = os.getenv('ALPACA_SYMBOL', 'AAPL')
            # Alpaca side: buy or sell
            side = 'buy' if direccion == 'LONG' else 'sell'
            res = colocar_orden_mercado(symbol, unidades, side)
            return jsonify({'ok': True, 'res': str(res)})
        elif OANDA_ENABLED:
             from ejecucion.ordenes import colocar_orden_mercado
             res = colocar_orden_mercado(direccion, unidades)
             return jsonify({'ok': True, 'res': res})
        else:
            return jsonify({'error': 'No API configured'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
