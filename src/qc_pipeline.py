import os
import pandas as pd
import numpy as np
from ingest.parsers import load_and_merge_data, resample_to_frequency
from models.energy_balance import calculate_energy_balance_residual, calculate_expected_clear_sky_solar, calculate_longwave_from_surface_temp, estimate_sensible_heat_from_temp, calculate_soil_heat_storage, estimate_soil_heat_flux_from_gradient, calculate_aerodynamic_resistance
from models.water_balance import calculate_water_balance_residual, integrate_soil_moisture_profile, flag_rain_soil_moisture_mismatch
from models.thermodynamics import check_dewpoint
from models.qc_rules import (
    check_statistical_anomalies,
    check_time_continuity,
    check_battery,
    check_battery_trend,
    check_fan_speed,
    check_albedo,
    check_shfp_status,
    check_soil_ec_spikes,
    check_ndvi_alignment,
    check_par_ratio,
    check_ir_temp_consistency,
    check_body_temp,
    check_soil_temp_redundancy,
    check_permittivity,
    check_precip_consistency,
    check_solar_radiation_bounds,
    check_nighttime_shortwave,
    check_radiation_redundancy,
    check_uncorrected_longwave,
    check_static_calibration,
    check_shfp_thermal_gradient_mismatch,
    check_dynamic_solar_bounds
)
from models.soil_moisture import van_genuchten, get_soil_params

