
import os
import backoff
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, AssetClass, TradeActivityType
from alpaca.trading.requests import GetOrderByIdRequest, ClosePositionRequest, GetPortfolioHistoryRequest
# Import dinámico para evitar fallos de versión
ActivitiesRequestClass = None
import alpaca.trading.requests as alp_req
for item in dir(alp_req):
    if "Activity" in item:
        ActivitiesRequestClass = getattr(alp_req, item)
        break

from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER, ALPACA_BASE_URL
from src.core.logger import logger

_TRADING_CLIENT = None

def _get_trading_client():
    global _TRADING_CLIENT
    if _TRADING_CLIENT is None:
        _TRADING_CLIENT = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)
    return _TRADING_CLIENT

@backoff.on_exception(backoff.expo, Exception, max_tries=5, giveup=lambda e: not any(x in str(e) for x in ["429", "SSL", "connection", "ConnectionPool", "Timeout"]))
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
            'pdt_reset': account.daytrade_count, # Útil para controlar PDT
        }
    except Exception as e:
        logger.error(f"Error en obtener_cuenta: {e}")
        return None

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
                'fecha_entrada': None # alpaca-py position object doesn't have entry time directly
            })
        return res
    except Exception as e:
        logger.error(f"Error en obtener_posiciones: {e}")
        return []

def obtener_posiciones_cerradas():
    """
    Obtiene el historial de posiciones cerradas usando actividades de trade.
    """
    try:
        from dateutil import parser
        client = _get_trading_client()
        
        # Obtenemos actividades de tipo FILL (ejecuciones)
        activities = []
        try:
            # Intentar métodos comunes según versión de SDK
            if hasattr(client, 'get_account_activities'):
                req = ActivitiesRequestClass(activity_types=[TradeActivityType.FILL]) if ActivitiesRequestClass else {"activity_types": "FILL"}
                activities = client.get_account_activities(filter=req) if ActivitiesRequestClass else client.get_account_activities(req)
            elif hasattr(client, 'get_activities'):
                activities = client.get_activities(activity_types="FILL")
        except:
            # Fallback silencioso para no romper el ciclo del bot
            activities = []
        
        raw_fills = []
        for f in activities:
            raw_fills.append({
                's': f.symbol,
                'side': f.side.name if hasattr(f.side, 'name') else str(f.side),
                'q': float(f.qty),
                'p': float(f.price),
                't': f.transaction_time
            })
        
        # Ordenar cronológicamente para el proceso FIFO
        raw_fills.sort(key=lambda x: x['t'])

        queues = {}
        res_closed = []
        res_opened = []

        for f in raw_fills:
            s = f['s']
            if s not in queues:
                queues[s] = {'longs': [], 'shorts': []}
            
            side = f['side'].upper()
            q_to_process = f['q']
            p_fill = f['p']
            t_fill = f['t']

            if side == 'BUY':
                while q_to_process > 0 and queues[s]['shorts']:
                    lot = queues[s]['shorts'][0]
                    match_q = min(q_to_process, lot['q'])
                    pl_unit = lot['p'] - p_fill
                    res_closed.append({
                        's': s, 'side': 'BUY (COVER)', 'q': round(match_q, 4),
                        'p': round(p_fill, 4), 'entry': round(lot['p'], 4),
                        'pl': round(pl_unit * match_q, 2), 'time': t_fill.isoformat()
                    })
                    q_to_process -= match_q
                    lot['q'] -= match_q
                    if lot['q'] <= 1e-8: queues[s]['shorts'].pop(0)

                if q_to_process > 0:
                    queues[s]['longs'].append({'q': q_to_process, 'p': p_fill, 't': t_fill})
                    res_opened.append({
                        's': s, 'side': 'BUY', 'q': round(q_to_process, 4),
                        'p': round(p_fill, 4), 'time': t_fill.isoformat()
                    })

            elif side in ['SELL', 'SELL_SHORT']:
                while q_to_process > 0 and queues[s]['longs']:
                    lot = queues[s]['longs'][0]
                    match_q = min(q_to_process, lot['q'])
                    pl_unit = p_fill - lot['p']
                    res_closed.append({
                        's': s, 'side': 'SELL', 'q': round(match_q, 4),
                        'p': round(p_fill, 4), 'entry': round(lot['p'], 4),
                        'pl': round(pl_unit * match_q, 2), 'time': t_fill.isoformat()
                    })
                    q_to_process -= match_q
                    lot['q'] -= match_q
                    if lot['q'] <= 1e-8: queues[s]['longs'].pop(0)

                if q_to_process > 0:
                    queues[s]['shorts'].append({'q': q_to_process, 'p': p_fill, 't': t_fill})
                    res_opened.append({
                        's': s, 'side': side, 'q': round(q_to_process, 4),
                        'p': round(p_fill, 4), 'time': t_fill.isoformat()
                    })

        res_closed.reverse()
        res_opened.reverse()
        return {'closed': res_closed, 'opened': res_opened}
    except Exception as e:
        logger.error(f"ERROR en obtener_posiciones_cerradas: {e}")
        return {'closed': [], 'opened': []}

def obtener_ordenes_activas():
    """
    Devuelve lista de órdenes pendientes usando TradingClient.
    """
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

def cancelar_ordenes_por_simbolo(symbol):
    """
    Cancela todas las órdenes abiertas para un símbolo específico.
    """
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

def cancelar_todas_las_ordenes():
    try:
        client = _get_trading_client()
        client.cancel_orders()
        return True
    except Exception as e:
        logger.error(f"Error cancelando órdenes: {e}")
        return False

def colocar_orden_mercado(symbol, qty, side, take_profit=None, stop_loss=None):
    """
    Ejecuta una orden de mercado usando alpaca-py.
    """
    try:
        client = _get_trading_client()
        
        is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])
        norm_sym = symbol.replace('/', '').upper()
        
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

def cerrar_posicion(symbol):
    try:
        client = _get_trading_client()
        norm_sym = symbol.replace('/', '').upper()
        # En alpaca-py close_position requiere symbol o id
        return client.close_position(norm_sym)
    except Exception as e:
        logger.error(f"Error cerrando posición en {symbol}: {e}")
        raise e

def obtener_historial_cartera(periodo='1M', timeframe='1D'):
    try:
        client = _get_trading_client()
        req = GetPortfolioHistoryRequest(period=periodo, timeframe=timeframe)
        try:
            # En algunas versiones es filter_data, en otras es filter, 
            # y en otras es puramente posicional.
            hist = client.get_portfolio_history(req)
        except Exception:
            try:
                hist = client.get_portfolio_history(filter_data=req)
            except:
                hist = client.get_portfolio_history(filter=req)
        
        
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

def es_mercado_abierto():
    """
    Comprueba si el mercado de acciones está abierto actualmente.
    """
    try:
        client = _get_trading_client()
        clock = client.get_clock()
        return clock.is_open
    except Exception as e:
        logger.error(f"Error comprobando reloj del mercado: {e}")
        return True # Fallback por seguridad
