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
    precip = pd.Series([0.0, 10.0, 0.0])
    delta_s = pd.Series([1.0, 5.0, 8.0])
    
    # threshold = 5.0
    flags = flag_rain_soil_moisture_mismatch(precip, delta_s, threshold=5.0)
    
    # Index 0: dS=1 < 5, False
    # Index 1: dS=5, P=10, False (no mismatch)
    # Index 2: dS=8 > 5, P=0 < 1, True (mismatch!)
    assert not flags[0]
    assert not flags[1]
    assert flags[2]
