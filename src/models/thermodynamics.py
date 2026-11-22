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

def calculate_vapor_pressure(temp_c):
    """
    Calculates saturation vapor pressure in kPa using Tetens formula.
    """
    return 0.61078 * np.exp((17.27 * temp_c) / (temp_c + 237.3))

def check_psychrometric_closure(temp_c, rh, measured_dp, measured_vpd=None, dp_threshold=1.0, vpd_threshold=0.15):
    """
    Redundantly verifies thermodynamic consistency between Air Temp, RH, Dew Point, and VPD.
    Flags sensor calibration drift or aspirated shield blockage.
    """
    theoretical_dp = calculate_dewpoint(temp_c, rh)
    dp_mismatch = np.abs(theoretical_dp - measured_dp) > dp_threshold
    
    if measured_vpd is not None:
        es = calculate_vapor_pressure(temp_c)
        ea = es * np.clip(rh / 100.0, 0.0, 1.0)
        expected_vpd = np.maximum(0.0, es - ea)
        vpd_mismatch = np.abs(expected_vpd - measured_vpd) > vpd_threshold
        return dp_mismatch | vpd_mismatch
        
    return dp_mismatch

def check_sonic_temperature_consistency(sonic_temp_c, air_temp_c, h2o_mole_frac=None, threshold=1.5):
    """
    Verifies consistency between ultrasonic anemometer sonic temperature (virtual temperature)
    and aspirated thermometer air temperature corrected for moisture content (Kaimal & Businger 1963).
    
    T_v = (T_air + 273.15) * (1 + 0.51 * q) - 273.15
    """
    t_air_k = air_temp_c + 273.15
    
    if h2o_mole_frac is not None:
        # Scale to mol/mol if reported in mmol/mol
        q = np.where(h2o_mole_frac > 1.0, h2o_mole_frac / 1000.0, h2o_mole_frac)
        q = np.nan_to_num(q, nan=0.01) # Default to typical 10 mmol/mol if NaN
        t_v_k = t_air_k * (1.0 + 0.51 * q)
        t_v_c = t_v_k - 273.15
    else:
        t_v_c = air_temp_c
        
    diff = np.abs(sonic_temp_c - t_v_c)
    return diff > threshold

def check_dual_station_rh(rh_primary, rh_secondary, threshold=8.0):
    """
    Dual-station atmospheric RH cross-check (e.g. Weather station HMP vs IRGA gas analyzer RH).
    """
    return np.abs(rh_primary - rh_secondary) > threshold

