import time
import datetime
from datetime import timezone
import traceback
import threading
from src.core.logger import logger
from src.utils.helpers import safe_float
from src.bot.trading_bot import TradingBot
from src.bot.analyzer_crypto import CryptoAnalyzer
from src.core.config import (
    CAPITAL_INICIAL, RIESGO_POR_OPERACION, RIESGO_CRYPTO, MIN_CONFLUENCIAS, WATCHLIST,
    TRADING_MODE_CRYPTO, ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER,
    CCXT_API_KEY, CCXT_EXCHANGE_ID, BOT_PASSWORD, CRYPTO_TRADING_ENABLED
)
from src.core.health import get_circuit_breaker_status
from src.risk.management import calcular_gestion_riesgo


# Providers and wrappers
from src.execution import alpaca_client, ccxt_client, alpaca_stream
from src.data import alpaca, ccxt, alpaca_data_stream

PROVIDER = (TRADING_MODE_CRYPTO or 'ALPACA').upper()
IS_ALPACA = PROVIDER == 'ALPACA'
LIVE_ENABLED = bool(ALPACA_API_KEY and ALPACA_SECRET_KEY) if IS_ALPACA else bool(CCXT_API_KEY)

# ── Dynamic State (Shared via references or simple instance) ─────────────────
import multiprocessing

# ── Dynamic State (Shared via multiprocessing to ensure consistency) ─────────
class TradingState:
    def __init__(self):
        self._active = multiprocessing.Value('b', False)
        self.BOT_HISTORY = []
        self.LAST_RUN_LOG = {}
        self.CONSOLE_EVENTS = []
        self.MAX_CONSOLE = 60
        self.LOCK = threading.Lock()

    @property
    def AUTO_TRADING_ACTIVE(self):
        return bool(self._active.value)

    @AUTO_TRADING_ACTIVE.setter
    def AUTO_TRADING_ACTIVE(self, value):
        self._active.value = bool(value)

state = TradingState()

# ── Cache para historial (evita spam a la API de Alpaca) ───────────
_closed_cache = {'closed': [], 'opened': []}
_closed_cache_ts = 0.0
CLOSED_CACHE_TTL = 60  # segundos

def _get_closed_cached():
    """Devuelve historial usando caché TTL para no sobrecargar la API de Alpaca."""
    global _closed_cache, _closed_cache_ts
    now = time.time()
    
    # Si la caché está vacía o ha expirado, intentar actualizarla
    if not _closed_cache['closed'] or (now - _closed_cache_ts > CLOSED_CACHE_TTL):
        try:
            newData = get_closed_positions()
            if newData and (newData.get('closed') or newData.get('opened')):
                _closed_cache = newData
                _closed_cache_ts = now
        except Exception as e:
            logger.debug(f"Error actualizando caché de historial: {e}")
            
    return _closed_cache


def push_event(etype, msg, socketio=None):
    """Push an event to the console log and broadcast via WebSocket."""
    evt = {
        'type': etype,
        'msg': msg,
        'time': datetime.datetime.now().strftime('%H:%M:%S'),
    }
    with state.LOCK:
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
    alpaca_client.cancelar_ordenes_por_simbolo(symbol)
    time.sleep(0.5)


