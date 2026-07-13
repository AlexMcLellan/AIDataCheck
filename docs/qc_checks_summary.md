# Quality Control Checks Summary

This document outlines the physics-based quality control checks and their underlying mathematical formulas used to validate the sensor data in `qc_pipeline.py`.

## 1. Radiation Bounds (Clear-Sky Modeling)
Incoming shortwave radiation ($SW_{in}$) is validated against a theoretical maximum global horizontal irradiance (GHI). 

**Calculating Expected GHI:**
The theoretical `Expected_GHI` is computed using the **Ineichen and Perez (2002)** clear-sky model [1] via the `pvlib` library, which requires the site's latitude, longitude, altitude, and time to calculate the Solar Zenith Angle ($Z$) and astronomical air mass. 

\[ GHI_{clearsky} = DNI_{clearsky} \times \cos(Z) + DHI_{clearsky} \]

Where:
- $DNI$ = Direct Normal Irradiance (beam radiation)
- $DHI$ = Diffuse Horizontal Irradiance (scattered radiation)
- $Z$ = Solar Zenith Angle (degrees from vertical)

**Variables Checked:**
- `R_SW_in_Avg`, `R_SW_out_Avg` (validated against computed `Expected_GHI`)
- `PPFD_IN_Avg` (PAR). Validated against $45\%$ of `Expected_GHI` because the visible spectrum (PAR) accounts for approximately 45% of the full global solar spectrum under typical atmospheric conditions [2]. The value is first converted from $\mu mol / m^2 / s$ to $W/m^2$ (divide by ~2.1).

**1A. Absolute Clear-Sky Upper Bound**
\[ SW_{in} \leq GHI_{clearsky} \times (1 + \text{buffer}) \]

At night (when $GHI_{clearsky} = 0$), $SW_{in}$ is flagged if it exceeds noise levels ($> 5 \text{ W/m}^2$).

**1B. Dynamic Weather Bounds (Met Office API)**
Using the real-time `weather_code` from the Met Office, the pipeline applies contextual bounding constraints:
- **Sunny (Code 1)**: Applies a **Lower Bound** to detect fouled, dirty, or shaded sensors.
  \[ SW_{in} > 0.70 \times GHI_{clearsky} \]
- **Overcast (Code 8)**: Applies a tighter **Upper Bound** to detect erroneously high readings on a cloudy day.
  \[ SW_{in} < 0.40 \times GHI_{clearsky} \]

## 2. Longwave & Stefan-Boltzmann Check
Outgoing longwave radiation ($LW_{out}$) is cross-checked against the surface temperature ($T_{surface}$) using the Stefan-Boltzmann law. A significant deviation indicates a fouled sensor or an uncorrected pyrgeometer body temperature.

**Variables Checked:**
- `R_LW_out_Avg` (vs `TargetTemp_C_Avg`)
- `R_LW_in_Avg` (corrected using `T_nr_Avg` if body temp missing)

\[ LW_{out} = \epsilon \sigma T_{surface}^4 \]

Where:
- $\epsilon$ = Emissivity (assumed $\approx 0.95$ for typical vegetated/soil surfaces, as per Arya, 2001 [7])
- $\sigma$ = $5.670374 \times 10^{-8} \text{ W m}^{-2} \text{ K}^{-4}$ (Stefan-Boltzmann constant, CODATA recommended value [3])
- $T_{surface}$ = Surface temperature in Kelvin

## 3. Sensible Heat Flux
The aerodynamic Sensible Heat Flux ($H$) is estimated to ensure energy balance closures aren't wildly violating thermodynamics. It uses the temperature gradient between the surface ($T_{surface}$) and the air ($T_{air}$), scaled by the aerodynamic resistance of the surface layer [8].

**Variables Checked:**
- Estimated from `TargetTemp_C_Avg` and `AirTemp_C`

\[ H = \frac{\rho c_p (T_s - T_a)}{r_a} \]

Where:
- $\rho$ = Air density (adjusted for altitude)
- $c_p$ = Specific heat capacity of air ($1004 \text{ J/(kg K)}$)
- $r_a$ = Aerodynamic resistance ($s/m$)

The aerodynamic resistance ($r_a$) is calculated dynamically from the measured wind speed ($u$) using the standard logarithmic wind profile (assuming neutral atmospheric stability) [2, 8]:

\[ r_a = \frac{\ln(z_m / z_{0m}) \ln(z_m / z_{0h})}{k^2 \cdot u} \]

Where:
- $z_m = 3.0 \text{ m}$ (anemometer measurement height)
- $z_{0m} \approx 0.03 \text{ m}$ (momentum roughness length for short vegetation)
- $z_{0h} \approx 0.1 z_{0m}$ (heat roughness length)
- $k = 0.4$ (von Kármán constant)
- $u$ = `Windspeed` or `WS` from the datalogger

*(Note: If wind speed data is completely missing from the datalogger output, the pipeline falls back to a static approximation of $r_a = 50 \text{ s/m}$).* 

## 4. Soil Heat Flux (Fourier's Law)
The measured soil heat flux plates ($G_{measured}$) are cross-validated against the theoretical gradient calculated using Fourier's Law of Heat Conduction [8] between two soil temperature sensors at different depths ($dz = z_2 - z_1$).

\[ G_{theory} = -\lambda_{soil} \frac{dT}{dz} \]

Where the thermal conductivity $\lambda_{soil}$ is calculated dynamically using the **Johansen (1975)** model [4], incorporating the real-time Volumetric Water Content ($\theta$):

\[ \lambda_{soil} = (\lambda_{sat} - \lambda_{dry}) K_e + \lambda_{dry} \]

