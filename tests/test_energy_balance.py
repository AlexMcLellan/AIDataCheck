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
    calculate_expected_clear_sky_solar
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

def test_calculate_expected_clear_sky_solar():
    # Test during noon at the equator
    times = pd.date_range('2023-03-21 12:00', periods=1, freq='h', tz='UTC')
    ghi = calculate_expected_clear_sky_solar(times, latitude=0.0, longitude=0.0)
    
    assert len(ghi) == 1
    # GHI should be high at noon on the equinox at the equator
    assert ghi[0] > 900.0 
