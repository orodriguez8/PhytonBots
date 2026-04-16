
import os
import json
from dotenv import load_dotenv
try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None

# Detect project root for absolute .env loading
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, '.env'))

def get_aws_secret(secret_name="secretAPI", region_name="eu-north-1"):
    """
    Intenta obtener secretos de AWS Secrets Manager si no están en entorno.
    """
    if not boto3:
        return {}
    
    # Si ya tenemos las llaves principales en el entorno, no necesitamos AWS
    if os.getenv('ALPACA_API_KEY') and os.getenv('ALPACA_SECRET_KEY'):
        return {}
        
    try:
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in get_secret_value_response:
            return json.loads(get_secret_value_response['SecretString'])
    except Exception as e:
        # Fallback silencioso si no hay permisos de IAM o no existe el secreto
        return {}
    return {}

# Fusionar secretos de AWS en el entorno si no están presentes
aws_secrets = get_aws_secret()
for key, value in aws_secrets.items():
    if not os.getenv(key):
        os.environ[key] = str(value)
        # Sincronizar también el SDK de Alpaca que usa variables específicas
        if key == 'ALPACA_API_KEY' and not os.getenv('APCA_API_KEY_ID'):
            os.environ['APCA_API_KEY_ID'] = str(value)
        if key == 'ALPACA_SECRET_KEY' and not os.getenv('APCA_API_SECRET_KEY'):
            os.environ['APCA_API_SECRET_KEY'] = str(value)

# =============================================================================
# CONFIGURACIÓN CENTRAL DEL BOT DE TRADING
# =============================================================================
# Todos los parámetros ajustables del bot están aquí.
# Modifica este archivo para cambiar el comportamiento del bot
# sin tocar el resto del código.
# =============================================================================

# --- Seguridad ---
# Si se establece una contraseña, el dashboard la solicitará para Start/Stop
BOT_PASSWORD        = os.getenv('BOT_PASSWORD', '').strip()

# --- Capital y Riesgo ---
CAPITAL_INICIAL = 10_000.0       # Capital inicial en USD
RIESGO_POR_OPERACION = 0.01      # Riesgo estándar para Acciones (1%)
RIESGO_CRYPTO        = 0.02      # Riesgo moderado para Cripto (2%)
CRYPTO_TRADING_ENABLED = False    # Desactiva el trading de cryptos sin borrar el código

# --- Modo de Trading ---
# 'ALPACA' para Acciones (Alpaca)
# 'OANDA' para Forex/CFDs (Oanda)
# 'CRYPTO' para Cripto (via CCXT/Coinbase)
TRADING_PROVIDER = os.getenv('TRADING_PROVIDER', 'ALPACA').strip().upper()

# Legacy fallback support
TRADING_MODE_CRYPTO = TRADING_PROVIDER # Para no romper compatibilidad donde se use esta variable
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

# --- Conexión Oanda ---
OANDA_API_KEY = os.getenv('OANDA_API_KEY', '')
OANDA_ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID', '')
OANDA_ENVIRONMENT = os.getenv('OANDA_ENVIRONMENT', 'practice') # 'practice' o 'live'
OANDA_INSTRUMENT = os.getenv('OANDA_INSTRUMENT', 'EUR_USD')
OANDA_GRANULARITY = os.getenv('OANDA_GRANULARITY', 'M1')

# --- Multiplicadores ATR para Stop Loss y Take Profit ---
# Estrategia Asimétrica para ACCIONES (Trend Following)
STOCK_ATR_SL = 1.8       # Stop Loss flexible (1.8x ATR)
STOCK_ATR_TP = 3.0       # Take Profit 1:1.66 Risk/Reward — más alcanzable

# Estrategia Equilibrada para CRIPTO (Basado en volatilidad)
CRYPTO_ATR_SL = 2.0      # Stop Loss por debajo de oscilaciones (2.0x ATR)
CRYPTO_ATR_TP = 2.5      # Take Profit 1:1.25 Risk/Reward (2.5x ATR)


# --- Vigilancia (Watchlist) ---
WATCHLIST = [
    # --- Acciones más Líquidas (U.S. & ADRs) ---
    'NVDA', 'TSLA', 'AAPL', 'AMD', 'AMZN', 'MSFT', 'META', 'GOOGL', 'NFLX', 'PLTR',
    'AVGO', 'SMCI', 'BABA', 'NIO', 'COIN', 'MSTR', 'MARA', 'ARM', 'MU', 'PYPL',
    'SQ', 'JPM', 'BAC', 'DIS', 'COST', 'WMT', 'LLY', 'UNH', 'V', 'MA',
    
    # --- Criptomonedas (vía CCXT/Coinbase) ---
    'BTC/USD', 'ETH/USD', 'SOL/USD', 'LTC/USD', 'LINK/USD', 'DOT/USD'
]
# Nota: Forex en Alpaca requiere permisos específicos, pero el bot ya lo soporta.

# --- Umbral de Confluencias ---
MIN_CONFLUENCIAS = 5.5           # Umbral reducido para scalping (Más señales)

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
