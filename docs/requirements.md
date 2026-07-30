# Data Quality Control (QC) Requirements

This document outlines the systematic requirements and constraints applied to the incoming datalogger streams to ensure scientific validity and sensor health.

## 1. Temporal & Structural Integrity
- **Uniformity**: Data must be uniformly resampled to a strict 30-minute frequency. *(Applies to: All variables)*
- **Missing Data**: Gaps and missing timestamps must be identified and accounted for before physical models are applied. *(Applies to: `TIMESTAMP`, All variables)*

## 2. Statistical Anomalies
- **Spike Detection**: Values exceeding expected statistical variance (Z-score thresholds) must be flagged as anomalous spikes. *(Applies to: All numerical variables)*
  - **Calc:** \( Z = \frac{x - \mu}{\sigma} \) (Flag if \(|Z| > 3.0\))
- **Gradient Jumps**: Physically impossible step-changes between consecutive 30-minute measurements must be flagged. *(Applies to: All numerical variables)*
  - **Calc:** \( \Delta x = |x_t - x_{t-1}| \) (Flag if \( \Delta x > \text{Threshold} \))
- **Flatlining**: Sensors reporting the exact same value for extended periods (e.g., > 6 hours) must be flagged as potentially jammed or frozen. *(Applies to: All numerical variables)*
  - **Calc:** Flag if standard deviation over a rolling 12-timestep (6-hour) window is exactly \( 0.0 \).

## 3. Radiometric & Solar Energy Bounds
- **Theoretical Maximums**: Global Horizontal Irradiance (GHI) must not exceed theoretical clear-sky solar maximums calculated for the specific latitude, longitude, and time. *(Applies to: `SW_in_Avg`, `SW_rad_Avg`, `R_SW_in_Avg`)*
  - **Calc:** \( \text{Expected GHI} \) calculated via PVLib Ineichen clear-sky model.
- **Dynamic Atmospheric Bounds**: Expected irradiance bounds must dynamically adjust using live contextual weather codes (e.g., Hukseflux readings must scale down appropriately during overcast conditions identified via the Met Office API). *(Applies to: `SW_in_Avg`, `SW_rad_Avg`, `R_SW_in_Avg`)*
  - **Calc:** 
    - If Sunny (Code 1): Flag if \( GHI < 0.70 \times \text{Expected GHI} \) or \( > 1.10 \times \text{Expected GHI} \)
    - If Overcast (Code 8): Flag if \( GHI > 0.40 \times \text{Expected GHI} \)
- **PAR Scaling**: Photosynthetically Active Radiation (PPFD) must remain a realistic fraction (approximately 45%) of the total broadband Shortwave Irradiance (GHI). *(Applies to: `PPFD_IN_Avg` against `SW_in_Avg` / `SW_rad_Avg` / `R_SW_in_Avg`)*
  - **Calc:** \( \text{PAR}_{W/m^2} = \text{PPFD} \times 0.219 \). Flag if \( \frac{\text{PAR}_{W/m^2}}{\text{GHI}} \notin [0.35, 0.55] \).
- **Longwave Thermodynamics**: Measured Longwave Radiation must remain consistent with the Stefan-Boltzmann law ($\epsilon \sigma T^4$) derived from the surface target temperature. *(Applies to: `LW_rad_Avg`, `R_LW_in_Avg` against `TargetTemp_C_Avg`)*
  - **Calc:** \( \text{LW}_{out} = \epsilon \sigma T_K^4 \) where \( \epsilon = 0.95 \) and \( \sigma = 5.67 \times 10^{-8} \text{ W m}^{-2}\text{K}^{-4} \).

## 4. Energy Balance Consistency
- **Sensible Heat Flux**: Must align with bulk aerodynamic transfer expectations, scaling the surface-to-air temperature gradient against the aerodynamic resistance ($r_a$) derived dynamically from the logarithmic wind profile. *(Applies to: `TargetTemp_C_Avg`, `AirTemp_C`, `Windspeed` / `WS`)*
  - **Calc:** \( H = \frac{\rho c_p (T_s - T_a)}{r_a} \) where \( r_a = \frac{\ln(z_m / z_{0m}) \ln(z_m / z_{0h})}{k^2 \cdot u} \).
- **Soil Heat Flux**: Heat flux plates must agree with the theoretical thermal gradient calculated via Fourier's Law of Heat Conduction, utilizing the Johansen (1975) thermal conductivity model and local soil textures. *(Applies to: `Heatflux_1_Avg`, `Heatflux_2_Avg` against `SoilTemp_C_Avg_1`, `SoilTemp_C_Avg_2`, etc.)*
  - **Calc:** \( G_{measured} \approx \lambda \frac{T_1 - T_2}{z_1 - z_2} \), where \( \lambda \) is the estimated soil thermal conductivity.

