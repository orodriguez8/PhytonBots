
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

# =============================================================================
# CONFIGURACIÓN CENTRAL DEL BOT DE TRADING
# =============================================================================
# Todos los parámetros ajustables del bot están aquí.
# Modifica este archivo para cambiar el comportamiento del bot
# sin tocar el resto del código.
# =============================================================================

# --- Capital y Riesgo ---
CAPITAL_INICIAL = 10_000.0       # Capital inicial en USD
RIESGO_POR_OPERACION = 0.015      # Máximo 1.5% del capital por operación (Conservative)

# --- Modo de Trading ---
# 'ALPACA' para Acciones, 'COINBASE' para Cripto (via CCXT)
TRADING_MODE_CRYPTO = os.getenv('TRADING_MODE_CRYPTO', 'ALPACA').strip().upper()
USE_TESTNET = True               # Cambiar a False para cuenta real

# --- Conexión Alpaca ---
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY', '')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY', '')
ALPACA_PAPER = os.getenv('ALPACA_PAPER', 'True').lower() == 'true'

# Limpiar la URL base: el SDK de Alpaca ya añade '/v2' internamente.
# Si el usuario pone 'https://.../v2', se duplicaría a '.../v2/v2' fallando la conexión.
_base_env = os.getenv('ALPACA_BASE_URL', '').strip()
if not _base_env:
    ALPACA_BASE_URL = 'https://paper-api.alpaca.markets' if ALPACA_PAPER else 'https://api.alpaca.markets'
else:
    # Eliminar '/v2' o '/' al final para evitar errores de duplicación
    ALPACA_BASE_URL = _base_env.rstrip('/').replace('/v2', '')

# --- Multiplicadores ATR para Stop Loss y Take Profit ---
# Estrategia Asimétrica para ACCIONES (Trend Following)
STOCK_ATR_SL = 1.5       # Stop Loss Ajustado
STOCK_ATR_TP = 4.5       # Take Profit Largo (1:3 Risk/Reward)

# Estrategia Seguro para CRIPTO (Optimized Mean Reversion)
# Ajustamos a un ratio positivo de 1:1.4 (Win 3.5 ATR / SL 2.5 ATR)
CRYPTO_ATR_SL = 2.5
CRYPTO_ATR_TP = 3.5


# --- Vigilancia (Watchlist) ---
WATCHLIST = [
    'AAPL', 'MSFT', 'TSLA', 'META', 'AMZN', 'NVDA'
]
# Nota: Forex en Alpaca requiere permisos específicos, pero el bot ya lo soporta.

# --- Umbral de Confluencias ---
MIN_CONFLUENCIAS = 4             # Mínimo de señales alineadas para operar

# --- Parámetros de Indicadores ---
PERIODO_EMA_RAPIDA  = 20         # EMA rápida (corto plazo)
PERIODO_EMA_MEDIA   = 50         # EMA media (medio plazo)
PERIODO_EMA_LENTA   = 200        # EMA lenta (largo plazo / tendencia principal)

MACD_RAPIDO         = 12         # EMA rápida del MACD
MACD_LENTO          = 26         # EMA lenta del MACD
MACD_SIGNAL         = 9          # EMA de la línea de señal del MACD

PERIODO_RSI         = 14         # Periodos del RSI
RSI_SOBREVENTA      = 35         # Por debajo → zona de sobreventa (señal LONG)
RSI_SOBRECOMPRA     = 65         # Por encima → zona de sobrecompra (señal SHORT)

PERIODO_BOLLINGER   = 20         # Periodos de las Bandas de Bollinger
DESVIACIONES_BB     = 2.0        # Número de desviaciones estándar

PERIODO_ATR         = 14         # Periodos del ATR (mide volatilidad)
PERIODO_VOLUMEN     = 20         # Periodos del volumen medio

# --- Datos Simulados ---
N_VELAS             = 300        # Número de velas a simular (mín. 200 para EMA 200)
PRECIO_INICIAL      = 1500.0     # Precio de partida (ej: índice, oro…)
TENDENCIA           = 0.0004     # Tendencia por vela (positivo = alcista)
VOLATILIDAD         = 0.013      # Volatilidad por vela
SEMILLA_ALEATORIA   = 99         # Semilla para reproducibilidad

# --- Conexión Exchange (CCXT) ---
# Puedes cambiar el exchange sin tocar código, por ejemplo:
# CCXT_EXCHANGE_ID=coinbase | kucoin | kraken | bybit
CCXT_EXCHANGE_ID = os.getenv('CCXT_EXCHANGE_ID', 'coinbase').strip().lower()

# Variables genéricas con fallback a nombres legacy de Coinbase.
CCXT_API_KEY = os.getenv('CCXT_API_KEY', os.getenv('COINBASE_API_KEY', ''))
CCXT_SECRET_KEY = os.getenv('CCXT_SECRET_KEY', os.getenv('COINBASE_SECRET_KEY', ''))
CCXT_TESTNET = os.getenv('CCXT_TESTNET', os.getenv('COINBASE_TESTNET', 'True')).lower() == 'true'

# Alias legacy para no romper imports existentes.
COINBASE_API_KEY = CCXT_API_KEY
COINBASE_SECRET_KEY = CCXT_SECRET_KEY
COINBASE_TESTNET = CCXT_TESTNET
