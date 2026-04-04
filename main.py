
import threading
import time
from src.core.logger import logger
from src.api.server import app, socketio
import src.api.routes  # To register routes
import src.api.socket_events  # To register events
from src.bot.engine import trading_loop, build_summary, PROVIDER, LIVE_ENABLED

def ws_data_emitter():
    """Background thread that pushes dashboard data via WebSocket every 3s."""
    while True:
        try:
            data = build_summary()
            if 'error' not in data:
                socketio.emit('data_update', data)
        except Exception as e:
            logger.debug(f"Emitter cycle error: {e}")
        time.sleep(3)

if __name__ == '__main__':
    logger.info("🚀 Starting Trading Bot System...")
    logger.info(f"   Provider: {PROVIDER}")
    logger.info(f"   Live: {LIVE_ENABLED}")
    
    # Start trading loop in daemon thread
    threading.Thread(target=trading_loop, args=(socketio,), daemon=True, name='TradingLoop').start()
    
    # Start WebSocket data emitter in daemon thread
    threading.Thread(target=ws_data_emitter, daemon=True, name='WSEmitter').start()
    
    # Run the server
    logger.info("   Application running on port 7860")
    socketio.run(app, host='0.0.0.0', port=7860, debug=False, allow_unsafe_werkzeug=True)
