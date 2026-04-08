
import sys
import os
sys.path.append(os.getcwd())

from src.execution.alpaca_client import _get_api, obtener_posiciones_cerradas

def debug():
    try:
        api = _get_api()
        print("--- Diagnosticando Alpaca Activities ---")
        tipos = ['FILL']
        # Usamos los parametros que pusimos en el fix
        activities = api.get_activities(activity_types=tipos, page_size=50)
        print(f"Total actividades crudas recibidas: {len(activities)}")
        
        for i, f in enumerate(activities[:5]):
            print(f"Actividad {i}: Symbol={getattr(f, 'symbol', 'N/A')}, Side={getattr(f, 'side', 'N/A')}, Type={f.activity_type}, Time={getattr(f, 'transaction_time', 'N/A')}")

        result = obtener_posiciones_cerradas()
        print(f"\nResultado de obtener_posiciones_cerradas: {len(result)} items")
        for r in result:
            print(r)

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    debug()
