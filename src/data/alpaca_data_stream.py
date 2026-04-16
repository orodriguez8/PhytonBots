
import multiprocessing
import asyncio
from alpaca.data.live import StockDataStream, CryptoDataStream
from src.core.config import ALPACA_API_KEY, ALPACA_SECRET_KEY
from src.core.logger import logger

# Utilizaremos un proceso separado para los WebSockets
# para evadir los bugs de bucles de asyncio causados por eventlet.
# Los precios se compartirán mediante un Manager.dict()

_manager = None
LATEST_PRICES = None

def _initialize_manager():
    global _manager, LATEST_PRICES
    if _manager is None:
        _manager = multiprocessing.Manager()
        LATEST_PRICES = _manager.dict()

async def _price_handler(data):
    try:
        sym = data.symbol.replace('/', '')
        LATEST_PRICES[sym] = float(data.price)
    except Exception as e:
        pass

def _run_stock_process(symbols, api_key, secret_key, shared_dict):
    global LATEST_PRICES
    LATEST_PRICES = shared_dict
    
    async def main():
        try:
            stream = StockDataStream(api_key, secret_key)
            stream.subscribe_trades(_price_handler, *symbols)
            await stream._run_forever()
        except Exception as e:
            logger.error(f"Error procesal WebSocket Acciones: {e}")

    asyncio.run(main())

def _run_crypto_process(symbols, api_key, secret_key, shared_dict):
    global LATEST_PRICES
    LATEST_PRICES = shared_dict
    
    async def main():
        try:
            stream = CryptoDataStream(api_key, secret_key)
            norm_crypto = [s if '/' in s else s.replace('USD', '/USD') for s in symbols]
            stream.subscribe_trades(_price_handler, *norm_crypto)
            await stream._run_forever()
        except Exception as e:
            logger.error(f"Error procesal WebSocket Cripto: {e}")

    asyncio.run(main())

class AlpacaDataStream:
    def __init__(self, symbols):
        _initialize_manager()
        self.symbols = symbols
        self.stock_symbols = [s for s in symbols if not any(q in s.upper() for q in ['USD', 'USDT', 'USDC', '/'])]
        self.crypto_symbols = [s for s in symbols if s not in self.stock_symbols]
        
    def start(self):
        if self.stock_symbols:
            p1 = multiprocessing.Process(
                target=_run_stock_process, 
                args=(self.stock_symbols, ALPACA_API_KEY, ALPACA_SECRET_KEY, LATEST_PRICES),
                daemon=True
            )
            p1.start()
        
        if self.crypto_symbols:
            p2 = multiprocessing.Process(
                target=_run_crypto_process, 
                args=(self.crypto_symbols, ALPACA_API_KEY, ALPACA_SECRET_KEY, LATEST_PRICES),
                daemon=True
            )
            p2.start()

def get_latest_price(symbol):
    if LATEST_PRICES is None: return None
    norm_sym = symbol.replace('/', '').upper()
    return LATEST_PRICES.get(norm_sym)
