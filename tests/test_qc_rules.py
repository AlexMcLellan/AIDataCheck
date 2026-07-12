import pandas as pd
import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.qc_rules import (
    check_time_continuity, check_battery, check_fan_speed,
    check_albedo, check_shfp_status, check_soil_ec_spikes, check_ndvi_alignment
)

def test_check_time_continuity():
    times = pd.to_datetime(['2026-06-29 23:00:00', '2026-06-29 23:30:00', '2026-06-30 00:30:00'])
    flags = check_time_continuity(times, expected_freq='30min')
    assert not flags[0]
    assert not flags[1]
    assert flags[2] # 1-hour gap

def test_check_battery():
    batt = pd.Series([13.0, 11.0, 11.0])
    expected_ghi = pd.Series([500.0, 500.0, 0.0])
    
    flags = check_battery(batt, expected_ghi, threshold_v=11.5, sw_in_threshold=200)
    assert not flags[0]
    assert flags[1]  # Low battery and high GHI -> True
    assert not flags[2] # Low battery but low GHI -> False

def test_check_albedo():
    sw_in = pd.Series([0.0, 500.0, 500.0])
    sw_out = pd.Series([0.0, 50.0, 500.0]) # albedos: NaN, 0.1, 1.0
    
    flags = check_albedo(sw_in, sw_out)
    assert not flags[0] # Invalid sw_in
    assert not flags[1] # Valid (0.1)
    assert flags[2] # Invalid (1.0 > 0.95)

def test_check_soil_ec_spikes():
    ec = pd.Series([100.0, 102.0, 200.0])
    flags = check_soil_ec_spikes(ec, threshold=50)
    
    assert not flags[0]
    assert not flags[1]
    assert flags[2] # Jumped from 102 to 200 > 50

def test_check_ndvi_alignment():
    angle = pd.Series([180.0, 182.0, 190.0])
    flags = check_ndvi_alignment(angle, threshold=5.0)
    
    assert not flags[0]
    assert not flags[1]
    assert flags[2]
