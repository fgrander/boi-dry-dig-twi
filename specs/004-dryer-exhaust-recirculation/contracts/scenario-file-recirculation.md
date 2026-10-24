# Contract: Scenario File, `[recirculation]` Section

**Covers**: FR-001, FR-003, FR-007 – FR-011, FR-016 – FR-018 | **Extends**:
[001 scenario-file](../../001-boiler-dryer-interface/contracts/scenario-file.md),
[002 boiler sections](../../002-boiler-house-model/contracts/scenario-file-boiler.md)

All rules of the earlier scenario files apply: `"<number> <unit>"` values, time series as
`{ file = ..., column = ... }`, unknown keys are errors, all issues are reported together with
file and line, physical ranges reject and validated ranges warn.

## Presence

- No `[recirculation]`: no recirculation, no pressure model; results identical to before.
- `[recirculation]` needs `[dryer.*]` sections (dryer-only or coupled run). With a
  boiler-house-only scenario it is rejected: `recirculation: needs a dryer`.
- All four sub-tables are required when `[recirculation]` is present.

## Sections (example values, not plant data)

```toml
[recirculation]
pressure_sensor_time_constant = "2 s"   # optional
duct_heat_loss = "0 W/K"                # optional, return duct UA
max_share = "70 %"                      # optional, range warning above
dew_point_margin = "10 K"               # optional

[recirculation.damper]
open_mass_flow = "12 kg/s"              # fully open, at the design pressure drop
design_pressure_drop = "400 Pa"
design_temperature = "120 degC"
# characteristic = [[0, 0.01], [0.2, 0.05], [0.4, 0.15], [0.6, 0.35], [0.8, 0.65], [1, 1]]
# leakage = "1 %"

[recirculation.exhaust_fan]
nominal_speed = "990 rpm"
speed = "990 rpm"                       # or a series / steps
curve_temperature = "20 degC"
curve = [["20 m^3/s", "3600 Pa"], ["35 m^3/s", "3200 Pa"], ["50 m^3/s", "2400 Pa"]]

[recirculation.resistances.drum_path]   # mixing chamber -> fan inlet (drum, cyclone, ducts)
mass_flow = "20 kg/s"
pressure_drop = "1500 Pa"
temperature = "120 degC"

[recirculation.resistances.stack]       # fan outlet -> stack exit
mass_flow = "12 kg/s"
pressure_drop = "300 Pa"
temperature = "120 degC"

[recirculation.controller]              # mixing chamber pressure -> damper position
mode = "automatic"                      # or "manual" with manual_output / manual_signal
setpoint = "-200 Pa"                    # or a series / steps
gain = "0.002 1/Pa"
integral_time = "10 s"
output_min = "0 %"
output_max = "100 %"
not_reached_band = "50 Pa"
not_reached_hold = "10 min"
```

The tuned values in `examples/plant_recirculation.toml` replace the example gains (research R5).

## Validation rules (FR-010)

| Field | Rejected (physical) | Warned (validated) |
|---|---|---|
| `max_share` | ≤ 0 or ≥ 100 % | – |
| `controller.output_min/max` | outside 0–100 % or min ≥ max | – |
| `controller.setpoint` | outside [−2000, 0] Pa | outside [−1000, −20] Pa |
| `controller.split_value`, `max_dilution_air` | present | – |
| `exhaust_fan.curve` | not 3 points, flows not increasing, pressure not falling | – |
| `exhaust_fan.speed` | < 0 or > 2 × nominal | outside 30–110 % of nominal |
| `damper.characteristic` | positions not 0 … 1 increasing, flows decreasing, last ≠ 1 | – |
| resistance points, damper design | ≤ 0 flow or pressure drop; temperature outside (−23, 627) °C | – |
| `duct_heat_loss` | < 0 | > 10 kW/K |
| `pressure_sensor_time_constant` | ≤ 0 or > 600 s | outside 0.5–30 s |

Manual mode: `controller.manual_output` (constant position) or `controller.manual_signal`
(series or steps), as for the feature-002 loops.

## Signals added to `LoadedScenario.signals`

| Name | Unit |
|---|---|
| `recirculation.exhaust_fan.speed` | 1/s |
| `recirculation.controller.setpoint` | Pa |
| `recirculation.controller.manual_output` | – (only in manual mode with a signal) |

Their breakpoints join the solver restarts like every other signal.

## Web app

- Every field above is an ordinary form field (quantity, steps or series) on the scenario page.
- `POST /api/scenarios/{name}/recirculation` (engineer): appends the default block above to a
  scenario that has a dryer and no `[recirculation]`; 409 if it has one, 422 without a dryer.
  The page shows it as the button "Add recirculation" / "Rückführung hinzufügen".
- Releasable for operator what-if cases like any field, typically
  `recirculation.controller.setpoint` and `recirculation.exhaust_fan.speed`.
