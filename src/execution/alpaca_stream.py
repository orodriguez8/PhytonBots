
import threading
import asyncio
import logging
from alpaca.trading.stream import TradingStream
from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER
from src.core.logger import logger

class AlpacaTradingStream:
    def __init__(self, state_ref, push_event_func):
        self.state = state_ref
        self.push_event = push_event_func
        self.stream = None
        self._thread = None
        self._loop = None

    async def _on_trade_update(self, data):
        """
        Handler para eventos de ejecución de órdenes (Execution Events)
        """
        event = data.event
        order = data.order
        symbol = order.symbol
        qty = order.filled_qty
        price = order.filled_avg_price

        msg = f"🔔 EVENTO ALPACA: {symbol} - {event.upper()} | Qty: {qty} | Price: {price}"
        logger.info(msg)
        self.push_event('info', msg)

        # Si la orden se llena, podemos registrarla en el historial oficial del estado
        if event == 'fill' or event == 'partial_fill':
            with self.state.LOCK:
                self.state.BOT_HISTORY.insert(0, {
                    'time': order.updated_at.isoformat(),
                    'sym': symbol,
                    'type': f"EXEC {order.side.name}",
                    'price': float(price),
                    'reason': f"Order {order.id} {event}"
                })

    def _run_stream(self):
        """Inicia el loop de asyncio para el stream."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        self.stream = TradingStream(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)
        self.stream.subscribe_trade_updates(self._on_trade_update)
        
        logger.info("📡 Iniciando TradingStream de Alpaca...")
        try:
            self.stream.run()
        except Exception as e:
            logger.error(f"❌ Error en TradingStream: {e}")

    def start(self):
        """Lanza el stream en un hilo separado."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run_stream, daemon=True)
        self._thread.start()

    def stop(self):
        if self.stream:
            # alpaca-py TradingStream doesn't have a simple stop() yet, 
            # but we can try closing the loop or similar if needed.
            pass