def run_pipeline(data_dir, latitude, longitude, altitude=0, tz='UTC', soil_types='silt_loam', battery_chemistry='lifepo4', nr01_sensitivities=None):
    if nr01_sensitivities is None:
        nr01_sensitivities = {'sw_in': 10.0, 'sw_out': 10.0, 'lw_in': 10.0, 'lw_out': 10.0}

    """
    Main execution pipeline for Environmental Data Quality Control.
    """
    print(f"Loading data from {data_dir}...")
    df = load_and_merge_data(data_dir)
    
    if df.empty:
        print("No data found!")
        return None
        
    print(f"Data loaded: {df.shape}. Resampling to 1-minute intervals with forward-filling...")
    # Use 1-minute frequency, and forward-fill soil data (which is 15-minute) up to 15 minutes.
    df_resampled = resample_to_frequency(df, freq='1min', ffill_limit=15)
    
    # In a full implementation, here we would explicitly map the column names 
    # to the required variables (Rn, G, H, LE, Precip, etc.) and run the models.
    # For now, we just log the columns available.
    
    print("Available columns after merging:")
    for col in df_resampled.columns[:10]: # Print first 10 for brevity
        print(f" - {col}")
        
    # 0. Calibrate NR01 Radiation Sensors
    # Convert raw millivolts (mV) to W/m2 using provided static sensitivities (in microvolts per W/m2)
    print("Applying static calibration sensitivities to NR01 radiation data...")
    if 'R_SW_in_Avg' in df_resampled.columns and 'sw_in' in nr01_sensitivities:
        df_resampled['R_SW_in_Avg'] = (df_resampled['R_SW_in_Avg'] * 1000) / nr01_sensitivities['sw_in']
    if 'R_SW_out_Avg' in df_resampled.columns and 'sw_out' in nr01_sensitivities:
        df_resampled['R_SW_out_Avg'] = (df_resampled['R_SW_out_Avg'] * 1000) / nr01_sensitivities['sw_out']
    if 'R_LW_in_Avg' in df_resampled.columns and 'lw_in' in nr01_sensitivities:
        df_resampled['R_LW_in_Avg'] = (df_resampled['R_LW_in_Avg'] * 1000) / nr01_sensitivities['lw_in']
    if 'R_LW_out_Avg' in df_resampled.columns and 'lw_out' in nr01_sensitivities:
        df_resampled['R_LW_out_Avg'] = (df_resampled['R_LW_out_Avg'] * 1000) / nr01_sensitivities['lw_out']

    # Apply QC Checks and Flagging
    print("Applying rule-based QC checks...")
    
    # 1. Time Continuity
    df_resampled['flag_time_gap'] = check_time_continuity(df_resampled.index, expected_freq='1min')
    
    # Calculate clear-sky solar model
    print(f"Calculating expected solar input for location ({latitude}, {longitude})...")
    try:
        df_resampled['Expected_GHI'] = calculate_expected_clear_sky_solar(
            df_resampled.index, latitude, longitude, altitude, tz
        )
        print("Clear-sky solar modeling completed successfully.")
    except Exception as e:
        print(f"Could not calculate clear-sky solar input: {e}")
        df_resampled['Expected_GHI'] = 0.0
        
    # Mocking Met Office Weather Codes for historical dataset testing
    print("Mocking Met Office weather_code for historical data...")
    # Alternating days: Even days = Overcast (8), Odd days = Sunny (1)
    df_resampled['weather_code'] = np.where(df_resampled.index.day % 2 == 0, 8, 1)

    # Check if measured solar exceeds theoretical maximum (cloudless sky + 20% buffer)
    if 'R_SW_in_Avg' in df_resampled.columns:
        df_resampled['flag_sw_exceeds_clearsky'] = check_solar_radiation_bounds(df_resampled['R_SW_in_Avg'], df_resampled['Expected_GHI'])
        
        # Apply Dynamic Weather Bounds (Lower bound if Sunny, tighter Upper bound if Overcast)
        df_resampled['flag_sw_dynamic_weather_mismatch'] = check_dynamic_solar_bounds(df_resampled['R_SW_in_Avg'], df_resampled['Expected_GHI'], df_resampled['weather_code'])
        
        # Check if measured solar is non-zero at night
        df_resampled['flag_sw_in_night_noise'] = check_nighttime_shortwave(df_resampled['R_SW_in_Avg'], df_resampled['Expected_GHI'])
    if 'R_SW_out_Avg' in df_resampled.columns:
        df_resampled['flag_sw_out_night_noise'] = check_nighttime_shortwave(df_resampled['R_SW_out_Avg'], df_resampled['Expected_GHI'])
        
    # Do the same for the PAR sensor (PPFD_IN_Avg) by converting umol/m2/s back to W/m2 approx (divide by ~2.1)
    # PAR only constitutes ~45% of the full shortwave solar spectrum (GHI).
    if 'PPFD_IN_Avg' in df_resampled.columns:
        expected_par_wm2 = df_resampled['Expected_GHI'] * 0.45
        df_resampled['flag_par_exceeds_clearsky'] = check_solar_radiation_bounds(df_resampled['PPFD_IN_Avg'] / 2.1, expected_par_wm2)
        df_resampled['flag_par_dynamic_weather_mismatch'] = check_dynamic_solar_bounds(df_resampled['PPFD_IN_Avg'] / 2.1, expected_par_wm2, df_resampled['weather_code'])

    output_dir = os.path.join(data_dir, 'data')
    os.makedirs(output_dir, exist_ok=True)

    # 4. Battery / Power Integrity
    if 'BattV' in df_resampled.columns and 'R_SW_in_Avg' in df_resampled.columns:
        df_resampled['flag_battery_anomaly'] = check_battery(df_resampled['BattV'], df_resampled['R_SW_in_Avg'])
        
    # 4b. Battery Longterm Trend
    if 'BattV' in df_resampled.columns and 'Expected_GHI' in df_resampled.columns:
        df_resampled['flag_battery_trend_flat'] = check_battery_trend(df_resampled['BattV'], df_resampled['Expected_GHI'], battery_chemistry, output_dir)
        
    # 5. Fan Status
    if 'TS100SS_Fan_RPM' in df_resampled.columns and 'R_SW_in_Avg' in df_resampled.columns:
        df_resampled['flag_fan_failure'] = check_fan_speed(df_resampled['TS100SS_Fan_RPM'], df_resampled['R_SW_in_Avg'])

    # 3. Thermodynamics
    if all(c in df_resampled.columns for c in ['AirTemp_C', 'RH', 'DewPoint_C']):
        df_resampled['flag_dewpoint_anomaly'] = check_dewpoint(df_resampled['AirTemp_C'], df_resampled['RH'], df_resampled['DewPoint_C'])

    # 4. Albedo bounds
    if all(c in df_resampled.columns for c in ['R_SW_in_Avg', 'R_SW_out_Avg']):
        df_resampled['flag_albedo_anomaly'] = check_albedo(df_resampled['R_SW_in_Avg'], df_resampled['R_SW_out_Avg'])

    # 5. Soil heat flux status
    if all(c in df_resampled.columns for c in ['shfp_cal_fail_1_1_1', 'shfp_cal_fail_1_1_2']):
        df_resampled['flag_shfp_invalid'] = check_shfp_status(df_resampled['shfp_cal_fail_1_1_1'], df_resampled['shfp_cal_fail_1_1_2'])

    # 6. Soil EC Spikes
    if 'TDR310_1_avg_EC' in df_resampled.columns:
        df_resampled['flag_soil_ec_spike'] = check_soil_ec_spikes(df_resampled['TDR310_1_avg_EC'])

    # 7. PAR to SW Ratio
    if all(c in df_resampled.columns for c in ['PPFD_IN_Avg', 'R_SW_in_Avg']):
        df_resampled['flag_par_ratio_anomaly'] = check_par_ratio(df_resampled['PPFD_IN_Avg'], df_resampled['R_SW_in_Avg'])
        
    # 8. NDVI Sensor Alignment
    if 'S2412_angle_offset' in df_resampled.columns:
        df_resampled['flag_ndvi_misaligned'] = check_ndvi_alignment(df_resampled['S2412_angle_offset'])
        
    # 8b. Longwave Uncorrected Body Temp Check & Correction
    if all(c in df_resampled.columns for c in ['R_LW_in_Avg', 'T_nr_Avg']):
        df_resampled['flag_lw_uncorrected'] = check_uncorrected_longwave(df_resampled['R_LW_in_Avg'])
        
        # AUTOMATIC CORRECTION: If the flag is raised for the majority of the dataset, 
        # it means the logger universally failed to add the body temperature.
        if df_resampled['flag_lw_uncorrected'].mean() > 0.5:
            print("WARNING: Uncorrected longwave data detected! Automatically correcting by adding sigma * T^4...")
            sigma = 5.670374419e-8
            body_emission = sigma * (df_resampled['T_nr_Avg'] ** 4)
            df_resampled['R_LW_in_Avg'] += body_emission
            if 'R_LW_out_Avg' in df_resampled.columns:
                df_resampled['R_LW_out_Avg'] += body_emission

    # 9. Stefan-Boltzmann Check (Target Temp vs R_LW_out)
    if all(c in df_resampled.columns for c in ['TargetTemp_C_Avg', 'R_LW_out_Avg']):
        estimated_lw_out = calculate_longwave_from_surface_temp(df_resampled['TargetTemp_C_Avg'])
        # Flag if deviation is > 20 W/m2
        df_resampled['flag_stefan_boltzmann_anomaly'] = (df_resampled['R_LW_out_Avg'] - estimated_lw_out).abs() > 20.0
        
    # 9b. Soil Heat Flux (G_PLATE) Correction & Storage Calculation
    # Convert raw plate output to W/m2 using self-calibration sensitivity
    for plate_idx in ['1_1_1', '1_1_2']:
        raw_col = f'G_PLATE_{plate_idx}'
        sens_col = f'shfp_cal_sensitivity_{plate_idx}'
        if all(c in df_resampled.columns for c in [raw_col, sens_col]):
            df_resampled[f'{raw_col}_Wm2'] = df_resampled[raw_col] / df_resampled[sens_col]
    
    # Calculate Soil Heat Storage (S_soil) for the 3cm layer above the plate
    if all(c in df_resampled.columns for c in ['TDR310_1_avg_VWC', 'TDR310_1_avg_T', 'G_PLATE_1_1_1_Wm2']):
        df_resampled['S_soil_1'] = calculate_soil_heat_storage(
            vwc_series=df_resampled['TDR310_1_avg_VWC'] / 100.0,  # Ensure VWC is a fraction if it was a percentage
            temp_series=df_resampled['TDR310_1_avg_T'],
            depth_m=0.03
        )
        df_resampled['G_0_1_1_1'] = df_resampled['G_PLATE_1_1_1_Wm2'] + df_resampled['S_soil_1']

    if all(c in df_resampled.columns for c in ['TDR310_1_avg_VWC', 'TDR310_1_avg_T', 'G_PLATE_1_1_2_Wm2']):
        df_resampled['S_soil_2'] = calculate_soil_heat_storage(
            vwc_series=df_resampled['TDR310_1_avg_VWC'] / 100.0,  # Assume same shallow soil VWC/T for both plates
            temp_series=df_resampled['TDR310_1_avg_T'],
            depth_m=0.03
        )
        df_resampled['G_0_1_1_2'] = df_resampled['G_PLATE_1_1_2_Wm2'] + df_resampled['S_soil_2']

    # 10. Soil Heat Flux spatial consistency (using corrected Surface Flux G_0 if available, else raw)
    g1_col = 'G_0_1_1_1' if 'G_0_1_1_1' in df_resampled.columns else 'G_PLATE_1_1_1'
    g2_col = 'G_0_1_1_2' if 'G_0_1_1_2' in df_resampled.columns else 'G_PLATE_1_1_2'
    if all(c in df_resampled.columns for c in [g1_col, g2_col]):
        # Flag if the two plates deviate by more than 25 W/m2
        df_resampled['flag_shfp_spatial_mismatch'] = (df_resampled[g1_col] - df_resampled[g2_col]).abs() > 25.0
        
    # 10b. Physics-Based Thermal Gradient SHFP Check
    # G_PLATE_1_1_2 is at 3cm depth. TDR310_1 is at 5cm. TargetTemp is surface.
    if all(c in df_resampled.columns for c in ['G_PLATE_1_1_2_Wm2', 'TDR310_1_avg_T', 'TDR310_1_avg_VWC', 'TargetTemp_C_Avg']):
        # Get soil params for the top layer
        top_soil_type = soil_types.get(1, 'silt_loam') if isinstance(soil_types, dict) else soil_types
        params = get_soil_params(top_soil_type)
        porosity = params[1]
        rho_b = params[5] if len(params) > 5 else 1.35
        q = params[6] if len(params) > 6 else 0.15
        
        # Calculate theoretical G between 0 and 5cm
        g_theory = estimate_soil_heat_flux_from_gradient(
            df_resampled['TargetTemp_C_Avg'],
            df_resampled['TDR310_1_avg_T'],
            df_resampled['TDR310_1_avg_VWC'] / 100.0,  # Ensure VWC is a fraction
            porosity, rho_b, q, depth_m=0.05
        )
        
        # Compare against the surface-corrected heat flux if available
        g_measured = df_resampled['G_0_1_1_2'] if 'G_0_1_1_2' in df_resampled.columns else df_resampled['G_PLATE_1_1_2_Wm2']
        
        df_resampled['flag_shfp_thermal_mismatch_2'] = check_shfp_thermal_gradient_mismatch(g_measured, g_theory, threshold=50.0)

    # 11. Rain vs Soil Moisture Mismatch (Time-Lagged by Depth)
    if 'RainE_Standard_Int_1m' in df_resampled.columns:
        tdr_depth_map = {1: 0.05, 2: 0.10, 3: 0.20, 4: 0.50, 5: 1.00, 6: 1.50}
        for i in range(1, 7):
            vwc_col = f'TDR310_{i}_avg_VWC'
            if vwc_col in df_resampled.columns:
                depth_m = tdr_depth_map.get(i, 0.05)
                
                # Get soil type for this layer
                if isinstance(soil_types, dict):
                    current_soil_type = soil_types.get(i, 'silt_loam')
                else:
                    current_soil_type = soil_types
                    
                # Get K_sat
                params = get_soil_params(current_soil_type)
                k_sat_cm_h = params[4] if len(params) > 4 else 0.45
                
                # Calculate delta S proxy for this layer (VWC diff * 10 for sensitivity)
                delta_s = df_resampled[vwc_col].diff().fillna(0) * 10.0
                
                # Run mismatch check with time lag
                df_resampled[f'flag_rain_soil_mismatch_{i}'] = flag_rain_soil_moisture_mismatch(
                    df_resampled['RainE_Standard_Int_1m'].fillna(0), 
                    delta_s,
                    depth_m=depth_m,
                    k_sat_cm_h=k_sat_cm_h,
                    threshold_ds=5.0
                )

    # 12. Aerodynamic Sensible Heat Estimation
    if 'TargetTemp_C_Avg' in df_resampled.columns and 'AirTemp_C' in df_resampled.columns:
        if 'Windspeed' in df_resampled.columns:
            wind_speed = df_resampled['Windspeed']
        elif 'WS' in df_resampled.columns:
            wind_speed = df_resampled['WS']
        else:
            wind_speed = None

        if wind_speed is not None:
            print("Calculating dynamic aerodynamic resistance from wind speed...")
            r_a = calculate_aerodynamic_resistance(wind_speed, z_m=3.0)
        else:
            r_a = 50.0

        df_resampled['Estimated_H_W_m2'] = estimate_sensible_heat_from_temp(
            df_resampled['TargetTemp_C_Avg'],
            df_resampled['AirTemp_C'],
            aerodynamic_resistance=r_a,
            altitude=altitude
        )

    # 12.5 Full Surface Energy Balance Closure
    rad_cols = ['R_SW_in_Avg', 'R_SW_out_Avg', 'R_LW_in_Avg', 'R_LW_out_Avg']
    eb_cols = rad_cols + ['Estimated_H_W_m2', 'G_PLATE_1_1_1']
    if all(c in df_resampled.columns for c in eb_cols):
        # Calculate Net Radiation (Rn)
        rn = (df_resampled['R_SW_in_Avg'] - df_resampled['R_SW_out_Avg'] + 
              df_resampled['R_LW_in_Avg'] - df_resampled['R_LW_out_Avg'])
        
        g = df_resampled['G_PLATE_1_1_1']
        h = df_resampled['Estimated_H_W_m2']
        
        # Calculate residual: Rn - G - H - LE
        # Assuming LE = 0 for the worst-case check
        residual = calculate_energy_balance_residual(rn, g, h, 0.0)
        
        # Flag if Residual < -50 W/m2 (impossible energy creation without LE)
        df_resampled['flag_energy_balance_anomaly'] = residual < -50.0

    # 13. IR Temp Consistency
    if all(c in df_resampled.columns for c in ['TargetTemp_C_Min', 'TargetTemp_C_Avg', 'TargetTemp_C_Max']):
        df_resampled['flag_ir_target_anomaly'] = check_ir_temp_consistency(df_resampled['TargetTemp_C_Min'], df_resampled['TargetTemp_C_Avg'], df_resampled['TargetTemp_C_Max'])
    if all(c in df_resampled.columns for c in ['BodyTemp_C_Min', 'BodyTemp_C_Avg', 'BodyTemp_C_Max']):
        df_resampled['flag_ir_body_anomaly'] = check_ir_temp_consistency(df_resampled['BodyTemp_C_Min'], df_resampled['BodyTemp_C_Avg'], df_resampled['BodyTemp_C_Max'])

    # 14. Sensor Body Temp bounds
    if 'T_nr_Avg' in df_resampled.columns and 'AirTemp_C' in df_resampled.columns:
        # T_nr_Avg is in Kelvin, AirTemp_C is in Celsius
        df_resampled['flag_nr_body_temp'] = check_body_temp(df_resampled['T_nr_Avg'] - 273.15, df_resampled['AirTemp_C'])
    if 'BodyTemp_C_Avg' in df_resampled.columns and 'AirTemp_C' in df_resampled.columns:
        df_resampled['flag_ir_body_temp'] = check_body_temp(df_resampled['BodyTemp_C_Avg'], df_resampled['AirTemp_C'])

    # 15. Radiation Redundancy
    if all(c in df_resampled.columns for c in ['SW_rad_Avg', 'R_SW_in_Avg']):
        df_resampled['flag_sw_rad_mismatch'] = check_radiation_redundancy(df_resampled['SW_rad_Avg'], df_resampled['R_SW_in_Avg'])
    if all(c in df_resampled.columns for c in ['LW_rad_Avg', 'R_LW_in_Avg']):
        df_resampled['flag_lw_rad_mismatch'] = check_radiation_redundancy(df_resampled['LW_rad_Avg'], df_resampled['R_LW_in_Avg'])
        
    # (Net radiation check removed because T_nr_Avg is actually a temperature)
        
    # 16. Precipitation consistency
    if all(c in df_resampled.columns for c in ['RainE_Standard_Precip_Tot', 'RainE_Standard_Int_1m']):
        df_resampled['flag_precip_consistency'] = check_precip_consistency(df_resampled['RainE_Standard_Precip_Tot'], df_resampled['RainE_Standard_Int_1m'])

    # 17. Calibration Sensitivity Change Detection
    for c in ['shfp_cal_sensitivity_1_1_1', 'shfp_cal_sensitivity_1_1_2']:
        if c in df_resampled.columns:
            df_resampled[f'flag_{c}_change'] = check_static_calibration(df_resampled[c])

    # 18. Generic Statistical Anomaly Detection
    # Exclude non-continuous/categorical/accumulating variables
    exclude_cols = ['time', 'RainE_Standard_Int_1m', 'RainE_Standard_Int_1m_hr', 
                    'RainE_Standard_Precip_lr', 'RainE_Standard_Precip_Tot',
                    'TS100SS_Fan_RPM']
    exclude_prefixes = ('flag_', 'shfp_cal_fail')
    
    for col in df_resampled.columns:
        if col not in exclude_cols and not col.startswith(exclude_prefixes) and pd.api.types.is_numeric_dtype(df_resampled[col]):
            # We skip flatline detection for solar radiation as it flatlines naturally at night (0.0)
            skip_flatline = ('SW' in col or 'PPFD' in col or 'PAR' in col or 'Expected_GHI' in col)
            
            spike, jump, flatline = check_statistical_anomalies(df_resampled[col], window_minutes=180, z_thresh=5.0)
            
            df_resampled[f'flag_stat_spike_{col}'] = spike
            df_resampled[f'flag_stat_jump_{col}'] = jump
            if not skip_flatline:
                df_resampled[f'flag_stat_flatline_{col}'] = flatline

    # 19. Soil Depth Checks (1 to 6)
    for i in range(1, 7):
        # EC spikes
        if f'TDR310_{i}_avg_EC' in df_resampled.columns:
            df_resampled[f'flag_tdr_{i}_ec_spike'] = check_soil_ec_spikes(df_resampled[f'TDR310_{i}_avg_EC'])
        if f'TDR310_{i}_avg_PEC' in df_resampled.columns:
            df_resampled[f'flag_tdr_{i}_pec_spike'] = check_soil_ec_spikes(df_resampled[f'TDR310_{i}_avg_PEC'])
        # Permittivity
        if f'TDR310_{i}_avg_P' in df_resampled.columns:
            df_resampled[f'flag_tdr_{i}_perm_anomaly'] = check_permittivity(df_resampled[f'TDR310_{i}_avg_P'])
        # Soil Temp redundancy
        if f'TEROS22_{i}_avg_Temp' in df_resampled.columns and f'TDR310_{i}_avg_T' in df_resampled.columns:
            df_resampled[f'flag_soil_temp_mismatch_{i}'] = check_soil_temp_redundancy(df_resampled[f'TEROS22_{i}_avg_Temp'], df_resampled[f'TDR310_{i}_avg_T'])
    # 13. Soil Moisture Validation (van Genuchten curve)
    for i in range(1, 7):
        # Determine soil type for this specific depth
        if isinstance(soil_types, dict):
            current_soil_type = soil_types.get(i, 'silt_loam')
        else:
            current_soil_type = soil_types
            
        # Look up van Genuchten parameters based on soil type input for this depth
        params = get_soil_params(current_soil_type)
        theta_r, theta_s, alpha, n = params[0], params[1], params[2], params[3]
        
        if f'TEROS22_{i}_avg_MP' in df_resampled.columns and f'TDR310_{i}_avg_VWC' in df_resampled.columns:
            # TEROS22 reports in kPa. The alpha parameter is in 1/cm.
            # Convert kPa to cm of water head (1 kPa = 10.197 cm)
            h_cm = df_resampled[f'TEROS22_{i}_avg_MP'].abs() * 10.197
            expected_vwc_frac = van_genuchten(h_cm, theta_r, theta_s, alpha, n)
            
            # TDR310 reports VWC in percent (0-100), but van_genuchten gives fraction (0-1)
            measured_vwc_frac = df_resampled[f'TDR310_{i}_avg_VWC'] / 100.0
            
            # Flag if VWC deviates from expected curve significantly (>10% absolute VWC)
            df_resampled[f'flag_vg_curve_{i}'] = np.abs(measured_vwc_frac - expected_vwc_frac) > 0.1

    # Example placeholder for Energy Balance
    # if 'R_SW_in_Avg' in df_resampled.columns:
    #    rn = df_resampled['R_SW_in_Avg'] - df_resampled['R_SW_out_Avg'] + df_resampled['R_LW_in_Avg'] - df_resampled['R_LW_out_Avg']
    
    # Print summary of failed checks
    flag_cols = [col for col in df_resampled.columns if col.startswith('flag_')]
    
    summary_lines = []
    if flag_cols:
        summary_lines.append("--- QC Check Summary ---")
        print(f"\n{summary_lines[0]}")
        for col in flag_cols:
            fails = df_resampled[col].sum()
            line = f" - {col}: {fails} anomalies detected"
            summary_lines.append(line)
            print(line)
        summary_lines.append("------------------------")
        print(summary_lines[-1])

    output_dir = os.path.join(data_dir, 'data')
    os.makedirs(output_dir, exist_ok=True)
    
    # Save CSV
    output_file = os.path.join(output_dir, 'qc_output_flagged.csv')
    df_resampled.to_csv(output_file)
    
    # Save TXT summary
    txt_output_file = os.path.join(output_dir, 'qc_summary.txt')
    with open(txt_output_file, 'w') as f:
        f.write("\n".join(summary_lines))
        
    print(f"\nPipeline execution finished successfully.")
    print(f"Data output saved to {output_file}")
    print(f"Text summary saved to {txt_output_file}")
    return df_resampled

if __name__ == "__main__":
    # Assuming running from the root of the repo
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    
    # Example of depth-specific soil types
    site_soil_profile = {
        1: 'sand',
        2: 'sandy_loam',
        3: 'loam',
        4: 'silty_clay_loam',
        5: 'silty_clay_loam',
        6: 'clay'
    }
    
    
    # Site-specific NR01 radiation sensitivities (in microvolts per W/m2)
    site_nr01_sensitivities = {
        'sw_in': 14.55,
        'sw_out': 12.44,
        'lw_in': 14.26,
        'lw_out': 13.90
    }
    
    run_pipeline(data_dir, 51.5074, -0.1278, altitude=35, soil_types=site_soil_profile, battery_chemistry='lifepo4', nr01_sensitivities=site_nr01_sensitivities)
