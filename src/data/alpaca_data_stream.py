
import threading
import asyncio
from alpaca.data.live import StockDataStream, CryptoDataStream
from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY, WATCHLIST
from src.core.logger import logger

# Global cache for the latest prices
LATEST_PRICES = {}
PRICE_LOCK = threading.Lock()

class AlpacaDataStream:
    def __init__(self, symbols):
        self.symbols = symbols
        self.stock_symbols = [s for s in symbols if not any(q in s.upper() for q in ['USD', 'USDT', 'USDC', '/'])]
        self.crypto_symbols = [s for s in symbols if s not in self.stock_symbols]
        
        self.stock_stream = None
        self.crypto_stream = None
        
        self._threads = []

    async def _handle_bar(self, data):
        """Handler para recibir velas en tiempo real (si quisiéramos usarlas)."""
        pass

    async def _handle_trade(self, data):
        """Handler para recibir el último precio ejecutado."""
        with PRICE_LOCK:
            LATEST_PRICES[data.symbol] = float(data.price)

    def _run_stock_stream(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.stock_stream = StockDataStream(ALPACA_API_KEY, ALPACA_SECRET_KEY)
        # Suscribirse a trades para tener precio actual al segundo
        self.stock_stream.subscribe_trades(self._handle_trade, *self.stock_symbols)
        
        logger.info(f"📡 WebSocket Acciones: Suscrito a {len(self.stock_symbols)} símbolos.")
        try:
            self.stock_stream.run()
        except Exception as e:
            logger.error(f"❌ Error en WebSocket Acciones: {e}")

    def _run_crypto_stream(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        self.crypto_stream = CryptoDataStream(ALPACA_API_KEY, ALPACA_SECRET_KEY)
        norm_crypto = [s if '/' in s else s.replace('USD', '/USD') for s in self.crypto_symbols]
        self.crypto_stream.subscribe_trades(self._handle_trade, *norm_crypto)
        
        logger.info(f"📡 WebSocket Cripto: Suscrito a {len(self.crypto_symbols)} símbolos.")
        try:
            self.crypto_stream.run()
        except Exception as e:
            logger.error(f"❌ Error en WebSocket Cripto: {e}")

    def start(self):
        """Lanza los hilos para acciones y cripto."""
        if self.stock_symbols:
            t1 = threading.Thread(target=self._run_stock_stream, daemon=True)
            t1.start()
            self._threads.append(t1)
        
        if self.crypto_symbols:
            t2 = threading.Thread(target=self._run_crypto_stream, daemon=True)
            t2.start()
            self._threads.append(t2)

def get_latest_price(symbol):
    """Devuelve el último precio conocido del cache global."""
    norm_sym = symbol.replace('/', '').upper()
    with PRICE_LOCK:
        return LATEST_PRICES.get(norm_sym)
