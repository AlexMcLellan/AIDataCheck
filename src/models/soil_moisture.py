import numpy as np
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