With:
- $K_e = \log_{10}\left(\frac{\theta}{\theta_s}\right) + 1.0$ (Kersten number for saturation)
- $\lambda_{sat}$ derived from the geometric mean of water and quartz conductivities.

## 5. Soil Heat Capacity
The volumetric heat capacity of the soil ($C_{soil}$) is dynamically modelled as a volume-weighted average of its constituents (dry soil matrix and water), following the classic de Vries (1963) mixing model [9]. Extreme spikes in temperature are flagged if the thermal mass of the wet soil makes such rapid heating physically impossible.

\[ C_{soil} = C_{dry} + (\theta \times C_{water}) \]

## 6. Soil Moisture Retention (van Genuchten)
The matric potential ($h$, measured in kPa by TEROS 22) is validated against the volumetric water content ($\theta$, measured by TDR310) using the **van Genuchten (1980)** soil water retention curve [5]:

**Variables Checked:**
- `TEROS22_X_avg_MP` cross-validated against `TDR310_X_avg_VWC` (for depths $X = 1 \text{ to } 6$)

\[ \theta(h) = \theta_r + \frac{\theta_s - \theta_r}{\left[1 + (\alpha |h|)^n\right]^{1 - 1/n}} \]

The parameters ($\theta_r, \theta_s, \alpha, n$) are derived from the specific USDA soil texture class at that depth (Carsel and Parrish, 1988) [6].

## 7. Precipitation Infiltration Time-Lag
Spikes in deep soil moisture are flagged if they occur immediately following a rain event without sufficient physical time to percolate. The expected time lag ($\Delta t_{lag}$) is calculated using the depth ($z$) and the saturated hydraulic conductivity ($K_{sat}$) of the soil layer, based on basic Darcian flow principles in porous media [10]:

**Variables Checked:**
- `RainE_Standard_Int_1m` compared against delayed spikes in `TDR310_X_avg_VWC` (for depths $X = 1 \text{ to } 6$)

\[ \Delta t_{lag} \approx \frac{z}{K_{sat}} \]

If $\theta$ jumps significantly before $t_{rain} + \Delta t_{lag}$, the reading is flagged as anomalous (e.g. preferential flow down the sensor cable).

---

## 8. Universal Statistical Anomaly Detection
Applied dynamically to **all continuous variables** (74 columns), identifying localized deviations from expected behaviors using a rolling window approach.

### A. Z-Score Spike Detection
Detects single-point spikes that significantly exceed the local standard deviation.
\[ Z_i = \frac{|x_i - \mu_{window}|}{\sigma_{window}} \]
- Flagged if $Z_i > 5.0$

### B. Step-Change (Jump) Detection
Detects physically impossible instantaneous changes between consecutive readings.
\[ \Delta x = |x_i - x_{i-1}| \]
- Flagged if $\Delta x > 5.0 \times \sigma_{window}$

### C. Flatline (Dead Sensor) Detection
Flags variables where the signal remains completely frozen for an extended period, indicating a frozen/dead sensor.
- Flagged if $\max(x_{window}) - \min(x_{window}) == 0$

## 9. Hardware & System Integrity Checks

### A. Battery Load Voltage
The battery voltage ($V_{batt}$) is checked under specific loads. A warning is raised if it drops below the critical minimum threshold for the configured chemistry (e.g., $V_{min} = 12.8V$ for LiFePO4).
Additionally, long-term trends check if the battery is actively draining on days with high expected Solar GHI (indicating solar panel failure).

### B. Fan Speed vs Solar Radiation
Aspiration fan speeds on the air temperature shield (e.g., TS100SS) must be active during the day to prevent radiational heating of the thermometer.
- Flagged if $SW_{in} > 500 \text{ W/m}^2$ AND $RPM_{fan} < 1000$

### C. Time Continuity
The time index ($t$) of the datalogger is checked for missing rows against the expected sampling frequency ($dt = 1 \text{ min}$ or $15 \text{ min}$).
\[ \Delta t = t_i - t_{i-1} \]
- Flagged if $\Delta t \neq \text{expected\_freq}$

---

## References
1. Ineichen, P., & Perez, R. (2002). A new airmass independent formulation for the Linke turbidity coefficient. *Solar Energy*, 73(3), 151-157.
2. Monteith, J. L., & Unsworth, M. H. (2013). *Principles of Environmental Physics* (4th ed.). Academic Press.
3. Tiesinga, E., Mohr, P. J., Newell, D. B., & Taylor, B. N. (2021). CODATA recommended values of the fundamental physical constants: 2018. *Reviews of Modern Physics*, 93(2), 025010.
4. Johansen, O. (1975). *Thermal conductivity of soils* (Ph.D. thesis). Norwegian University of Science and Technology, Trondheim.
5. van Genuchten, M. T. (1980). A closed-form equation for predicting the hydraulic conductivity of unsaturated soils. *Soil Science Society of America Journal*, 44(5), 892-898.
6. Carsel, R. F., & Parrish, R. S. (1988). Developing joint probability distributions of soil water retention characteristics. *Water Resources Research*, 24(5), 755-769.
7. Arya, S. P. (2001). *Introduction to Micrometeorology* (2nd ed.). Academic Press.
8. Campbell, G. S., & Norman, J. M. (1998). *An Introduction to Environmental Biophysics* (2nd ed.). Springer.
9. de Vries, D. A. (1963). Thermal properties of soils. In *Physics of plant environment* (pp. 210-235). North-Holland.
10. Hillel, D. (1998). *Environmental Soil Physics*. Academic Press.
