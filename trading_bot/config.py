
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
RIESGO_POR_OPERACION = 0.02      # Máximo 2% del capital por operación

# --- Modo de Trading ---
# 'ALPACA' para Acciones, 'BINANCE' para Cripto (via CCXT)
TRADING_MODE_CRYPTO = 'BINANCE' 
USE_TESTNET = True               # Cambiar a False para cuenta real

# --- Multiplicadores ATR para Stop Loss y Take Profit ---
MULTIPLICADOR_ATR_SL = 1.5       # Stop Loss  = entrada ± (ATR × 1.5)
MULTIPLICADOR_ATR_TP = 3.0       # Take Profit = entrada ± (ATR × 3.0)
# → Esto da un ratio Riesgo:Beneficio de 1:2

# --- Vigilancia (Watchlist) ---
WATCHLIST = [
    'AAPL', 'TSLA', 'NVDA', 'MSFT', 'AMZN', 'META', # Acciones (Alpaca)
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT' # Cripto (Binance)
]
# Nota: Forex en Alpaca requiere permisos específicos, pero el bot ya lo soporta.

# --- Umbral de Confluencias ---
MIN_CONFLUENCIAS = 3             # Mínimo de señales alineadas para operar

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

# --- Conexión Oanda (Legacy) ---
# Estos valores actúan como fallback si no se definen en el archivo .env o en HF Secrets
OANDA_INSTRUMENT    = os.getenv('OANDA_INSTRUMENT', 'EUR_USD')  # Par a operar
OANDA_GRANULARITY   = os.getenv('OANDA_GRANULARITY', 'H1')       # Temporalidad
OANDA_ENVIRONMENT   = os.getenv('OANDA_ENVIRONMENT', 'practice') # 'practice' o 'live'

# --- Conexión Binance (CCXT) ---
BINANCE_API_KEY     = os.getenv('BINANCE_API_KEY', '')
BINANCE_SECRET_KEY  = os.getenv('BINANCE_SECRET_KEY', '')
BINANCE_TESTNET     = os.getenv('BINANCE_TESTNET', 'True').lower() == 'true'
