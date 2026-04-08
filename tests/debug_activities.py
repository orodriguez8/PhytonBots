
import sys
import os
sys.path.append(os.getcwd())

from src.execution.alpaca_client import _get_api, obtener_posiciones_cerradas

def debug():
    try:
        api = _get_api()
        print("--- Diagnosticando Alpaca Activities ---")
        tipos = ['FILL']
        activities = api.get_activities(activity_types=tipos, page_size=50)
        print(f"Total actividades crudas recibidas: {len(activities)}")
        
        result = obtener_posiciones_cerradas()
        print(f"\nResultado de obtener_posiciones_cerradas: {len(result)} items")
        for r in result:
            print(r)

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    debug()
