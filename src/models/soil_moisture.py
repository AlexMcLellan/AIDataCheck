import numpy as np
import pandas as pd
from scipy.optimize import curve_fit

# Typical van Genuchten parameters for USDA soil texture classes (Carsel and Parrish, 1988)
# Returns a tuple of 7 parameters:
# 1. theta_r: Residual volumetric water content (cm^3/cm^3)
# 2. theta_s: Saturated volumetric water content (cm^3/cm^3)
# 3. alpha: Parameter related to the inverse of the air entry suction (1/cm)
# 4. n: Pore-size distribution index (dimensionless)
# 5. K_sat: Saturated Hydraulic Conductivity (cm/h). Used as a proxy for 
#           gravity-driven percolation velocity of a wetting front.
# 6. rho_b: Bulk Density (g/cm^3). Estimated typical value for texture.
# 7. q: Quartz fraction (dimensionless). Estimated typical value for texture.
SOIL_PARAMS = {
    'sand': (0.045, 0.430, 0.145, 2.68, 29.70, 1.55, 0.90),
    'loamy_sand': (0.057, 0.410, 0.124, 2.28, 14.59, 1.50, 0.80),
    'sandy_loam': (0.065, 0.410, 0.075, 1.89, 4.42, 1.45, 0.65),
    'loam': (0.078, 0.430, 0.036, 1.56, 1.04, 1.40, 0.40),
    'silt_loam': (0.067, 0.450, 0.020, 1.41, 0.45, 1.35, 0.15),
    'sandy_clay_loam': (0.100, 0.390, 0.059, 1.48, 1.31, 1.40, 0.55),
    'clay_loam': (0.095, 0.410, 0.019, 1.31, 0.26, 1.35, 0.25),
    'silty_clay_loam': (0.089, 0.430, 0.010, 1.23, 0.07, 1.30, 0.10),
    'sandy_clay': (0.100, 0.380, 0.027, 1.23, 0.12, 1.35, 0.50),
    'silty_clay': (0.070, 0.360, 0.005, 1.09, 0.02, 1.25, 0.05),
    'clay': (0.068, 0.380, 0.008, 1.09, 0.20, 1.20, 0.15)
}

def get_soil_params(soil_type):
    """Returns (theta_r, theta_s, alpha, n, k_sat) for a given soil type string."""
    # Default to silt_loam if not found
    return SOIL_PARAMS.get(soil_type.lower().replace('-', '_').replace(' ', '_'), SOIL_PARAMS['silt_loam'])

def van_genuchten(h, theta_r, theta_s, alpha, n):
    """
    Van Genuchten (1980) equation for soil water retention.
    
    Parameters:
    -----------
    h : array_like
        Matric potential (often negative pressure head, here we assume positive magnitude for calculation)
    theta_r : float
        Residual volumetric water content
    theta_s : float
        Saturated volumetric water content
    alpha : float
        Parameter related to the inverse of the air entry suction (cm^-1 or kPa^-1)
    n : float
        Pore-size distribution index
        
    Returns:
    --------
    theta : array_like
        Volumetric water content
    """
    m = 1 - (1 / n)
    
    # Avoid division by zero or invalid powers
    h_abs = np.abs(h)
    
    # Calculate effective saturation
    se = (1 + (alpha * h_abs)**n)**(-m)
    
    # Calculate theta
    theta = theta_r + (theta_s - theta_r) * se
    
    return theta

def fit_van_genuchten(matric_potential, vwc, p0=None, bounds=None):
    """
    Fit the Van Genuchten curve to observed matric potential and volumetric water content data.
    
    Parameters:
    -----------
    matric_potential : array_like
        Observed matric potential values (e.g. from TEROS 22)
    vwc : array_like
        Observed volumetric water content values (e.g. from TDRs)
    p0 : list, optional
        Initial guess for the parameters (theta_r, theta_s, alpha, n)
    bounds : tuple, optional
        Bounds for the parameters
        
    Returns:
    --------
    popt : array
        Fitted parameters (theta_r, theta_s, alpha, n)
    """
    # Filter out NaNs
    mask = ~np.isnan(matric_potential) & ~np.isnan(vwc)
    h_data = np.abs(matric_potential[mask])
    theta_data = vwc[mask]
    
    if p0 is None:
        p0 = [0.05, 0.5, 0.01, 1.5] # Default generic guess
        
    if bounds is None:
        bounds = (
            [0.0, 0.2, 0.0001, 1.001], # Lower bounds
            [0.2, 1.0, 1.0, 10.0]      # Upper bounds
        )
        
    try:
        popt, pcov = curve_fit(van_genuchten, h_data, theta_data, p0=p0, bounds=bounds)
        return popt
    except RuntimeError:
        return None

