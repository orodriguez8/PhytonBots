
import time
import datetime
import traceback
from src.core.logger import logger
from src.utils.helpers import safe_float
from src.bot.trading_bot import TradingBot
from src.bot.analyzer_crypto import CryptoAnalyzer
from src.core.config import (
    CAPITAL_INICIAL, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS, WATCHLIST,
    TRADING_MODE_CRYPTO, ALPACA_API_KEY, ALPACA_SECRET_KEY,
    CCXT_API_KEY, CCXT_EXCHANGE_ID, BOT_PASSWORD
)
from src.core.health import get_circuit_breaker_status
from src.risk.management import calcular_gestion_riesgo


# Providers and wrappers
from src.execution import alpaca_client, ccxt_client
from src.data import alpaca, ccxt

PROVIDER = (TRADING_MODE_CRYPTO or 'ALPACA').upper()
IS_ALPACA = PROVIDER == 'ALPACA'
LIVE_ENABLED = bool(ALPACA_API_KEY and ALPACA_SECRET_KEY) if IS_ALPACA else bool(CCXT_API_KEY)

# ── Dynamic State (Shared via references or simple instance) ─────────────────
class TradingState:
    AUTO_TRADING_ACTIVE = False
    BOT_HISTORY = []
    LAST_RUN_LOG = {}
    CONSOLE_EVENTS = []
    MAX_CONSOLE = 60

state = TradingState()

# ── Cache para posiciones cerradas (evita spam a la API de Alpaca) ────────────
_closed_cache = []
_closed_cache_ts = 0.0
CLOSED_CACHE_TTL = 60  # segundos

def _get_closed_cached():
    """Devuelve posiciones cerradas usando caché TTL para no sobrecargar la API de Alpaca."""
    global _closed_cache, _closed_cache_ts
    now = time.time()
    if now - _closed_cache_ts > CLOSED_CACHE_TTL:
        _closed_cache = get_closed_positions()
        _closed_cache_ts = now
    return _closed_cache

def push_event(etype, msg, socketio=None):
    """Push an event to the console log and broadcast via WebSocket."""
    evt = {
        'type': etype,
        'msg': msg,
        'time': datetime.datetime.now().strftime('%H:%M:%S'),
    }
    state.CONSOLE_EVENTS.insert(0, evt)
    if len(state.CONSOLE_EVENTS) > state.MAX_CONSOLE:
        state.CONSOLE_EVENTS.pop()
    
    if socketio:
        try:
            socketio.emit('console_event', evt)
        except Exception:
            pass

def get_data(symbol):
    if not LIVE_ENABLED: return None
    return alpaca.obtener_datos_alpaca(symbol) if IS_ALPACA else ccxt.obtener_datos_ccxt(symbol)

def get_account():
    if not LIVE_ENABLED: return None
    return alpaca_client.obtener_cuenta() if IS_ALPACA else ccxt_client.obtener_cuenta_ccxt()

def get_positions():
    if not LIVE_ENABLED: return []
    return alpaca_client.obtener_posiciones_abiertas() if IS_ALPACA else ccxt_client.obtener_posiciones_abiertas_ccxt()

def get_orders():
    if not LIVE_ENABLED: return []
    return alpaca_client.obtener_ordenes_activas() if IS_ALPACA else []

def get_closed_positions():
    if not LIVE_ENABLED: return []
    return alpaca_client.obtener_posiciones_cerradas() if IS_ALPACA else []

def place_order(symbol, qty, side, tp=None, sl=None):
    if not LIVE_ENABLED: return None
    if IS_ALPACA:
        return alpaca_client.colocar_orden_mercado(symbol, qty, side, tp, sl)
    return ccxt_client.colocar_orden_mercado_ccxt(symbol, qty, side)

def cancel_all_orders():
    if not LIVE_ENABLED: return False
    return alpaca_client.cancelar_todas_las_ordenes() if IS_ALPACA else ccxt_client.cancelar_todas_las_ordenes_ccxt()

def cancel_orders_for_symbol(symbol):
    """Cancela órdenes específicamente para un símbolo antes de cerrar posición."""
    if not IS_ALPACA or not LIVE_ENABLED: return
    try:
        api = alpaca_client._get_api()
        norm_sym = symbol.replace('/', '').upper()
        orders = api.list_orders(status='open', symbols=[norm_sym])
        for o in orders:
            api.cancel_order(o.id)
            logger.info(f"Canceled pending order {o.id} for {symbol} before closing.")
        time.sleep(0.5) # Give Alpaca a moment to process the cancellations
    except Exception as e:
        logger.error(f"Error canceling orders for {symbol}: {e}")


