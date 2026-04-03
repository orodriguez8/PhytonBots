# VERSION 2.1.0 - BINANCE ONLY
import os, sys, io, json, logging, threading, time, datetime, traceback
from flask import Flask, render_template, jsonify
from flask_cors import CORS
import numpy as np
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE PANELES ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] - %(message)s')
logger = logging.getLogger(__name__)

# --- CARGA DE ENTORNO ---
load_dotenv()
TOP_DIR = os.path.dirname(os.path.abspath(__file__))
if TOP_DIR not in sys.path: sys.path.insert(0, TOP_DIR)

# --- IMPORTACIÓN ROBUSTA (SOLO BINANCE) ---
try:
    from trading_bot.bot.trading_bot import TradingBot
    from trading_bot.config import (
        CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS, WATCHLIST,
        BINANCE_API_KEY, TRADING_MODE_CRYPTO
    )
    
    # CCXT / Binance
    from trading_bot.ejecucion.ccxt_orders import (
        obtener_cuenta_ccxt, 
        obtener_posiciones_abiertas_ccxt,
        colocar_orden_mercado_ccxt,
        cancelar_todas_las_ordenes_ccxt
    )
    from trading_bot.data.ccxt_feed import obtener_datos_ccxt

    def get_data(symbol):
        if BINANCE_API_KEY: return obtener_datos_ccxt(symbol)
        return None

    def get_account():
        if BINANCE_API_KEY: return obtener_cuenta_ccxt()
        return None

    def get_positions():
        if BINANCE_API_KEY: return obtener_posiciones_abiertas_ccxt()
        return []

    def place_order(symbol, qty, side, tp=None, sl=None):
        if BINANCE_API_KEY: return colocar_orden_mercado_ccxt(symbol, qty, side)
        return None

    logger.info("✅ Módulos internos (Binance) listos.")
except Exception:
    logger.error(f"⚠️ Error cargando módulos:\n{traceback.format_exc()}")
    WATCHLIST = ['BTC/USDT']; CAPITAL_INICIAL = 10000.0; BINANCE_API_KEY = None

app = Flask(__name__)
CORS(app)

# --- ESTADO ---
AUTO_TRADING_ACTIVE = False
BOT_HISTORY = []
LAST_RUN_LOG = {}

def safe_float(val, ndigits=2):
    try:
        if val is None or (isinstance(val, (float, np.floating, np.float64)) and np.isnan(val)): return 0.0
        return round(float(val), ndigits)
    except: return 0.0

