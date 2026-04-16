
from flask_socketio import emit
from src.api.server import socketio
from src.core.logger import logger
from src.bot.engine import state, push_event, build_summary

@socketio.on('connect')
def handle_connect():
    # logger.info(f"🔌 WebSocket client connected")
    push_event('info', 'Client connected', socketio)

@socketio.on('disconnect')
def handle_disconnect():
    # logger.info(f"🔌 WebSocket client disconnected")
    pass

@socketio.on('ping_latency')
def handle_ping():
    emit('pong_latency')

@socketio.on('toggle_bot')
def handle_toggle():
    state.AUTO_TRADING_ACTIVE = not state.AUTO_TRADING_ACTIVE
    state_label = 'ACTIVE' if state.AUTO_TRADING_ACTIVE else 'STANDBY'
    push_event('info', f"Bot toggled → {state_label}", socketio)
    logger.info(f"🤖 Bot → {state_label}")
    data = build_summary()
    socketio.emit('data_update', data)
