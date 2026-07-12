import os
import requests
import pandas as pd
from datetime import datetime

def fetch_met_office_forecast(latitude, longitude):
    """
    Fetches Observation Land data from the UK Met Office DataHub.
    Requires MET_OFFICE_CLIENT_ID to be set in the environment.
    """
    api_key = os.getenv('MET_OFFICE_CLIENT_ID')
    
    if not api_key:
        raise ValueError("Met Office API key not found. Please set MET_OFFICE_CLIENT_ID in your .env file.")
        
    headers = {
        "apikey": api_key,
        "accept": "application/json"
    }
    
    print(f"Finding nearest Met Office Observation station for {latitude}, {longitude}...")
    try:
        # 1. Find nearest geohash
        nearest_url = f"https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest?lat={latitude}&lon={longitude}"
        res_nearest = requests.get(nearest_url, headers=headers)
        res_nearest.raise_for_status()
        nearest_data = res_nearest.json()
        
        if not nearest_data:
            raise ValueError("No nearby stations found.")
            
        geohash = nearest_data[0]['geohash']
        print(f"Found nearest station geohash: {geohash} ({nearest_data[0].get('area', 'Unknown')})")
        
        # 2. Fetch observations for geohash
        obs_url = f"https://data.hub.api.metoffice.gov.uk/observation-land/1/{geohash}"
        res_obs = requests.get(obs_url, headers=headers)
        res_obs.raise_for_status()
        time_series = res_obs.json()
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(time_series)
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            # Sort by time just in case
            df.sort_index(inplace=True)
            
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Met Office data: {e}")
        return pd.DataFrame()