## 5. Hydrological Constraints
- **Porosity Limits**: Volumetric Water Content (VWC) must not exceed the theoretical saturated capacity (porosity) of the specific USDA soil texture class. *(Applies to: `VWC_Avg_1`, `VWC_Avg_2`, etc.)*
  - **Calc:** Flag if \( \text{VWC} > \theta_s \) (where \( \theta_s \) is the Van Genuchten porosity parameter for the soil texture).
- **Precipitation Mismatch**: Significant spikes in deep soil moisture must be flagged if there has been no corresponding precipitation in the recent past, accounting for soil-specific percolation time-lags based on saturated hydraulic conductivity. *(Applies to: `VWC_Avg_x` against `Rain_mm_Tot`)*
  - **Calc:** \( t_{lag} = \frac{\text{depth (cm)}}{K_{sat} \text{ (cm/hr)}} \). Flag if \( \Delta \text{Storage} > 5\text{mm} \) AND \( \sum_{window} P_{lagged} < 1.0\text{mm} \).

## 6. System Health
- **Power Stability**: Battery voltage must remain above critical chemistry-specific thresholds (e.g., 11.5V for a 12.8V LFP system), with flags indicating if the system is failing to charge during high solar irradiance periods. *(Applies to: `Batt_V_Avg` against expected GHI)*

## 7. Secondary Hardware & Consistency Checks
- **Thermodynamic Consistency**: Expected dew point calculated via the Magnus-Tetens formula must match the measured dew point. *(Applies to: `DewPoint_C`, `AirTemp_C`, `RH`)*
  - **Calc:** \( T_{dp} = \frac{237.3 \cdot \alpha}{17.27 - \alpha} \), where \( \alpha = \frac{17.27 T}{237.3 + T} + \ln(RH) \).
- **Fan Aspiration**: The active ventilation fan for the temperature/RH shield must not fail when solar radiation is high, to prevent artificial heating of the sensor. *(Applies to: `TS100SS_Fan_RPM` against `R_SW_in_Avg`)*
- **Albedo Bounds**: Surface albedo must remain within physical bounds (0.05 to 0.95). *(Applies to: `R_SW_in_Avg`, `R_SW_out_Avg`)*
- **Precipitation Consistency**: Increases in cumulative total precipitation must align with non-zero rainfall intensity metrics. *(Applies to: `RainE_Standard_Precip_Tot` vs `RainE_Standard_Int_1m`)*
- **Radiometer Body Temperatures**: Internal body thermistors of the radiometers must not severely deviate from ambient air temperature. *(Applies to: `T_nr_Avg`, `BodyTemp_C_Avg` against `AirTemp_C`)*
- **IR Temperature Integrity**: Target temperatures must follow logical bounds (Min \(\le\) Avg \(\le\) Max). *(Applies to: `TargetTemp_C_Min`, `Avg`, `Max`)*
- **Soil Sensor Integrity**: Soil apparent permittivity must remain within 1.0 (air) to 80.0 (water). Sudden massive spikes in Electrical Conductivity (EC) are flagged. *(Applies to: `TDR310_x_avg_P`, `TDR310_x_avg_EC`)*
- **Radiation Redundancy**: Redundant shortwave and longwave sensors must agree within acceptable margins. *(Applies to: `SW_rad_Avg` vs `R_SW_in_Avg` and `LW_rad_Avg` vs `R_LW_in_Avg`)*
- **NDVI Alignment**: The tilt angle offset of the NDVI sensor must remain within 5.0 degrees of horizontal. *(Applies to: `S2412_angle_offset`)*

## 8. Variable to QC Check Mapping Table

*Note: All numerical variables undergo **Statistical Anomalies** checks (Spikes, Jumps, Flatlines) unless explicitly excluded.* 

