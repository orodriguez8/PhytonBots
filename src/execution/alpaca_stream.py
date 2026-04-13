
import multiprocessing
import asyncio
from alpaca.trading.stream import TradingStream
from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER
from src.core.logger import logger

# Usamos Multiprocessing para el stream de eventos
# para evitar conflictos de bucle de asyncio con eventlet.
# Los eventos se envían de vuelta al hilo principal vía Queue.

_event_queue = multiprocessing.Queue()

def get_stream_events():
    """Recupera los eventos acumulados en la cola."""
    events = []
    while not _event_queue.empty():
        events.append(_event_queue.get())
    return events

async def _trade_update_handler(data):
    try:
        # Serializamos los datos necesarios para enviarlos por la cola
        event_data = {
            'event': data.event,
            'symbol': data.order.symbol,
            'qty': float(data.order.filled_qty or 0),
            'price': float(data.order.filled_avg_price or 0),
            'side': data.order.side.name,
            'id': str(data.order.id),
            'updated_at': data.order.updated_at.isoformat() if data.order.updated_at else None
        }
        _event_queue.put(event_data)
    except Exception as e:
        pass

def _run_stream_process(api_key, secret_key, paper, queue):
    global _event_queue
    _event_queue = queue
    
    async def main():
        try:
            stream = TradingStream(api_key, secret_key, paper=paper)
            stream.subscribe_trade_updates(_trade_update_handler)
            await stream._run_forever()
        except Exception as e:
            logger.error(f"Error procesal TradingStream: {e}")

    asyncio.run(main())

class AlpacaTradingStream:
    def __init__(self, state_ref, push_event_func):
        self.state = state_ref
        self.push_event = push_event_func
        self._process = None

    def start(self):
        if self._process and self._process.is_alive():
            return
        self._process = multiprocessing.Process(
            target=_run_stream_process,
            args=(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER, _event_queue),
            daemon=True
        )
        self._process.start()

    def process_incoming_events(self):
        """Método para ser llamado desde el bucle principal (engine) para procesar la cola."""
        for evt in get_stream_events():
            msg = f"🔔 EVENTO: {evt['symbol']} - {evt['event'].upper()} | Qty: {evt['qty']} | Price: {evt['price']}"
            logger.info(msg)
            self.push_event('info', msg)
            
            if evt['event'] in ['fill', 'partial_fill']:
                with self.state.LOCK:
                    self.state.BOT_HISTORY.insert(0, {
                        'time': evt['updated_at'],
                        'sym': evt['symbol'],
                        'type': f"EXEC {evt['side']}",
                        'price': evt['price'],
                        'reason': f"Order {evt['id']} {evt['event']}"
                    })
