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
