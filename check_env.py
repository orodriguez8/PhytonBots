import os
from dotenv import load_dotenv
load_dotenv()
print(f"ALPACA_API_KEY: {'[SET]' if os.getenv('ALPACA_API_KEY') else '[EMPTY]'}")
print(f"APCA_API_KEY_ID: {'[SET]' if os.getenv('APCA_API_KEY_ID') else '[EMPTY]'}")
print(f"Working Directory: {os.getcwd()}")
