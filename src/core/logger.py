
import logging

def setup_logger(name=__name__):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(name)

logger = setup_logger("TradingBot")