def build_summary():
    """Build the full dashboard data payload (used by both HTTP and WS)."""
    try:
        active_mode = 'ALPACA' if IS_ALPACA else (CCXT_EXCHANGE_ID.upper() if CCXT_EXCHANGE_ID else 'CCXT')
        data = {
            'mode': active_mode if LIVE_ENABLED else 'SIM',
            'auto': state.AUTO_TRADING_ACTIVE,
            'summary': state.LAST_RUN_LOG,
            'history': state.BOT_HISTORY,
            'equity': 10000.0,
            'bp': 10000.0,
            'pl': 0.0,
            'day_pl': 0.0,
            'pl_crypto': 0.0,
            'pl_stocks': 0.0,
            'pl_crypto_realized': 0.0,
            'pl_stocks_realized': 0.0,
            'pos': [],
            'closed': [],
            'orders': [],
            'security_enabled': bool(BOT_PASSWORD),
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
                    'v': safe_float(p.get('valor_total', 0)),
                    't': p.get('fecha_entrada', None)
                } for p in raw_pos]

                total_open_pl = sum(p['p'] for p in data['pos'])
                data['pl'] = safe_float(total_open_pl)

                data['orders'] = get_orders()

        # ── Desglose P/L: Crypto vs Acciones ──────────────────────────────────
        def _is_crypto(sym):
            return any(q in str(sym).upper() for q in ['USD', 'USDT', 'USDC', '/'])

        data['pl_crypto'] = safe_float(sum(p['p'] for p in data['pos'] if _is_crypto(p['s'])))
        data['pl_stocks'] = safe_float(sum(p['p'] for p in data['pos'] if not _is_crypto(p['s'])))

        # Cargar posiciones cerradas (si hay keys configuradas)
        if LIVE_ENABLED:
            data['closed'] = _get_closed_cached()

        cl = data.get('closed', [])
        data['pl_crypto_realized'] = safe_float(sum((c.get('pl') or 0) for c in cl if _is_crypto(c['s']) and c.get('pl') is not None))
        data['pl_stocks_realized'] = safe_float(sum((c.get('pl') or 0) for c in cl if not _is_crypto(c['s']) and c.get('pl') is not None))


        return data
    except Exception as e:
        logger.error(f"Error building summary: {traceback.format_exc()}")
        return {'error': str(e)}

