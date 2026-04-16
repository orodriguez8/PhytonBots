import os
import backoff
from datetime import datetime, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOrdersRequest, MarketOrderRequest, LimitOrderRequest, 
    TakeProfitRequest, StopLossRequest, GetPortfolioHistoryRequest,
    ClosePositionRequest
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, AssetClass
from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER, ALPACA_BASE_URL
from src.core.logger import logger

_TRADING_CLIENT = None

def _get_trading_client():
    global _TRADING_CLIENT
    if _TRADING_CLIENT is None:
        _TRADING_CLIENT = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)
    return _TRADING_CLIENT

# Decorador genérico para reintentos en errores de red/SSL
retry_strategy = backoff.on_exception(
    backoff.expo, 
    Exception, 
    max_tries=5, 
    giveup=lambda e: not any(x in str(e) for x in ["429", "SSL", "connection", "ConnectionPool", "Timeout", "unexpected message"])
)

@retry_strategy
def obtener_cuenta():
    """
    Devuelve resumen de la cuenta Alpaca usando alpaca-py.
    """
    try:
        client = _get_trading_client()
        account = client.get_account()
        
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        pl_total = equity - last_equity

        return {
            'id': str(account.id),
            'moneda': account.currency,
            'balance': float(account.cash),
            'nav': equity,
            'pl': pl_total,
            'pl_abierto': float(getattr(account, 'unrealized_pl', 0) or 0),
            'margen_libre': float(account.buying_power),
            'posiciones': 0, 
            'apalancamiento': account.multiplier,
            'pdt_reset': account.daytrade_count,
        }
    except Exception as e:
        logger.error(f"Error en obtener_cuenta: {e}")
        return None

@retry_strategy
def obtener_posiciones_abiertas():
    """
    Devuelve lista de trades abiertos.
    """
    try:
        client = _get_trading_client()
        positions = client.get_all_positions()
        
        res = []
        for p in positions:
            res.append({
                'instrumento': p.symbol,
                'direccion': 'LONG' if float(p.qty) > 0 else 'SHORT',
                'unidades': abs(float(p.qty)),
                'precio_medio': float(p.avg_entry_price),
                'precio_actual': float(p.current_price),
                'pl': float(p.unrealized_pl),
                'pl_pct': float(p.unrealized_plpc) * 100,
                'valor_total': float(p.market_value),
                'fecha_entrada': None
            })
        return res
    except Exception as e:
        logger.error(f"Error en obtener_posiciones: {e}")
        return []

