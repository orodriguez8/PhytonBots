
import pandas as pd
import pandas_ta_classic as ta

def calcular_obv(df: pd.DataFrame) -> pd.Series:
    """Calcula el On-Balance Volume (OBV)."""
    return ta.obv(df['close'], df['volume'])
