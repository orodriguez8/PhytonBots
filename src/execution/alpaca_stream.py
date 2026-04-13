
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
        self._thread = None

    async def _on_trade_update(self, data):
        """
        Handler para eventos de ejecución de órdenes (Execution Events)
        """
        try:
            event = data.event
            order = data.order
            symbol = order.symbol
            qty = order.filled_qty
            price = order.filled_avg_price

            msg = f"🔔 EVENTO ALPACA: {symbol} - {event.upper()} | Qty: {qty} | Price: {price}"
            logger.info(msg)
            self.push_event('info', msg)

            if event == 'fill' or event == 'partial_fill':
                with self.state.LOCK:
                    self.state.BOT_HISTORY.insert(0, {
                        'time': order.updated_at.isoformat() if order.updated_at else "",
                        'sym': symbol,
                        'type': f"EXEC {order.side.name}",
                        'price': float(price or 0),
                        'reason': f"Order {order.id} {event}"
                    })
        except Exception as e:
            logger.error(f"Error en _on_trade_update: {e}")

    async def _run_async_stream(self):
        logger.info("📡 Iniciando TradingStream de Alpaca (Eventos)...")
        try:
            stream = TradingStream(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=ALPACA_PAPER)
            stream.subscribe_trade_updates(self._on_trade_update)
            await stream._run_forever()
        except Exception as e:
            logger.error(f"❌ Error en TradingStream: {e}")

    def _thread_target(self):
        try:
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_async_stream())
            loop.close()
        except Exception as e:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._run_async_stream())
            except Exception as e2:
                logger.error(f"Fallo crítico en TradingStream: {e2}")

    def start(self):
        """Lanza el stream en un hilo separado."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._thread_target, daemon=True)
        self._thread.start()
