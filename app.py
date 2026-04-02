import os, sys, io, json, logging, threading, time, datetime, traceback
from flask import Flask, render_template, jsonify
from flask_cors import CORS
import numpy as np
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE LOGS (ÓPTIMO PARA PRODUCCIÓN) ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- CARGA DE ENTORNO ---
load_dotenv()
TOP_DIR = os.path.dirname(os.path.abspath(__file__))
if TOP_DIR not in sys.path: sys.path.insert(0, TOP_DIR)

# --- FALLBACKS Y MOCKUPS ---
def obtener_cuenta(): return None
def obtener_posiciones_abiertas(): return []
def colocar_orden_mercado(*args,**kw): return None
def obtener_datos_alpaca(*args,**kw): return None

# --- IMPORTACIÓN REAL ---
try:
    from trading_bot.bot.trading_bot import TradingBot
    from trading_bot.config import (
        CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS, WATCHLIST,
        ALPACA_API_KEY, ALPACA_SECRET_KEY
    )
    from trading_bot.ejecucion.alpaca_orders import (
        obtener_cuenta as real_account,
        obtener_posiciones_abiertas as real_pos,
        colocar_orden_mercado as real_order
    )
    from trading_bot.data.alpaca_feed import obtener_datos_alpaca as real_feed
    
    obtener_cuenta, obtener_posiciones_abiertas, colocar_orden_mercado, obtener_datos_alpaca = \
        real_account, real_pos, real_order, real_feed
    
    ALPACA_ENABLED = bool(ALPACA_API_KEY and ALPACA_SECRET_KEY)
    logger.info("✅ Entorno de Trading cargado.")
except Exception:
    logger.error(f"⚠️ Error de carga (Modo Simulador activo):\n{traceback.format_exc()}")
    WATCHLIST = ['AAPL', 'TSLA', 'BTCUSD', 'ETHUSD']; CAPITAL_INICIAL = 10000.0; RIESGO_POR_OPERACION = 0.02; MIN_CONFLUENCIAS = 3
    ALPACA_ENABLED = False

app = Flask(__name__)
CORS(app)

# --- ESTADO GLOBAL (MÍNIMA MEMORIA) ---
AUTO_TRADING_ACTIVE = False
BOT_HISTORY = [] # Máximo 20 elementos para ahorrar RAM
LAST_RUN_LOG = {} # Resumen rápido de la última ejecución

def safe_float(val, ndigits=2):
    try:
        if val is None or (isinstance(val, (float, np.floating, np.float64)) and np.isnan(val)): return 0.0
        return round(float(val), ndigits)
    except: return 0.0

# --- LOOP TRADING OPTIMIZADO (UNA ÚNICA CONEXIÓN POR CICLO) ---
def trading_loop():
    global AUTO_TRADING_ACTIVE, BOT_HISTORY
    while True:
        if AUTO_TRADING_ACTIVE:
            logger.info("--- LOOP AUTOMÁTICO ---")
            for symbol in WATCHLIST:
                try:
                    if ALPACA_ENABLED:
                        datos = obtener_datos_alpaca(symbol=symbol)
                    else:
                        from trading_bot.data.simulador import generar_datos
                        datos = generar_datos()

                    if datos is None or datos.empty: continue

                    bot = TradingBot(datos, CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS)
                    bot.ejecutar()

                    dec = bot.decision
                    dir_ = dec['direccion']
                    LAST_RUN_LOG[symbol] = {'time': datetime.datetime.now().strftime('%H:%M:%S'), 'dir': dir_, 'reason': dec['razon']}

                    if dir_ != 'NEUTRAL' and ALPACA_ENABLED:
                        pos = obtener_posiciones_abiertas()
                        if not any(p['instrumento'] == symbol for p in pos):
                            side = 'buy' if dir_ == 'LONG' else 'sell'
                            ges = dec.get('gestion', {})
                            qty = int(ges.get('tamano_posicion', 1))
                            if qty > 0:
                                colocar_orden_mercado(symbol, qty, side, ges.get('take_profit'), ges.get('stop_loss'))
                                entry = {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"REAL {dir_}", 'price': safe_float(datos['close'].iloc[-1]), 'reason': 'Ejecutado'}
                                BOT_HISTORY.insert(0, entry)
                    elif dir_ != 'NEUTRAL':
                        entry = {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"SIM {dir_}", 'price': safe_float(datos['close'].iloc[-1]), 'reason': dec['razon']}
                        BOT_HISTORY.insert(0, entry)
                    
                    if len(BOT_HISTORY) > 20: BOT_HISTORY.pop()
                except Exception as e: logger.error(f"Error {symbol}: {e}")
            time.sleep(60)
        else: time.sleep(10)

threading.Thread(target=trading_loop, daemon=True).start()

# --- RUTAS OPTIMIZADAS ---
@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/toggle', methods=['POST'])
def toggle():
    global AUTO_TRADING_ACTIVE
    AUTO_TRADING_ACTIVE = not AUTO_TRADING_ACTIVE
    return jsonify({'ok': True, 'state': AUTO_TRADING_ACTIVE})

@app.route('/api/summary')
def summary():
    """ 
    Ruta ÚNICA que devuelve todo el estado. 
    Reduce el número de peticiones HTTP del frontend a la mitad.
    """
    try:
        data = {
            'mode': 'ALPACA' if ALPACA_ENABLED else 'SIM',
            'auto': AUTO_TRADING_ACTIVE,
            'summary': LAST_RUN_LOG,
            'history': BOT_HISTORY,
            'equity': 10000.0,
            'pl': 0.0,
            'pos': []
        }
        if ALPACA_ENABLED:
            acc = obtener_cuenta()
            if acc:
                data['equity'] = safe_float(acc.get('nav', 0))
                data['pl'] = safe_float(acc.get('pl', 0))
                positions = obtener_posiciones_abiertas()
                data['pos'] = [{
                    's': p['instrumento'], 'q': p['unidades'], 'e': safe_float(p['precio_medio']),
                    'c': safe_float(p.get('precio_actual', 0)), 'p': safe_float(p['pl']), 'pct': safe_float(p.get('pl_pct', 0))
                } for p in positions]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, threaded=True)