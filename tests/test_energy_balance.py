import pandas as pd
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.energy_balance import (
    calculate_energy_balance_residual,
    check_solar_radiation,
    estimate_sensible_heat_from_temp,
    calculate_expected_clear_sky_solar,
    calculate_aerodynamic_resistance
)

def test_calculate_energy_balance_residual():
    # Rn = 500, G = 50, H = 200, LE = 250 -> Residual = 0
    rn = pd.Series([500.0, 600.0])
    g = pd.Series([50.0, 60.0])
    h = pd.Series([200.0, 240.0])
    le = pd.Series([250.0, 300.0])
    
    residual = calculate_energy_balance_residual(rn, g, h, le)
    np.testing.assert_allclose(residual.values, [0.0, 0.0])
    
def test_check_solar_radiation():
    sw_in = pd.Series([0.0, 500.0, 1000.0])
    ppfd = pd.Series([0.0, 1050.0, 2100.0])
    
    ratio = check_solar_radiation(sw_in, ppfd)
    
    assert np.isnan(ratio[0]) # below 10 W/m2 threshold should be NaN
    assert np.isclose(ratio[1], 2.1)
    assert np.isclose(ratio[2], 2.1)

def test_estimate_sensible_heat_from_temp():
    # Ts = 25C, Ta = 20C, ra = 50 s/m
    Ts = pd.Series([25.0])
    Ta = pd.Series([20.0])
    ra = 50.0
    
    h_est = estimate_sensible_heat_from_temp(Ts, Ta, ra)
    
    # h = 1.225 * 1004 * (5) / 50 = 122.99
    expected = (1.225 * 1004.0 * 5.0) / 50.0
    np.testing.assert_allclose(h_est.values, [expected])

def test_calculate_aerodynamic_resistance():
    # Test normal wind speed
    wind_speed = pd.Series([2.0, 5.0, 0.0]) # m/s
    ra = calculate_aerodynamic_resistance(wind_speed, z_m=3.0, z_0m=0.03, z_0h=0.003)
    
    # Manual calc for wind_speed = 2.0:
    # ln(3.0/0.03) * ln(3.0/0.003) / (0.16 * 2.0) 
    # = 4.605 * 6.907 / 0.32 = 31.806 / 0.32 = 99.39
    
    assert len(ra) == 3
    np.testing.assert_allclose(ra[0], 99.39, rtol=1e-2)
    np.testing.assert_allclose(ra[1], 39.75, rtol=1e-2)
    
    # Wind speed 0.0 is capped to 0.1
    # 31.806 / (0.16 * 0.1) = 31.806 / 0.016 = 1987.8
    np.testing.assert_allclose(ra[2], 1987.8, rtol=1e-2)

def test_calculate_expected_clear_sky_solar():
    # Test during noon at the equator
    times = pd.date_range('2023-03-21 12:00', periods=1, freq='h', tz='UTC')
    ghi = calculate_expected_clear_sky_solar(times, latitude=0.0, longitude=0.0)
    
    assert len(ghi) == 1
    # GHI should be high at noon on the equinox at the equator
    assert ghi[0] > 900.0 

def test_check_radiative_surface_temp_consistency():
    from models.energy_balance import check_radiative_surface_temp_consistency
    # At ~20C (293.15K), blackbody LW is sigma * T^4 = 5.67e-8 * (293.15)^4 ~ 418 W/m2
    lw_in = pd.Series([350.0, 350.0])
    lw_out = pd.Series([418.0, 418.0])
    target_temp = pd.Series([20.0, 35.0]) # second is 15C discrepancy
    
    flags = check_radiative_surface_temp_consistency(lw_in, lw_out, target_temp, threshold=3.5)
    assert not flags[0]
    assert flags[1]

def test_check_albedo_ndvi_concordance():
    from models.energy_balance import check_albedo_ndvi_concordance
    sw_in = pd.Series([600.0, 600.0])
    sw_out = pd.Series([120.0, 300.0]) # albedo: 0.20, 0.50
    ndvi = pd.Series([0.75, 0.75])     # Dense vegetation with 0.50 albedo is anomalous
    
    flags = check_albedo_ndvi_concordance(sw_in, sw_out, ndvi)
    assert not flags[0]
    assert flags[1]

def test_check_monin_obukhov_stability_consistency():
    from models.energy_balance import check_monin_obukhov_stability_consistency
    l_mo = pd.Series([-100.0, 100.0]) # unstable, stable
    h_ec = pd.Series([150.0, 150.0])  # H > 0 with L > 0 is sign violation
    u_star = pd.Series([0.35, 0.35])
    
    flags = check_monin_obukhov_stability_consistency(l_mo, h_ec, u_star)
    assert not flags[0]
    assert flags[1]

def test_check_integral_turbulence_characteristics():
    from models.energy_balance import check_integral_turbulence_characteristics
    sigma_w = pd.Series([0.45, 1.20]) # ratio: 0.45/0.35 = 1.28 (normal), 1.20/0.35 = 3.42 (excessive)
    u_star = pd.Series([0.35, 0.35])
    
    flags = check_integral_turbulence_characteristics(sigma_w, u_star)
    assert not flags[0]
    assert flags[1]

def test_check_priestley_taylor_bounds():
    from models.energy_balance import check_priestley_taylor_bounds
    # Available energy = 400 W/m2. Delta/(Delta+gamma) ~ 0.65 -> LE_eq ~ 260 W/m2
    le = pd.Series([250.0, 700.0]) # second exceeds 2 * LE_eq
    rn = pd.Series([450.0, 450.0])
    g = pd.Series([50.0, 50.0])
    ta = pd.Series([20.0, 20.0])
    
    flags = check_priestley_taylor_bounds(le, rn, g, ta, alpha_max=2.0)
    assert not flags[0]
    assert flags[1]
 
