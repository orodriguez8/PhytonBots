import os
import ccxt
import time
import random
from src.core.config import CCXT_API_KEY, CCXT_SECRET_KEY, CCXT_TESTNET, CCXT_EXCHANGE_ID

# --- Circuit Breaker & Retry State ---
CIRCUIT_MAX_FAILURES = 5
_consecutive_failures = 0
_is_paused = False
_pause_until = 0

def get_circuit_breaker_status():
    """Devuelve si el sistema está en pausa por errores técnicos."""
    global _is_paused, _pause_until
    if _is_paused and time.time() > _pause_until:
        _is_paused = False # Reset automático tras el tiempo de espera
    return _is_paused

def _record_success():
    global _consecutive_failures, _is_paused
    _consecutive_failures = 0
    _is_paused = False

def _record_failure():
    global _consecutive_failures, _is_paused, _pause_until
    _consecutive_failures += 1
    if _consecutive_failures >= CIRCUIT_MAX_FAILURES:
        _is_paused = True
        _pause_until = time.time() + 300 # Pausa de 5 minutos
        print(f"🚨 CIRCUIT BREAKER: {CIRCUIT_MAX_FAILURES} errores seguidos. Pausando 5min.")

def _get_exchange():
    """
    Inicializa el exchange configurado via CCXT.
    """
    params = {
        'apiKey': CCXT_API_KEY or os.getenv('CCXT_API_KEY', ''),
        'secret': CCXT_SECRET_KEY or os.getenv('CCXT_SECRET_KEY', ''),
        'enableRateLimit': True,
    }
    
    # Binance Futures configuration
    if 'binance' in CCXT_EXCHANGE_ID.lower():
        params['options'] = {'defaultType': 'future'}

    exchange_cls = getattr(ccxt, CCXT_EXCHANGE_ID, None)
    if exchange_cls is None:
        raise ValueError(f"Exchange CCXT no soportado: {CCXT_EXCHANGE_ID}")

    exchange = exchange_cls(params)
    if CCXT_TESTNET and getattr(exchange, 'urls', None) and exchange.urls.get('test'):
        exchange.set_sandbox_mode(True)
    return exchange

def obtener_cuenta_ccxt():
    """
    Obtiene el balance de la cuenta con reintentos y exponential backoff.
    """
    if get_circuit_breaker_status():
        return None

    for attempt in range(3):
        try:
            exchange = _get_exchange()
            # In futures, we might need to fetch the futures specific balance
            if 'binance' in CCXT_EXCHANGE_ID.lower():
                balance = exchange.fetch_balance(params={'type': 'future'})
                main_free = balance.get('USDT', {}).get('free', 0.0)
                main_total = balance.get('USDT', {}).get('total', 0.0)
            else:
                balance = exchange.fetch_balance()
                main_free = balance.get('USD', {}).get('free', 0.0) or balance.get('USDC', {}).get('free', 0.0)
                main_total = balance.get('USD', {}).get('total', 0.0) or balance.get('USDC', {}).get('total', 0.0)
            
            _record_success()
            return {
                'id': f'{CCXT_EXCHANGE_ID}_Acc',
                'moneda': 'USDT' if 'binance' in CCXT_EXCHANGE_ID.lower() else 'USD',
                'balance': float(main_free),
                'nav': float(main_total),
                'margen_libre': float(main_free),
                'pl': 0.0,
                'posiciones': 0
            }
        except Exception as e:
            wait = (2 ** attempt) + random.random()
            print(f"⚠️ Reintento {attempt+1}/3 (Backoff {wait:.1f}s) en obtener_cuenta_ccxt: {e}")
            time.sleep(wait)
    
    _record_failure()
    return None

def obtener_posiciones_abiertas_ccxt():
    """
    Obtiene saldos de criptos que no sean USD/USDC.
    """
    try:
        exchange = _get_exchange()
        
        # Proper way to fetch positions in CCXT for derivatives
        if hasattr(exchange, 'fetch_positions'):
            positions = exchange.fetch_positions()
            res = []
            for p in positions:
                if p['contracts'] is not None and float(p['contracts']) > 0:
                    res.append({
                        'instrumento': p['symbol'],
                        'direccion': p['side'].upper(), # 'LONG' or 'SHORT'
                        'unidades': float(p['contracts']),
                        'precio_medio': float(p['entryPrice'] or 0),
                        'precio_actual': float(p['markPrice'] or 0),
                        'pl': float(p['unrealizedPnl'] or 0),
                        'pl_pct': 0.0 # Calculate if needed
                    })
            _record_success()
            return res
        
        # Fallback for Spot (like before)
        balance = exchange.fetch_balance()
        res = []
        for asset, data in balance.get('total', {}).items():
            if asset not in ['USD', 'USDC', 'USDT'] and data > 0:
                symbol = f"{asset}/USDT"
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                    res.append({
                        'instrumento': symbol,
                        'direccion': 'LONG',
                        'unidades': float(data),
                        'precio_medio': 0.0,
                        'precio_actual': float(current_price),
                        'pl': 0.0,
                        'pl_pct': 0.0
                    })
                except:
                    continue
        _record_success()
        return res
    except Exception as e:
        print(f"Error en obtener_posiciones_ccxt ({CCXT_EXCHANGE_ID}): {e}")
        _record_failure()
        return []

def colocar_orden_mercado_ccxt(symbol, qty, side):
    """
    Ejecuta una orden de mercado con protección de Circuit Breaker.
    """
    if get_circuit_breaker_status():
        raise Exception("Circuit Breaker activo: operando en pausa.")

    try:
        exchange = _get_exchange()
        
        # Normalizar símbolo (BTCUSD -> BTC/USD)
        if '/' not in symbol:
            symbol = symbol.replace('USDT', '/USD').replace('USD', '/USD')
            
        print(f"⚙️ CCXT: Enviando orden {side} de {qty} {symbol} en {CCXT_EXCHANGE_ID}")
        
        order = exchange.create_market_order(symbol, side.lower(), qty)
        _record_success()
        return order
    except Exception as e:
        print(f"Error colocando orden CCXT-{CCXT_EXCHANGE_ID} en {symbol}: {e}")
        _record_failure()
        raise e

def cancelar_todas_las_ordenes_ccxt():
    """
    Cancela todas las órdenes abiertas con protección de Circuit Breaker.
    """
    if get_circuit_breaker_status():
        return False

    try:
        exchange = _get_exchange()
        open_orders = exchange.fetch_open_orders()
        for o in open_orders:
            exchange.cancel_order(o['id'], o['symbol'])
        _record_success()
        return True
    except Exception as e:
        print(f"Error cancelando órdenes CCXT-{CCXT_EXCHANGE_ID}: {e}")
        _record_failure()
        return False
