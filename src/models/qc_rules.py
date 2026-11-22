import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

BATTERY_THRESHOLDS = {
    'lead_acid': 11.9,
    'lifepo4': 12.8,
    'agm': 11.8,
    'gel': 11.9
}

def check_statistical_anomalies(series, window_minutes=180, z_thresh=5.0):
    """
    Applies generic statistical trend analysis to a time-series.
    Returns boolean masks for 'spikes', 'jumps', and 'flatlines'.
    """
    flags_spike = pd.Series(False, index=series.index)
    flags_jump = pd.Series(False, index=series.index)
    flags_flatline = pd.Series(False, index=series.index)
    
    if len(series.dropna()) < window_minutes:
        return flags_spike, flags_jump, flags_flatline
        
    # 1. Z-Score Spikes
    rolling_mean = series.rolling(window=window_minutes, min_periods=window_minutes//2, center=True).mean()
    rolling_std = series.rolling(window=window_minutes, min_periods=window_minutes//2, center=True).std()
    
    # Avoid division by zero
    rolling_std = rolling_std.replace(0, np.nan)
    z_scores = ((series - rolling_mean) / rolling_std).abs()
    flags_spike = (z_scores > z_thresh).fillna(False)
    
    # 2. Gradient (Rate of Change) Jump
    diffs = series.diff().abs()
    if diffs.notna().sum() > 0:
        # Exclude exact zeros from percentile calculation to avoid a 0.0 threshold on step-functions
        non_zero_diffs = diffs[diffs > 0]
        if not non_zero_diffs.empty:
            max_jump_threshold = non_zero_diffs.quantile(0.999)
            # We also require the jump to be at least larger than the standard deviation
            # to avoid flagging tiny jumps in highly stable sensors.
            overall_std = series.std()
            flags_jump = (diffs > max_jump_threshold) & (diffs > overall_std)
    
    # 3. Flatline Detection
    # Check if a 6-hour rolling std is exactly 0.0
    flat_window = 360  # 6 hours in minutes
    rolling_std_6h = series.rolling(window=flat_window, min_periods=flat_window).std()
    flags_flatline = (rolling_std_6h == 0.0).fillna(False)
    
    return flags_spike, flags_jump, flags_flatline

def check_time_continuity(time_index, expected_freq='30min'):
    """
    Flags gaps in the time index that are larger than the expected frequency.
    """
    diffs = time_index.to_series().diff()
    expected_delta = pd.to_timedelta(expected_freq)
    
    # Flag True if the gap is strictly greater than expected
    # (the first element will be NaT, so fill with False)
    flags = (diffs > expected_delta).fillna(False)
    return flags.values

def check_battery(batt_v, measured_sw_in, threshold_v=11.5, sw_in_threshold=200):
    """
    Flags if battery voltage drops significantly while measured solar input is high.
    (indicates panel disconnected, dirt, or battery failure).
    """
    # Flag if voltage is below threshold AND the solar panel is actively receiving light
    flags = (batt_v < threshold_v) & (measured_sw_in > sw_in_threshold)
    return flags

def check_battery_trend(batt_v, expected_ghi, chemistry='lifepo4', output_dir='.'):
    """
    Checks if the overnight battery voltage is trending down.
    Generates a plot estimating days until failure.
    Returns a boolean mask. True = critical failure imminent (< 7 days).
    """
    threshold = BATTERY_THRESHOLDS.get(chemistry.lower(), 11.9)
    flags = pd.Series(False, index=batt_v.index)
    
    # Use < 5 W/m2 since clear sky models rarely hit exactly 0.0
    overnight = batt_v[expected_ghi < 5]
    if overnight.empty:
        return flags
        
    daily_min = overnight.resample('D').min().dropna()
    
    if len(daily_min) < 3:
        return flags
        
    # Fit a linear trend to the last 14 days (or less if not enough data)
    recent_min = daily_min.iloc[-14:]
    x = (recent_min.index - recent_min.index[0]).days.values
    y = recent_min.values
    
    # Only fit if we have more than 1 point to avoid RankWarning
    if len(x) > 1:
        m, c = np.polyfit(x, y, 1)
    else:
        m, c = 0, y[0]
    
    # Calculate days until failure
    days_until_fail = np.inf
    if m < 0:
        days_from_start = (threshold - c) / m
        days_until_fail = days_from_start - x[-1]
        
    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(daily_min.index, daily_min.values, marker='o', label='Daily Overnight Min Voltage')
    
    # Plot the trendline for the recent period and extrapolate
    if m < 0 and days_until_fail < 60:
        # Extrapolate up to the failure point or 60 days
        extrap_x = np.linspace(x[0], x[-1] + days_until_fail, 50)
        extrap_dates = [recent_min.index[0] + pd.Timedelta(days=d) for d in extrap_x]
        extrap_y = m * extrap_x + c
        plt.plot(extrap_dates, extrap_y, 'r--', label=f'Trend (Fails in {int(days_until_fail)} days)')
    elif m < 0:
        extrap_x = np.linspace(x[0], x[-1] + 30, 50)
        extrap_dates = [recent_min.index[0] + pd.Timedelta(days=d) for d in extrap_x]
        extrap_y = m * extrap_x + c
        plt.plot(extrap_dates, extrap_y, 'r--', label='Trend (Stable/Slow drop)')
    else:
        extrap_x = np.linspace(x[0], x[-1], 50)
        extrap_dates = [recent_min.index[0] + pd.Timedelta(days=d) for d in extrap_x]
        extrap_y = m * extrap_x + c
        plt.plot(extrap_dates, extrap_y, 'g--', label='Trend (Charging/Stable)')
        
    plt.axhline(threshold, color='red', linestyle='-', alpha=0.3, label=f'Critical Threshold ({threshold}V)')
    
    plt.title(f'Battery Longterm Trend Analysis ({chemistry.capitalize()})')
    plt.ylabel('Voltage (V)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'battery_trend.png'))
    plt.close()
    
    # Flag the entire dataset if failure is imminent (< 7 days)
    if 0 < days_until_fail <= 7:
        flags[:] = True
        
    return flags

def check_uncorrected_longwave(lw_in, threshold_w_m2=50):
    """
    Flags if the longwave radiation is unphysically low (e.g. < 50 W/m2).
    This indicates the datalogger output raw thermopile values without adding the body temperature (sigma * T^4).
    """
    # True if lw_in is extremely low and not NaN
    return (lw_in < threshold_w_m2) & lw_in.notna()

def check_solar_radiation_bounds(measured_sw_in, expected_ghi):
    """
    Flags if the measured solar radiation significantly exceeds the theoretical clear-sky maximum.
    Allows a 20% buffer for cloud-edge focusing/refraction.
    """
    # Only check during daylight when expected_ghi is meaningful
    is_day = expected_ghi > 10
    return is_day & (measured_sw_in > (expected_ghi * 1.20))

def check_nighttime_shortwave(measured_sw, expected_ghi, noise_threshold=5):
    """
    Flags if the measured shortwave radiation exceeds a noise threshold during the night.
    """
    is_night = expected_ghi < 5
    return is_night & (measured_sw.abs() > noise_threshold)

def check_fan_speed(rpm, sw_in, rpm_threshold=100, sw_in_threshold=500):
    """
    Flags if the aspirated fan speed drops below a threshold when solar radiation is high,
    meaning air temp/RH readings might be artificially high due to heating.
    """
    flags = (rpm < rpm_threshold) & (sw_in > sw_in_threshold)
    return flags

def check_albedo(sw_in, sw_out, min_albedo=0.05, max_albedo=0.95):
    """
    Flags an invalid albedo. 
    Requires some meaningful SW incoming radiation to avoid division by near-zero.
    """
    valid_sw = sw_in > 10.0
    albedo = np.where(valid_sw, sw_out / sw_in, np.nan)
    
    # Flag if out of bounds (ignore NaNs)
    flags = valid_sw & ((albedo < min_albedo) | (albedo > max_albedo))
    return flags

def check_shfp_status(fail_flag_1, fail_flag_2):
    """
    Flags soil heat flux plates if either calibration flag is active (1).
    """
    flags = (fail_flag_1 == 1) | (fail_flag_2 == 1)
    return flags

def check_soil_ec_spikes(ec_series, threshold=50):
    """
    Flags sudden spikes in Electrical Conductivity (EC) which shouldn't happen 
    without heavy water flow.
    Uses absolute rolling diff.
    """
    diffs = ec_series.diff().abs()
    flags = diffs > threshold
    return flags.fillna(False)

def check_par_ratio(ppfd, sw_in, min_ratio=1.8, max_ratio=2.4):
    """
    Flags if PAR (PPFD) to Shortwave Incoming ratio is outside physical bounds
    (typically ~2.1 umol/J during daylight).
    """
    valid_sw = sw_in > 50.0
    ratio = np.where(valid_sw, ppfd / sw_in, np.nan)
    flags = valid_sw & ((ratio < min_ratio) | (ratio > max_ratio))
    return flags

def check_ndvi_alignment(angle_offset, threshold=5.0):
    """
    Flags if the NDVI sensor tilt deviates from horizontal (assuming 0 is ideal, 
    or check against installed base value if known).
    """
    # Absolute deviation from 0 degrees (assuming 0 is level)
    # If the default is ~180 (as in some sensors), need to adjust.
    # The artifact said "deviates from installed level". We'll flag > threshold.
    # From data preview, S2412_angle_offset was ~178.
    # We will flag if it deviates by more than `threshold` from 180.
    flags = np.abs(angle_offset - 180.0) > threshold
    return flags

def check_ir_temp_consistency(t_min, t_avg, t_max):
    """
    Flags if Min > Avg or Avg > Max.
    """
    return (t_min > t_avg) | (t_avg > t_max)

def check_body_temp(body_temp, air_temp, threshold=15.0):
    """
    Flags if a sensor body temperature deviates massively from air temperature.
    """
    return np.abs(body_temp - air_temp) > threshold

def check_soil_temp_redundancy(t_teros, t_tdr, threshold=2.0):
    """
    Flags periods where two soil temperature sensors at the same depth differ significantly.
    """
    return (t_teros - t_tdr).abs() > threshold

def check_soil_vwc_redundancy(vwc_tdr, vwc_soilvue, threshold=0.15):
    """
    Flags periods where TDR and SoilVUE volumetric water contents diverge beyond a threshold.
    Standardizes units to volumetric fraction (0.0 - 1.0).
    """
    # Normalize TDR to fraction if reported in percentage (0 - 100)
    tdr_frac = np.where(vwc_tdr > 1.0, vwc_tdr / 100.0, vwc_tdr)
    soilvue_frac = np.where(vwc_soilvue > 1.0, vwc_soilvue / 100.0, vwc_soilvue)
    
    diff = np.abs(tdr_frac - soilvue_frac)
    return pd.Series(diff > threshold, index=getattr(vwc_tdr, 'index', None))

def check_soil_temp_3way(t_teros, t_tdr, t_soilvue, threshold=3.0):
    """
    Triple redundancy temperature check. Flags if the maximum spread between
    TEROS22, TDR310, and SoilVUE10 exceeds the threshold.
    """
    df_temp = pd.concat([t_teros, t_tdr, t_soilvue], axis=1)
    spread = df_temp.max(axis=1) - df_temp.min(axis=1)
    return spread > threshold

def check_shfp_thermal_gradient_mismatch(g_measured, g_theory, threshold=50.0):
    """
    Check if measured SHFP drastically mismatches theoretical gradient flux.
    Both should generally have the same sign (heat going same direction).
    Since theoretical lambda is an approximation, we flag extreme differences (e.g. > 50 W/m2).
    """
    diff = (g_measured - g_theory).abs()
    return diff > threshold

def check_permittivity(perm, min_p=1.0, max_p=80.0):
    """
    Flags physically impossible permittivity values.
    """
    return (perm < min_p) | (perm > max_p)

def check_static_calibration(cal_series, threshold=1e-3):
    """
    Flags if a calibration coefficient changes (non-zero variance over a short window).
    """
    diffs = cal_series.diff().abs()
    return diffs > threshold

def check_precip_consistency(precip_tot, precip_int):
    """
    Flags if Total Precipitation increases but Intensity is zero.
    """
    tot_diff = precip_tot.diff()
    return (tot_diff > 0) & (precip_int <= 0)

def check_radiation_redundancy(rad_1, rad_2, threshold=50.0):
    """
    Flags if secondary radiation measurements disagree with primary.
    """
    return np.abs(rad_1 - rad_2) > threshold

def check_dynamic_solar_bounds(measured_sw, expected_ghi, weather_codes):
    """
    Applies dynamic bounding based on the Met Office weather code.
    Code 1 = Sunny (lower bound = 70% expected).
    Code 8 = Overcast (upper bound = 40% expected).
    """
    flags = pd.Series(False, index=measured_sw.index)
    
    # Only check during daylight when expected_ghi is meaningful
    is_day = expected_ghi > 10
    
    # Sunny: lower bound check
    is_sunny = weather_codes == 1
    flags.loc[is_day & is_sunny] = measured_sw[is_day & is_sunny] < (expected_ghi[is_day & is_sunny] * 0.70)
    
    # Overcast: upper bound check
    is_overcast = weather_codes == 8
    flags.loc[is_day & is_overcast] = measured_sw[is_day & is_overcast] > (expected_ghi[is_day & is_overcast] * 0.40)
    
    return flags

def check_matric_potential_decoupling(mp_series, vwc_series=None, decoupling_threshold_kpa=-200.0, vwc_threshold=0.08):
    """
    Unified Physical Check for Tensiometer Hydraulic Decoupling:
    
    Flags periods where the tensiometer (TEROS 22) loses hydraulic continuity with the soil matrix.
    Physical signature:
    - Matric suction is elevated (|ψ| >= |decoupling_threshold_kpa|)
    - AND soil moisture has dropped into the dry range (VWC <= vwc_threshold) or tensiometer rate-of-change stalls (dψ/dt ~ 0).
    
    This naturally captures both premature contact loss at intermediate suctions (-200 to -400 kPa)
    and datalogger/ceramic saturation ceilings (-750 to -850 kPa) under a single physical framework.
    
    Parameters:
    -----------
    mp_series : pd.Series
        Matric potential time-series in kPa (typically negative).
    vwc_series : pd.Series, optional
        Volumetric water content series (0.0 to 1.0 or 0 to 100%).
    decoupling_threshold_kpa : float
        Suction threshold where hydraulic contact loss can initiate (default -200 kPa).
    vwc_threshold : float
        Volumetric water content below which soil matrix contact breaks (default 0.08 m³/m³).
        
    Returns:
    --------
    flags_decoupled : pd.Series (bool)
        True where physical hydraulic decoupling / contact loss is detected.
    """
    flags_decoupled = pd.Series(False, index=mp_series.index)
    mp_clean = mp_series.dropna()
    
    if mp_clean.empty:
        return flags_decoupled
        
    # 1. High suction condition
    high_suction = (mp_series <= decoupling_threshold_kpa)
    
    # 2. Dynamic decoupling signature
    if vwc_series is not None:
        vwc_norm = vwc_series if vwc_series.max() <= 1.0 else vwc_series / 100.0
        
        # Check if tensiometer has plateaued/stalled
        if isinstance(mp_series.index, pd.DatetimeIndex):
            rolling_mp_std = mp_series.rolling('6h', min_periods=6).std()
        else:
            rolling_mp_std = mp_series.rolling(window=min(len(mp_series), 6), min_periods=1).std()
            
        mp_stalled = (rolling_mp_std < 5.0).fillna(False)
        vwc_dry = (vwc_norm <= vwc_threshold)
        
        flags_decoupled = high_suction & (mp_stalled | vwc_dry)
    else:
        flags_decoupled = high_suction
        
    return flags_decoupled

