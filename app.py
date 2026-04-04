# ═══════════════════════════════════════════════════════════════════════════════
# MERA VICTORINO — Pro Trading Server v3.0
# Flask-SocketIO · WebSocket Data Stream · Latency Monitor · Event Console
# ═══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE:
#   - WebSocket (Socket.IO) replaces HTTP polling → lower latency, less CPU
#   - Background emitter pushes data every 3s (only to connected clients)
#   - HTTP /api/* endpoints kept for backward compatibility & fallback
#   - Trading logic (bot, orders, feeds) is UNTOUCHED
# ═══════════════════════════════════════════════════════════════════════════════

import os, sys, io, json, logging, threading, time, datetime, traceback
from flask import Flask, render_template, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import numpy as np
from dotenv import load_dotenv

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv()
TOP_DIR = os.path.dirname(os.path.abspath(__file__))
if TOP_DIR not in sys.path:
    sys.path.insert(0, TOP_DIR)

# ── Robust Module Import (ALPACA + CCXT) — UNTOUCHED LOGIC ────────────────────
try:
    from trading_bot.bot.trading_bot import TradingBot
    from trading_bot.config import (
        CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS, WATCHLIST,
        TRADING_MODE_CRYPTO,
        ALPACA_API_KEY, ALPACA_SECRET_KEY,
        CCXT_API_KEY, CCXT_EXCHANGE_ID,
    )

    # Alpaca
    from trading_bot.ejecucion.alpaca_orders import (
        obtener_cuenta,
        obtener_posiciones_abiertas,
        obtener_posiciones_cerradas,
        obtener_ordenes_activas,
        colocar_orden_mercado,
        cancelar_todas_las_ordenes,
    )
    from trading_bot.data.alpaca_feed import obtener_datos_alpaca

    # CCXT / Exchange configurable
    from trading_bot.ejecucion.ccxt_orders import (
        obtener_cuenta_ccxt,
        obtener_posiciones_abiertas_ccxt,
        colocar_orden_mercado_ccxt,
        cancelar_todas_las_ordenes_ccxt
    )
    from trading_bot.data.ccxt_feed import obtener_datos_ccxt

    PROVIDER = (TRADING_MODE_CRYPTO or 'ALPACA').upper()
    IS_ALPACA = PROVIDER == 'ALPACA'
    LIVE_ENABLED = bool(ALPACA_API_KEY and ALPACA_SECRET_KEY) if IS_ALPACA else bool(CCXT_API_KEY)

    # ── Data/Account/Order Wrappers (100% original logic) ──────────────────────
    def get_data(symbol):
        if not LIVE_ENABLED:
            return None
        if IS_ALPACA:
            return obtener_datos_alpaca(symbol)
        return obtener_datos_ccxt(symbol)

    def get_account():
        if not LIVE_ENABLED:
            return None
        if IS_ALPACA:
            return obtener_cuenta()
        return obtener_cuenta_ccxt()

    def get_positions():
        if not LIVE_ENABLED:
            return []
        if IS_ALPACA:
            return obtener_posiciones_abiertas()
        return obtener_posiciones_abiertas_ccxt()

    def get_orders():
        if not LIVE_ENABLED:
            return []
        if IS_ALPACA:
            return obtener_ordenes_activas()
        return []

    def get_closed_positions():
        if not LIVE_ENABLED:
            return []
        if IS_ALPACA:
            return obtener_posiciones_cerradas()
        return []

    def place_order(symbol, qty, side, tp=None, sl=None):
        if not LIVE_ENABLED:
            return None
        if IS_ALPACA:
            return colocar_orden_mercado(symbol, qty, side, tp, sl)
        return colocar_orden_mercado_ccxt(symbol, qty, side)

    def cancel_all_orders():
        if not LIVE_ENABLED:
            return False
        if IS_ALPACA:
            return cancelar_todas_las_ordenes()
        return cancelar_todas_las_ordenes_ccxt()

    active_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
    logger.info(f"✅ Módulos internos ({active_name}) listos.")

