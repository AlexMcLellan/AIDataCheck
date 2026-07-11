import pandas as pd
import numpy as np

def calculate_water_balance_residual(precip, et, delta_s, runoff=0.0):
    """
    Calculate the residual of the water balance equation:
    P = ET + Delta_S + Runoff + Residual
    
    Parameters:
    -----------
    precip : pd.Series
        Precipitation (mm)
    et : pd.Series
        Evapotranspiration (mm)
    delta_s : pd.Series
        Change in soil moisture storage (mm)
    runoff : pd.Series or float
        Surface runoff or deep percolation (mm)
        
    Returns:
    --------
    residual : pd.Series
    """
    residual = precip - et - delta_s - runoff
    return residual

def integrate_soil_moisture_profile(vwc_layers, depths):
    """
    Integrates Volumetric Water Content (m3/m3) over a depth profile to get 
    total water storage (mm).
    
    Parameters:
    -----------
    vwc_layers : list of pd.Series or 2D array
        VWC at each depth
    depths : list of float
        Depths (in meters) corresponding to each layer
        
    Returns:
    --------
    total_storage : pd.Series
        Total soil water storage in mm
    """
    # Assuming trapezoidal integration or simple layer thickness multiplication
    # For a simple representation, layer thickness = distance between midpoints
    # Convert meters to mm (multiply by 1000)
    
    storage = 0.0
    for i, (vwc, depth) in enumerate(zip(vwc_layers, depths)):
        if i == 0:
            thickness = depths[0] + (depths[1] - depths[0]) / 2.0
        elif i == len(depths) - 1:
            thickness = (depths[-1] - depths[-2]) / 2.0
        else:
            thickness = (depths[i] - depths[i-1]) / 2.0 + (depths[i+1] - depths[i]) / 2.0
            
        # VWC is m3/m3 (dimensionless), depth thickness in meters
        # Water amount in mm = VWC * thickness(m) * 1000(mm/m)
        storage += vwc * thickness * 1000.0
        
    return storage

import pandas as pd

def flag_rain_soil_moisture_mismatch(precip_interval, delta_s, depth_m, k_sat_cm_h, threshold_ds=5.0, rain_window='24h'):
    """
    Flags times where soil moisture spikes significantly without corresponding precipitation
    in the expected recent past, accounting for the percolation time-lag to the sensor's depth.
    
    precip_interval: The rainfall amount in the current timestep (not cumulative)
    delta_s: Change in soil moisture storage
    depth_m: Depth of the sensor in meters
    k_sat_cm_h: Saturated hydraulic conductivity in cm/h
    """
    # Calculate time-lag to reach this depth
    # Convert depth_m to cm, divide by K_sat (cm/h) to get hours
    # Note: If K_sat is very low (e.g., clay), this lag could be very long.
    depth_cm = depth_m * 100.0
    t_lag_hours = depth_cm / k_sat_cm_h if k_sat_cm_h > 0 else 0
    
    # The expected time rain would have hit the surface to arrive here NOW
    # We shift the precip_interval array forward by t_lag_hours so that past rain aligns with current time
    # Ensure the dataframe index is a datetime index
    if not isinstance(precip_interval.index, pd.DatetimeIndex):
        raise ValueError("precip_interval must have a DatetimeIndex to calculate time lag")
    
    # Shift rain forward by t_lag_hours
    # e.g., rain that fell 10 hours ago is shifted to now.
    lagged_precip = precip_interval.shift(freq=pd.Timedelta(hours=t_lag_hours))
    
    # Calculate rolling sum of lagged rain over the recent window
    # We reindex to match the original index since shifting might have altered the time alignment slightly
    # We use exact time-based rolling sum
    recent_lagged_rain = lagged_precip.reindex(precip_interval.index, method='bfill', limit=1).rolling(rain_window).sum().fillna(0)
    
    # Flag if soil moisture spikes but there was almost no lagged rain recently
    mismatch_no_rain = (delta_s > threshold_ds) & (recent_lagged_rain < 1.0)
    
    return mismatch_no_rain