| Variable Name | Specific Physics & Hardware Checks Applied | Calculation / Formula |
| :--- | :--- | :--- |
| `time` | Continuity (Gaps) | \( \Delta t == 30\text{min} \) |
| `BattV` | Power Stability (Charging Check), Battery Trend | Flag if \( V < 11.5 \) when \( GHI > 200 \) |
| `AirTemp_C` | Sensible Heat Flux, Thermodynamic Consistency, Radiometer Body Temp Divergence | \( H = \frac{\rho c_p (T_s - T_a)}{r_a} \), Flag if \( \|T_{body} - T_a\| > 15^\circ\text{C} \) |
| `RH` | Thermodynamic Consistency (Dew Point) | \( T_{dp} = \frac{237.3 \cdot \alpha}{17.27 - \alpha} \), \( \alpha = \frac{17.27 T_a}{237.3 + T_a} + \ln(RH) \) |
| `DewPoint_C` | Thermodynamic Consistency (Dew Point) | Compared against theoretical \( T_{dp} \) |
| `TS100SS_Fan_RPM` | Fan Aspiration | Flag if \( \text{RPM} < 100 \) when \( SW_{in} > 500 \text{ W/m}^2 \) |
| `RainE_Standard_Int_1m` | Precipitation Consistency | Flag if \( \Delta P_{tot} > 0 \) and \( P_{int} \le 0 \) |
| `RainE_Standard_Int_1m_hr` | *None (Unchecked)* | N/A |
| `RainE_Standard_Precip_lr` | *None (Unchecked)* | N/A |
| `RainE_Standard_Precip_Tot` | Precipitation Consistency, Precipitation Mismatch (Soil) | Flag if \( \Delta \text{Storage} > 5\text{mm} \) and \( \sum P_{lagged} < 1\text{mm} \) |
| `PPFD_IN_Avg` | PAR Scaling | \( PAR = PPFD \times 0.219 \), check \( PAR/GHI \in [0.35, 0.55] \) |
| `albedo_Avg` | *Statistical Checks Only* | N/A |
| `R_SW_in_Avg` | Theoretical Maximums, Dynamic Bounds, Albedo Bounds, Fan Aspiration, PAR Scaling, Redundancy | Ineichen clear-sky max limits \( GHI_{clear} \), \( \alpha = \frac{SW_{out}}{SW_{in}} \) |
| `R_SW_out_Avg` | Nighttime Noise, Albedo Bounds | Flag if \( |SW_{out}| > 5 \) at night, \( \alpha = \frac{SW_{out}}{SW_{in}} \in [0.05, 0.95] \) |
| `R_LW_in_Avg` | Longwave Thermodynamics (Uncorrected check), Radiation Redundancy | Flag if \( < 50 \text{ W/m}^2 \) (thermopile not corrected for body temp) |
| `R_LW_out_Avg` | Longwave Thermodynamics (Stefan-Boltzmann constraint) | \( LW_{out} = \epsilon \sigma T_{targ}^4 \pm 20 \text{ W/m}^2 \) |
| `T_nr_Avg` | Radiometer Body Temperatures Divergence | Flag if \( |T_{nr} - T_a| > 15^\circ\text{C} \) |
| `G_PLATE_1_1_x` | Soil Heat Flux (Fourier's Law) | \( G \approx \lambda \frac{\Delta T}{\Delta z} \pm 50 \text{ W/m}^2 \) |
| `shfp_cal_fail_1_1_x` | Boolean Status Integrity | Flag if \( == 1 \) |
| `shfp_cal_sensitivity_1_1_x` | Static Calibration Change Tracker | Flag if \( \Delta cal > 1\times 10^{-3} \) |
| `TargetTemp_C_Avg`, `Max`, `Min` | Sensible Heat Flux (Avg), IR Temperature Integrity | \( H = \frac{\rho c_p (T_s - T_a)}{r_a} \), Flag if \( Min > Avg \) or \( Avg > Max \) |
| `BodyTemp_C_Avg`, `Max`, `Min` | Radiometer Body Temp Divergence (Avg), IR Temperature Integrity | Flag if \( |T_{body} - T_a| > 15^\circ\text{C} \) |
| `SW_rad_Avg` | Radiation Redundancy | Flag if \( |SW_{rad} - R\_SW_{in}| > 50 \text{ W/m}^2 \) |
| `LW_rad_Avg` | Radiation Redundancy | Flag if \( |LW_{rad} - R\_LW_{in}| > 50 \text{ W/m}^2 \) |
| `TEROS22_x_avg_MP` | Hydrological Constraints (Van Genuchten Curve) | \( \theta = \theta_r + \frac{\theta_s - \theta_r}{[1 + (\alpha \|h\|)^n]^m} \) |
| `TEROS22_x_avg_Temp` | Soil Temperature Redundancy | Flag if \( |T_{TEROS} - T_{TDR}| > 2.0^\circ\text{C} \) |
| `TDR310_x_avg_VWC` | Porosity Limits, Precipitation Mismatch | Flag if \( VWC > \theta_s \) |
| `TDR310_x_avg_T` | Soil Heat Flux (Fourier's Law gradient), Soil Temperature Redundancy | \( G \approx \lambda \frac{\Delta T}{\Delta z} \) |
| `TDR310_x_avg_P` | Soil Sensor Integrity (Permittivity bounds) | Flag if \( P \notin [1.0, 80.0] \) |
| `TDR310_x_avg_EC`, `PEC` | Soil Sensor Integrity (EC Spikes) | Flag if \( |EC_t - EC_{t-1}| > 50 \) |
| `S2412_angle_offset` | NDVI Alignment | Flag if \( |angle| > 5.0^\circ \) |
