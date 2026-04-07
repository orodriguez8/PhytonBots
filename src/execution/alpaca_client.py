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
        
        # Intentamos obtener actividades recientes para aproximar la fecha de entrada
        fills = {}
        try:
            activities = api.get_activities(activity_types='FILL')
            for f in activities:
                if f.symbol not in fills:
                    fills[f.symbol] = f.transaction_time
        except:
            pass

        res = []
        for p in positions:
            entry_time = fills.get(p.symbol)
            res.append({
                'instrumento': p.symbol,
                'direccion': 'LONG' if float(p.qty) > 0 else 'SHORT',
                'unidades': abs(float(p.qty)),
                'precio_medio': float(p.avg_entry_price),
                'precio_actual': float(p.current_price),
                'pl': float(p.unrealized_pl),
                'pl_pct': float(p.unrealized_plpc) * 100,
                'valor_total': float(p.cost_basis),
                'fecha_entrada': entry_time.isoformat() if entry_time else None
            })
        return res
    except Exception as e:
        print(f"Error en obtener_posiciones: {e}")
        return []

def obtener_posiciones_cerradas():
    """
    Obtiene el historial de posiciones cerradas recientemente agrupando 'fills' 
    para evitar duplicados visuales y mostrar el P/L real por operación.
    """
    try:
        api = _get_api()
        # Buscamos 'FILL' (ejecuciones)
        activities = api.get_activities(activity_types='FILL')
        
        # Mapa para agrupar por símbolo y tipo de operación (BUY/SELL) aproximando por hora
        # Esto ayuda a consolidar órdenes que se llenaron en varios pedazos
        agrupados = {}
        
        for f in activities:
            if not (hasattr(f, 'price') and hasattr(f, 'qty')): continue
            
            # Creamos una clave única: Símbolo + Lado + Hora/Minuto aproximado
            # (Si se cerraron al mismo tiempo, son la misma operación para el usuario)
            time_key = f.transaction_time.strftime('%Y-%m-%d %H:%M')
            key = f"{f.symbol}_{f.side}_{time_key}"
            
            if key not in agrupados:
                agrupados[key] = {
                    's': f.symbol,
                    'side': f.side.upper(),
                    'q': 0.0,
                    'total_val': 0.0,
                    'time': f.transaction_time.isoformat()
                }
            
            agrupados[key]['q'] += float(f.qty)
            agrupados[key]['total_val'] += float(f.qty) * float(f.price)

        # Ahora procesamos los agrupados para calcular el histórico con P/L
        res = []
        buys = {} # Para rastrear el costo de entrada
        
        # Procesamos de antiguo a nuevo para casar compras con ventas
        sorted_keys = sorted(agrupados.keys(), key=lambda x: agrupados[x]['time'])
        
        for k in sorted_keys:
            item = agrupados[k]
            avg_price = item['total_val'] / item['q']
            
            if item['side'] == 'BUY':
                buys[item['s']] = avg_price
            elif item['side'] == 'SELL' and item['s'] in buys:
                entry = buys[item['s']]
                pl = (avg_price - entry) * item['q']
                res.insert(0, {
                    's': item['s'],
                    'side': 'SELL',
                    'q': round(item['q'], 4),
                    'p': round(avg_price, 4),
                    'entry': round(entry, 4),
                    'pl': round(pl, 2),
                    'time': item['time']
                })
        
        # Si no hay ventas casadas, mostrar los últimos movimientos agrupados
        if not res:
            return [{ 
                's': i['s'], 
                'side': i['side'], 
                'q': round(i['q'], 4), 
                'p': round(i['total_val']/i['q'], 4), 
                'pl': 0, 
                'time': i['time'] 
            } for i in list(agrupados.values())[:10]]
            
        return res[:10]
    except Exception as e:
        print(f"Error en historial de cerradas consolidado: {e}")
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
    Si hay SL/TP, crea una orden Bracket (excepto para Crypto).
    """
    try:
        api = _get_api()
        
        is_crypto = any(q in symbol.upper() for q in ['USD', 'USDT', 'USDC', '/'])
        precision = 8 if is_crypto else 2
        
        # Fractional orders MUST be 'day' orders and 'simple' in Alpaca
        is_fractional = float(qty) != int(float(qty))
        tif = 'day' if (is_fractional and not is_crypto) else 'gtc'
        
        # Alpaca does NOT support advanced order classes (bracket, oco, etc) for Crypto OR Fractional
        order_class = 'simple'
        tp_dict = None
        sl_dict = None
        
        if (take_profit or stop_loss) and not is_crypto and not is_fractional:
            order_class = 'bracket'
            if take_profit:
                tp_dict = dict(limit_price=round(float(take_profit), precision))
            if stop_loss:
                sl_dict = dict(stop_price=round(float(stop_loss), precision))
        elif (take_profit or stop_loss) and (is_crypto or is_fractional):
            reason_skip = "Crypto" if is_crypto else "Fractional"
            print(f"INFO: SL/TP ignorado para {symbol} (Alpaca no permite bracket orders en {reason_skip} assets)")

        order = api.submit_order(
            symbol=symbol.replace('/', ''), # Alpaca crypto icons don't like '/'
            qty=qty,
            side=side.lower(),
            type='market',
            time_in_force=tif,
            order_class=order_class,
            take_profit=tp_dict,
            stop_loss=sl_dict,
        )
        return order
    except Exception as e:
        print(f"Error colocando orden en {symbol}: {e}")
        raise e

def cerrar_posicion(symbol):
    """
    Cierra completamente una posición abierta para el símbolo indicado.
    """
    try:
        api = _get_api()
        # Alpaca crypto icons don't like '/'
        norm_sym = symbol.replace('/', '').upper()
        return api.close_position(norm_sym)
    except Exception as e:
        print(f"Error cerrando posición en {symbol}: {e}")
        raise e