def pdi_model(h, theta_s, theta_r, alpha, n, h0=1e6):
    """
    Peters-Durner-Iden (PDI) Soil Water Retention Model (Peters, 2013; Iden & Durner, 2014).
    Unifies capillary water retention and adsorptive water films across the entire suction range,
    ensuring water content reaches zero at oven-dryness (h0 = 10^6 cm).
    
    Parameters:
    -----------
    h : array_like
        Matric suction head (cm)
    theta_s : float
        Saturated volumetric water content (m3/m3)
    theta_r : float
        Maximum adsorptive (film) water capacity (m3/m3)
    alpha : float
        Inverse air-entry suction (1/cm)
    n : float
        Pore-size distribution index
    h0 : float, optional
        Suction at oven-dryness (default 1e6 cm = 10^5 kPa = pF 6.8)
        
    Returns:
    --------
    theta : array_like
        Volumetric water content (m3/m3)
    """
    h_abs = np.abs(h)
    m = 1.0 - (1.0 / n)
    
    # 1. Truncated Capillary Saturation Sc(h)
    gamma_h = (1.0 + (alpha * h_abs)**n)**(-m)
    gamma_h0 = (1.0 + (alpha * h0)**n)**(-m)
    Sc = np.clip((gamma_h - gamma_h0) / (1.0 - gamma_h0), 0.0, 1.0)
    
    # 2. Adsorptive Film Saturation Sa(h) (Linear adsorption from air-entry ha to oven-dryness h0)
    ha = 1.0 / np.maximum(alpha, 1e-6)
    Sa = np.where(
        h_abs <= ha,
        1.0,
        np.clip(np.log(h0 / np.maximum(h_abs, 1e-6)) / np.log(h0 / ha), 0.0, 1.0)
    )
    
    # Total VWC: theta(h) = (theta_s - theta_r) * Sc(h) + theta_r * Sa(h)
    return (theta_s - theta_r) * Sc + theta_r * Sa

def fit_pdi(h_data, theta_data, p0=None, bounds=None, h0=1e6):
    """
    Fit the Peters-Durner-Iden (PDI) curve to observed matric suction and volumetric water content data.
    """
    mask = ~np.isnan(h_data) & ~np.isnan(theta_data)
    h_clean = np.abs(h_data[mask])
    theta_clean = theta_data[mask]
    
    if p0 is None:
        p0 = [max(theta_clean.max(), 0.30), 0.05, 0.01, 1.5]
    if bounds is None:
        bounds = (
            [0.15, 0.0, 0.00005, 1.05],
            [0.60, 0.30, 1.0, 10.0]
        )
    try:
        popt, _ = curve_fit(
            lambda h, ts, tr, a, n: pdi_model(h, ts, tr, a, n, h0=h0),
            h_clean, theta_clean, p0=p0, bounds=bounds, maxfev=5000
        )
        return popt
    except Exception:
        return None

def check_topp_permittivity_consistency(vwc, permittivity, threshold=0.035):
    """
    Validates Volumetric Water Content (VWC) against raw apparent dielectric permittivity (Ka)
    using the universal empirical polynomial of Topp et al. (1980):
    theta = -0.053 + 0.0292*Ka - 5.5e-4*Ka^2 + 4.3e-6*Ka^3
    
    Flags probe firmware calculation errors, air gaps, or organic/high-salinity dielectric distortions.
    """
    vwc_frac = np.where(vwc > 1.0, vwc / 100.0, vwc)
    ka = np.clip(permittivity, 1.0, 80.0)
    
    # Calculate theoretical VWC from permittivity
    theta_topp = -0.053 + (0.0292 * ka) - (5.5e-4 * (ka**2)) + (4.3e-6 * (ka**3))
    theta_topp = np.clip(theta_topp, 0.0, 0.65)
    
    diff = np.abs(vwc_frac - theta_topp)
    valid = vwc.notna() & permittivity.notna() & (permittivity >= 2.0)
    return pd.Series(valid & (diff > threshold), index=getattr(vwc, 'index', None)).fillna(False)

def check_hilhorst_pore_water_ec(bulk_ec, permittivity, pore_ec, soil_temp_c, e0=4.1):
    """
    Validates reported pore-water electrical conductivity (PEC) against theoretical
    Hilhorst (2000) dielectric conversion model:
    PEC_theo = (eps_water(T) * bulk_ec) / (permittivity - e0)
    """
    # Water permittivity as a function of temperature (Weast, 1986)
    eps_w = 80.1 - (0.35 * (soil_temp_c - 20.0))
    denom = np.maximum(0.5, permittivity - e0)
    
    pec_theo = (eps_w * bulk_ec) / denom
    
    # Only validate when soil is moist enough for pore water continuity (permittivity >= 6.0)
    valid = (permittivity >= 6.0) & (bulk_ec > 0.01) & pore_ec.notna() & (pore_ec > 0)
    ratio = np.where(valid, pore_ec / np.maximum(pec_theo, 1e-4), 1.0)
    
    # Flag if reported pore EC deviates by more than a factor of 2.5
    flags = valid & ((ratio < 0.40) | (ratio > 2.50))
    return pd.Series(flags, index=getattr(pore_ec, 'index', None)).fillna(False)

