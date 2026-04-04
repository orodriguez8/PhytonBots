
import numpy as np

def safe_float(val, ndigits=2):
    """Safe float conversion — handles None, NaN, and numpy types."""
    try:
        if val is None:
            return 0.0
        if isinstance(val, (float, np.floating)) and np.isnan(val):
            return 0.0
        return round(float(val), ndigits)
    except Exception:
        return 0.0
