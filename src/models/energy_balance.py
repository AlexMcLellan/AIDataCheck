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

def calculate_aerodynamic_resistance(wind_speed, z_m=3.0, z_0m=0.03, z_0h=0.003):
    """
    Calculate aerodynamic resistance (r_a) using the standard logarithmic wind profile.
    Assumes neutral atmospheric stability for simplicity.
    
    Parameters:
    wind_speed : pd.Series or float
        Wind speed in m/s.
    z_m : float
        Measurement height of wind speed and air temperature (m).
    z_0m : float
        Momentum roughness length (m) (approx 0.03 for short grass/soil).
    z_0h : float
        Heat roughness length (m) (approx 0.1 * z_0m).
        
    Returns:
    pd.Series or float
        Aerodynamic resistance (s/m).
    """
    k = 0.4  # von Karman constant
    
    # Prevent division by absolute zero wind speed
    wind_safe = np.where(wind_speed < 0.1, 0.1, wind_speed)
    
    r_a = (np.log(z_m / z_0m) * np.log(z_m / z_0h)) / ((k ** 2) * wind_safe)
    return r_a

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

def check_turbulent_flux_sum(h, le, expected_ghi=None, max_solar_buffer=1.25, base_buffer=50.0, night_threshold=60.0):
    """
    Checks the sum of convective turbulent heat fluxes (H + LE) against physical and solar expectations.
    
    1. Solar bound: H + LE should not exceed clear-sky solar radiation (with buffer for cloud focusing/advection).
    2. Nocturnal bound: During nighttime (GHI < 5 W/m2), H + LE should not be largely positive (> 60 W/m2).
    3. Extreme bounds: H + LE outside [-300, 900] W/m2.
    """
    turb_sum = h + le
    flags = pd.Series(False, index=getattr(h, 'index', None))
    
    # Extreme physical bounds
    flags = flags | (turb_sum < -300.0) | (turb_sum > 900.0)
    
    if expected_ghi is not None:
        ghi = pd.Series(expected_ghi, index=getattr(h, 'index', None))
        # Daytime solar exceedance
        is_day = ghi > 20.0
        day_limit = (ghi * max_solar_buffer) + base_buffer
        flags = flags | (is_day & (turb_sum > day_limit))
        
        # Nocturnal positive flux anomaly
        is_night = ghi < 5.0
        flags = flags | (is_night & (turb_sum > night_threshold))
        
    return flags

def check_ec_flux_bounds(h, le, h_min=-250.0, h_max=700.0, le_min=-100.0, le_max=700.0):
    """
    Flags individual Sensible Heat (H) and Latent Heat (LE) boundary violations.
    """
    flag_h = (h < h_min) | (h > h_max)
    flag_le = (le < le_min) | (le > le_max)
    return flag_h | flag_le

def check_bowen_ratio(h, le, expected_ghi=None, min_ratio=-1.5, max_ratio=15.0):
    """
    Flags anomalous Bowen ratio (beta = H / LE) during active daylight evapotranspiration.
    Extreme negative ratios or decoupling during transpiration indicate flux distortion.
    """
    bowen = h / le.replace(0, np.nan)
    flags = pd.Series(False, index=getattr(h, 'index', None))
    
    # Only evaluate during daylight with active transpiration
    valid_transpiration = (le > 20.0)
    if expected_ghi is not None:
        valid_transpiration = valid_transpiration & (pd.Series(expected_ghi, index=getattr(h, 'index', None)) > 50.0)
        
    flags = valid_transpiration & ((bowen < min_ratio) | (bowen > max_ratio))
    return flags.fillna(False)

def check_low_turbulence_decoupling(u_star, ustar_threshold=0.10):
    """
    Flags periods where friction velocity (u*) is below the threshold,
    indicating laminar/stagnant decoupling where eddy-covariance assumptions break down.
    """
    return (u_star < ustar_threshold) & u_star.notna()

def check_ec_turbulence_quality(qc_flag, max_allowed_flag=1.0):
    """
    Flags records where the Mauder & Foken (2004) turbulence quality flag is > 1 (e.g. flag 2 = reject).
    """
    return (qc_flag > max_allowed_flag) & qc_flag.notna()