def limpiar_ordenes_atascadas(socketio=None):
    """
    Busca órdenes de Cripto que lleven más de 60 segundos abiertas (atascadas por slippage)
    y las cancela para liberar el bot.
    """
    if not LIVE_ENABLED or not IS_ALPACA: return
    
    try:
        current_orders = get_orders()
        now = datetime.datetime.now(timezone.utc)
        
        for o in current_orders:
            # Solo aplicamos limpieza agresiva a Cripto
            is_crypto = any(q in o['symbol'].upper() for q in ['USD', 'USDT', 'USDC', '/'])
            if not is_crypto: continue
            
            # Parsear fecha de creación (ISO format de Alpaca)
            try:
                created_at = datetime.datetime.fromisoformat(o['created_at'].replace('Z', '+00:00'))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
            except:
                continue
                
            segundos_abierta = (now - created_at).total_seconds()
            
            if segundos_abierta > 60: # 1 minuto máximo para mercado cripto
                logger.info(f"🕒 LIMPIEZA: Cancelando orden atascada de {o['symbol']} ({segundos_abierta:.0f}s abierta)")
                push_event('warn', f"Stale order cleaned: {o['symbol']} ({segundos_abierta:.0f}s)", socketio)
                
                api = alpaca_client._get_api()
                api.cancel_order(o['id'])
    except Exception as e:
        logger.debug(f"Error en limpieza de órdenes: {e}")


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
            'opened': [],
            'orders': [],
            'security_enabled': bool(BOT_PASSWORD),
        }
        if LIVE_ENABLED:
            try:
                acc = get_account()
                if acc:
                    data['equity'] = safe_float(acc.get('nav', 0))
                    data['bp'] = safe_float(acc.get('margen_libre', 0))
                    data['day_pl'] = safe_float(acc.get('pl', 0))
            except Exception as e:
                logger.debug(f"Summary: Error obteniendo cuenta: {e}")

            try:
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
            except Exception as e:
                logger.debug(f"Summary: Error obteniendo posiciones: {e}")

            data['pl'] = safe_float(sum(p['p'] for p in data['pos']))
            
            try:
                data['orders'] = get_orders()
            except Exception as e:
                logger.debug(f"Summary: Error obteniendo ordenes: {e}")

        # ── Desglose P/L: Crypto vs Acciones ──────────────────────────────────
        def _is_crypto(sym):
            return any(q in str(sym).upper() for q in ['USD', 'USDT', 'USDC', '/'])

        data['pl_crypto'] = safe_float(sum(p['p'] for p in data['pos'] if _is_crypto(p['s'])))
        data['pl_stocks'] = safe_float(sum(p['p'] for p in data['pos'] if not _is_crypto(p['s'])))

        # Cargar historial (si hay keys configuradas)
        if LIVE_ENABLED:
            try:
                hist = _get_closed_cached()
                data['closed'] = hist.get('closed', [])
                data['opened'] = hist.get('opened', [])
            except Exception as e:
                logger.debug(f"Summary: Error obteniendo historial: {e}")

        cl = data.get('closed', [])
        now_dt = datetime.datetime.now(timezone.utc)
        today_str = now_dt.strftime('%Y-%m-%d')
        month_str = now_dt.strftime('%Y-%m')

        data['pl_crypto_realized'] = 0.0
        data['pl_stocks_realized'] = 0.0
        data['pl_crypto_daily'] = 0.0
        data['pl_stocks_daily'] = 0.0
        data['pl_crypto_monthly'] = 0.0
        data['pl_stocks_monthly'] = 0.0

        for c in cl:
            pl_val = safe_float(c.get('pl', 0))
            is_cryp = _is_crypto(c['s'])
            
            # Global Realized (from the loaded history)
            if is_cryp:
                data['pl_crypto_realized'] += pl_val
            else:
                data['pl_stocks_realized'] += pl_val

            # Filter by date
            c_time = c.get('time', '')
            if c_time:
                try:
                    # Alpaca time is usually ISO with timezone
                    dt = datetime.datetime.fromisoformat(c_time.replace('Z', '+00:00'))
                    item_day = dt.strftime('%Y-%m-%d')
                    item_month = dt.strftime('%Y-%m')
                    
                    if item_day == today_str:
                        if is_cryp: data['pl_crypto_daily'] += pl_val
                        else: data['pl_stocks_daily'] += pl_val
                    
                    if item_month == month_str:
                        if is_cryp: data['pl_crypto_monthly'] += pl_val
                        else: data['pl_stocks_monthly'] += pl_val
                except:
                    pass


        return data
    except Exception as e:
        logger.error(f"Error building summary: {traceback.format_exc()}")
        return {'error': str(e)}

