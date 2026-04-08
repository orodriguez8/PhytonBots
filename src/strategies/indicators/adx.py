
import pandas as pd
import pandas_ta_classic as ta

def calcular_adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Calcula el Average Directional Index (ADX) usando pandas_ta."""
    adx_df = ta.adx(df['high'], df['low'], df['close'], length=length)
    if adx_df is not None:
        return adx_df[f'ADX_{length}']
    return pd.Series(0, index=df.index)
