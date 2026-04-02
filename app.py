import os
import sys
import io
import json
import logging
import threading
import time
import datetime
import traceback
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import numpy as np
from dotenv import load_dotenv

# Configuración de logs detallada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración de Rutas (PYTHONPATH)
TOP_DIR = os.path.dirname(os.path.abspath(__file__))
# Añadimos tanto el raíz como trading_bot al path
if TOP_DIR not in sys.path:
    sys.path.insert(0, TOP_DIR)
BOT_DIR = os.path.join(TOP_DIR, 'trading_bot')
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)

# UTF-8 Encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Estado global alpaca
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_ENABLED = bool(ALPACA_API_KEY and ALPACA_SECRET_KEY)

# Funciones Mockup iniciales (Evitan NameError si falla import)
def obtener_cuenta(): return None
def obtener_posiciones_abiertas(): return []
def colocar_orden_mercado(*args, **kwargs): return None
def obtener_datos_alpaca(*args, **kwargs): return None

# Bloque de importación real con log detallado
try:
    logger.info(f"Intentando cargar módulos desde: {BOT_DIR}")
    
    # Intentamos importación absoluta desde trading_bot
    from bot.trading_bot import TradingBot
    from config import (
        CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS, WATCHLIST
    )
    from data.alpaca_feed import obtener_datos_alpaca as real_obtener_datos
    from ejecucion.alpaca_orders import obtener_cuenta as real_obtener_cuenta, \
                                       obtener_posiciones_abiertas as real_obtener_pos, \
                                       colocar_orden_mercado as real_colocar_orden
    
    # Reasignación
    obtener_datos_alpaca = real_obtener_datos
    obtener_cuenta = real_obtener_cuenta
    obtener_posiciones_abiertas = real_obtener_pos
    colocar_orden_mercado = real_colocar_orden
    
    logger.info("✅ Todos los módulos se cargaron correctamente.")

except Exception:
    error_msg = traceback.format_exc()
    logger.error(f"❌ FALLO CRÍTICO AL CARGAR MÓDULOS:\n{error_msg}")
    
    # Valores de emergencia
    WATCHLIST = ['AAPL', 'TSLA']
    CAPITAL_INICIAL = 10000.0
    RIESGO_POR_OPERACION = 0.02
    MIN_CONFLUENCIAS = 3

app = Flask(__name__)
CORS(app)

AUTO_TRADING_ACTIVE = False
ACTIVE_SYMBOLS = WATCHLIST
BOT_HISTORY = []
LAST_RUN_LOG = {}

def safe_float(val, ndigits=2):
    try:
        if val is None or (isinstance(val, (float, np.floating, np.float64)) and np.isnan(val)): return 0.0
        return round(float(val), ndigits)
    except:
        return 0.0

# LOOP DE TRADING
def trading_loop():
    global AUTO_TRADING_ACTIVE, BOT_HISTORY
    while True:
        if AUTO_TRADING_ACTIVE:
            logger.info("--- 🔄 Ciclo Automático Iniciado ---")
            for symbol in ACTIVE_SYMBOLS:
                try:
                    # 1. Obtener datos
                    if ALPACA_ENABLED:
                        datos = obtener_datos_alpaca(symbol=symbol)
                    else:
                        from data.simulador import generar_datos
                        datos = generar_datos()

                    if datos is None or datos.empty:
                        logger.warning(f"⚠️ {symbol}: Sin datos.")
                        continue

                    # 2. Análisis
                    bot = TradingBot(datos, CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS)
                    bot.ejecutar()

                    dec = bot.decision
                    dir_ = dec['direccion']
                    
                    LAST_RUN_LOG[symbol] = {
                        'time': datetime.datetime.now().strftime('%H:%M:%S'),
                        'dir': dir_,
                        'reason': dec['razon']
                    }

                    # 3. Orden Real
                    if dir_ != 'NEUTRAL' and ALPACA_ENABLED:
                        try:
                            posiciones = obtener_posiciones_abiertas()
                            ya_en_posicion = any(p['instrumento'] == symbol for p in posiciones) if posiciones else False
                            
                            if not ya_en_posicion:
                                side = 'buy' if dir_ == 'LONG' else 'sell'
                                ges = dec.get('gestion', {})
                                qty = int(ges.get('tamano_posicion', 1))
                                if qty > 0:
                                    res = colocar_orden_mercado(symbol, qty, side, ges.get('take_profit'), ges.get('stop_loss'))
                                    logger.info(f"💰 REAL ORDER: {side} {qty} {symbol}")
                                    BOT_HISTORY.insert(0, {
                                        'time': datetime.datetime.now().strftime('%H:%M:%S'),
                                        'symbol': symbol,
                                        'type': f"REAL {dir_}",
                                        'price': safe_float(datos['close'].iloc[-1]),
                                        'reason': f"Ejecutado: {side} {qty}"
                                    })
                        except Exception as e_order:
                            logger.error(f"❌ Error Alpaca ({symbol}): {e_order}")
                    
                    elif dir_ != 'NEUTRAL':
                        BOT_HISTORY.insert(0, {
                            'time': datetime.datetime.now().strftime('%H:%M:%S'),
                            'symbol': symbol,
                            'type': f"SIM {dir_}",
                            'price': safe_float(datos['close'].iloc[-1]),
                            'reason': dec['razon']
                        })
                    
                    if len(BOT_HISTORY) > 50: BOT_HISTORY.pop()

                except Exception as e:
                    logger.error(f"❌ Error en {symbol}: {e}")
            
            logger.info("--- ✅ Ciclo Fin. Esperando 1m ---")
            time.sleep(60) 
        else:
            time.sleep(5) 

threading.Thread(target=trading_loop, daemon=True).start()

# API ROUTES
@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'online',
        'modo': 'ALPACA' if ALPACA_ENABLED else 'SIMULADOR',
        'auto_trading': AUTO_TRADING_ACTIVE,
        'symbols': ACTIVE_SYMBOLS,
        'last_run_log': LAST_RUN_LOG
    })

@app.route('/api/toggle-auto', methods=['POST'])
def api_toggle_auto():
    global AUTO_TRADING_ACTIVE
    AUTO_TRADING_ACTIVE = not AUTO_TRADING_ACTIVE
    return jsonify({'ok': True, 'auto_trading': AUTO_TRADING_ACTIVE})

@app.route('/api/account')
def api_account():
    try:
        if ALPACA_ENABLED:
            cuenta = obtener_cuenta()
            if not cuenta:
                return jsonify({'error': 'La API de Alpaca no devolvió datos de cuenta (revisa las llaves)'}), 500
                
            pos = obtener_posiciones_abiertas()
            return jsonify({
                'equity': safe_float(cuenta.get('nav', 0)),
                'pl_total': safe_float(cuenta.get('pl', 0)),
                'posiciones': [{
                    'symbol': p['instrumento'],
                    'qty': float(p['unidades']),
                    'entry_price': safe_float(p['precio_medio']),
                    'current_price': safe_float(p.get('precio_actual', 0)),
                    'pl': safe_float(p['pl']),
                    'pl_pct': safe_float(p.get('pl_pct', 0))
                } for p in pos],
                'history': BOT_HISTORY
            })
        else:
            return jsonify({
                'equity': 10000.0, 'pl_total': 0.0, 'posiciones': [], 'history': BOT_HISTORY
            })
    except Exception as e:
        logger.error(f"CRASH api/account: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)