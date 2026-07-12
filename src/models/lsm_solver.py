import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from models.soil_moisture import SOIL_PARAMS
from models.energy_balance import estimate_soil_heat_flux_from_gradient

def get_johansen_thermal_conductivity(vwc, soil_type='silt_loam'):
    """
    Calculates the Johansen thermal conductivity for a given VWC and soil type.
    """
    params = SOIL_PARAMS.get(soil_type.lower(), SOIL_PARAMS['silt_loam'])
    porosity = params[1] # theta_s
    rho_b = params[5] # g/cm3
    q = params[6] 
    
    # Solid particles (lambda_s)
    lambda_s = (7.7 ** q) * (2.0 ** (1 - q))
    
    # Saturated (lambda_sat)
    lambda_w = 0.57
    lambda_sat = (lambda_s ** (1 - porosity)) * (lambda_w ** porosity)
    
    # Dry (lambda_dry)
    lambda_dry = (0.135 * rho_b) + 0.064
    
    # Degree of saturation
    Sr = np.clip(vwc / porosity, 0.0, 1.0)
    
    # Normalized (Ke)
    Ke = np.log10(np.where(Sr == 0, 1e-6, Sr)) + 1.0
    Ke = np.clip(Ke, 0.0, None)
    Ke = np.where(Sr <= 0.05, 0.0, Ke)
    
    lambda_soil = (lambda_sat - lambda_dry) * Ke + lambda_dry
    return lambda_soil

def get_volumetric_heat_capacity(vwc, soil_type='silt_loam'):
    """
    Calculates volumetric heat capacity (J / m^3 K)
    """
    params = SOIL_PARAMS.get(soil_type.lower(), SOIL_PARAMS['silt_loam'])
    porosity = params[1]
    # Solid fraction
    f_solid = 1.0 - porosity
    
    C_dry = 2.0e6 * f_solid # approx for minerals
    C_water = 4.18e6 * vwc
    
    return C_dry + C_water

def heat_conduction_ode(t, T, z, dz, T_surface_func, T_bottom_func, lambda_func, C_func):
    """
    1D Heat Equation ODE system: dT/dt = (1/C) * d/dz( lambda * dT/dz )
    T: array of temperatures at depths z
    """
    N = len(T)
    dTdt = np.zeros(N)
    
    T_surf = T_surface_func(t)
    T_bot = T_bottom_func(t)
    
    # Extend T array with boundaries for gradient calc
    T_ext = np.concatenate(([T_surf], T, [T_bot]))
    
    # Thermal conductivity at interfaces (harmonic mean could be used, but arithmetic is simpler)
    # Assuming uniform VWC for now
    lam = lambda_func(t)
    C = C_func(t)
    
    # Central difference for interior
    for i in range(N):
        # Flux from above (i to i+1 in extended array)
        q_in = -lam * (T_ext[i+1] - T_ext[i]) / dz
        # Flux to below (i+1 to i+2)
        q_out = -lam * (T_ext[i+2] - T_ext[i+1]) / dz
        
        # dT/dt = - dQ/dz / C
        dTdt[i] = -(q_out - q_in) / dz / C
        
    return dTdt

def run_1d_heat_simulation(weather_df, soil_texture_desc, depths_m=np.linspace(0.05, 1.0, 20)):
    """
    Runs the numerical LSM solver.
    """
    if weather_df.empty:
        return pd.DataFrame()
        
    # Map UKSO description to USDA class
    soil_type = 'silt_loam'
    if 'sand' in soil_texture_desc.lower():
        soil_type = 'sand'
    elif 'clay' in soil_texture_desc.lower() and 'loam' not in soil_texture_desc.lower():
        soil_type = 'clay'
        
    # Time domain (seconds from start)
    weather_df = weather_df.sort_index()
    t_seconds = (weather_df.index - weather_df.index[0]).total_seconds().values
    
    # Boundary interpolators
    # For a proper energy balance, T_surface is solved simultaneously. 
    # Here we approximate T_surface based on T_air + solar radiation effect
    # Air temp is given, assume surface is slightly warmer during day, colder at night.
    
    t_air = weather_df['temperature'].values
    # We use weather code to guess solar heating
    # 1=Sunny, 3=Partly, 8=Overcast
    heating = np.zeros(len(weather_df))
    if 'weather_code' in weather_df.columns:
        wc = weather_df['weather_code'].values
        heating = np.where(wc <= 1, 5.0, heating) # +5C if sunny
        heating = np.where(wc == 3, 2.0, heating) # +2C if partly cloudy
        heating = np.where(wc >= 7, 0.0, heating) # +0C if overcast
        
    t_surf_arr = t_air + heating
    
    def T_surface_func(t):
        return np.interp(t, t_seconds, t_surf_arr)
        
    # Bottom boundary (constant deep soil temp, e.g. mean air temp)
    mean_temp = np.mean(t_air)
    def T_bottom_func(t):
        return mean_temp
        
    # Constant moisture for now (approx field capacity, roughly 60% of porosity)
    porosity = SOIL_PARAMS.get(soil_type.lower(), SOIL_PARAMS['silt_loam'])[1]
    vwc_constant = porosity * 0.6
    def lambda_func(t):
        return get_johansen_thermal_conductivity(vwc_constant, soil_type)
        
    def C_func(t):
        return get_volumetric_heat_capacity(vwc_constant, soil_type)
        
    dz = depths_m[1] - depths_m[0] if len(depths_m) > 1 else 0.1
    
    # Initial condition: uniform profile at mean temp
    T0 = np.full(len(depths_m), mean_temp)
    
    print("Integrating 1D Heat Equation...")
    # Solve IVP
    res = solve_ivp(
        heat_conduction_ode,
        t_span=(t_seconds[0], t_seconds[-1]),
        y0=T0,
        t_eval=t_seconds,
        args=(depths_m, dz, T_surface_func, T_bottom_func, lambda_func, C_func),
        method='RK45',
        vectorized=False
    )
    
    # Format results
    out_df = pd.DataFrame(index=weather_df.index)
    for i, z in enumerate(depths_m):
        out_df[f'T_soil_{z:.2f}m'] = res.y[i, :]
        
    out_df['T_surface_driven'] = t_surf_arr
    out_df['T_air'] = t_air
    
    return out_df
