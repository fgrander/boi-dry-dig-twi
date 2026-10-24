# Contract: Results with a Recirculation

**Covers**: FR-004, FR-006, FR-008, FR-011, FR-012 | **Extends**: DryerResults (feature 001
data-model §4), run record (feature 001/002)

## Rule

Columns below are written **only** when the scenario has `[recirculation]`. A run without it
has exactly the columns and values it had before this feature (SC-001).

## Changed meaning (with a recirculation)

| Column | Meaning |
|---|---|
| `exhaust_mass_flow` | stack exhaust = drum outlet gas minus the returned gas |
| `exhaust_temperature`, `exhaust_humidity`, `exhaust_x_*`, `exhaust_dew_point` | stack exhaust; equal to the drum outlet gas (adiabatic cyclone and fan) |
| `drum_inlet_gas_temperature` | after mixing in the returned gas |
| `heat_supplied`, `specific_energy` | heat of flue gas plus dilution air only (unchanged definition) |

## New columns

| Column | Unit (`RESULT_UNITS`) | Meaning |
|---|---|---|
| `drum_outlet_mass_flow` | kg/s | wet gas leaving the drum |
| `recirculation_damper_position` | – | applied damper position 0–1 |
| `recirculation_share` | – | returned / drum outlet gas (dry basis) |
| `recirculation_mass_flow` | kg/s | returned wet gas |
| `recirculation_temperature` | K | returned gas entering the mixing chamber (after duct loss) |
| `mixing_chamber_pressure` | Pa | relative to ambient |
| `mixing_chamber_pressure_setpoint` | Pa | controller set point |
| `mixing_chamber_pressure_measured` | Pa | transmitter (lagged) |
| `exhaust_fan_speed` | 1/s | |
| `exhaust_fan_volume_flow` | m³/s | at fan inlet |
| `exhaust_fan_pressure_rise` | Pa | |
| `drum_inlet_humidity` | kg/kg dry gas | after mixing |
| `drum_inlet_x_O2` | mol/mol | wet, after mixing |
| `drum_inlet_dew_point` | K | after mixing |
| `duct_heat_loss` | W | |

Profiles (`profiles.csv`) are unchanged.

## Run record

- `controllers` gains `mixing_chamber_pressure` with its settings (as the feature-002 loops),
  and its `setpoint_not_reached` periods appear in the flags like those of the other loops.
- `balances` gains `recirculation_loop` (mass, energy; in, out, relative error, passed).
- `warnings` may contain `mixing_chamber_overpressure`, `recirculation_backflow`,
  `drum_inlet_condensation_risk` (periods), and range warnings for `exhaust_fan_curve`,
  `exhaust_fan.speed` and `recirculation_share`.

## Comparison with measured data

`validation/compare.py` accepts the new columns (`mixing_chamber_pressure`: pressure,
`recirculation_damper_position`: fraction, `recirculation_mass_flow`: mass flow) like the
existing ones.
