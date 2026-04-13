
import threading
import asyncio
from alpaca.data.live import StockDataStream, CryptoDataStream
from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from src.core.logger import logger

# Global cache for the latest prices
LATEST_PRICES = {}
PRICE_LOCK = threading.Lock()

class AlpacaDataStream:
    def __init__(self, symbols):
        self.symbols = symbols
        self.stock_symbols = [s for s in symbols if not any(q in s.upper() for q in ['USD', 'USDT', 'USDC', '/'])]
        self.crypto_symbols = [s for s in symbols if s not in self.stock_symbols]
        
    async def _handle_trade(self, data):
        """Handler para recibir el último precio ejecutado."""
        try:
            with PRICE_LOCK:
                # Clean symbol name (e.g. BTC/USD -> BTCUSD for internal consistency)
                sym = data.symbol.replace('/', '')
                LATEST_PRICES[sym] = float(data.price)
        except Exception as e:
            logger.error(f"Error en _handle_trade: {e}")

    async def _run_stock_stream(self):
        if not self.stock_symbols: return
        logger.info(f"📡 Iniciando WebSocket Acciones para {len(self.stock_symbols)} símbolos...")
        try:
            stream = StockDataStream(ALPACA_API_KEY, ALPACA_SECRET_KEY)
            stream.subscribe_trades(self._handle_trade, *self.stock_symbols)
            await stream._run_forever()
        except Exception as e:
            logger.error(f"❌ Error en WebSocket Acciones: {e}")

    async def _run_crypto_stream(self):
        if not self.crypto_symbols: return
        logger.info(f"📡 Iniciando WebSocket Cripto para {len(self.crypto_symbols)} símbolos...")
        try:
            stream = CryptoDataStream(ALPACA_API_KEY, ALPACA_SECRET_KEY)
            norm_crypto = [s if '/' in s else s.replace('USD', '/USD') for s in self.crypto_symbols]
            stream.subscribe_trades(self._handle_trade, *norm_crypto)
            await stream._run_forever()
        except Exception as e:
            logger.error(f"❌ Error en WebSocket Cripto: {e}")

    def _thread_target(self, coro):
        try:
            # Intentar resetear la política de loops para este hilo
            # para evadir la interferencia de eventlet si es posible
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
            loop.close()
        except Exception as e:
            # Si aún falla, intentamos una aproximación directa sin set_event_loop
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(coro)
            except Exception as e2:
                logger.error(f"Fallo crítico lanzando WebSocket: {e2}")

    def start(self):
        """Lanza los hilos para acciones y cripto."""
        if self.stock_symbols:
            t1 = threading.Thread(target=self._thread_target, args=(self._run_stock_stream(),), daemon=True)
            t1.start()
        
        if self.crypto_symbols:
            t2 = threading.Thread(target=self._thread_target, args=(self._run_crypto_stream(),), daemon=True)
            t2.start()

def get_latest_price(symbol):
    """Devuelve el último precio conocido del cache global."""
    norm_sym = symbol.replace('/', '').upper()
    with PRICE_LOCK:
        return LATEST_PRICES.get(norm_sym)
