import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.soil_moisture import van_genuchten, fit_van_genuchten

def test_van_genuchten():
    theta_r = 0.05
    theta_s = 0.50
    alpha = 0.01
    n = 1.5
    
    # At h = 0, se = 1 -> theta = theta_s
    theta = van_genuchten(0.0, theta_r, theta_s, alpha, n)
    assert np.isclose(theta, theta_s)
    
    # At large h, se -> 0, theta -> theta_r
    theta_large = van_genuchten(1e9, theta_r, theta_s, alpha, n)
    assert np.isclose(theta_large, theta_r, atol=1e-3)

def test_fit_van_genuchten():
    # Generate mock data using known parameters
    h_data = np.array([0, 10, 100, 1000, 10000])
    true_params = [0.06, 0.45, 0.015, 1.4]
    
    theta_data = van_genuchten(h_data, *true_params)
    
    # Add a little noise
    np.random.seed(42)
    theta_data += np.random.normal(0, 0.001, len(theta_data))
    
    popt = fit_van_genuchten(h_data, theta_data)
    
    # The fitted params should be close to the true params
    assert popt is not None
    assert np.isclose(popt[0], true_params[0], atol=0.05)
    assert np.isclose(popt[1], true_params[1], atol=0.05)

def test_check_topp_permittivity_consistency():
    import pandas as pd
    from models.soil_moisture import check_topp_permittivity_consistency
    # Permittivity Ka = 10 -> Topp VWC ~ 0.19
    vwc = pd.Series([0.19, 0.45]) # second is huge mismatch (45% vs 19%)
    ka = pd.Series([10.0, 10.0])
    
    flags = check_topp_permittivity_consistency(vwc, ka, threshold=0.035)
    assert not flags[0]
    assert flags[1]

def test_check_hilhorst_pore_water_ec():
    import pandas as pd
    from models.soil_moisture import check_hilhorst_pore_water_ec
    # At 20C, eps_w = 80.1. ka = 14.1 (denom = 10.0). bulk_ec = 0.1 dS/m -> PEC_theo = 0.8 dS/m
    bulk_ec = pd.Series([0.1, 0.1])
    ka = pd.Series([14.1, 14.1])
    pore_ec = pd.Series([0.8, 5.0]) # second is 5.0 vs 0.8 (>2.5x mismatch)
    t_soil = pd.Series([20.0, 20.0])
    
    flags = check_hilhorst_pore_water_ec(bulk_ec, ka, pore_ec, t_soil)
    assert not flags[0]
    assert flags[1]

def test_check_archies_law_salinity():
    import pandas as pd
    from models.soil_moisture import check_archies_law_salinity
    bulk_ec = pd.Series([0.05, 0.90]) # second is bulk_ec > pore_ec
    pore_ec = pd.Series([0.50, 0.50])
    vwc = pd.Series([0.20, 0.20])
    
    flags = check_archies_law_salinity(bulk_ec, pore_ec, vwc, m=1.5)
    assert not flags[0]
    assert flags[1]

def test_check_crns_depth_profile_integration():
    import pandas as pd
    from models.soil_moisture import check_crns_depth_profile_integration
    crns = pd.Series([0.20, 0.40])
    tdr_dict = {i: pd.Series([0.20, 0.20]) for i in range(1, 7)}
    
    flags = check_crns_depth_profile_integration(crns, tdr_dict, threshold=0.08)
    assert not flags[0]
    assert flags[1]

def test_check_snow_water_equivalent_consistency():
    import pandas as pd
    from models.soil_moisture import check_snow_water_equivalent_consistency
    swe = pd.Series([5.0, 5.0])
    ta = pd.Series([0.0, 18.0]) # warm 18C summer day
    sw_in = pd.Series([500.0, 500.0])
    sw_out = pd.Series([350.0, 80.0]) # second has albedo = 0.16 (no snow)
    
    flags = check_snow_water_equivalent_consistency(swe, ta, sw_in, sw_out)
    assert not flags[0]
    assert flags[1]

def test_check_darcy_hydraulic_gradient():
    import pandas as pd
    from models.soil_moisture import check_darcy_hydraulic_gradient
    mp1 = pd.Series([-500.0, -500.0]) # shallow dry (-500 kPa)
    mp2 = pd.Series([-50.0, -50.0])   # deep moist (-50 kPa) -> strong upward gradient
    vwc2 = pd.Series([0.20, 0.25])    # sudden deep wetting without rain
    rain = pd.Series([0.0, 0.0])
    
    flags = check_darcy_hydraulic_gradient(mp1, mp2, vwc2, rain_int=rain)
    assert not flags[0]
    assert flags[1]

