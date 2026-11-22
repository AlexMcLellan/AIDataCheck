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

def test_check_soil_vwc_redundancy():
    from models.qc_rules import check_soil_vwc_redundancy
    tdr = pd.Series([20.0, 22.0, 45.0]) # %
    soilvue = pd.Series([0.21, 0.22, 0.20]) # fraction
    flags = check_soil_vwc_redundancy(tdr, soilvue, threshold=0.15)
    
    assert not flags[0]
    assert not flags[1]
    assert flags[2] # 0.45 vs 0.20 > 0.15 diff

def test_check_soil_temp_3way():
    from models.qc_rules import check_soil_temp_3way
    t_teros = pd.Series([18.0, 18.2, 18.0])
    t_tdr = pd.Series([18.1, 18.0, 18.2])
    t_soilvue = pd.Series([18.2, 18.1, 23.5]) # outlier in last
    flags = check_soil_temp_3way(t_teros, t_tdr, t_soilvue, threshold=3.0)
    
    assert not flags[0]
    assert not flags[1]
    assert flags[2]

def test_check_turbulent_flux_sum():
    from models.energy_balance import check_turbulent_flux_sum
    h = pd.Series([100.0, 500.0, 100.0, -400.0])
    le = pd.Series([100.0, 400.0, 50.0, 20.0])
    ghi = pd.Series([500.0, 500.0, 0.0, 0.0]) # Day, Day (exceeds), Night (anomalous +150W), Night (extreme negative)
    
    flags = check_turbulent_flux_sum(h, le, expected_ghi=ghi)
    assert not flags[0] # 200 <= 500*1.25 + 50 = 675 -> False
    assert flags[1]     # 900 > 675 -> True
    assert flags[2]     # Nighttime 150 > 60 -> True
    assert flags[3]     # -380 < -300 -> True

def test_check_ec_flux_bounds():
    from models.energy_balance import check_ec_flux_bounds
    h = pd.Series([100.0, -300.0, 100.0])
    le = pd.Series([100.0, 50.0, 800.0])
    flags = check_ec_flux_bounds(h, le)
    assert not flags[0]
    assert flags[1] # H < -250
    assert flags[2] # LE > 700

def test_check_bowen_ratio():
    from models.energy_balance import check_bowen_ratio
    h = pd.Series([100.0, -100.0, 500.0])
    le = pd.Series([100.0, 50.0, 5.0]) # beta: 1.0, -2.0, 100.0 (but LE <= 20)
    ghi = pd.Series([400.0, 400.0, 400.0])
    flags = check_bowen_ratio(h, le, expected_ghi=ghi)
    assert not flags[0]
    assert flags[1] # beta = -2.0 < -1.5 during active daytime LE
    assert not flags[2] # LE <= 20 not evaluated

def test_check_matric_potential_decoupling():
    from models.qc_rules import check_matric_potential_decoupling
    # mp: -50 kPa (normal), -800 kPa (ceiling/stalled), -250 kPa with low VWC (decoupled)
    mp = pd.Series([-50.0, -800.0, -250.0])
    vwc = pd.Series([0.25, 0.04, 0.03])
    
    flags_decoupled = check_matric_potential_decoupling(
        mp, vwc_series=vwc, decoupling_threshold_kpa=-200.0, vwc_threshold=0.08
    )
    
    assert not flags_decoupled[0] # -50 kPa > -200 kPa (Normal)
    assert flags_decoupled[1]     # -800 kPa and VWC = 0.04 <= 0.08 (Decoupled)
    assert flags_decoupled[2]     # -250 kPa and VWC = 0.03 <= 0.08 (Decoupled)

