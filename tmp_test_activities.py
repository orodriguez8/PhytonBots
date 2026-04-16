
import os
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL')

def test():
    api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_BASE_URL, api_version='v2')
    activities = api.get_activities(activity_types=['FILL'], page_size=20)
    for f in activities:
        print(f"Symbol: {f.symbol}, Side: {f.side}, Qty: {f.qty}, Price: {f.price}, Time: {f.transaction_time}, OrderID: {getattr(f, 'order_id', 'N/A')}")

if __name__ == "__main__":
    test()