def trading_loop(socketio=None):
    """Main trading loop (runs in background thread)"""
    
    stream_mgr = None
    # Iniciar stream de eventos (Trade Updates)
    if IS_ALPACA and LIVE_ENABLED:
        try:
            stream_mgr = alpaca_stream.AlpacaTradingStream(state, lambda t, m: push_event(t, m, socketio))
            stream_mgr.start()
        except Exception as e:
            logger.error(f"Error iniciando TradingStream: {e}")

    # Iniciar stream de datos (Precios en tiempo real)
    if IS_ALPACA and LIVE_ENABLED:
        try:
            p_stream = alpaca_data_stream.AlpacaDataStream(WATCHLIST)
            p_stream.start()
        except Exception as e:
            logger.info("⚡ Motor de trading iniciado y esperando señales...")

    while True:
        try:
            # Procesar eventos acumulados del proceso del stream
            if stream_mgr:
                stream_mgr.process_incoming_events()
            
            if not state.AUTO_TRADING_ACTIVE:
                # Latido para confirmar que el hilo no está colgado
                if time.time() % 60 < 1: # Log cada ~60s para no inundar
                     logger.debug("⏳ Motor en standby, esperando activación...")
                time.sleep(1)
                continue

            logger.info("🔍 Ejecutando ciclo de análisis activo...")
            real_equity = CAPITAL_INICIAL
            buying_power = real_equity
            positions_list = []

            if LIVE_ENABLED:
                try:
                    acc = get_account()
                    if acc:
                        real_equity = float(acc.get('nav', real_equity))
                        buying_power = float(acc.get('margen_libre', real_equity))
                    positions_list = get_positions()
                except Exception as e:
                    logger.warning(f"⚠️ Error recuperando info de cuenta (usando fallback): {e}")

                # Limpiar órdenes atascadas antes de procesar las señales
                try:
                    limpiar_ordenes_atascadas(socketio)
                except:
                    pass

                # Check Circuit Breaker
                if not IS_ALPACA and get_circuit_breaker_status():
                    logger.warning("📉 CIRCUIT BREAKER activo. Saltando ciclo para evitar spam.")
                    push_event('warn', "Circuit Breaker Active: Skipping cycle to prevent spam", socketio)
                    time.sleep(60)
                    continue

            # --- Market Hours Check (Only for Alpaca Stocks) ---
            market_is_open = True
            if IS_ALPACA:
                market_is_open = alpaca_client.es_mercado_abierto()

            logger.info(f"--- 🌀 CICLO: Equity ${real_equity} | BP ${buying_power} | Posiciones: {len(positions_list)} | Mercado: {'Abierto' if market_is_open else 'Cerrado'} ---")
            push_event('info', f"Cycle: Equity ${real_equity:,.2f} | BP ${buying_power:,.2f} | {len(positions_list)} pos", socketio)

            for symbol in WATCHLIST:
                try:
                    is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])

                    # Check market hours for stocks
                    if not is_crypto and not market_is_open:
                        continue
                    
                    if is_crypto and not CRYPTO_TRADING_ENABLED:
                        continue
                    
                    try:
                        datos = get_data(symbol)
                    except Exception as e:
                        logger.error(f"❌ Error obteniendo datos para {symbol}: {e}")
                        continue

                    if datos is None or datos.empty:
                        logger.warning(f"⚠️ {symbol}: Sin datos, saltando.")
                        push_event('warn', f"{symbol}: No data, skipping", socketio)
                        continue

                    # Unificamos todo bajo el mismo TradingBot (que ya tiene logica separada interna)
                    riesgo_actual = RIESGO_CRYPTO if is_crypto else RIESGO_POR_OPERACION
                    bot = TradingBot(datos, real_equity, riesgo_actual, MIN_CONFLUENCIAS, is_crypto=is_crypto)
                    bot.ejecutar()
                    dec = bot.decision
                    dir_ = dec['direccion']
                    reason = dec['razon']
                    
                    state.LAST_RUN_LOG[symbol] = {
                        'time': datetime.datetime.now().isoformat(),
                        'dir': dir_,
                        'reason': reason,
                    }
                    # Intentar usar el precio de WebSocket (si está disponible) para mayor precisión
                    ws_price = alpaca_data_stream.get_latest_price(symbol)
                    price = ws_price if ws_price else float(datos['close'].iloc[-1])


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

                            # --- PDT & Safety Check ---
                            if not is_crypto and real_equity < 25000:
                                pdt_count = acc.get('pdt_reset', 0) if acc else 0
                                if pdt_count >= 3:
                                    logger.warning(f"⚠️ {symbol}: BLOQUEO PDT. {pdt_count} day trades detectados con cuenta < $25k. Operación cancelada.")
                                    push_event('warn', f"PDT Limit Warning: {symbol} entry blocked", socketio)
                                    continue

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

                except Exception as e_sym:
                    logger.error(f"Error procesando {symbol}: {e_sym}")

            # Espera entre ciclos completos para no saturar
            time.sleep(30)

        except Exception as e_loop:
            logger.error(f"❌ Error fatal en el bucle principal: {e_loop}")
            time.sleep(5)
