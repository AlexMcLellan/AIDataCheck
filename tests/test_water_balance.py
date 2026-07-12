import pandas as pd
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.water_balance import (
    calculate_water_balance_residual,
    integrate_soil_moisture_profile,
    flag_rain_soil_moisture_mismatch
)

def test_calculate_water_balance_residual():
    # P = ET + dS + Runoff
    P = pd.Series([10.0])
    ET = pd.Series([2.0])
    dS = pd.Series([7.0])
    
    residual = calculate_water_balance_residual(P, ET, dS, runoff=1.0)
    np.testing.assert_allclose(residual.values, [0.0])

def test_integrate_soil_moisture_profile():
    # depths: 0.1, 0.2, 0.3 meters
    vwc = [pd.Series([0.2]), pd.Series([0.3]), pd.Series([0.4])]
    depths = [0.1, 0.2, 0.3]
    
    storage = integrate_soil_moisture_profile(vwc, depths)
    
    # Layer 1: thickness = 0.1 + (0.2-0.1)/2 = 0.15 m
    # Layer 2: thickness = (0.2-0.1)/2 + (0.3-0.2)/2 = 0.1 m
    # Layer 3: thickness = (0.3-0.2)/2 = 0.05 m
    # Storage = 0.2*0.15*1000 + 0.3*0.1*1000 + 0.4*0.05*1000 = 30 + 30 + 20 = 80 mm
    np.testing.assert_allclose(storage.values, [80.0])

def test_flag_rain_soil_moisture_mismatch():
    idx = pd.date_range('2023-01-01', periods=3, freq='h')
    precip = pd.Series([0.0, 10.0, 0.0], index=idx)
    delta_s = pd.Series([1.0, 1.0, 10.0], index=idx)
    
    # Test 1: Spikes in soil moisture without rain
    # depth_m = 0.5, k_sat_cm_h = 5.0 -> lag is 10 hours.
    # For this test, let's use depth_m = 0.05 (5cm) so lag is 1 hour.
    flags = flag_rain_soil_moisture_mismatch(
        precip_interval=precip, 
        delta_s=delta_s, 
        depth_m=0.05, 
        k_sat_cm_h=5.0,
        threshold_ds=5.0,
        rain_window='2h'
    )
    
    # Index 0: dS=1 < 5, False
    # Index 1: dS=1 < 5, False
    # Index 2: dS=10 > 5. BUT lagged rain (10.0 shifted by 1 hour) arrived exactly at index 2.
    # recent_lagged_rain will be 10.0 > 1.0, so mismatch_no_rain = False.
    assert not flags.iloc[0]
    assert not flags.iloc[1]
    assert not flags.iloc[2]

    # Test 2: Spike with NO rain
    precip_no_rain = pd.Series([0.0, 0.0, 0.0], index=idx)
    flags_no_rain = flag_rain_soil_moisture_mismatch(
        precip_no_rain, delta_s, depth_m=0.05, k_sat_cm_h=5.0, threshold_ds=5.0
    )
    assert not flags_no_rain.iloc[0]
    assert not flags_no_rain.iloc[1]
    assert flags_no_rain.iloc[2] # dS > 5 and NO rain -> True
