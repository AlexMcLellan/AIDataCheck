import pandas as pd
import glob
import os

def load_and_merge_data(data_dir):
    """
    Loads all CSV files in the data directory and merges them on the 'time' column.
    
    Parameters:
    -----------
    data_dir : str
        Directory containing the CSV files.
        
    Returns:
    --------
    merged_df : pd.DataFrame
        Data merged and sorted by time.
    """
    # Load all CSVs except for our output files
    files = [f for f in glob.glob(os.path.join(data_dir, "*.csv")) if "qc_output" not in f]
    if not files:
        files = [f for f in glob.glob(os.path.join(data_dir, "data", "*.csv")) if "qc_output" not in f]
    
    dataframes = []
    mapping = {
        'fdri_CH-TRIGR-01_PT1M_Processed_Air temperature': 'AirTemp_C',
        'fdri_CH-TRIGR-01_PT1M_Processed_Relative humidity': 'RH',
        'fdri_CH-TRIGR-01_PT1M_Processed_Dew point temperature': 'DewPoint_C',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Latent heat flux': 'LE',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Sensible heat flux': 'H_EC',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Friction velocity': 'u_star',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Co2 flux': 'FCO2',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Steady State and Integral Turbulence Characteristics for sensible heat flux': 'qc_H_flag',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Steady State and Integral Turbulence Characteristics for latent heat flux': 'qc_LE_flag',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Ambient water vapour pressure deficit': 'VPD',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Wind speed': 'Windspeed',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Wind direction': 'WindDir',
        'fdri_CH-TRIGR-01_PT30M_Processed_Battery voltage': 'BattV',
        'fdri_CH-TRIGR-01_PT15M_Processed_Target temperature': 'TargetTemp_C_Avg',
        'fdri_CH-TRIGR-01_PT15M_Processed_Maximum target temperature': 'TargetTemp_C_Max',
        'fdri_CH-TRIGR-01_PT15M_Processed_Minimum target temperature': 'TargetTemp_C_Min',
        # Physical Depth 1: 5cm (wired to 50cm raw channel)
        'fdri_CH-TRIGR-01_PT15M_Processed_Volumetric water content (50cm depth - TDR)': 'TDR310_1_avg_VWC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (50cm depth - TDR)': 'TDR310_1_avg_T',
        'fdri_CH-TRIGR-01_PT15M_Processed_Electrical permittivity (50cm depth - TDR)': 'TDR310_1_avg_P',
        'fdri_CH-TRIGR-01_PT15M_Processed_Pore water electrical conductivity (50cm depth - TDR)': 'TDR310_1_avg_PEC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Bulk electrical conductivity (50cm depth - TDR)': 'TDR310_1_avg_EC',
        # Physical Depth 2: 10cm (wired to 10cm raw channel)
        'fdri_CH-TRIGR-01_PT15M_Processed_Volumetric water content (10cm depth - TDR)': 'TDR310_2_avg_VWC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (10cm depth - TDR)': 'TDR310_2_avg_T',
        'fdri_CH-TRIGR-01_PT15M_Processed_Electrical permittivity (10cm depth - TDR)': 'TDR310_2_avg_P',
        'fdri_CH-TRIGR-01_PT15M_Processed_Pore water electrical conductivity (10cm depth - TDR)': 'TDR310_2_avg_PEC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Bulk electrical conductivity (10cm depth - TDR)': 'TDR310_2_avg_EC',
        # Physical Depth 3: 20cm (wired to 30cm raw channel)
        'fdri_CH-TRIGR-01_PT15M_Processed_Volumetric water content (30cm depth - TDR)': 'TDR310_3_avg_VWC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (30cm depth - TDR)': 'TDR310_3_avg_T',
        'fdri_CH-TRIGR-01_PT15M_Processed_Electrical permittivity (30cm depth - TDR)': 'TDR310_3_avg_P',
        'fdri_CH-TRIGR-01_PT15M_Processed_Pore water electrical conductivity (30cm depth - TDR)': 'TDR310_3_avg_PEC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Bulk electrical conductivity (30cm depth - TDR)': 'TDR310_3_avg_EC',
        # Physical Depth 4: 30cm (wired to 40cm raw channel)
        'fdri_CH-TRIGR-01_PT15M_Processed_Volumetric water content (40cm depth - TDR)': 'TDR310_4_avg_VWC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (40cm depth - TDR)': 'TDR310_4_avg_T',
        'fdri_CH-TRIGR-01_PT15M_Processed_Electrical permittivity (40cm depth - TDR)': 'TDR310_4_avg_P',
        'fdri_CH-TRIGR-01_PT15M_Processed_Pore water electrical conductivity (40cm depth - TDR)': 'TDR310_4_avg_PEC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Bulk electrical conductivity (40cm depth - TDR)': 'TDR310_4_avg_EC',
        # Physical Depth 5: 40cm (wired to 20cm raw channel)
        'fdri_CH-TRIGR-01_PT15M_Processed_Volumetric water content (20cm depth - TDR)': 'TDR310_5_avg_VWC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (20cm depth - TDR)': 'TDR310_5_avg_T',
        'fdri_CH-TRIGR-01_PT15M_Processed_Electrical permittivity (20cm depth - TDR)': 'TDR310_5_avg_P',
        'fdri_CH-TRIGR-01_PT15M_Processed_Pore water electrical conductivity (20cm depth - TDR)': 'TDR310_5_avg_PEC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Bulk electrical conductivity (20cm depth - TDR)': 'TDR310_5_avg_EC',
        # Physical Depth 6: 50cm (wired to 5cm raw channel)
        'fdri_CH-TRIGR-01_PT15M_Processed_Volumetric water content (5cm depth - TDR)': 'TDR310_6_avg_VWC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (5cm depth - TDR)': 'TDR310_6_avg_T',
        'fdri_CH-TRIGR-01_PT15M_Processed_Electrical permittivity (5cm depth - TDR)': 'TDR310_6_avg_P',
        'fdri_CH-TRIGR-01_PT15M_Processed_Pore water electrical conductivity (5cm depth - TDR)': 'TDR310_6_avg_PEC',
        'fdri_CH-TRIGR-01_PT15M_Processed_Bulk electrical conductivity (5cm depth - TDR)': 'TDR310_6_avg_EC',
        'fdri_CH-TRIGR-01_PT1M_Processed_Precipitation (Standard height RG)': 'RainE_Standard_Precip_Tot',
        'fdri_CH-TRIGR-01_PT1M_Processed_Precipitation intensity (Standard height RG)': 'RainE_Standard_Int_1m',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil matric potential (5cm depth - East - Teros22)': 'TEROS22_1_avg_MP',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (5cm depth - East - Teros22)': 'TEROS22_1_avg_Temp',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil matric potential (10cm depth - East - Teros22)': 'TEROS22_2_avg_MP',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (10cm depth - East - Teros22)': 'TEROS22_2_avg_Temp',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil matric potential (20cm depth - East - Teros22)': 'TEROS22_3_avg_MP',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (20cm depth - East - Teros22)': 'TEROS22_3_avg_Temp',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil matric potential (30cm depth - East - Teros22)': 'TEROS22_4_avg_MP',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (30cm depth - East - Teros22)': 'TEROS22_4_avg_Temp',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil matric potential (40cm depth - East - Teros22)': 'TEROS22_5_avg_MP',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (40cm depth - East - Teros22)': 'TEROS22_5_avg_Temp',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil matric potential (50cm depth - East - Teros22)': 'TEROS22_6_avg_MP',
        'fdri_CH-TRIGR-01_PT15M_Processed_Soil temperature (50cm depth - East - Teros22)': 'TEROS22_6_avg_Temp',
        # SoilVUE10 Profile Probe (Depths 1 to 6)
        'fdri_CH-TRIGR-01_PT30M_Processed_Volumetric water content (5cm depth - SoilVUE)': 'SoilVUE_1_avg_VWC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Soil temperature (5cm depth - SoilVUE)': 'SoilVUE_1_avg_Temp',
        'fdri_CH-TRIGR-01_PT30M_Processed_Apparent permittivity (5cm depth - SoilVUE)': 'SoilVUE_1_avg_P',
        'fdri_CH-TRIGR-01_PT30M_Processed_Bulk electrical conductivity (5cm depth - SoilVUE)': 'SoilVUE_1_avg_EC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Volumetric water content (10cm depth - SoilVUE)': 'SoilVUE_2_avg_VWC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Soil temperature (10cm depth - SoilVUE)': 'SoilVUE_2_avg_Temp',
        'fdri_CH-TRIGR-01_PT30M_Processed_Apparent permittivity (10cm depth - SoilVUE)': 'SoilVUE_2_avg_P',
        'fdri_CH-TRIGR-01_PT30M_Processed_Bulk electrical conductivity (10cm depth - SoilVUE)': 'SoilVUE_2_avg_EC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Volumetric water content (20cm depth - SoilVUE)': 'SoilVUE_3_avg_VWC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Soil temperature (20cm depth - SoilVUE)': 'SoilVUE_3_avg_Temp',
        'fdri_CH-TRIGR-01_PT30M_Processed_Apparent permittivity (20cm depth - SoilVUE)': 'SoilVUE_3_avg_P',
        'fdri_CH-TRIGR-01_PT30M_Processed_Bulk electrical conductivity (20cm depth - SoilVUE)': 'SoilVUE_3_avg_EC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Volumetric water content (30cm depth - SoilVUE)': 'SoilVUE_4_avg_VWC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Soil temperature (30cm depth - SoilVUE)': 'SoilVUE_4_avg_Temp',
        'fdri_CH-TRIGR-01_PT30M_Processed_Apparent permittivity (30cm depth - SoilVUE)': 'SoilVUE_4_avg_P',
        'fdri_CH-TRIGR-01_PT30M_Processed_Bulk electrical conductivity (30cm depth - SoilVUE)': 'SoilVUE_4_avg_EC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Volumetric water content (40cm depth - SoilVUE)': 'SoilVUE_5_avg_VWC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Soil temperature (40cm depth - SoilVUE)': 'SoilVUE_5_avg_Temp',
        'fdri_CH-TRIGR-01_PT30M_Processed_Apparent permittivity (40cm depth - SoilVUE)': 'SoilVUE_5_avg_P',
        'fdri_CH-TRIGR-01_PT30M_Processed_Bulk electrical conductivity (40cm depth - SoilVUE)': 'SoilVUE_5_avg_EC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Volumetric water content (50cm depth - SoilVUE)': 'SoilVUE_6_avg_VWC',
        'fdri_CH-TRIGR-01_PT30M_Processed_Soil temperature (50cm depth - SoilVUE)': 'SoilVUE_6_avg_Temp',
        'fdri_CH-TRIGR-01_PT30M_Processed_Apparent permittivity (50cm depth - SoilVUE)': 'SoilVUE_6_avg_P',
        'fdri_CH-TRIGR-01_PT30M_Processed_Bulk electrical conductivity (50cm depth - SoilVUE)': 'SoilVUE_6_avg_EC',
        'fdri_CH-TRIGR-01_PT1M_Processed_Incoming photosynthetic photon flux density': 'PPFD_IN_Avg',
        # Sonic & Turbulence Variables
        'fdri_CH_TRIGR_EC_PT30M_Raw_Sonic temperature': 'Sonic_Temp_C',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Monin-Obukhov length': 'L_MO',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Wind speed in vertical direction (standard deviation)': 'sigma_w',
        'fdri_CH_TRIGR_EC_PT30M_Raw_H2O mole fraction in wet air': 'H2O_mole_fraction',
        'fdri_CH_TRIGR_EC_PT30M_Raw_Relative humidity': 'RH_EC',
        # Optics & Landscape Sensing
        'fdri_CH-TRIGR-01_PT15M_Processed_Normalised difference vegetation index': 'NDVI',
        'fdri_CH-TRIGR-01_PT30M_Processed_Soil moisture (Finapp)': 'Soil_Moisture_CRNS',
        'fdri_CH-TRIGR-01_PT30M_Processed_Local snow water equivalent (Finapp)': 'SWE_CRNS',
    }
    
    for f in files:
        df = pd.read_csv(f)
        df = df.rename(columns=mapping)
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            dataframes.append(df)
            
    if not dataframes:
        return pd.DataFrame()
        
    # Merge all dataframes. Outer join to handle different frequencies (1min, 15min, etc)
    # Using reduce or concat
    merged_df = pd.concat(dataframes, axis=1)
    
    # Remove duplicate columns if any
    merged_df = merged_df.loc[:, ~merged_df.columns.duplicated()]
    merged_df.sort_index(inplace=True)
    
    return merged_df

def resample_to_frequency(df, freq='30min', ffill_limit=None):
    """
    Resamples the dataframe to a unified temporal resolution.
    
    Parameters:
    -----------
    df : pd.DataFrame
    freq : str
        Pandas frequency string (default '30T' for 30 minutes)
    ffill_limit : int, optional
        Number of periods to forward-fill NaNs.
        
    Returns:
    --------
    resampled_df : pd.DataFrame
    """
    # For a real pipeline, we should differentiate between state variables (mean) 
    # and fluxes/totals (sum). For now, we take the mean for simplicity.
    resampled_df = df.resample(freq).mean()
    if ffill_limit is not None:
        resampled_df = resampled_df.ffill(limit=ffill_limit)
    return resampled_df