except Exception:
    logger.error(f"⚠️ Error cargando módulos:\n{traceback.format_exc()}")
    WATCHLIST = ['BTC/USD']
    CAPITAL_INICIAL = 10000.0
    PROVIDER = 'ALPACA'
    IS_ALPACA = True
    LIVE_ENABLED = False
    CCXT_EXCHANGE_ID = 'coinbase'

    def get_data(s): return None
    def get_account(): return None
    def get_positions(): return []
    def get_orders(): return []
    def get_closed_positions(): return []
    def place_order(*a, **kw): return None
    def cancel_all_orders(): return False


# ═══════════════════════════════════════════════════════════════════════════════
# FLASK + SOCKETIO APP
# ═══════════════════════════════════════════════════════════════════════════════
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mera-victorino-pro-3.0')
CORS(app)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=30,
    ping_interval=15,
    logger=False,
    engineio_logger=False,
)

# ── Shared State ───────────────────────────────────────────────────────────────
AUTO_TRADING_ACTIVE = False
BOT_HISTORY = []
LAST_RUN_LOG = {}
CONSOLE_EVENTS = []       # Server-side event log (pushed to clients)
MAX_CONSOLE = 60

def safe_float(val, ndigits=2):
    """Safe float conversion — handles None, NaN, and numpy types."""
    try:
        if val is None:
            return 0.0
        if isinstance(val, (float, np.floating)) and np.isnan(val):
            return 0.0
        return round(float(val), ndigits)
    except Exception:
        return 0.0


def push_event(etype, msg):
    """Push an event to the console log and broadcast via WebSocket."""
    global CONSOLE_EVENTS
    evt = {
        'type': etype,
        'msg': msg,
        'time': datetime.datetime.now().strftime('%H:%M:%S'),
    }
    CONSOLE_EVENTS.insert(0, evt)
    if len(CONSOLE_EVENTS) > MAX_CONSOLE:
        CONSOLE_EVENTS.pop()
    # Non-blocking emit to all connected clients
    try:
        socketio.emit('console_event', evt)
    except Exception:
        pass


