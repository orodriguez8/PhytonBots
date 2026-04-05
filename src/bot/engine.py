
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
    CCXT_API_KEY, CCXT_EXCHANGE_ID
)

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

            logger.info(f"--- 🌀 CICLO: Equity ${real_equity} | BP ${buying_power} | Posiciones: {len(positions_list)} ---")
            push_event('info', f"Cycle: Equity ${real_equity:,.2f} | BP ${buying_power:,.2f} | {len(positions_list)} pos", socketio)

            for symbol in WATCHLIST:
                try:
                    is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])
                    
                    if is_crypto:
                        analyzer = CryptoAnalyzer(symbol, real_equity, RIESGO_POR_OPERACION)
                        analysis_res = analyzer.analyze()
                        dir_ = analysis_res['signal']
                        reason = analysis_res['key_reasons'][0] if analysis_res['key_reasons'] else "No trade"
                        
                        # Normalize for dashboard
                        analysis_res['dir'] = dir_
                        analysis_res['time'] = datetime.datetime.now().strftime('%H:%M:%S')
                        state.LAST_RUN_LOG[symbol] = analysis_res
                        logger.info(f"🔍 ANALYSIS {symbol}: {dir_} (Score: {analysis_res['confidence_score']})")
                        
                        price = analysis_res['entry_price']
                        if price <= 0:
                            datos = get_data(symbol)
                            if datos is not None and not datos.empty:
                                price = float(datos['close'].iloc[-1])
                    else:
                        datos = get_data(symbol)
                        if datos is None or datos.empty:
                            logger.warning(f"⚠️ {symbol}: Sin datos, saltando.")
                            push_event('warn', f"{symbol}: No data, skipping", socketio)
                            continue

                        bot = TradingBot(datos, real_equity, RIESGO_POR_OPERACION, MIN_CONFLUENCIAS)
                        bot.ejecutar()
                        dec = bot.decision
                        dir_ = dec['direccion']
                        reason = dec['razon']
                        state.LAST_RUN_LOG[symbol] = {
                            'time': datetime.datetime.now().strftime('%H:%M:%S'),
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
                        if current_pos:
                            is_long = current_pos['direccion'] == 'LONG'
                            should_close = (
                                (dir_ in ['NEUTRAL', 'NO_TRADE'])
                                or (is_long and dir_ == 'SHORT')
                                or (not is_long and dir_ == 'LONG')
                            )

                            if should_close:
                                market_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
                                logger.info(f"🛑 CERRANDO {symbol} en {market_name}")
                                push_event('order', f"CLOSING {symbol} on {market_name}", socketio)
                                side_close = 'sell' if is_long else 'buy'
                                place_order(symbol, current_pos['unidades'], side_close)
                                state.BOT_HISTORY.insert(0, {
                                    'time': datetime.datetime.now().strftime('%d/%m %H:%M'),
                                    'sym': symbol,
                                    'type': 'CLOSE',
                                    'price': safe_float(price),
                                    'reason': f"Signal {dir_}",
                                })

                        elif dir_ == 'LONG':
                            side = 'buy'
                            if is_crypto:
                                raw_qty = (real_equity * (analysis_res['position_size_pct'] / 100)) / price
                                sl = analysis_res['stop_loss']
                                tp = analysis_res['take_profit_1']
                            else:
                                ges = dec.get('gestion', {})
                                raw_qty = float(ges.get('tamano_posicion', 0))
                                sl = ges.get('stop_loss')
                                tp = ges.get('take_profit')

                            safe_bp_cap = buying_power * 0.10
                            if (raw_qty * price) > safe_bp_cap:
                                raw_qty = safe_bp_cap / price

                            qty = round(raw_qty, 4)
                            if qty > 0:
                                try:
                                    market_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
                                    logger.info(f"🚀 ABRIENDO: {symbol} x{qty} {side.upper()} en {market_name} (SL: {sl}, TP: {tp})")
                                    push_event('order', f"OPENING {symbol} x{qty} {side.upper()} on {market_name}", socketio)
                                    place_order(symbol, qty, side, tp=tp, sl=sl)
                                    state.BOT_HISTORY.insert(0, {
                                        'time': datetime.datetime.now().strftime('%d/%m %H:%M'),
                                        'sym': symbol,
                                        'type': f"OPEN {dir_}",
                                        'price': safe_float(price),
                                        'reason': 'Executed',
                                    })
                                    buying_power -= (qty * price)
                                except Exception as e_order:
                                    market_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
                                    logger.error(f"❌ Error {market_name} {symbol}: {e_order}")
                                    push_event('error', f"Order failed {symbol}: {e_order}", socketio)

                    elif dir_ != 'NEUTRAL':
                        hist_type = f"{dir_}" if LIVE_ENABLED else f"SIM {dir_}"
                        state.BOT_HISTORY.insert(0, {
                            'time': datetime.datetime.now().strftime('%d/%m %H:%M'),
                            'sym': symbol,
                            'type': hist_type,
                            'price': safe_float(price),
                            'reason': reason,
                        })

                    if len(state.BOT_HISTORY) > 20:
                        state.BOT_HISTORY.pop()

                except Exception as e:
                    logger.error(f"Error {symbol}: {e}")
                    push_event('error', f"Error processing {symbol}: {e}", socketio)

            time.sleep(60)
        else:
            time.sleep(1) # Check toggle state more frequently
