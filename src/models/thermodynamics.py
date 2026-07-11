import numpy as np

def calculate_dewpoint(temp_c, rh):
    """
    Calculates the theoretical dew point temperature using the Magnus-Tetens formula.
    
    Parameters:
    -----------
    temp_c : pd.Series or float
        Air temperature in Celsius.
    rh : pd.Series or float
        Relative humidity in percent (0-100).
        
    Returns:
    --------
    dewpoint_c : pd.Series or float
        Dew point temperature in Celsius.
    """
    # Constants for Magnus-Tetens formula
    a = 17.27
    b = 237.3
    
    # Ensure RH is not 0 to avoid log(0)
    rh_frac = np.clip(rh / 100.0, 1e-6, 1.0)
    
    alpha = ((a * temp_c) / (b + temp_c)) + np.log(rh_frac)
    
    dewpoint_c = (b * alpha) / (a - alpha)
    return dewpoint_c

def check_dewpoint(temp_c, rh, measured_dp, threshold=1.0):
    """
    Returns a boolean mask where the measured dewpoint deviates from 
    the theoretical dewpoint by more than `threshold` degrees.
    """
    theoretical_dp = calculate_dewpoint(temp_c, rh)
    
    # Allow some NaN propagation natively
    mask = np.abs(theoretical_dp - measured_dp) > threshold
    return mask