def build_summary():
    """Build the full dashboard data payload (used by both HTTP and WS)."""
    try:
        active_mode = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
        data = {
            'mode': active_mode if LIVE_ENABLED else 'SIM',
            'auto': AUTO_TRADING_ACTIVE,
            'summary': LAST_RUN_LOG,
            'history': BOT_HISTORY,
            'equity': 10000.0,
            'bp': 10000.0,
            'pl': 0.0,
            'day_pl': 0.0,
            'pos': [],
            'closed': [],
            'orders': [],
        }
        if LIVE_ENABLED:
            acc = get_account()
            if acc:
                data['equity'] = safe_float(acc.get('nav', 0))
                data['bp'] = safe_float(acc.get('margen_libre', 0))
                data['day_pl'] = safe_float(acc.get('pl', 0))

                raw_pos = get_positions()
                data['pos'] = [{
                    's': p['instrumento'],
                    'd': p['direccion'],
                    'q': p['unidades'],
                    'e': safe_float(p['precio_medio']),
                    'c': safe_float(p.get('precio_actual', 0)),
                    'p': safe_float(p['pl']),
                    'pct': safe_float(p.get('pl_pct', 0)),
                } for p in raw_pos]

                total_open_pl = sum(p['p'] for p in data['pos'])
                data['pl'] = safe_float(total_open_pl)

                data['closed'] = get_closed_positions()
                data['orders'] = get_orders()
        return data
    except Exception as e:
        logger.error(f"Error building summary: {traceback.format_exc()}")
        return {'error': str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING LOOP — 100% ORIGINAL LOGIC (UNTOUCHED)
# ═══════════════════════════════════════════════════════════════════════════════
def trading_loop():
    global AUTO_TRADING_ACTIVE, BOT_HISTORY
    while True:
        if AUTO_TRADING_ACTIVE:
            real_equity = CAPITAL_INICIAL
            buying_power = real_equity
            positions_list = []

            if LIVE_ENABLED:
                acc = get_account()
                if acc:
                    real_equity = float(acc.get('nav', real_equity))
                    buying_power = float(acc.get('margen_libre', real_equity))
                positions_list = get_positions()

            logger.info(f"--- 🌀 CICLO: Equity ${real_equity} | BP ${buying_power} | Posiciones: {len(positions_list)} ---")
            push_event('info', f"Cycle: Equity ${real_equity:,.2f} | BP ${buying_power:,.2f} | {len(positions_list)} pos")

            for symbol in WATCHLIST:
                try:
                    datos = get_data(symbol)
                    if datos is None or datos.empty:
                        logger.warning(f"⚠️ {symbol}: Sin datos, saltando.")
                        push_event('warn', f"{symbol}: No data, skipping")
                        continue

                    bot = TradingBot(datos, real_equity, 0.01, MIN_CONFLUENCIAS)
                    bot.ejecutar()
                    dec = bot.decision
                    dir_ = dec['direccion']

                    LAST_RUN_LOG[symbol] = {
                        'time': datetime.datetime.now().strftime('%H:%M:%S'),
                        'dir': dir_,
                        'reason': dec['razon'],
                    }

                    norm_sym = symbol.replace('/', '').upper()
                    current_pos = next(
                        (p for p in positions_list if p['instrumento'].replace('/', '').upper() == norm_sym),
                        None
                    )

                    if LIVE_ENABLED:
                        if current_pos:
                            is_long = current_pos['direccion'] == 'LONG'
                            should_close = (
                                (dir_ == 'NEUTRAL')
                                or (is_long and dir_ == 'SHORT')
                                or (not is_long and dir_ == 'LONG')
                            )

                            if should_close:
                                market_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
                                logger.info(f"🛑 CERRANDO {symbol} en {market_name}")
                                push_event('order', f"CLOSING {symbol} on {market_name}")
                                side_close = 'sell' if is_long else 'buy'
                                place_order(symbol, current_pos['unidades'], side_close)
                                BOT_HISTORY.insert(0, {
                                    'time': datetime.datetime.now().strftime('%H:%M'),
                                    'sym': symbol,
                                    'type': 'CLOSE',
                                    'price': safe_float(datos['close'].iloc[-1]),
                                    'reason': f"Signal {dir_}",
                                })

                        elif dir_ != 'NEUTRAL':
                            side = 'buy' if dir_ == 'LONG' else 'sell'
                            ges = dec.get('gestion', {})
                            price = float(datos['close'].iloc[-1])
                            raw_qty = float(ges.get('tamano_posicion', 0))

                            # BP cap: max 10% per asset
                            safe_bp_cap = buying_power * 0.10
                            if (raw_qty * price) > safe_bp_cap:
                                raw_qty = safe_bp_cap / price

                            qty = round(raw_qty, 4)
                            if qty > 0:
                                try:
                                    market_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
                                    logger.info(f"🚀 ABRIENDO: {symbol} x{qty} {side.upper()} en {market_name}")
                                    push_event('order', f"OPENING {symbol} x{qty} {side.upper()} on {market_name}")
                                    place_order(symbol, qty, side)
                                    BOT_HISTORY.insert(0, {
                                        'time': datetime.datetime.now().strftime('%H:%M'),
                                        'sym': symbol,
                                        'type': f"OPEN {dir_}",
                                        'price': safe_float(price),
                                        'reason': 'Executed',
                                    })
                                    buying_power -= (qty * price)
                                except Exception as e_order:
                                    market_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
                                    logger.error(f"❌ Error {market_name} {symbol}: {e_order}")
                                    push_event('error', f"Order failed {symbol}: {e_order}")

                    elif dir_ != 'NEUTRAL':
                        BOT_HISTORY.insert(0, {
                            'time': datetime.datetime.now().strftime('%H:%M'),
                            'sym': symbol,
                            'type': f"SIM {dir_}",
                            'price': safe_float(datos['close'].iloc[-1]),
                            'reason': dec['razon'],
                        })

                    if len(BOT_HISTORY) > 20:
                        BOT_HISTORY.pop()

                except Exception as e:
                    logger.error(f"Error {symbol}: {e}")
                    push_event('error', f"Error processing {symbol}: {e}")

            time.sleep(60)
        else:
            time.sleep(10)


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET DATA EMITTER — Pushes data to all clients every 3s
# Replaces HTTP polling → less CPU, lower latency, no re-render overhead
# ═══════════════════════════════════════════════════════════════════════════════
def ws_data_emitter():
    """Background thread that pushes dashboard data via WebSocket every 3s."""
    while True:
        try:
            data = build_summary()
            if 'error' not in data:
                socketio.emit('data_update', data)
        except Exception as e:
            logger.debug(f"Emitter cycle error: {e}")
        time.sleep(3)


# ═══════════════════════════════════════════════════════════════════════════════
# SOCKET.IO EVENT HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
@socketio.on('connect')
def handle_connect():
    logger.info(f"🔌 WebSocket client connected")
    push_event('info', 'Client connected')
    # Send initial state immediately
    data = build_summary()
    emit('data_update', data)


@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"🔌 WebSocket client disconnected")


