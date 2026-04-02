
# =============================================================================
# PUNTO DE ENTRADA PRINCIPAL — main.py
# =============================================================================
# Ejecuta este archivo para lanzar el bot:
#
#   cd trading_bot
#   python main.py
#
# Para usar datos reales en el futuro, sustituye la llamada a
# generar_datos() por la carga de datos de tu broker o fuente de datos.
# =============================================================================

import sys
import os

# Asegurar que el directorio raíz del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.simulador   import generar_datos
from bot.trading_bot  import TradingBot
from config import (
    N_VELAS, PRECIO_INICIAL, TENDENCIA, VOLATILIDAD,
    SEMILLA_ALEATORIA, CAPITAL_INICIAL, RIESGO_POR_OPERACION,
    MIN_CONFLUENCIAS
)


def main():
    """
    Función principal de ejecución del bot.

    Pasos:
        1. Generar (o cargar) datos OHLCV
        2. Crear el bot con la configuración deseada
        3. Ejecutar un ciclo completo de análisis
        4. Mostrar instrucciones para usar datos reales
    """

    # ── PASO 1: Datos ────────────────────────────────────────────────────────
    print("\n📦 Generando datos OHLCV simulados...")
    datos = generar_datos(
        n_velas        = N_VELAS,
        precio_inicial = PRECIO_INICIAL,
        tendencia      = TENDENCIA,
        volatilidad    = VOLATILIDAD,
        semilla        = SEMILLA_ALEATORIA,
    )

    print(f"   ✅ {len(datos)} velas | "
          f"{datos.index[0].strftime('%Y-%m-%d %H:%M')} → "
          f"{datos.index[-1].strftime('%Y-%m-%d %H:%M')}")
    print(f"   Precio inicial: ${datos['close'].iloc[0]:.2f}")
    print(f"   Precio actual:  ${datos['close'].iloc[-1]:.2f}")
    cambio = (datos['close'].iloc[-1] / datos['close'].iloc[0] - 1) * 100
    print(f"   Variación:      {cambio:+.2f}%")

    # ── PASO 2: Crear y configurar el bot ─────────────────────────────────────
    bot = TradingBot(
        datos            = datos,
        capital          = CAPITAL_INICIAL,
        riesgo           = RIESGO_POR_OPERACION,
        min_confluencias = MIN_CONFLUENCIAS,
    )

    # ── PASO 3: Ejecutar ciclo de análisis ────────────────────────────────────
    bot.ejecutar()

    # ── PASO 4: Información para uso con datos reales ─────────────────────────
    sep = "=" * 60
    print(f"\n{sep}")
    print("   💡 PARA USAR CON DATOS REALES")
    print(sep)
    print("   Sustituye generar_datos() en main.py por:")
    print()
    print("   # Opción A — CSV local:")
    print("   import pandas as pd")
    print("   datos = pd.read_csv('mi_datos.csv', index_col=0, parse_dates=True)")
    print()
    print("   # Opción B — CCXT (criptomonedas):")
    print("   import ccxt")
    print("   exchange = ccxt.binance()")
    print("   ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)")
    print("   datos = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])")
    print()
    print("   # El DataFrame debe tener columnas:")
    print("   # open, high, low, close, volume")
    print(sep + "\n")


if __name__ == "__main__":
    main()
