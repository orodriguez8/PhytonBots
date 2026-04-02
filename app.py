import os, sys, io, json, logging, threading, time, datetime, traceback
from flask import Flask, render_template, jsonify
from flask_cors import CORS
import numpy as np
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE LOGS ---
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
        CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS, WATCHLIST
    )
    from trading_bot.ejecucion.alpaca_orders import (
        obtener_cuenta as real_account,
        obtener_posiciones_abiertas as real_pos,
        colocar_orden_mercado as real_order
    )
    from trading_bot.data.alpaca_feed import obtener_datos_alpaca as real_feed
    
    obtener_cuenta, obtener_posiciones_abiertas, colocar_orden_mercado, obtener_datos_alpaca = \
        real_account, real_pos, real_order, real_feed
    
    logger.info("✅ Módulos internos cargados correctamente.")
except Exception:
    logger.error(f"⚠️ Error de carga de módulos:\n{traceback.format_exc()}")
    WATCHLIST = ['AAPL', 'TSLA']; CAPITAL_INICIAL = 10000.0; RIESGO_POR_OPERACION = 0.02; MIN_CONFLUENCIAS = 3

app = Flask(__name__)
CORS(app)

# --- ESTADO GLOBAL ---
AUTO_TRADING_ACTIVE = False
BOT_HISTORY = []
LAST_RUN_LOG = {}

def safe_float(val, ndigits=2):
    try:
        if val is None or (isinstance(val, (float, np.floating, np.float64)) and np.isnan(val)): return 0.0
        return round(float(val), ndigits)
    except: return 0.0

# --- LOOP TRADING ---
def trading_loop():
    global AUTO_TRADING_ACTIVE, BOT_HISTORY
    while True:
        if AUTO_TRADING_ACTIVE:
            key = os.getenv('ALPACA_API_KEY')
            sec = os.getenv('ALPACA_SECRET_KEY')
            ALPACA_READY = bool(key and sec)
            
            # Sincronizamos Equity Real antes de empezar el ciclo
            real_equity = CAPITAL_INICIAL
            if ALPACA_READY:
                acc = obtener_cuenta()
                if acc: real_equity = float(acc.get('nav', real_equity))

            logger.info(f"--- LOOP AUTOMÁTICO (Base Equity: ${real_equity}) ---")
            for symbol in WATCHLIST:
                try:
                    if ALPACA_READY:
                        datos = obtener_datos_alpaca(symbol=symbol)
                    else:
                        from trading_bot.data.simulador import generar_datos
                        datos = generar_datos()

                    if datos is None or datos.empty: continue
                    
                    bot = TradingBot(datos, real_equity, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS)
                    bot.ejecutar()
                    dec = bot.decision; dir_ = dec['direccion']
                    LAST_RUN_LOG[symbol] = {'time': datetime.datetime.now().strftime('%H:%M:%S'), 'dir': dir_, 'reason': dec['razon']}

                    if dir_ != 'NEUTRAL' and ALPACA_READY:
                        pos = obtener_posiciones_abiertas()
                        ya_en_pos = any(p['instrumento'] == symbol for p in pos) if pos else False
                        
                        if not ya_en_pos:
                            side = 'buy' if dir_ == 'LONG' else 'sell'
                            ges = dec.get('gestion', {})
                            
                            # CÁLCULO SEGURO DE CANTIDAD
                            raw_qty = float(ges.get('tamano_posicion', 0))
                            unit_price = float(datos['close'].iloc[-1])
                            
                            # PROTECCIÓN: Nunca más del 20% del Equity por trade
                            max_val = real_equity * 0.20
                            current_val = raw_qty * unit_price
                            if current_val > max_val:
                                raw_qty = max_val / unit_price
                                logger.info(f"🛡️ Ajustando cantidad de {symbol} por límite de Equity (Max 20%)")

                            # Formateo (Crypto admite decimales, Stocks no en Alpaca Standard API)
                            is_crypto = 'USD' in symbol or '/' in symbol
                            qty = round(raw_qty, 4) if is_crypto else max(1, int(raw_qty))

                            if qty > 0:
                                try:
                                    logger.info(f"🚀 Enviando a Alpaca: {symbol} {qty} {side}")
                                    colocar_orden_mercado(symbol, qty, side, ges.get('take_profit'), ges.get('stop_loss'))
                                    BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"REAL {dir_}", 'price': safe_float(unit_price), 'reason': 'Ejecutado'})
                                except Exception as e_order:
                                    logger.error(f"❌ Error Alpaca ({symbol}): {e_order}")
                    elif dir_ != 'NEUTRAL':
                        BOT_HISTORY.insert(0, {'time': datetime.datetime.now().strftime('%H:%M'), 'sym': symbol, 'type': f"SIM {dir_}", 'price': safe_float(datos['close'].iloc[-1]), 'reason': dec['razon']})
                    
                    if len(BOT_HISTORY) > 20: BOT_HISTORY.pop()
                except Exception as e: logger.error(f"Error {symbol}: {e}")
            time.sleep(60)
        else: time.sleep(10)

threading.Thread(target=trading_loop, daemon=True).start()

# --- ROUTES ---
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
        key = os.getenv('ALPACA_API_KEY'); sec = os.getenv('ALPACA_SECRET_KEY')
        is_ready = bool(key and sec)
        data = {'mode': 'ALPACA' if is_ready else 'SIM', 'auto': AUTO_TRADING_ACTIVE, 'summary': LAST_RUN_LOG, 'history': BOT_HISTORY, 'equity': 10000.0, 'pl': 0.0, 'pos': []}
        if is_ready:
            acc = obtener_cuenta()
            if acc:
                data['equity'] = safe_float(acc.get('nav', 0))
                data['pl'] = safe_float(acc.get('pl', 0))
            raw_pos = obtener_posiciones_abiertas()
            if raw_pos:
                data['pos'] = [{ 's': p['instrumento'], 'q': p['unidades'], 'e': safe_float(p['precio_medio']), 'c': safe_float(p.get('precio_actual', 0)), 'p': safe_float(p['pl']), 'pct': safe_float(p.get('pl_pct', 0)) } for p in raw_pos]
        return jsonify(data)
    except Exception as e: return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)