@socketio.on('ping_latency')
def handle_ping():
    emit('pong_latency')


@socketio.on('toggle_bot')
def handle_toggle():
    global AUTO_TRADING_ACTIVE
    AUTO_TRADING_ACTIVE = not AUTO_TRADING_ACTIVE
    state_label = 'ACTIVE' if AUTO_TRADING_ACTIVE else 'STANDBY'
    push_event('info', f"Bot toggled → {state_label}")
    logger.info(f"🤖 Bot → {state_label}")
    data = build_summary()
    socketio.emit('data_update', data)


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP ROUTES — Backward-compatible fallback
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/toggle', methods=['POST'])
def toggle():
    global AUTO_TRADING_ACTIVE
    AUTO_TRADING_ACTIVE = not AUTO_TRADING_ACTIVE
    push_event('info', f"Bot toggled → {'ACTIVE' if AUTO_TRADING_ACTIVE else 'STANDBY'}")
    return jsonify({'ok': True, 'state': AUTO_TRADING_ACTIVE})


@app.route('/api/summary')
def summary():
    data = build_summary()
    if 'error' in data:
        return jsonify(data), 500
    return jsonify(data)


@app.route('/api/cancel_all', methods=['POST'])
def cancel_all():
    global BOT_HISTORY
    if LIVE_ENABLED:
        try:
            cancel_all_orders()
            BOT_HISTORY.insert(0, {
                'time': datetime.datetime.now().strftime('%H:%M'),
                'sym': 'ALL',
                'type': 'CANCEL',
                'price': 0,
                'reason': 'Manual cancel',
            })
            push_event('order', 'All orders cancelled')
            return jsonify({'ok': True})
        except Exception:
            pass
    return jsonify({'ok': False, 'error': 'No activo'})


@app.route('/api/test_alpaca')
def test_alpaca():
    from trading_bot.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL
    res = {
        'key_present': bool(ALPACA_API_KEY),
        'secret_present': bool(ALPACA_SECRET_KEY),
        'base_url': ALPACA_BASE_URL,
        'key_start': ALPACA_API_KEY[:5] if ALPACA_API_KEY else 'N/A',
        'status': 'UNKNOWN',
        'error': None,
    }
    try:
        from trading_bot.ejecucion.alpaca_orders import _get_api
        api = _get_api()
        acc = api.get_account()
        res['status'] = 'CONNECTED'
        res['equity'] = float(acc.equity)
    except Exception as e:
        res['status'] = 'FAILED'
        res['error'] = str(e)
    return jsonify(res)


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════════════════════
# Start trading loop in daemon thread
threading.Thread(target=trading_loop, daemon=True, name='TradingLoop').start()
# Start WebSocket data emitter in daemon thread
threading.Thread(target=ws_data_emitter, daemon=True, name='WSEmitter').start()

if __name__ == '__main__':
    logger.info("🚀 Mera Victorino Pro v3.0 starting...")
    logger.info(f"   Provider: {'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()}")
    logger.info(f"   Live: {LIVE_ENABLED}")
    logger.info(f"   WebSocket: enabled")
    socketio.run(app, host='0.0.0.0', port=7860, debug=False, allow_unsafe_werkzeug=True)