@retry_strategy
def obtener_posiciones_cerradas():
    """
    Obtiene el historial de posiciones cerradas via REST directo.

    NOTA: TradingClient de alpaca-py NO expone get_account_activities().
    Usamos client.get() heredado de RESTClient para llamar directamente
    al endpoint /account/activities/FILL que devuelve una lista de dicts.
    Fallback: órdenes cerradas/ejecutadas vía get_orders(status='closed').
    """
    try:
        client = _get_trading_client()
        raw_activities = []

        # ── Intento 1: REST directo /account/activities/FILL ─────────────────
        try:
            raw_activities = client.get(
                "/account/activities/FILL",
                {"page_size": 100, "direction": "desc"}
            )
            if not isinstance(raw_activities, list):
                raw_activities = []
            logger.debug(f"[FILLS] Recuperados {len(raw_activities)} registros vía REST directo")
        except Exception as e1:
            logger.debug(f"[FILLS] Endpoint directo falló ({e1}), probando fallback...")

            # ── Intento 2: órdenes filled como historial alternativo ──────────
            try:
                req = GetOrdersRequest(status='closed', limit=100)
                orders = client.get_orders(filter=req)
                for o in orders:
                    filled_qty  = float(getattr(o, 'filled_qty', None)  or 0)
                    filled_price = float(getattr(o, 'filled_avg_price', None) or 0)
                    if filled_qty <= 0 or filled_price <= 0:
                        continue
                    side_raw = getattr(o, 'side', None)
                    side_str = side_raw.name if hasattr(side_raw, 'name') else str(side_raw)
                    t_raw = getattr(o, 'filled_at', None) or getattr(o, 'updated_at', None)
                    raw_activities.append({
                        'symbol': o.symbol,
                        'side': side_str,
                        'qty': str(filled_qty),
                        'price': str(filled_price),
                        'transaction_time': t_raw.isoformat() if hasattr(t_raw, 'isoformat') else str(t_raw),
                    })
                logger.debug(f"[FILLS] Fallback órdenes: {len(raw_activities)} registros")
            except Exception as e2:
                logger.warning(f"[FILLS] Ambos métodos fallaron. e1={e1} | e2={e2}")
                raw_activities = []

        # ── Normalizar cada actividad a raw_fills ─────────────────────────────
        raw_fills = []
        for f in raw_activities:
            try:
                # La respuesta de /account/activities es una lista de dicts
                if isinstance(f, dict):
                    s          = f.get('symbol', '')
                    side_val   = str(f.get('side', '')).upper()
                    qty        = float(f.get('qty', 0) or 0)
                    price      = float(f.get('price', 0) or 0)
                    t_raw      = f.get('transaction_time') or f.get('created_at', '')
                else:
                    # Objeto modelo (raro, pero por compatibilidad)
                    s          = getattr(f, 'symbol', '')
                    side_raw   = getattr(f, 'side', '')
                    side_val   = side_raw.name.upper() if hasattr(side_raw, 'name') else str(side_raw).upper()
                    qty        = float(getattr(f, 'qty', 0) or 0)
                    price      = float(getattr(f, 'price', 0) or 0)
                    t_raw      = getattr(f, 'transaction_time', None) or getattr(f, 'filled_at', None)

                if not s or qty <= 0 or price <= 0:
                    continue

                # Normalizar timestamp → datetime con tz
                if isinstance(t_raw, str) and t_raw:
                    t_parsed = datetime.fromisoformat(t_raw.replace('Z', '+00:00'))
                elif hasattr(t_raw, 'isoformat'):
                    t_parsed = t_raw if t_raw.tzinfo else t_raw.replace(tzinfo=timezone.utc)
                else:
                    t_parsed = datetime.now(timezone.utc)

                raw_fills.append({'s': s, 'side': side_val, 'q': qty, 'p': price, 't': t_parsed})
            except (AttributeError, TypeError, ValueError) as e:
                logger.debug(f"[FILLS] Error procesando entrada: {e}")
                continue

        # ── Ordenar cronológicamente (FIFO) ───────────────────────────────────
        raw_fills.sort(key=lambda x: x['t'])
        logger.debug(f"[FILLS] {len(raw_fills)} fills válidos a procesar")

        queues    = {}
        res_closed = []
        res_opened = []

        for f in raw_fills:
            s = f['s']
            if s not in queues:
                queues[s] = {'longs': [], 'shorts': []}

            side        = f['side']
            q_to_process = f['q']
            p_fill       = f['p']
            t_fill       = f['t']

            if side == 'BUY':
                # Cerrar shorts pendientes primero (BUY to COVER)
                while q_to_process > 0 and queues[s]['shorts']:
                    lot     = queues[s]['shorts'][0]
                    match_q = min(q_to_process, lot['q'])
                    pl_unit = lot['p'] - p_fill
                    res_closed.insert(0, {
                        's': s, 'side': 'BUY (COVER)', 'q': round(match_q, 4),
                        'p': round(p_fill, 4), 'entry': round(lot['p'], 4),
                        'pl': round(pl_unit * match_q, 2),
                        'time': t_fill.isoformat()
                    })
                    q_to_process -= match_q
                    lot['q']     -= match_q
                    if lot['q'] <= 1e-8:
                        queues[s]['shorts'].pop(0)

                if q_to_process > 0:
                    queues[s]['longs'].append({'q': q_to_process, 'p': p_fill, 't': t_fill})
                    res_opened.insert(0, {
                        's': s, 'side': 'BUY (OPEN)', 'q': round(q_to_process, 4),
                        'p': round(p_fill, 4), 'time': t_fill.isoformat()
                    })

            elif side in ['SELL', 'SELL_SHORT']:
                # Cerrar longs pendientes primero
                while q_to_process > 0 and queues[s]['longs']:
                    lot     = queues[s]['longs'][0]
                    match_q = min(q_to_process, lot['q'])
                    pl_unit = p_fill - lot['p']
                    res_closed.insert(0, {
                        's': s, 'side': 'SELL', 'q': round(match_q, 4),
                        'p': round(p_fill, 4), 'entry': round(lot['p'], 4),
                        'pl': round(pl_unit * match_q, 2),
                        'time': t_fill.isoformat()
                    })
                    q_to_process -= match_q
                    lot['q']     -= match_q
                    if lot['q'] <= 1e-8:
                        queues[s]['longs'].pop(0)

                if q_to_process > 0:
                    queues[s]['shorts'].append({'q': q_to_process, 'p': p_fill, 't': t_fill})
                    res_opened.insert(0, {
                        's': s, 'side': side, 'q': round(q_to_process, 4),
                        'p': round(p_fill, 4), 'time': t_fill.isoformat()
                    })

        logger.info(f"[FILLS] Resultado: {len(res_closed)} cerradas, {len(res_opened)} abiertas")
        return {'closed': res_closed, 'opened': res_opened}
    except Exception as e:
        logger.error(f"ERROR en obtener_posiciones_cerradas: {e}")
        return {'closed': [], 'opened': []}

