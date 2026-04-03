# VERSION 2.0.1 - MODIFICADO POR ANTIGRAVITY
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

# --- FALLBACKS ---
def obtener_cuenta(): return None
def obtener_posiciones_abiertas(): return []
def colocar_orden_mercado(*args,**kw): return None
def obtener_datos_alpaca(*args,**kw): return None

# --- IMPORTACIÓN ROBUSTA ---
try:
    from trading_bot.bot.trading_bot import TradingBot
    from trading_bot.config import (
        CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS, WATCHLIST,
        BINANCE_API_KEY, TRADING_MODE_CRYPTO
    )
    # Alpaca
    from trading_bot.ejecucion.alpaca_orders import (
        obtener_cuenta as alp_account,
        obtener_posiciones_abiertas as alp_pos,
        obtener_posiciones_cerradas as alp_history,
        obtener_ordenes_activas as alp_orders,
        cancelar_todas_las_ordenes as alp_cancel,
        colocar_orden_mercado as alp_order
    )
    from trading_bot.data.alpaca_feed import obtener_datos_alpaca as alp_feed
    
    # CCXT / Binance
    from trading_bot.ejecucion.ccxt_orders import (
        obtener_cuenta_ccxt, 
        obtener_posiciones_abiertas_ccxt,
        colocar_orden_mercado_ccxt
    )
    from trading_bot.data.ccxt_feed import obtener_datos_ccxt

    # Mapeo de funciones inteligentes
    def get_data(symbol):
        is_crypto = 'USD' in symbol or '/' in symbol
        if is_crypto and TRADING_MODE_CRYPTO == 'BINANCE' and BINANCE_API_KEY:
            return obtener_datos_ccxt(symbol)
        return alp_feed(symbol)

    def get_account():
        if TRADING_MODE_CRYPTO == 'BINANCE' and BINANCE_API_KEY:
            return obtener_cuenta_ccxt()
        return alp_account()

    def get_positions():
        if TRADING_MODE_CRYPTO == 'BINANCE' and BINANCE_API_KEY:
            return obtener_posiciones_abiertas_ccxt()
        return alp_pos()

    def place_order(symbol, qty, side, tp=None, sl=None):
        is_crypto = 'USD' in symbol or '/' in symbol
        if is_crypto and TRADING_MODE_CRYPTO == 'BINANCE' and BINANCE_API_KEY:
            return colocar_orden_mercado_ccxt(symbol, qty, side)
        return alp_order(symbol, qty, side, tp, sl)

    logger.info("✅ Módulos internos (Alpaca + CCXT) listos.")
except Exception:
    logger.error(f"⚠️ Error cargando módulos:\n{traceback.format_exc()}")
    WATCHLIST = ['AAPL', 'TSLA']; CAPITAL_INICIAL = 10000.0; RIESGO_POR_OPERACION = 0.02; MIN_CONFLUENCIAS = 3

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

