import os
import sys
import io
import json
import logging
import traceback
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Configuración de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Añadir el directorio trading_bot al PYTHONPATH para que los módulos internos funcionen
TOP_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_DIR = os.path.join(TOP_DIR, 'trading_bot')
sys.path.insert(0, BOT_DIR)

# Forzar codificación UTF-8 para consola
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Importaciones del bot original
try:
    from bot.trading_bot import TradingBot
    from config import (
        CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS
    )
except ImportError as e:
    logger.error(f"Error importando módulos del bot: {e}")
    # Definir valores por defecto si falla la importación
    CAPITAL_INICIAL = 10000.0
    RIESGO_POR_OPERACION = 0.02
    MIN_CONFLUENCIAS = 3

app = Flask(__name__)
CORS(app)

# Detectar modo
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_ENABLED = bool(ALPACA_API_KEY and ALPACA_SECRET_KEY)
AUTO_TRADING = False

# Estado persistente básico (en memoria por ahora)
BOT_HISTORY = [] # Historial de acciones
VIRTUAL_POSITIONS = [] # Posiciones en modo simulado

def to_python(obj):
    if isinstance(obj, (np.integer,)):   return int(obj)
    if isinstance(obj, (np.floating,)):  return float(obj)
    if isinstance(obj, np.ndarray):      return obj.tolist()
    return obj

def safe_float(val, ndigits=2):
    if val is None or (isinstance(val, float) and np.isnan(val)): return 0.0
    return round(float(val), ndigits)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    symbol = os.getenv('ALPACA_SYMBOL', 'AAPL') if ALPACA_ENABLED else 'SIMULADO'
    return jsonify({
        'status': 'online',
        'modo': 'ALPACA' if ALPACA_ENABLED else 'SIMULADOR',
        'auto_trading': AUTO_TRADING,
        'symbol': symbol,
        'last_run': BOT_HISTORY[-1]['time'] if BOT_HISTORY else None
    })

@app.route('/api/run')
def api_run():
    try:
        # 1. Obtener datos
        if ALPACA_ENABLED:
            from data.alpaca_feed import obtener_datos_alpaca
            symbol = os.getenv('ALPACA_SYMBOL', 'AAPL')
            datos = obtener_datos_alpaca(symbol=symbol)
        else:
            from data.simulador import generar_datos
            datos = generar_datos()

        # 2. Ejecutar Bot
        bot = TradingBot(datos, CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS)
        bot.ejecutar()

        dec = bot.decision
        ges = dec.get('gestion') or {}
        
        # Registrar acción en historial
        import datetime
        action = {
            'time': datetime.datetime.now().strftime('%H:%M:%S'),
            'type': dec['direccion'],
            'price': safe_float(datos['close'].iloc[-1]),
            'reason': dec['razon'],
            'profit_loss': 0 # Esto requeriría seguimiento de posición
        }
        BOT_HISTORY.insert(0, action)
        if len(BOT_HISTORY) > 20: BOT_HISTORY.pop()

        payload = {
            'last_price': safe_float(datos['close'].iloc[-1]),
            'direction': dec['direccion'],
            'reason': dec['razon'],
            'confluences': {
                'long': len(bot.confluencias_long),
                'short': len(bot.confluencias_short),
                'total_long': dec.get('total_long', 0),
                'total_short': dec.get('total_short', 0),
                'min': MIN_CONFLUENCIAS
            },
            'gestion': {k: safe_float(v) if isinstance(v, (float, np.floating)) else v for k, v in ges.items()} if ges else None,
            'history': BOT_HISTORY
        }
        
        return jsonify(payload)
    except Exception as e:
        logger.error(f"Error en /api/run: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/account')
def api_account():
    try:
        if ALPACA_ENABLED:
            from ejecucion.alpaca_orders import obtener_cuenta, obtener_posiciones_abiertas
            cuenta = obtener_cuenta()
            pos = obtener_posiciones_abiertas()
            
            # Formatear datos de Alpaca para el frontend
            # cuenta suele tener equity, buying_power, etc.
            # pos suele tener symbol, qty, unrealized_pl, etc.
            
            return jsonify({
                'equity': safe_float(float(cuenta.equity)),
                'pl_total': safe_float(float(cuenta.equity) - float(cuenta.last_equity)),
                'posiciones': [{
                    'symbol': p.symbol,
                    'qty': float(p.qty),
                    'entry_price': safe_float(float(p.avg_entry_price)),
                    'current_price': safe_float(float(p.current_price)),
                    'pl': safe_float(float(p.unrealized_pl)),
                    'pl_pct': safe_float(float(p.unrealized_pl_pc) * 100)
                } for p in pos]
            })
        else:
            # Datos simulados para demostración
            return jsonify({
                'equity': 10000.0,
                'pl_total': 150.25,
                'posiciones': [
                    {
                        'symbol': 'BTC/USD (Simulado)',
                        'qty': 0.05,
                        'entry_price': 50000.0,
                        'current_price': 51200.0,
                        'pl': 60.0,
                        'pl_pct': 1.2
                    }
                ]
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Hugging Face Spaces necesita el puerto 7860
    app.run(host='0.0.0.0', port=7860)