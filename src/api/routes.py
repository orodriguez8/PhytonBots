
import os
import datetime
import traceback
from flask import render_template, jsonify, request
from src.api.server import app, socketio
from src.bot.engine import (
    state, push_event, build_summary, cancel_all_orders, 
    LIVE_ENABLED, IS_ALPACA, CCXT_EXCHANGE_ID
)
from src.core.config import BOT_PASSWORD

def build_api_summary():
    # Helper to call engine's build_summary with fallback
    try:
        from src.bot.engine import build_summary
        return build_summary()
    except Exception as e:
        return {'error': str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/positions')
def positions():
    return render_template('positions.html')

@app.route('/api/status')
def status():
    return jsonify({
        'modo': 'ALPACA' if IS_ALPACA else 'CRYPTO',
        'auto_trading': state.AUTO_TRADING_ACTIVE,
        'instrumento': 'PORTFOLIO'
    })

@app.route('/api/run')
@app.route('/api/summary')
def summary():
    data = build_summary()
    if 'error' in data:
        return jsonify(data), 500
    return jsonify(data)

@app.route('/api/toggle-auto', methods=['POST'])
@app.route('/api/toggle', methods=['POST'])
def toggle():
    # Verificar contraseña si está configurada
    if BOT_PASSWORD:
        req_data = request.get_json(silent=True) or {}
        user_pwd = req_data.get('password', '')
        if user_pwd != BOT_PASSWORD:
            return jsonify({'ok': False, 'error': 'Invalid PIN'}), 401
    
    state.AUTO_TRADING_ACTIVE = not state.AUTO_TRADING_ACTIVE
    push_event('info', f"Bot toggled → {'ACTIVE' if state.AUTO_TRADING_ACTIVE else 'STANDBY'}", socketio)
    return jsonify({'ok': True, 'state': state.AUTO_TRADING_ACTIVE, 'auto_trading': state.AUTO_TRADING_ACTIVE})

@app.route('/api/cancel_all', methods=['POST'])
def cancel_all():
    # Verificar contraseña si está configurada
    if BOT_PASSWORD:
        user_pwd = request.json.get('password', '')
        if user_pwd != BOT_PASSWORD:
            return jsonify({'ok': False, 'error': 'Invalid PIN'}), 401

    if LIVE_ENABLED:
        try:
            cancel_all_orders()
            state.BOT_HISTORY.insert(0, {
                'time': datetime.datetime.now().strftime('%d/%m %H:%M'),
                'sym': 'ALL',
                'type': 'CANCEL',
                'price': 0,
                'reason': 'Manual cancel',
            })
            push_event('order', 'All orders cancelled', socketio)
            return jsonify({'ok': True})
        except Exception:
            pass
    return jsonify({'ok': False, 'error': 'No activo o error'})

@app.route('/api/test_alpaca')
def test_alpaca():
    from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL
    res = {
        'key_present': bool(ALPACA_API_KEY),
        'secret_present': bool(ALPACA_SECRET_KEY),
        'base_url': ALPACA_BASE_URL,
        'key_start': ALPACA_API_KEY[:5] if ALPACA_API_KEY else 'N/A',
        'status': 'UNKNOWN',
        'error': None,
    }
    try:
        from src.execution.alpaca_client import _get_api
        api = _get_api()
        acc = api.get_account()
        res['status'] = 'CONNECTED'
        res['equity'] = float(acc.equity)
    except Exception as e:
        res['status'] = 'FAILED'
        res['error'] = str(e)
    return jsonify(res)

@app.route('/api/portfolio_history')
def portfolio_history():
    period = request.args.get('period', '1M').upper()
    # Map the user-friendly names to Alpaca periods
    m = {'DAY': '1D', 'WEEK': '1W', 'MONTH': '1M', 'YEAR': '1Y', 'ALL': 'ALL'}
    alpaca_period = m.get(period, '1M')
    
    # Map the user-friendly names to Alpaca timeframes
    tf_map = {'DAY': '1Min', 'WEEK': '5Min', 'MONTH': '1D', 'YEAR': '1D', 'ALL': '1D'}
    alpaca_tf = tf_map.get(period, '1H')
    
    try:
        from src.execution.alpaca_client import obtener_historial_cartera
        data = obtener_historial_cartera(alpaca_period, alpaca_tf)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/close_position', methods=['POST'])
def close_position():
    # Verificar contraseña si está configurada
    if BOT_PASSWORD:
        user_pwd = request.json.get('password', '')
        if user_pwd != BOT_PASSWORD:
            return jsonify({'ok': False, 'error': 'Invalid PIN'}), 401
    
    symbol = request.json.get('symbol')
    if not symbol:
        return jsonify({'ok': False, 'error': 'Symbol is required'}), 400
        
    if LIVE_ENABLED:
        try:
            from src.bot.engine import IS_ALPACA, place_order, get_positions, cancel_orders_for_symbol
            from src.execution import alpaca_client
            
            if IS_ALPACA:
                cancel_orders_for_symbol(symbol)
                alpaca_client.cerrar_posicion(symbol)
            else:
                # CCXT closure logic
                pos = get_positions()
                match = next((p for p in pos if p['instrumento'] == symbol), None)
                if match:
                    side = 'sell' if match['direccion'] == 'LONG' else 'buy'
                    place_order(symbol, match['unidades'], side)
                else:
                    return jsonify({'ok': False, 'error': 'Position not found'}), 404

            state.BOT_HISTORY.insert(0, {
                'time': datetime.datetime.now().isoformat(),
                'sym': symbol,
                'type': 'CLOSE',
                'price': 0,
                'reason': 'Manual close',
            })
            push_event('order', f"Position closed manually: {symbol}", socketio)
            return jsonify({'ok': True})
        except Exception as e:
            traceback.print_exc()
            return jsonify({'ok': False, 'error': f"Error closing {symbol}: {str(e)}"}), 500
            
    return jsonify({'ok': False, 'error': 'Live trading not enabled'})