def check_archies_law_salinity(bulk_ec, pore_ec, vwc, m=1.5):
    """
    Enforces Archie's geometric tortuosity upper bound:
    bulk_ec <= pore_ec * (theta)^m
    Bulk electrical conductivity cannot physically exceed pore fluid conductivity scaled by saturation.
    """
    vwc_frac = np.where(vwc > 1.0, vwc / 100.0, vwc)
    valid = (vwc_frac > 0.05) & pore_ec.notna() & bulk_ec.notna() & (pore_ec > 0)
    
    max_bulk_ec = pore_ec * (vwc_frac ** m) * 1.30 # 30% tolerance buffer
    flags = valid & (bulk_ec > max_bulk_ec)
    return pd.Series(flags, index=getattr(bulk_ec, 'index', None)).fillna(False)

def check_crns_depth_profile_integration(crns_moisture, tdr_vwc_dict, threshold=0.08):
    """
    Compares intermediate-scale Cosmic-Ray Neutron Sensing (CRNS Finapp) footprint soil moisture
    against an exponentially depth-weighted point-probe integration across the profile.
    
    w(z) = exp(-z / 15.0 cm)
    """
    depths = [5.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    weights = [np.exp(-z / 15.0) for z in depths]
    total_w = sum(weights)
    norm_w = [w / total_w for w in weights]
    
    # Compute weighted sum of available TDR layers
    integrated_vwc = 0.0
    for idx, d_idx in enumerate(range(1, 7)):
        if d_idx in tdr_vwc_dict and tdr_vwc_dict[d_idx] is not None:
            v = tdr_vwc_dict[d_idx]
            v_frac = np.where(v > 1.0, v / 100.0, v)
            integrated_vwc = integrated_vwc + (norm_w[idx] * v_frac)
            
    crns_frac = np.where(crns_moisture > 1.0, crns_moisture / 100.0, crns_moisture)
    valid = crns_moisture.notna() & (integrated_vwc > 0)
    
    diff = np.abs(crns_frac - integrated_vwc)
    return pd.Series(valid & (diff > threshold), index=getattr(crns_moisture, 'index', None)).fillna(False)

def check_snow_water_equivalent_consistency(swe, air_temp_c, sw_in, sw_out, target_temp_c=None):
    """
    Validates Cosmic-Ray / Finapp Snow Water Equivalent (SWE).
    A true snow pack requires high broadband albedo (alpha >= 0.50) or freezing surface temperatures (<= 1.5 C).
    Flags false-positive snow detections during warm, snow-free conditions.
    """
    valid_rad = (sw_in > 50.0) & sw_out.notna()
    albedo = np.where(valid_rad, sw_out / sw_in, np.nan)
    
    has_swe = swe.notna() & (swe > 1.0) # > 1 mm SWE
    is_warm = (air_temp_c > 6.0)
    is_low_albedo = valid_rad & (albedo < 0.30)
    
    flags = has_swe & is_warm & is_low_albedo
    return pd.Series(flags, index=getattr(swe, 'index', None)).fillna(False)

def check_darcy_hydraulic_gradient(mp_shallow_kpa, mp_deep_kpa, vwc_deep, rain_int=None, dz_m=0.10):
    """
    Checks Darcy-Buckingham upward suction gradient against deep layer wetting.
    If shallow suction is much higher than deep suction (strong upward matric gradient driving evaporation),
    unphysical rapid wetting in deep soil without precipitation is flagged as sensor error or crack bypass.
    """
    # 1 kPa = 0.10197 m head
    h_shallow_m = -np.abs(mp_shallow_kpa) * 0.10197
    h_deep_m = -np.abs(mp_deep_kpa) * 0.10197 - dz_m
    
    # Total hydraulic head gradient dH/dz (positive means water drawn upwards to surface)
    upward_gradient = (h_shallow_m < (h_deep_m - 0.50)) # > 0.5m head driving upward
    
    # Deep layer wetting rate
    vwc_deep_frac = np.where(vwc_deep > 1.0, vwc_deep / 100.0, vwc_deep)
    deep_wetting = pd.Series(vwc_deep_frac, index=getattr(vwc_deep, 'index', None)).diff() > 0.02
    
    no_rain = True
    if rain_int is not None:
        no_rain = (rain_int <= 0.1)
        
    flags = upward_gradient & deep_wetting & no_rain
    return pd.Series(flags, index=getattr(vwc_deep, 'index', None)).fillna(False)


