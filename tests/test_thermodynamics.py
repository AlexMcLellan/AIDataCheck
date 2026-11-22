import pandas as pd
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.thermodynamics import calculate_dewpoint, check_dewpoint

def test_calculate_dewpoint():
    # At 20C and 100% RH, dewpoint is 20C
    dp_100 = calculate_dewpoint(20.0, 100.0)
    assert np.isclose(dp_100, 20.0)
    
    # At 20C and 50% RH, dewpoint is ~9.3C
    dp_50 = calculate_dewpoint(20.0, 50.0)
    assert np.isclose(dp_50, 9.27, atol=0.1)

def test_check_dewpoint():
    temp = pd.Series([20.0, 20.0])
    rh = pd.Series([100.0, 50.0])
    
    # Accurate measurements
    measured_accurate = pd.Series([20.0, 9.27])
    assert not check_dewpoint(temp, rh, measured_accurate, threshold=1.0).any()
    
    # Inaccurate measurement
    measured_inaccurate = pd.Series([15.0, 9.27])
    flags = check_dewpoint(temp, rh, measured_inaccurate, threshold=1.0)
    assert flags[0] == True
    assert flags[1] == False

def test_check_psychrometric_closure():
    from models.thermodynamics import check_psychrometric_closure
    temp = pd.Series([20.0, 20.0])
    rh = pd.Series([50.0, 50.0])
    dp = pd.Series([9.3, 16.0]) # second is mismatch
    vpd = pd.Series([1.17, 1.17])
    
    flags = check_psychrometric_closure(temp, rh, dp, measured_vpd=vpd)
    assert not flags[0]
    assert flags[1]

def test_check_sonic_temperature_consistency():
    from models.thermodynamics import check_sonic_temperature_consistency
    sonic = pd.Series([20.1, 25.0]) # second is huge mismatch (+5C)
    air = pd.Series([20.0, 20.0])
    h2o = pd.Series([10.0, 10.0]) # mmol/mol
    
    flags = check_sonic_temperature_consistency(sonic, air, h2o_mole_frac=h2o, threshold=1.5)
    assert not flags[0]
    assert flags[1]

def test_check_dual_station_rh():
    from models.thermodynamics import check_dual_station_rh
    rh1 = pd.Series([60.0, 60.0])
    rh2 = pd.Series([62.0, 80.0]) # second is 20% mismatch > 8%
    
    flags = check_dual_station_rh(rh1, rh2, threshold=8.0)
    assert not flags[0]
    assert flags[1]

