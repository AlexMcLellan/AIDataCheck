import pandas as pd
import numpy as np

try:
    from pvlib.location import Location
except ImportError:
    Location = None

def calculate_longwave_from_surface_temp(surface_temp_c, emissivity=0.95):
    """
    Calculate theoretical outgoing longwave radiation from surface temperature
    using the Stefan-Boltzmann law.
    LW_out = emissivity * sigma * T_K^4
    """
    sigma = 5.670374419e-8  # Stefan-Boltzmann constant (W m-2 K-4)
    surface_temp_k = surface_temp_c + 273.15
    return emissivity * sigma * (surface_temp_k ** 4)

def calculate_soil_heat_storage(vwc_series, temp_series, depth_m=0.03):
    """
    Calculate the soil heat storage flux (S_soil) for a soil layer above a heat flux plate.
    
    Parameters:
    vwc_series : pd.Series
        Volumetric water content (fraction, m3/m3).
    temp_series : pd.Series
        Soil temperature (Celsius or Kelvin).
    depth_m : float
        Depth of the heat flux plate in meters (default 0.03 m).
        
    Returns:
    pd.Series
        Soil heat storage flux in W/m2.
    """
    # Volumetric heat capacity of dry mineral soil (~1.25 MJ/m3K)
    C_dry = 1.25e6
    # Volumetric heat capacity of water (~4.18 MJ/m3K)
    C_water = 4.18e6
    
    # Calculate total volumetric heat capacity (J / m3 K)
    # Note: vwc_series is assumed to be a fraction (e.g. 0.20 for 20%)
    C_soil = C_dry + (vwc_series * C_water)
    
    # Calculate dT/dt using a 15-minute rolling window to reduce high-frequency noise
    # temp_series is assumed to have a DateTimeIndex with 1-minute frequency
    # We take the difference over 15 periods (15 minutes)
    dt_seconds = 15 * 60
    dT = temp_series.diff(periods=15)
    dT_dt = dT / dt_seconds
    
    # S_soil (W/m2) = C_soil (J/m3K) * dT_dt (K/s) * depth (m)
    s_soil = C_soil * dT_dt * depth_m
    return s_soil

def calculate_energy_balance_residual(rn, g, h, le):
    """
    Calculate the residual of the energy balance equation:
    Rn - G = H + LE + Residual
    """
    residual = rn - g - h - le
    
    return residual

def estimate_soil_heat_flux_from_gradient(surface_temp_c, soil_temp_c, vwc, porosity, rho_b, q, depth_m=0.05):
    """
    Estimate Soil Heat Flux using Fourier's Law and Johansen (1975) thermal conductivity model.
    Positive flux means heat entering the soil (Surface warmer than Soil).
    
    Parameters:
    surface_temp_c : pd.Series, surface temperature in C
    soil_temp_c : pd.Series, soil temperature at depth in C
    vwc : pd.Series, Volumetric Water Content (fraction m3/m3)
    porosity : float, Soil porosity (usually theta_s)
    rho_b : float, Bulk density (g/cm3)
    q : float, Quartz fraction (0.0 to 1.0)
    depth_m : float, depth of the soil temperature sensor in meters (default 0.05)
    """
    # 1. Johansen (1975) Thermal Conductivity Model
    # Thermal conductivity of solid particles (lambda_s)
    lambda_s = (7.7 ** q) * (2.0 ** (1 - q))
    
    # Saturated thermal conductivity (lambda_sat)
    lambda_w = 0.57 # W/mK for water
    lambda_sat = (lambda_s ** (1 - porosity)) * (lambda_w ** porosity)
    
    # Dry thermal conductivity (lambda_dry)
    lambda_dry = (0.135 * rho_b) + 0.064
    
    # Degree of saturation (Sr)
    Sr = vwc / porosity
    Sr = Sr.clip(lower=0.0, upper=1.0)
    
    # Normalized thermal conductivity (Ke) for unfrozen soils
    # Ke = log10(Sr) + 1.0 (for Sr > 0.05)
    Ke = np.log10(Sr.replace(0, 1e-6)) + 1.0
    Ke = Ke.clip(lower=0.0)
    Ke.loc[Sr <= 0.05] = 0.0
    
    # Final thermal conductivity (lambda) in W/mK
    lambda_soil = (lambda_sat - lambda_dry) * Ke + lambda_dry
    
    # 2. Fourier's Law of Heat Conduction
    # G = - lambda * dT/dz
    # dT = T_soil - T_surface (if soil is colder, dT is negative, G is positive -> heat goes down)
    # dz = depth_m - 0
    dT = soil_temp_c - surface_temp_c
    dz = depth_m
    
    g_theory = -lambda_soil * (dT / dz)
    return g_theory

def check_solar_radiation(sw_in, ppfd, albedo=None):
    """
    Cross-checks incoming shortwave radiation against PAR (PPFD).
    Typically, PAR (umol m-2 s-1) is approximately 2.0 to 2.2 times SW_in (W m-2) for daylight.
    """
    ratio = ppfd / np.where(sw_in > 10, sw_in, np.nan)
    return ratio

def estimate_sensible_heat_from_temp(surface_temp, air_temp, aerodynamic_resistance, altitude=0):
    """
    Estimate Sensible Heat (H) from surface temperature and air temperature.
    H = rho * Cp * (Ts - Ta) / ra
    """
    # Adjust air density for altitude using standard atmosphere model
    # rho = rho0 * (1 - L*h/T0)^(g*M/(R*L) - 1)
    rho_sea_level = 1.225 # kg/m3
    rho = rho_sea_level * (1 - 2.25577e-5 * altitude)**4.25588
    
    cp = 1004.0 # Specific heat capacity of air J/(kg K)
    
    h_est = (rho * cp * (surface_temp - air_temp)) / aerodynamic_resistance
    return h_est

def calculate_expected_clear_sky_solar(times, latitude, longitude, altitude=0, tz='UTC'):
    """
    Calculates expected clear-sky global horizontal irradiance (GHI) based on location and time.
    Requires pvlib.
    
    Parameters:
    -----------
    times : pd.DatetimeIndex
        Times to calculate the solar input.
    latitude : float
        Latitude in decimal degrees.
    longitude : float
        Longitude in decimal degrees.
    altitude : float
        Altitude in meters.
    tz : str
        Timezone string (e.g. 'UTC'). If times are tz-aware, this is ignored.
        
    Returns:
    --------
    expected_ghi : pd.Series
        Clear-sky GHI (W/m^2)
    """
    if Location is None:
        raise ImportError("pvlib is required for solar clear-sky modeling")
        
    loc = Location(latitude, longitude, tz, altitude)
    
    # If the time index is tz-naive, localize it
    if times.tzinfo is None:
        times = times.tz_localize(tz)
        
    clearsky = loc.get_clearsky(times)
    return clearsky['ghi'].values # Global Horizontal Irradiance
