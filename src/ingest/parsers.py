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
    files = glob.glob(os.path.join(data_dir, "fdri_data_explorer_*.csv"))
    
    dataframes = []
    for f in files:
        df = pd.read_csv(f)
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
