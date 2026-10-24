# Contract: Scenario File, Boiler House Sections

**Covers**: FR-002, FR-003, FR-005 – FR-012, FR-015 | **Extends**: [001 scenario-file](../../001-boiler-dryer-interface/contracts/scenario-file.md)

All rules of the feature-001 scenario file apply: every physical value is written as
`"<number> <unit>"`, time series are given as `{ file = ..., column = ... }`, unknown keys are
errors, all issues are reported together with file and line, and fields have physical and
validated ranges.

## Selecting the run type

```toml
[flue_gas]
source = "boiler_house"    # the dryer is fed by the [boiler_house] section (coupled run)
```

- `source = "boiler_house"` with `[dryer.*]` sections: coupled run.
- `[boiler_house]` without `[dryer.*]` and without `[flue_gas]`: boiler-house-only run.
- `[boiler_house]` together with `source = "constant"` or `"timeseries"`: rejected as
  ambiguous.

## Sections

```toml
[boiler_house.fuel]
kind = "wood_chips"                 # "wood_chips" | "bark" | "custom"
# C = "51.3 %"  H = "6.1 %"  N = "0.4 %"  S = "0.02 %"  ash = "1.3 %"   (custom; O by difference)
moisture_wet_basis = "45 %"         # or { file = ..., column = ... }
temperature = "10 degC"
# hhv_dry = "20.8 MJ/kg"

[boiler_house.combustion_air]
temperature = "20 degC"
relative_humidity = "60 %"

[boiler_house.furnace]
rated_fuel_power = "15 MW"
min_load_fraction = "30 %"
bed_time_constant = "15 min"
water_time_constant = "10 min"
feed_dead_time = "2 min"
refractory_mass_hot_face = "20 t"
refractory_mass_bulk = "60 t"
# ... remaining fields: data-model.md §2, with defaults

[[boiler_house.heaters]]            # heater 1: radiant
type = "radiant"
tube_area = "300 m^2"
cold_plane_area = "150 m^2"
flame_emissivity = 0.5
tube_mass = "25 t"
oil_volume = "6 m^3"
tube_inner_diameter = "100 mm"
n_parallel_passes = 4

[[boiler_house.heaters]]            # heater 2: convective
type = "convective"
n_cells = 5
tube_outer_diameter = "60.3 mm"
tube_inner_diameter = "50 mm"
transverse_pitch = "120 mm"
longitudinal_pitch = "100 mm"
n_rows = 16
tubes_per_row = 20
tube_length = "4 m"
fouling_resistance = "0.008 m^2*K/W"
tube_mass = "15 t"
oil_volume = "3 m^3"
n_parallel_passes = 4

[[boiler_house.heaters]]            # heater 3: convective
type = "convective"
# ... as heater 2

[boiler_house.bypass]
starts_after_heater = 1             # bypasses heaters 2 and 3

[boiler_house.thermal_oil]
oil = "shell_s2"
mass_flow = "60 kg/s"               # or a time series (manufacturing demand)
return_temperature = "240 degC"     # or a time series

[boiler_house.controllers.oil_temperature]
mode = "automatic"
setpoint = "282 degC"
gain = "0.02 kg/(s*K)"              # SIMC defaults from scripts/tune_controllers.py
integral_time = "15 min"
output_min = "0.4 kg/s"
output_max = "2.2 kg/s"

[boiler_house.controllers.oxygen]
mode = "automatic"
setpoint = "7 %"                    # dry
gain = 5.0                          # λ per mol/mol
integral_time = "2 min"
output_min = 1.1
output_max = 2.5

[boiler_house.controllers.drum_inlet_temperature]
mode = "automatic"
setpoint = "540 degC"
gain = "0.004 1/K"
integral_time = "5 min"
split_value = 0.5
max_dilution_air = "6 kg/s"

[boiler_house.initial_state]
kind = "steady_state"               # "cold" | "steady_state" | "explicit"
```

The example values are illustrative: a 15 MW reference plant, not measured data.

## Time series

All signals that accept time series use the feature-001 CSV format: oil flow, oil return
temperature, fuel moisture and temperature, air temperature and humidity, set points and
manual outputs.

## Validation

In addition to the feature-001 rules:
- the composition sum is 1 ± 0.005 (when O is given);
- `heaters[0].type` is `radiant`, and the others are `convective`;
- `starts_after_heater` is less than the number of heaters;
- controller `output_min` < `output_max`, and the manual output lies within the limits;
- in a coupled run, a drum inlet set point is required when that loop is automatic;
- a fixed combustion air amount is rejected while the O₂ loop is automatic.