# --- LOOP TRADING BINANCE ---
def trading_loop():
    global AUTO_TRADING_ACTIVE, BOT_HISTORY
    while True:
        if AUTO_TRADING_ACTIVE:
            real_equity = CAPITAL_INICIAL
            buying_power = real_equity
            positions_list = []
            
            if BINANCE_API_KEY:
                acc = get_account()
                if acc:
                    real_equity = float(acc.get('nav', real_equity))
                    buying_power = float(acc.get('margen_libre', real_equity))
                positions_list = get_positions()

            logger.info(f"--- 🌀 CICLO: Equity ${real_equity} | BP ${buying_power} | Posiciones: {len(positions_list)} ---")
            
            for symbol in WATCHLIST:
                try:
                    datos = get_data(symbol)
                    if datos is None or datos.empty:
                        logger.warning(f"⚠️ {symbol}: Sin datos, saltando.")
                        continue
                    
                    bot = TradingBot(datos, real_equity, 0.01, MIN_CONFLUENCIAS)
                    bot.ejecutar()
                    dec = bot.decision; dir_ = dec['direccion']
                    
                    LAST_RUN_LOG[symbol] = {'time': datetime.datetime.now().strftime('%H:%M:%S'), 'dir': dir_, 'reason': dec['razon']}

                    norm_sym = symbol.replace('/', '').upper()
                    current_pos = next((p for p in positions_list if p['instrumento'].replace('/', '').upper() == norm_sym), None)

                    if BINANCE_API_KEY:
                        if current_pos:
                            is_long = current_pos['direccion'] == 'LONG'
                            should_close = (dir_ == 'NEUTRAL') or (is_long and dir_ == 'SHORT') or (not is_long and dir_ == 'LONG')
                            
                            if should_close:
                                logger.info(f"🛑 CERRANDO {symbol}")
                                side_close = 'sell' if is_long else 'buy'
                                place_order(symbol, current_pos['unidades'], side_close)
                                BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"CLOSE", 'price': safe_float(datos['close'].iloc[-1]), 'reason': f"Señal {dir_}"})
                        
                        elif dir_ != 'NEUTRAL':
                            side = 'buy' if dir_ == 'LONG' else 'sell'
                            ges = dec.get('gestion', {})
                            price = float(datos['close'].iloc[-1])
                            raw_qty = float(ges.get('tamano_posicion', 0))
                            
                            # Gestión de BP (10% max por activo)
                            safe_bp_cap = buying_power * 0.10
                            if (raw_qty * price) > safe_bp_cap:
                                raw_qty = safe_bp_cap / price

                            qty = round(raw_qty, 4)
                            if qty > 0:
                                try:
                                    logger.info(f"🚀 ABRIENDO: {symbol} x{qty} {side.upper()}")
                                    place_order(symbol, qty, side)
                                    BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"OPEN {dir_}", 'price': safe_float(price), 'reason': 'Ejecutado'})
                                    buying_power -= (qty * price)
                                except Exception as e_order:
                                    logger.error(f"❌ Error Binance {symbol}: {e_order}")
                    
                    elif dir_ != 'NEUTRAL':
                        BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"SIM {dir_}", 'price': safe_float(datos['close'].iloc[-1]), 'reason': dec['razon']})
                    
                    if len(BOT_HISTORY) > 20: BOT_HISTORY.pop()
                except Exception as e:
                    logger.error(f"Error {symbol}: {e}")
            time.sleep(60)
        else: time.sleep(10)

threading.Thread(target=trading_loop, daemon=True).start()

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/toggle', methods=['POST'])
def toggle():
    global AUTO_TRADING_ACTIVE
    AUTO_TRADING_ACTIVE = not AUTO_TRADING_ACTIVE
    return jsonify({'ok': True, 'state': AUTO_TRADING_ACTIVE})

@app.route('/api/summary')
def summary():
    try:
        is_binance = bool(os.getenv('BINANCE_API_KEY'))
        data = {
            'mode': 'BINANCE' if is_binance else 'SIM', 
            'auto': AUTO_TRADING_ACTIVE, 
            'summary': LAST_RUN_LOG, 
            'history': BOT_HISTORY, 
            'equity': 10000.0, 
            'bp': 10000.0,
            'pl': 0.0, 
            'pos': [],
            'orders': []
        }
        if is_binance:
            acc = get_account()
            if acc:
                data['equity'] = safe_float(acc.get('nav', 0))
                data['bp'] = safe_float(acc.get('margen_libre', 0))
                raw_pos = get_positions()
                data['pos'] = [{ 's': p['instrumento'], 'd': p['direccion'], 'q': p['unidades'], 'e': safe_float(p['precio_medio']), 'c': safe_float(p.get('precio_actual', 0)), 'p': safe_float(p['pl']), 'pct': safe_float(p.get('pl_pct', 0)) } for p in raw_pos]
                total_open_pl = sum(p['p'] for p in data['pos'])
                data['pl'] = safe_float(total_open_pl)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error en summary: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cancel_all', methods=['POST'])
def cancel_all():
    global BOT_HISTORY
    if bool(os.getenv('BINANCE_API_KEY')):
        try:
            cancelar_todas_las_ordenes_ccxt()
            BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': 'ALL', 'type': 'CANCEL', 'price': 0, 'reason': 'Manual cancel'})
            return jsonify({'ok': True})
        except: pass
    return jsonify({'ok': False, 'error': 'No activo'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)