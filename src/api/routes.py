
import os
import datetime
import traceback
from flask import render_template, jsonify, request
from src.api.server import app, socketio
from src.bot.engine import (
    state, push_event, build_summary, cancel_all_orders, 
    LIVE_ENABLED, IS_ALPACA, CCXT_EXCHANGE_ID
)

def build_api_summary():
    # Helper to call engine's build_summary with fallback
    try:
        from src.bot.engine import build_summary
        return build_summary()
    except Exception as e:
        return {'error': str(e)}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/toggle', methods=['POST'])
def toggle():
    state.AUTO_TRADING_ACTIVE = not state.AUTO_TRADING_ACTIVE
    push_event('info', f"Bot toggled → {'ACTIVE' if state.AUTO_TRADING_ACTIVE else 'STANDBY'}", socketio)
    return jsonify({'ok': True, 'state': state.AUTO_TRADING_ACTIVE})

@app.route('/api/summary')
def summary():
    data = build_summary()
    if 'error' in data:
        return jsonify(data), 500
    return jsonify(data)

@app.route('/api/cancel_all', methods=['POST'])
def cancel_all():
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
    return jsonify({'ok': False, 'error': 'No activo'})

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
