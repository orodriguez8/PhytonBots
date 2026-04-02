import os
import alpaca_trade_api as tradeapi

def _get_api():
    key    = os.getenv('ALPACA_API_KEY')
    secret = os.getenv('ALPACA_SECRET_KEY')
    base   = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    return tradeapi.REST(key, secret, base, api_version='v2')

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

def colocar_orden_mercado(symbol, qty, side, take_profit=None, stop_loss=None):
    """
    Ejecuta una orden de mercado en Alpaca.
    """
    try:
        api = _get_api()
        
        # Alpaca requiere un objeto bracket para TP/SL
        order_type = 'market'
        time_in_force = 'gtc'
        
        order = api.submit_order(
            symbol=symbol,
            qty=qty,
            side=side.lower(), # buy or sell
            type=order_type,
            time_in_force=time_in_force,
            take_profit=dict(limit_price=take_profit) if take_profit else None,
            stop_loss=dict(stop_price=stop_loss) if stop_loss else None,
        )
        return order
    except Exception as e:
        print(f"Error colocando orden en {symbol}: {e}")
        raise e
