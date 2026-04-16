
import pandas as pd
import pandas_ta_classic as ta
import warnings

def calcular_vwap(df: pd.DataFrame) -> pd.Series:
    """Calcula el VWAP (Volume Weighted Average Price) intradía."""
    # pandas_ta vwap require anchor (D for day)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        return ta.vwap(df['high'], df['low'], df['close'], df['volume'], anchor="D")
