
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
                    'v': safe_float(p.get('valor_total', 0)),
                    't': p.get('fecha_entrada', None)
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
                        if current_pos:
                            is_long = current_pos['direccion'] == 'LONG'
                            entry_price = float(current_pos['precio_medio'])
                            atr_val = float(bot.indicadores['atr'].iloc[-1])

                            # Synthetic SL/TP Check
                            tmp_gestion = calcular_gestion_riesgo(
                                current_pos['direccion'], entry_price, atr_val, 
                                is_crypto=is_crypto
                            )
                            sl_hit = False
                            tp_hit = False
                            
                            if tmp_gestion:
                                sl_price = tmp_gestion.get('stop_loss')
                                tp_price = tmp_gestion.get('take_profit')
                                if is_long:
                                    if price <= sl_price: sl_hit = True
                                    if price >= tp_price: tp_hit = True
                                else: # SHORT
                                    if price >= sl_price: sl_hit = True
                                    if price <= tp_price: tp_hit = True

                            signal_close = (
                                (dir_ in ['NEUTRAL', 'NO_TRADE'])
                                or (is_long and dir_ == 'SHORT')
                                or (not is_long and dir_ == 'LONG')
                            )

                            should_close = signal_close or sl_hit or tp_hit

                            if should_close:
                                market_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
                                reason_close = f"Signal {dir_}"
                                if sl_hit: reason_close = "STOP LOSS HIT"
                                if tp_hit: reason_close = "TAKE PROFIT HIT"

                                logger.info(f"🛑 CERRANDO {symbol} ({reason_close}) en {market_name}")
                                push_event('order', f"CLOSING {symbol} ({reason_close}) on {market_name}", socketio)
                                
                                try:
                                    if IS_ALPACA:
                                        # Cancelar órdenes primero para evitar "insufficient qty"
                                        cancel_orders_for_symbol(symbol)
                                        alpaca_client.cerrar_posicion(symbol)
                                    else:
                                        side_close = 'sell' if is_long else 'buy'
                                        place_order(symbol, current_pos['unidades'], side_close)
                                except Exception as e_close:
                                    logger.error(f"Error cerrando {symbol}: {e_close}")
                                    push_event('error', f"Error processing {symbol}: {e_close}", socketio)

                                state.BOT_HISTORY.insert(0, {
                                    'time': datetime.datetime.now().isoformat(),
                                    'sym': symbol,
                                    'type': 'CLOSE',
                                    'price': safe_float(price),
                                    'reason': reason_close,
                                })

                        elif dir_ == 'LONG':
                            side = 'buy'
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
                                        'time': datetime.datetime.now().isoformat(),
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
                        elif dir_ == 'SHORT':
                            if IS_ALPACA and is_crypto:
                                logger.warning(f"⚠️ SHORT ignored for {symbol}: Alpaca does not support crypto shorting.")
                                push_event('warn', f"Short ignored: {symbol} (Alpaca Crypto)", socketio)
                                side = None
                            else:
                                side = 'sell'
                                ges = dec.get('gestion', {})
                                raw_qty = float(ges.get('tamano_posicion', 0))
                                sl = ges.get('stop_loss')
                                tp = ges.get('take_profit')

                                # BP check for shorting
                                safe_bp_cap = buying_power * 0.10
                                if (raw_qty * price) > safe_bp_cap:
                                    raw_qty = safe_bp_cap / price

                                # Force whole shares for shorting in Alpaca (to avoid error)
                                if IS_ALPACA:
                                    qty = int(raw_qty)
                                else:
                                    qty = round(raw_qty, 4)

                                if qty > 0 and side:
                                    try:
                                        market_name = 'ALPACA' if IS_ALPACA else CCXT_EXCHANGE_ID.upper()
                                        logger.info(f"🚀 ABRIENDO SHORT: {symbol} x{qty} en {market_name} (SL: {sl}, TP: {tp})")
                                        push_event('order', f"OPENING SHORT {symbol} x{qty} on {market_name}", socketio)
                                        place_order(symbol, qty, side, tp=tp, sl=sl)
                                        state.BOT_HISTORY.insert(0, {
                                            'time': datetime.datetime.now().isoformat(),
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

                    # History Logging (record the scan result if no order was just placed)
                    # We check if the last item is already this symbol/time to avoid duplicates
                    if dir_ not in ['NEUTRAL', 'NO_TRADE']:
                        hist_type = f"{dir_}" if LIVE_ENABLED else f"SIM {dir_}"
                        state.BOT_HISTORY.insert(0, {
                            'time': datetime.datetime.now().isoformat(),
                            'sym': symbol,
                            'type': hist_type,
                            'price': safe_float(price),
                            'reason': reason,
                        })

                    if len(state.BOT_HISTORY) > 100:
                        state.BOT_HISTORY.pop()

                except Exception as e:
                    logger.error(f"Error {symbol}: {e}")
                    push_event('error', f"Error processing {symbol}: {e}", socketio)

            time.sleep(30)
        else:
            time.sleep(1) # Check toggle state more frequently
