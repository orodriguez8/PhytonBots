
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.getcwd())

load_dotenv()

from src.execution.alpaca_client import obtener_posiciones_cerradas

def test():
    try:
        data = obtener_posiciones_cerradas()
        print(f"Closed: {len(data.get('closed', []))}")
        print(f"Opened: {len(data.get('opened', []))}")
        for c in data.get('closed', [])[:5]:
            print(f"Closed trade: {c['s']} {c['side']} PL: {c['pl']}")
        for o in data.get('opened', [])[:5]:
            print(f"Opened/Entry: {o['s']} {o['side']} Q: {o['q']}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
