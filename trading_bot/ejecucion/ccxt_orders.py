import os
import ccxt
import time
from ..config import BINANCE_API_KEY, BINANCE_SECRET_KEY, BINANCE_TESTNET

def _get_exchange():
    """
    Inicializa el exchange de Binance via CCXT.
    """
    params = {
        'apiKey': BINANCE_API_KEY or os.getenv('BINANCE_API_KEY', ''),
        'secret': BINANCE_SECRET_KEY or os.getenv('BINANCE_SECRET_KEY', ''),
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot' # Solo spot para empezar
        }
    }
    
    exchange = ccxt.binance(params)
    
    if BINANCE_TESTNET or os.getenv('BINANCE_TESTNET', 'True').lower() == 'true':
        exchange.set_sandbox_mode(True)
        
    return exchange

def obtener_cuenta_ccxt():
    """
    Obtiene el balance de la cuenta de Binance.
    """
    try:
        exchange = _get_exchange()
        balance = exchange.fetch_balance()
        
        # En Binance no hay un 'Equity' único como en Alpaca, sumamos USDT y Valor estimado
        usdt_free = balance.get('USDT', {}).get('free', 0.0)
        usdt_total = balance.get('USDT', {}).get('total', 0.0)
        
        return {
            'id': 'Binance_Acc',
            'moneda': 'USDT',
            'balance': float(usdt_free),
            'nav': float(usdt_total), # Equity simplificado
            'margen_libre': float(usdt_free),
            'pl': 0.0, # Binance no da P/L diario tan fácil como Alpaca
            'posiciones': 0
        }
    except Exception as e:
        print(f"Error en obtener_cuenta_ccxt: {e}")
        return None

def obtener_posiciones_abiertas_ccxt():
    """
    Obtiene saldos de criptos que no sean USDT (simulando posiciones).
    """
    try:
        exchange = _get_exchange()
        balance = exchange.fetch_balance()
        
        res = []
        for asset, data in balance.get('total', {}).items():
            if asset != 'USDT' and data > 0:
                # Obtenemos precio actual para calcular P/L aproximado
                symbol = f"{asset}/USDT"
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                    res.append({
                        'instrumento': symbol,
                        'direccion': 'LONG',
                        'unidades': float(data),
                        'precio_medio': 0.0, # Binance no guarda el precio medio de compra en el balance
                        'precio_actual': float(current_price),
                        'pl': 0.0,
                        'pl_pct': 0.0
                    })
                except:
                    continue
        return res
    except Exception as e:
        print(f"Error en obtener_posiciones_ccxt: {e}")
        return []

def colocar_orden_mercado_ccxt(symbol, qty, side):
    """
    Ejecuta una orden de mercado en Binance.
    """
    try:
        exchange = _get_exchange()
        
        # Normalizar símbolo (BTCUSD -> BTC/USDT)
        if '/' not in symbol:
            symbol = symbol.replace('USD', '/USDT')
            
        print(f"⚙️ CCXT: Enviando orden {side} de {qty} {symbol}")
        
        # Binance requiere el símbolo con barra en CCXT
        order = exchange.create_market_order(symbol, side.lower(), qty)
        
        return order
    except Exception as e:
        print(f"Error colocando orden CCXT en {symbol}: {e}")
        raise e

def cancelar_todas_las_ordenes_ccxt():
    """
    Cancela todas las órdenes abiertas en el exchange.
    """
    try:
        exchange = _get_exchange()
        # Binance tiene fetch_open_orders
        open_orders = exchange.fetch_open_orders()
        for o in open_orders:
            exchange.cancel_order(o['id'], o['symbol'])
        return True
    except Exception as e:
        print(f"Error cancelando órdenes CCXT: {e}")
        return False