@retry_strategy
def obtener_ordenes_activas():
    try:
        client = _get_trading_client()
        req = GetOrdersRequest(status='open', limit=50)
        orders = client.get_orders(filter=req)
        return [{
            'id': str(o.id),
            'symbol': o.symbol,
            'qty': o.qty,
            'side': o.side.name,
            'type': o.order_type.name,
            'status': o.status.name,
            'created_at': o.created_at.isoformat()
        } for o in orders]
    except Exception as e:
        logger.error(f"Error en obtener_ordenes: {e}")
        return []

@retry_strategy
def cancelar_ordenes_por_simbolo(symbol):
    try:
        client = _get_trading_client()
        norm_sym = symbol.replace('/', '').upper()
        req = GetOrdersRequest(status='open', symbols=[norm_sym])
        orders = client.get_orders(filter=req)
        for o in orders:
            client.cancel_order_by_id(o.id)
        return True
    except Exception as e:
        logger.error(f"Error cancelando órdenes para {symbol}: {e}")
        return False

@retry_strategy
def cancelar_todas_las_ordenes():
    try:
        client = _get_trading_client()
        client.cancel_orders()
        return True
    except Exception as e:
        logger.error(f"Error cancelando órdenes: {e}")
        return False

@retry_strategy
def colocar_orden_mercado(symbol, qty, side, take_profit=None, stop_loss=None):
    try:
        client = _get_trading_client()
        norm_sym = symbol.replace('/', '').upper()
        is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])
        
        # Fractional check
        is_fractional = float(qty) != int(float(qty))
        tif = TimeInForce.DAY if (is_fractional and not is_crypto) else TimeInForce.GTC
        
        order_class = OrderClass.SIMPLE
        tp_data = None
        sl_data = None
        
        if (take_profit or stop_loss) and not is_crypto and not is_fractional:
            order_class = OrderClass.BRACKET
            if take_profit:
                tp_data = TakeProfitRequest(limit_price=round(float(take_profit), 2))
            if stop_loss:
                sl_data = StopLossRequest(stop_price=round(float(stop_loss), 2))

        req = MarketOrderRequest(
            symbol=norm_sym,
            qty=qty,
            side=OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL,
            time_in_force=tif,
            order_class=order_class,
            take_profit=tp_data,
            stop_loss=sl_data
        )

        order = client.submit_order(order_data=req)
        return order
    except Exception as e:
        logger.error(f"Error colocando orden en {symbol}: {e}")
        raise e

@retry_strategy
def cerrar_posicion(symbol):
    try:
        client = _get_trading_client()
        norm_sym = symbol.replace('/', '').upper()
        return client.close_position(norm_sym)
    except Exception as e:
        logger.error(f"Error cerrando posición en {symbol}: {e}")
        raise e

@retry_strategy
def obtener_historial_cartera(periodo='1M', timeframe='1D'):
    try:
        client = _get_trading_client()
        req = GetPortfolioHistoryRequest(period=periodo, timeframe=timeframe)
        
        # Multi-version compatibility
        try:
            hist = client.get_portfolio_history(req)
        except Exception:
            try:
                hist = client.get_portfolio_history(filter=req)
            except:
                hist = client.get_portfolio_history(filter_data=req)
        
        res = []
        for i in range(len(hist.timestamp)):
            res.append({
                'time': hist.timestamp[i],
                'value': float(hist.equity[i])
            })
        return res
    except Exception as e:
        logger.error(f"Error en obtener_historial_cartera: {e}")
        return []

@retry_strategy
def es_mercado_abierto():
    try:
        client = _get_trading_client()
        clock = client.get_clock()
        return clock.is_open
    except Exception as e:
        logger.debug(f"Error comprobando reloj del mercado: {e}")
        return True
