
import pandas as pd
import pandas_ta_classic as ta

def calcular_vwap(df: pd.DataFrame) -> pd.Series:
    """Calcula el VWAP (Volume Weighted Average Price) intradía."""
    # pandas_ta vwap require anchor (D for day)
    return ta.vwap(df['high'], df['low'], df['close'], df['volume'], anchor="D")
