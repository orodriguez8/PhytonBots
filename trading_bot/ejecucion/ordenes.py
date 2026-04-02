
# =============================================================================
# MÓDULO: EJECUCIÓN DE ÓRDENES EN OANDA
# =============================================================================
# Gestiona el ciclo completo de una operación:
#   - Consultar estado de la cuenta (balance, equity, margen)
#   - Colocar órdenes de mercado (LONG / SHORT)
#   - Consultar posiciones abiertas y trades
#   - Cerrar posiciones
# =============================================================================

import os
import oandapyV20
import oandapyV20.endpoints.orders    as ep_orders
import oandapyV20.endpoints.accounts  as ep_accounts
import oandapyV20.endpoints.positions as ep_positions
import oandapyV20.endpoints.trades    as ep_trades

from config import OANDA_INSTRUMENT


def _get_client() -> oandapyV20.API:
    api_key     = os.getenv('OANDA_API_KEY')
    environment = os.getenv('OANDA_ENVIRONMENT', 'practice')
    if not api_key:
        raise ValueError("OANDA_API_KEY no encontrada. Revisa tu archivo .env")
    return oandapyV20.API(access_token=api_key, environment=environment)


def _get_account_id() -> str:
    account_id = os.getenv('OANDA_ACCOUNT_ID')
    if not account_id:
        raise ValueError("OANDA_ACCOUNT_ID no encontrado. Revisa tu archivo .env")
    return account_id


# ── Consulta de cuenta ────────────────────────────────────────────────────────
def obtener_cuenta() -> dict:
    """
    Devuelve el resumen de la cuenta: balance, equity, margen usado/libre, P&L.
    """
    client     = _get_client()
    account_id = _get_account_id()

    req = ep_accounts.AccountSummary(account_id)
    client.request(req)
    cuenta = req.response.get('account', {})

    return {
        'id':             cuenta.get('id', ''),
        'moneda':         cuenta.get('currency', 'USD'),
        'balance':        float(cuenta.get('balance', 0)),
        'nav':            float(cuenta.get('NAV', 0)),           # Net Asset Value (equity)
        'pl':             float(cuenta.get('pl', 0)),             # P&L realizado total
        'pl_abierto':     float(cuenta.get('unrealizedPL', 0)),   # P&L no realizado
        'margen_usado':   float(cuenta.get('marginUsed', 0)),
        'margen_libre':   float(cuenta.get('marginAvailable', 0)),
        'posiciones':     int(cuenta.get('openPositionCount', 0)),
        'trades_abiertos':int(cuenta.get('openTradeCount', 0)),
        'apalancamiento': cuenta.get('marginRate', '0.02'),
    }


# ── Posiciones y trades ───────────────────────────────────────────────────────
def obtener_posiciones_abiertas() -> list:
    """Devuelve la lista de posiciones abiertas en la cuenta."""
    client     = _get_client()
    account_id = _get_account_id()

    req = ep_positions.OpenPositions(account_id)
    client.request(req)
    posiciones = req.response.get('positions', [])

    resultado = []
    for p in posiciones:
        instrumento = p.get('instrument', '')
        long_side  = p.get('long',  {})
        short_side = p.get('short', {})

        if int(long_side.get('units', 0)) != 0:
            resultado.append({
                'instrumento': instrumento,
                'direccion':   'LONG',
                'unidades':    int(long_side.get('units', 0)),
                'precio_medio':float(long_side.get('averagePrice', 0)),
                'pl':          float(long_side.get('unrealizedPL', 0)),
            })
        if int(short_side.get('units', 0)) != 0:
            resultado.append({
                'instrumento': instrumento,
                'direccion':   'SHORT',
                'unidades':    abs(int(short_side.get('units', 0))),
                'precio_medio':float(short_side.get('averagePrice', 0)),
                'pl':          float(short_side.get('unrealizedPL', 0)),
            })

    return resultado


def obtener_trades_abiertos() -> list:
    """Devuelve los trades individuales abiertos."""
    client     = _get_client()
    account_id = _get_account_id()

    req = ep_trades.OpenTrades(account_id)
    client.request(req)
    trades = req.response.get('trades', [])

    return [{
        'id':          t.get('id'),
        'instrumento': t.get('instrument'),
        'unidades':    float(t.get('currentUnits', 0)),
        'precio':      float(t.get('price', 0)),
        'pl':          float(t.get('unrealizedPL', 0)),
        'apertura':    t.get('openTime', ''),
    } for t in trades]


# ── Ejecución de órdenes ──────────────────────────────────────────────────────
def colocar_orden_mercado(direccion: str,
                          unidades: int,
                          instrumento: str = None,
                          stop_loss: float = None,
                          take_profit: float = None) -> dict:
    """
    Coloca una orden de mercado en Oanda.

    Args:
        direccion   : 'LONG' o 'SHORT'
        unidades    : Número de unidades (positivo para LONG, se invierte para SHORT)
        instrumento : Par de divisas. Por defecto usa OANDA_INSTRUMENT del .env/config
        stop_loss   : Precio de stop loss (opcional)
        take_profit : Precio de take profit (opcional)

    Returns:
        Respuesta de la API de Oanda
    """
    instrumento = instrumento or os.getenv('OANDA_INSTRUMENT', OANDA_INSTRUMENT)
    client      = _get_client()
    account_id  = _get_account_id()

    # Las unidades son negativas para posiciones SHORT
    units = unidades if direccion == 'LONG' else -abs(unidades)

    order_body = {
        "order": {
            "type":          "MARKET",
            "instrument":    instrumento,
            "units":         str(int(units)),
            "timeInForce":   "FOK",
            "positionFill":  "DEFAULT",
        }
    }

    # Añadir Stop Loss si se proporciona
    if stop_loss:
        order_body["order"]["stopLossOnFill"] = {
            "price": f"{stop_loss:.5f}"
        }

    # Añadir Take Profit si se proporciona
    if take_profit:
        order_body["order"]["takeProfitOnFill"] = {
            "price": f"{take_profit:.5f}"
        }

    req = ep_orders.OrderCreate(account_id, data=order_body)
    client.request(req)
    return req.response


def cerrar_posicion(instrumento: str = None) -> dict:
    """Cierra todas las posiciones abiertas para el instrumento indicado."""
    instrumento = instrumento or os.getenv('OANDA_INSTRUMENT', OANDA_INSTRUMENT)
    client      = _get_client()
    account_id  = _get_account_id()

    data = {"longUnits": "ALL", "shortUnits": "ALL"}
    req  = ep_positions.PositionClose(account_id, instrumento, data=data)
    client.request(req)
    return req.response