def trading_loop(socketio=None):
    """Main trading loop (runs in background thread)"""
    while True:
        if state.AUTO_TRADING_ACTIVE:
            real_equity = CAPITAL_INICIAL
            buying_power = real_equity
            positions_list = []

            if LIVE_ENABLED:
                acc = get_account()
                if acc:
                    real_equity = float(acc.get('nav', real_equity))
                    buying_power = float(acc.get('margen_libre', real_equity))
                positions_list = get_positions()

            # Check Circuit Breaker
            if not IS_ALPACA and get_circuit_breaker_status():
                logger.warning("📉 CIRCUIT BREAKER activo. Saltando ciclo para evitar spam.")
                push_event('warn', "Circuit Breaker Active: Skipping cycle to prevent spam", socketio)
                time.sleep(60)
                continue

            logger.info(f"--- 🌀 CICLO: Equity ${real_equity} | BP ${buying_power} | Posiciones: {len(positions_list)} ---")
            push_event('info', f"Cycle: Equity ${real_equity:,.2f} | BP ${buying_power:,.2f} | {len(positions_list)} pos", socketio)

            for symbol in WATCHLIST:
                try:
                    is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])
                    
                    datos = get_data(symbol)
                    if datos is None or datos.empty:
                        logger.warning(f"⚠️ {symbol}: Sin datos, saltando.")
                        push_event('warn', f"{symbol}: No data, skipping", socketio)
                        continue

                    # Unificamos todo bajo el mismo TradingBot (que ya tiene logica separada interna)
                    bot = TradingBot(datos, real_equity, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS, is_crypto=is_crypto)
                    bot.ejecutar()
                    dec = bot.decision
                    dir_ = dec['direccion']
                    reason = dec['razon']
                    
                    state.LAST_RUN_LOG[symbol] = {
                        'time': datetime.datetime.now().isoformat(),
                        'dir': dir_,
                        'reason': reason,
                    }
                    price = float(datos['close'].iloc[-1])


                    norm_sym = symbol.replace('/', '').upper()
                    current_pos = next(
                        (p for p in positions_list if p['instrumento'].replace('/', '').upper() == norm_sym),
                        None
                    )

                    if LIVE_ENABLED:
                        # 1. Pending Order Check (Critical to prevent spam)
                        all_pending = get_orders()
                        has_pending = any(o['symbol'].upper() == norm_sym for o in all_pending)
                        
                        if has_pending:
                            logger.warning(f"⚠️ {symbol}: Skip cycle, order already pending.")
                            continue

                        # 2. Position Handling
                        if current_pos:
                            is_long = current_pos['direccion'] == 'LONG'
                            entry_p = float(current_pos['precio_medio'])
                            atr_v = float(bot.indicadores['atr'].iloc[-1])

                            # SL/TP Check
                            ges_tmp = calcular_gestion_riesgo(current_pos['direccion'], entry_p, atr_v, is_crypto=is_crypto)
                            sl_hit = False
                            tp_hit = False
                            
                            if ges_tmp:
                                if is_long:
                                    if price <= ges_tmp['stop_loss']: sl_hit = True
                                    if price >= ges_tmp['take_profit']: tp_hit = True
                                else: # SHORT
                                    if price >= ges_tmp['stop_loss']: sl_hit = True
                                    if price <= ges_tmp['take_profit']: tp_hit = True

                            signal_close = (dir_ in ['NEUTRAL', 'NO_TRADE']) or \
                                           (is_long and dir_ == 'SHORT') or \
                                           (not is_long and dir_ == 'LONG')

                            if signal_close or sl_hit or tp_hit:
                                reason_close = f"Signal {dir_}"
                                if sl_hit: reason_close = "STOP LOSS HIT"
                                if tp_hit: reason_close = "TAKE PROFIT HIT"

                                logger.info(f"🛑 Closing {symbol}: {reason_close}")
                                push_event('order', f"Closing {symbol} ({reason_close})", socketio)
                                
                                try:
                                    if IS_ALPACA:
                                        cancel_orders_for_symbol(symbol)
                                        alpaca_client.cerrar_posicion(symbol)
                                    else:
                                        place_order(symbol, current_pos['unidades'], 'sell' if is_long else 'buy')
                                    
                                    state.BOT_HISTORY.insert(0, {
                                        'time': datetime.datetime.now().isoformat(),
                                        'sym': symbol, 'type': 'CLOSE', 'price': price, 'reason': reason_close
                                    })
                                except Exception as e_c:
                                    logger.error(f"Error closing {symbol}: {e_c}")

                        # 3. New Entry Handling
                        elif dir_ in ['LONG', 'SHORT']:
                            if dir_ == 'SHORT' and IS_ALPACA and is_crypto:
                                logger.warning(f"⚠️ SHORT ignored for {symbol} (Alpaca Crypto)")
                                continue

                            side = 'buy' if dir_ == 'LONG' else 'sell'
                            ges = dec.get('gestion', {})
                            raw_qty = float(ges.get('tamano_posicion', 0))
                            sl = ges.get('stop_loss')
                            tp = ges.get('take_profit')

                            # Limit to 10% equity per trade
                            max_val = buying_power * 0.10
                            if (raw_qty * price) > max_val:
                                raw_qty = max_val / price

                            qty = int(raw_qty) if (IS_ALPACA and dir_ == 'SHORT') else round(raw_qty, 4)

                            if qty > 0:
                                try:
                                    logger.info(f"🚀 Opening {dir_} for {symbol} x{qty}")
                                    push_event('order', f"Opening {dir_} {symbol} x{qty}", socketio)
                                    place_order(symbol, qty, side, tp=tp, sl=sl)
                                    state.BOT_HISTORY.insert(0, {
                                        'time': datetime.datetime.now().isoformat(),
                                        'sym': symbol, 'type': f"OPEN {dir_}", 'price': price, 'reason': 'Strategy executed'
                                    })
                                    buying_power -= (qty * price)
                                except Exception as e_o:
                                    logger.error(f"Order failed for {symbol}: {e_o}")
                                    push_event('error', f"Order failed {symbol}: {e_o}", socketio)

                    # 4. History Update (Scans)
                    if dir_ not in ['NEUTRAL', 'NO_TRADE']:
                        state.BOT_HISTORY.insert(0, {
                            'time': datetime.datetime.now().isoformat(),
                            'sym': symbol, 'type': f"{dir_}", 'price': price, 'reason': reason
                        })

                    if len(state.BOT_HISTORY) > 100:
                        state.BOT_HISTORY.pop()

                except Exception as e:
                    logger.error(f"Error {symbol}: {e}")
                    push_event('error', f"Error processing {symbol}: {e}", socketio)

            time.sleep(30)
        else:
            time.sleep(1) # Check toggle state more frequently