def check_radiative_surface_temp_consistency(lw_in, lw_out, target_temp_c, emissivity=0.98, threshold=3.5):
    """
    Compares radiative surface temperature derived from 4-component net radiometer longwave fluxes
    via Stefan-Boltzmann equation against infrared radiometer TargetTemp.
    
    R_LW_out = epsilon * sigma * T_surf^4 + (1 - epsilon) * R_LW_in
    """
    sigma = 5.670374419e-8
    # Valid longwave fluxes
    valid = (lw_out > 100.0) & (lw_in > 100.0) & target_temp_c.notna()
    
    emitted = np.maximum(10.0, lw_out - (1.0 - emissivity) * lw_in)
    t_rad_k = (emitted / (emissivity * sigma)) ** 0.25
    t_rad_c = t_rad_k - 273.15
    
    diff = np.abs(t_rad_c - target_temp_c)
    flags = valid & (diff > threshold)
    return pd.Series(flags, index=getattr(target_temp_c, 'index', None)).fillna(False)

def check_albedo_ndvi_concordance(sw_in, sw_out, ndvi):
    """
    Flags discordance between broadband shortwave albedo (SW_out / SW_in) and spectral NDVI.
    Active green canopies (NDVI > 0.65) must exhibit vegetation albedo (~0.12-0.24).
    Flags optical fouling or tilt errors.
    """
    valid_sw = (sw_in > 50.0) & sw_out.notna() & ndvi.notna()
    albedo = np.where(valid_sw, sw_out / sw_in, np.nan)
    
    # Anomaly 1: High NDVI with high albedo (e.g. snow/reflective dust on lens)
    high_ndvi_high_albedo = valid_sw & (ndvi > 0.65) & (albedo > 0.32)
    # Anomaly 2: Low NDVI (bare/dead) with unnaturally low albedo
    low_ndvi_low_albedo = valid_sw & (ndvi < 0.15) & (albedo < 0.08)
    
    return pd.Series(high_ndvi_high_albedo | low_ndvi_low_albedo, index=getattr(ndvi, 'index', None)).fillna(False)

def check_monin_obukhov_stability_consistency(l_mo, h_ec, u_star, ustar_min=0.10):
    """
    Enforces sign consistency between Monin-Obukhov stability length (L) and Sensible Heat Flux (H_EC).
    - Convective day: H > 20 W/m2 requires L < 0.
    - Stable night: H < -20 W/m2 requires L > 0.
    """
    valid = (u_star >= ustar_min) & l_mo.notna() & h_ec.notna() & (l_mo != 0)
    
    unstable_violation = valid & (h_ec > 20.0) & (l_mo > 0) & (l_mo < 500.0)
    stable_violation = valid & (h_ec < -20.0) & (l_mo < 0) & (l_mo > -500.0)
    
    return pd.Series(unstable_violation | stable_violation, index=getattr(h_ec, 'index', None)).fillna(False)

def check_integral_turbulence_characteristics(sigma_w, u_star, ustar_min=0.15, min_ratio=0.6, max_ratio=2.5):
    """
    Checks Kansas/Foken surface layer similarity variance ratio: sigma_w / u* ~ 1.25 +/- 0.3.
    Flags flow distortion, mast vibration, or sonic transducer blockage.
    """
    valid = (u_star >= ustar_min) & sigma_w.notna() & (u_star > 0)
    ratio = np.where(valid, sigma_w / u_star, np.nan)
    
    flags = valid & ((ratio < min_ratio) | (ratio > max_ratio))
    return pd.Series(flags, index=getattr(sigma_w, 'index', None)).fillna(False)

def check_priestley_taylor_bounds(le, rn, g, air_temp_c, alpha_max=2.0):
    """
    Checks latent heat against Priestley-Taylor equilibrium evapotranspiration.
    LE_eq = (Delta / (Delta + gamma)) * (Rn - G)
    """
    # Vapor pressure curve slope Delta (kPa/C)
    es = 0.61078 * np.exp((17.27 * air_temp_c) / (air_temp_c + 237.3))
    delta = (4098.0 * es) / ((air_temp_c + 237.3) ** 2)
    gamma = 0.066 # Psychrometric constant (kPa/C)
    
    available_energy = rn - g
    valid = (available_energy > 50.0) & le.notna()
    
    le_eq = (delta / (delta + gamma)) * available_energy
    flags = valid & (le > (alpha_max * le_eq + 50.0))
    return pd.Series(flags, index=getattr(le, 'index', None)).fillna(False)