# --- LOOP TRADING CONGESTIÓN BAJA ---
def trading_loop():
    global AUTO_TRADING_ACTIVE, BOT_HISTORY
    while True:
        if AUTO_TRADING_ACTIVE:
            key = os.getenv('ALPACA_API_KEY'); sec = os.getenv('ALPACA_SECRET_KEY')
            ALPACA_READY = bool(key and sec)
            
            real_equity = CAPITAL_INICIAL
            buying_power = real_equity
            positions_list = []
            
            if ALPACA_READY or BINANCE_API_KEY:
                acc = get_account()
                if acc:
                    real_equity = float(acc.get('nav', real_equity))
                    buying_power = float(acc.get('margen_libre', real_equity))
                
                positions_list = get_positions()
                active_orders = [] # Por ahora simple
                if ALPACA_READY: 
                    try: active_orders = alp_orders()
                    except: pass

            logger.info(f"--- 🌀 CICLO: Equity ${real_equity} | BP ${buying_power} | Posiciones: {len(positions_list)} ---")
            
            for symbol in WATCHLIST:
                try:
                    datos = get_data(symbol)
                    if datos is None or datos.empty:
                        logger.warning(f"⚠️ {symbol}: Sin datos, saltando.")
                        continue
                    
                    # Decisión del bot
                    bot = TradingBot(datos, real_equity, 0.01, MIN_CONFLUENCIAS)
                    bot.ejecutar()
                    dec = bot.decision; dir_ = dec['direccion']
                    
                    # Actualizar log para dashboard
                    LAST_RUN_LOG[symbol] = {'time': datetime.datetime.now().strftime('%H:%M:%S'), 'dir': dir_, 'reason': dec['razon']}

                    # Normalización de símbolos para matching
                    norm_sym = symbol.replace('/', '').upper()
                    current_pos = next((p for p in positions_list if p['instrumento'].replace('/', '').upper() == norm_sym), None)
                    pending_order = next((o for o in active_orders if o['symbol'].replace('/', '').upper() == norm_sym), None)

                    if ALPACA_READY or BINANCE_API_KEY:
                        if current_pos:
                            # YA TENEMOS POSICIÓN: ¿Debemos cerrar?
                            is_long = current_pos['direccion'] == 'LONG'
                            should_close = (dir_ == 'NEUTRAL') or (is_long and dir_ == 'SHORT') or (not is_long and dir_ == 'LONG')
                            
                            if should_close:
                                logger.info(f"🛑 CERRANDO {symbol} (Señal: {dir_})")
                                side_close = 'sell' if is_long else 'buy'
                                place_order(symbol, current_pos['unidades'], side_close)
                                BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"CLOSE {current_pos['direccion']}", 'price': safe_float(datos['close'].iloc[-1]), 'reason': f"Señal {dir_}"})
                        
                        elif pending_order:
                            # YA HAY UNA ORDEN PENDIENTE
                            logger.info(f"⏳ {symbol}: Ya hay una orden pendiente ({pending_order['side']}), esperando...")

                        elif dir_ != 'NEUTRAL':
                            # NO HAY POSICIÓN NI ORDEN: ¿Debemos abrir?
                            side = 'buy' if dir_ == 'LONG' else 'sell'
                            ges = dec.get('gestion', {})
                            price = float(datos['close'].iloc[-1])
                            raw_qty = float(ges.get('tamano_posicion', 0))
                            
                            safe_bp_cap = buying_power * 0.10
                            if (raw_qty * price) > safe_bp_cap:
                                raw_qty = safe_bp_cap / price
                                logger.info(f"🛡️ Ajustando {symbol} al 10% del BP.")

                            is_crypto = 'USD' in symbol or '/' in symbol
                            qty = round(raw_qty, 4) if is_crypto else int(raw_qty)

                            if qty > 0:
                                try:
                                    logger.info(f"🚀 ABRIENDO: {symbol} x{qty} {side.upper()}")
                                    place_order(symbol, qty, side, ges.get('take_profit'), ges.get('stop_loss'))
                                    BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"OPEN {dir_}", 'price': safe_float(price), 'reason': 'Ejecutado'})
                                    buying_power -= (qty * price)
                                except Exception as e_order:
                                    logger.error(f"❌ Error Ejecución {symbol}: {e_order}")
                            else:
                                logger.warning(f"⚠️ {symbol}: Cantidad 0.")


                    elif dir_ != 'NEUTRAL':
                        # Modo simulación
                        BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"SIM {dir_}", 'price': safe_float(datos['close'].iloc[-1]), 'reason': dec['razon']})
                    
                    if len(BOT_HISTORY) > 20: BOT_HISTORY.pop()
                except Exception as e:
                    logger.error(f"Error {symbol} en el loop: {e}")
            time.sleep(60)

        else: time.sleep(10)

threading.Thread(target=trading_loop, daemon=True).start()

# RUTA BASE
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
        is_alpaca = bool(os.getenv('ALPACA_API_KEY'))
        is_binance = bool(os.getenv('BINANCE_API_KEY'))
        
        data = {
            'mode': 'BINANCE' if (is_binance and TRADING_MODE_CRYPTO == 'BINANCE') else ('ALPACA' if is_alpaca else 'SIM'), 
            'auto': AUTO_TRADING_ACTIVE, 
            'summary': LAST_RUN_LOG, 
            'history': BOT_HISTORY, 
            'equity': 10000.0, 
            'bp': 10000.0,
            'pl': 0.0, 
            'pos': [],
            'orders': []
        }
        
        if is_alpaca or is_binance:
            acc = get_account()
            if acc:
                data['equity'] = safe_float(acc.get('nav', 0))
                data['bp'] = safe_float(acc.get('margen_libre', 0))
                
                raw_pos = get_positions()
                data['pos'] = [{ 's': p['instrumento'], 'd': p['direccion'], 'q': p['unidades'], 'e': safe_float(p['precio_medio']), 'c': safe_float(p.get('precio_actual', 0)), 'p': safe_float(p['pl']), 'pct': safe_float(p.get('pl_pct', 0)) } for p in raw_pos]
                
                # Para órdenes activas, seguimos con Alpaca por ahora o vacio para Binance
                if is_alpaca:
                    try: data['orders'] = alp_orders()
                    except: pass
                
                # TOTAL OPEN P/L
                total_open_pl = sum(p['p'] for p in data['pos'])
                data['pl'] = safe_float(total_open_pl)
                
                # Historial (Alpaca)
                if is_alpaca:
                    try: data['closed'] = alp_history()
                    except: pass

        return jsonify(data)

    except Exception as e: 
        logger.error(f"Error en summary: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cancel_all', methods=['POST'])
def cancel_all():
    global BOT_HISTORY
    # Por ahora cancelamos en Alpaca si está activo
    if bool(os.getenv('ALPACA_API_KEY')):
        alp_cancel()
        BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': 'ALL', 'type': 'CANCEL', 'price': 0, 'reason': 'Manual cancel'})
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'No activo o no soportado'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)