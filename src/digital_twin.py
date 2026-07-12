import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np

# Try loading environment variables for API keys
load_dotenv()

from ingest.met_office import fetch_met_office_forecast
from ingest.ukso import fetch_bgs_soil_properties
from models.lsm_solver import run_1d_heat_simulation

def run_digital_twin(latitude, longitude):
    """
    Coordinates the UK-Specific Digital Twin simulation.
    1. Fetches soil properties from UKSO.
    2. Fetches forcing data from Met Office.
    3. Runs 1D soil-water-heat simulation.
    """
    print(f"Initializing Digital Twin for coordinates ({latitude}, {longitude})...")
    
    # 1. Fetch Soil Properties
    print("\n--- 1. Fetching Soil Characteristics (BGS/UKSO) ---")
    soil_props = fetch_bgs_soil_properties(latitude, longitude)
    print("Retrieved Soil Properties:", soil_props)
    
    # 2. Fetch Met Office Weather Forcing
    print("\n--- 2. Fetching Weather Forcing (Met Office DataHub) ---")
    try:
        weather_df = fetch_met_office_forecast(latitude, longitude)
        print(f"Retrieved {len(weather_df)} hourly forecast steps.")
    except ValueError as e:
        print(f"Skipping Met Office fetch: {e}")
        weather_df = pd.DataFrame()
        
    # 3. Simulate (1D Finite Difference LSM)
    print("\n--- 3. Running 1D Land Surface Model ---")
    if not weather_df.empty and soil_props:
        # Get the simple texture description from UKSO
        texture_desc = soil_props.get('Parent.Material.Soil.texture.simple', 'SILT_LOAM')
        
        print(f"Executing numerical solver (Fourier Heat Eq) for {len(weather_df)} steps...")
        # Define depth grid (e.g. 5cm to 100cm)
        depths = np.linspace(0.05, 1.0, 20)
        sim_df = run_1d_heat_simulation(weather_df, texture_desc, depths_m=depths)
        
        print("Simulation complete!")
        print("\nPredicted Temperatures for the first 5 hours:")
        print(sim_df[['T_air', 'T_surface_driven', 'T_soil_0.05m', 'T_soil_0.10m']].head())
        
        output_path = "digital_twin_output.csv"
        sim_df.to_csv(output_path)
        print(f"\nSaved simulation results to {output_path}")
        return sim_df
    else:
        print("Missing inputs. Simulation skipped.")
        return pd.DataFrame()
        
if __name__ == "__main__":
    # Default to the CH-TRIGR-01 coordinates roughly (e.g. 51.5, -1.0)
    run_digital_twin(51.5, -1.0)
