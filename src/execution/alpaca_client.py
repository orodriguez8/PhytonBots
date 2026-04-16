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
            activities = api.get_activities(activity_types=['FILL'], page_size=50)
            for f in activities:
                if f.symbol not in fills:
                    fills[f.symbol] = f.transaction_time
        except Exception as e:
            print(f"DEBUG: Error recuperando fills recientes en historial abierto: {e}")
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
        from dateutil import parser
        api = _get_api()
        # Activity types en el SDK suelen preferir un string separado por comas
        # o un solo string si es un solo tipo. 'FILL' es el estándar para trades.
        tipos = 'FILL' 
        
        # Aumentamos el límite para permitir encontrar el 'BUY' de un 'SELL' antiguo
        activities = api.get_activities(activity_types=tipos, page_size=100)
        
        if not activities:
            return []

        agrupados = []
        # Procesamos todas las actividades de 'FILL'
        for f in activities:
            symbol = getattr(f, 'symbol', '')
            side = getattr(f, 'side', '').upper()
            qty = float(getattr(f, 'qty', 0))
            price = float(getattr(f, 'price', 0))
            
            if not symbol or not side or qty <= 0: continue
            
            t = getattr(f, 'transaction_time', None)
            if not t: continue
            if isinstance(t, str):
                t = parser.parse(t)
            
            agrupados.append({
                's': symbol,
                'side': side,
                'q': qty,
                'p': price,
                'time': t
            })

        # Ordenar por tiempo (ascendente) para reconstruir el historial
        agrupados.sort(key=lambda x: x['time'])

        res = []
        # Diccionario para trackear lotes de compra por símbolo (FIFO)
        inventory = {} 

        for item in agrupados:
            sym = item['s']
            if item['side'] == 'BUY':
                if sym not in inventory: inventory[sym] = []
                inventory[sym].append(item)
            elif item['side'] == 'SELL':
                # Intentamos buscar el precio de entrada (matching)
                entry_price = None
                if sym in inventory and len(inventory[sym]) > 0:
                    # Usamos el primer lote de compra (FIFO) para el matching
                    entry_batch = inventory[sym].pop(0)
                    entry_price = entry_batch['p']
                
                pl = (item['p'] - entry_price) * item['q'] if entry_price else 0
                
                res.insert(0, {
                    's': sym,
                    'side': 'SELL',
                    'q': round(item['q'], 4),
                    'p': round(item['p'], 4),
                    'entry': round(entry_price, 4) if entry_price else None,
                    'pl': round(pl, 2),
                    'time': item['time'].isoformat()
                })
        
        # Si NO hay cierres calculados (res vacío), mostramos las actividades brutas como fallback
        if not res:
            return [{ 
                's': i['s'], 
                'side': i['side'], 
                'q': round(i['q'], 4), 
                'p': round(i['p'], 4), 
                'pl': 0, 
                'time': i['time'].isoformat() 
            } for i in sorted(agrupados, key=lambda x: x['time'], reverse=True)[:20]]
            
        return res[:20]
    except Exception as e:
        print(f"ERROR en obtener_posiciones_cerradas: {e}")
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

def obtener_historial_cartera(periodo='1M', timeframe='1D'):
    """
    Devuelve el historial del valor de la cartera de Alpaca.
    Periodos: 1D, 1W, 1M, 3M, 1Y, ALL
    Timeframes: 1Min, 5Min, 15Min, 1H, 1D
    """
    try:
        api = _get_api()
        hist = api.get_portfolio_history(period=periodo, timeframe=timeframe)
        
        # Formatear para que el frontend lo entienda facilmente
        res = []
        for i in range(len(hist.timestamp)):
            res.append({
                'time': hist.timestamp[i], # Int (epoch)
                'value': float(hist.equity[i])
            })
        return res
    except Exception as e:
        print(f"Error en obtener_historial_cartera: {e}")
        return []
