import os
import alpaca_trade_api as tradeapi

from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL

def _get_api():
    return tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2')

def obtener_cuenta():
    """
    Devuelve resumen de la cuenta Alpaca (Paper/Live).
    """
    try:
        api = _get_api()
        account = api.get_account()
        
        # Calculamos el P/L total aproximado (Equity actual vs Equity de ayer)
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        pl_total = equity - last_equity

        return {
            'id': account.id,
            'moneda': account.currency,
            'balance': float(account.cash),
            'nav': equity,
            'pl': pl_total,
            'pl_abierto': float(getattr(account, 'unrealized_intraday_pl', 0)),
            'margen_libre': float(account.buying_power),
            'posiciones': 0, 
            'apalancamiento': account.multiplier,
        }
    except Exception as e:
        print(f"Error en obtener_cuenta: {e}")
        return None

def obtener_posiciones_abiertas():
    """
    Devuelve lista de trades abiertos.
    """
    try:
        api = _get_api()
        positions = api.list_positions()
        
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
            })
        return res
    except Exception as e:
        print(f"Error en obtener_posiciones: {e}")
        return []

def obtener_posiciones_cerradas():
    """
    Obtiene el historial de posiciones cerradas recientemente con P/L realizado.
    """
    try:
        api = _get_api()
        # Buscamos 'FILL' (ejecuciones)
        activities = api.get_activities(activity_types='FILL')
        
        # Filtrar solo las que tienen precio y cantidad
        fills = [f for f in activities if hasattr(f, 'price') and hasattr(f, 'qty')]
        
        res = []
        # Mapa simple para recordar el "cost basis" aproximado (solo para el historial visual)
        buys = {} # symbol -> last_buy_price
        
        for f in reversed(fills): # Del más antiguo al más nuevo para rastrear buys
            sym = f.symbol
            price = float(f.price)
            qty = float(f.qty)
            side = f.side.upper()
            
            if side == 'BUY':
                buys[sym] = price
            elif side == 'SELL' and sym in buys:
                # Si vendemos y tenemos un precio de compra guardado, calculamos P/L
                entry = buys[sym]
                pl = (price - entry) * qty
                res.insert(0, {
                    's': sym,
                    'side': 'SELL',
                    'q': qty,
                    'p': price,
                    'entry': entry,
                    'pl': round(pl, 2),
                    'time': f.transaction_time.isoformat()
                })
        
        # Si no hay ventas emparejadas, mostrar rellenos sueltos
        if not res:
            return [{ 's': f.symbol, 'side': f.side.upper(), 'q': float(f.qty), 'p': float(f.price), 'pl': 0, 'time': f.transaction_time.isoformat() } for f in fills[:10]]
            
        return res[:10]
    except Exception as e:
        print(f"Error en historial de cerradas: {e}")
        return []

def obtener_ordenes_activas():
    """
    Devuelve lista de órdenes pendientes (no ejecutadas).
    """
    try:
        api = _get_api()
        orders = api.list_orders(status='open', limit=50)
        return [{
            'id': o.id,
            'symbol': o.symbol,
            'qty': o.qty,
            'side': o.side,
            'type': o.type,
            'status': o.status,
            'created_at': o.created_at.isoformat()
        } for o in orders]
    except Exception as e:
        print(f"Error en obtener_ordenes: {e}")
        return []

def cancelar_todas_las_ordenes():
    """
    Cancela todas las órdenes pendientes en la cuenta.
    """
    try:
        api = _get_api()
        api.cancel_all_orders()
        return True
    except Exception as e:
        print(f"Error cancelando órdenes: {e}")
        return False

def colocar_orden_mercado(symbol, qty, side, take_profit=None, stop_loss=None):
    """
    Ejecuta una orden de mercado en Alpaca. 
    Si hay SL/TP, crea una orden Bracket.
    """
    try:
        api = _get_api()
        
        is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])
        precision = 8 if is_crypto else 2
        
        order_class = 'simple'
        tp_dict = None
        sl_dict = None
        
        if take_profit or stop_loss:
            order_class = 'bracket'
            if take_profit:
                tp_dict = dict(limit_price=round(float(take_profit), precision))
            if stop_loss:
                sl_dict = dict(stop_price=round(float(stop_loss), precision))

        order = api.submit_order(
            symbol=symbol.replace('/', ''), # Alpaca crypto icons don't like '/'
            qty=qty,
            side=side.lower(),
            type='market',
            time_in_force='gtc',
            order_class=order_class,
            take_profit=tp_dict,
            stop_loss=sl_dict,
        )
        return order
    except Exception as e:
        print(f"Error colocando orden en {symbol}: {e}")
        raise e
