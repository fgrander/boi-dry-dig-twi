# Contract: Scenario File and Time Series Input

**Covers**: FR-003, FR-006, FR-007, FR-009, FR-014, SC-001 | **Entities**: [data-model.md §2](../data-model.md)

A scenario is a **TOML** file. Every physical value is a string `"<number> <unit>"` parsed by
pint (e.g. `"450 degC"`, `"12.5 t/h"`, `"-2 mbar"` for gauge with `pressure_reference`), or
refers to a time series column. Values without a unit are rejected. Dimensionless values
(fractions, counts) accept plain numbers or `"%"`.

## Structure

```toml
schema_version = 1
name = "Reference case: 10 t/h wet chips, 50 % → 15 %"

[time]
start = "2026-01-01T00:00:00Z"
end = "2026-01-02T00:00:00Z"
output_interval = "1 min"

[flue_gas]                      # FlueGasSupply
source = "constant"             # "constant" | "timeseries"
mass_flow = "8.0 kg/s"
temperature = "650 degC"
pressure = "101.0 kPa"          # absolute
composition_basis = "wet"
x_N2 = "70.5 %"
x_O2 = "6.0 %"
x_CO2 = "10.5 %"
x_H2O = "12.0 %"
x_other = "1.0 %"
# for source = "timeseries":
# file = "data/flue_gas.csv"
# max_gap = "5 min"
# allow_gaps = false

[dilution_air]
mass_flow = "2.0 kg/s"          # or file/column reference

[product_feed]
mass_flow_wet = "10 t/h"
moisture_wet_basis = "50 %"
temperature = "10 degC"

[ambient]
temperature = "10 degC"
relative_humidity = "70 %"
pressure = "101.3 kPa"

[dryer.geometry]
length = "20 m"
diameter = "4 m"
slope = "2 deg"
n_flights = 24
flight_lip_length = "0.3 m"
shell_thickness = "16 mm"
shell_mass = "60 t"
insulation_thickness = "0 mm"

[dryer.operation]
rotation_speed = "4 rpm"
gas_flow_direction = "co-current"

[dryer.discretisation]
n_cells = 20

[dryer.product]
chip_equivalent_diameter = "15 mm"
particle_density = "450 kg/m^3"
bulk_density = "160 kg/m^3"
critical_moisture = "0.8"       # dry basis kg/kg
falling_rate_exponent = 1.0

[dryer.calibration]             # defaults documented; changed by calibration only
drag_coefficient = 1.0
kilning_coefficient = 1.0
flight_capacity_factor = 1.0
heat_transfer_multiplier = 1.0
shell_contact_htc = "100 W/(m^2*K)"

[initial_state]
kind = "cold_empty"             # "cold_empty" | "steady_state" | "explicit"
# file = "runs/<run_id>/final_state.json"   # for "explicit"

[balance_tolerances]
mass = "0.1 %"
energy = "1 %"
```

The example values are illustrative, not plant data.

## Time series CSV

Used for `source = "timeseries"` and for any input given as a time series.

```text
time,mass_flow,temperature,pressure,x_N2,x_O2,x_CO2,x_H2O,x_other,quality
unit,kg/s,degC,kPa,%,%,%,%,%,
2026-01-01T00:00:00Z,8.0,650,101.0,70.5,6.0,10.5,12.0,1.0,good
2026-01-01T00:01:00Z,8.1,648,101.0,70.4,6.1,10.5,12.0,1.0,good
```

Rules:
- the **second row holds the units**; every column except `time` and `quality` needs one;
- `time` is ISO 8601 with a timezone (`Z` or offset); converted to UTC;
- timestamps are strictly increasing;
- `quality` is optional (`good` | `missing` | `bad`), default `good`; empty cells are
  `missing`;
- column names map to the fields of the section that references the file.

## Validation

The whole scenario is validated before any simulation. All issues are collected and reported
together in the format of [flue-gas-interface.md](flue-gas-interface.md#validation-errors-boundary),
with file and line/row. Unknown keys are errors (catches typos). Parameters outside their
documented valid range are errors for physical impossibilities, and range warnings for
values outside the model's validated range.
