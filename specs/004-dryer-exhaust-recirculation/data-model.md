# Data Model: Dryer Exhaust Gas Recirculation

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md)

All values in SI internally (pressures in Pa relative to ambient, flows in kg/s, temperatures
in K, positions as fractions 0–1). The scenario file uses `"<number> <unit>"` as everywhere
else ([contracts/scenario-file-recirculation.md](contracts/scenario-file-recirculation.md)).

## 1. RecirculationSpec (scenario, normalised; `scenario/schema.py`)

Optional field `ScenarioSpec.recirculation: RecirculationSpec | None = None`. `None` means no
recirculation and no pressure model (FR-005, FR-018).

| Field | Type | Default | Physical range | Validated range | Notes |
|---|---|---|---|---|---|
| `damper` | DamperSpec | – | – | – | required |
| `exhaust_fan` | ExhaustFanSpec | – | – | – | required |
| `resistances` | ResistancesSpec | – | – | – | required |
| `controller` | ControllerSpec (feature 002) | – | – | – | set point = mixing chamber pressure, output = damper position |
| `pressure_sensor_time_constant` | float s | 2.0 | (0, 600] | [0.5, 30] | transmitter lag (R5) |
| `duct_heat_loss` | float W/K | 0.0 | [0, 1e6] | [0, 1e4] | UA of the return duct (FR-003); loss q = C (T_out − T_a)(1 − e^(−UA/C)), C = heat capacity flow of the returned gas |
| `max_share` | float – | 0.70 | (0, 1) | – | range warning above this share (FR-010, FR-011); ≥ 1 rejected |
| `dew_point_margin` | float K | 10.0 | [0, 100] | – | warning margin for the mixed drum inlet (FR-011) |

Controller rules (on top of feature-002 `ControllerSpec`): `output_min ≥ 0`, `output_max ≤ 1`;
`action` defaults to `"reverse"` (pressure below set point → open); `split_value` and
`max_dilution_air` are not allowed (rejected); set point within [−2000, 0] Pa physical,
[−1000, −20] Pa validated; `not_reached_band` default 50 Pa, `not_reached_hold` default 10 min.

### DamperSpec

| Field | Type | Default | Rules |
|---|---|---|---|
| `open_mass_flow` | float kg/s | – | > 0; flow when fully open at `design_pressure_drop` |
| `design_pressure_drop` | float Pa | – | > 0 |
| `design_temperature` | float K | – | (250, 900) |
| `characteristic` | tuple of (position, relative flow) | opposed-blade default (R3) | positions strictly increasing from 0 to 1, flows non-decreasing, last flow = 1, first ≥ 0 |
| `leakage` | float – | 0.01 | [0, 0.2]; relative flow at position 0 (replaces the first table value if the table is not given) |

### ExhaustFanSpec

| Field | Type | Default | Rules |
|---|---|---|---|
| `curve` | 3 × (volume flow m³/s, pressure rise Pa) | – | volume flows strictly increasing; pressure rise strictly falling; fitted quadratic must have a₂ < 0 |
| `nominal_speed` | float 1/s | – | > 0 (scenario may give rpm) |
| `curve_temperature` | float K | 293.15 | density reference of the curve |
| `speed` | SignalSpec (1/s) | = nominal | constant, series or steps; physical [0, 2·nominal], validated [0.3, 1.1]·nominal |

### ResistancesSpec

| Field | Type | Rules |
|---|---|---|
| `drum_path` | ResistancePoint | drum + cyclone + ducts between mixing chamber and fan inlet |
| `stack` | ResistancePoint | fan outlet to stack exit (ambient) |

ResistancePoint: `mass_flow` (kg/s, > 0), `pressure_drop` (Pa, > 0), `temperature` (K,
(250, 900)).

## 2. GasPath (model; `dryer/gas_path.py`)

Built from `RecirculationSpec`; pure functions, no state.

| Method | Returns |
|---|---|
| `fan_pressure_rise(V̇, n, ρ)` | Pa, fan laws on the fitted quadratic |
| `resistance(point, ṁ, ρ)` | Pa |
| `damper_flow(s, Δp, ρ)` | kg/s wet; 0 for Δp ≤ 0 |
| `solve(G_in, Y_out, T_out, s, n, p_ambient)` | `GasPathState` (R2) |

### GasPathState (one evaluation)

| Field | Unit | Meaning |
|---|---|---|
| `recirculated_dry_gas` | kg/s | G_rec |
| `drum_dry_gas` | kg/s | G_in + G_rec |
| `mixing_chamber_pressure` | Pa | p_mc, relative to ambient |
| `fan_outlet_pressure` | Pa | p_fan_out |
| `fan_volume_flow` | m³/s | at fan inlet conditions |
| `fan_pressure_rise` | Pa | |
| `backflow` | bool | F(0) ≤ 0: no driving pressure difference across the damper |
| `fan_out_of_curve` | bool | fan volume flow outside the curve's points |

## 3. Dryer state vector (`dryer/model.py`)

Without a recirculation: unchanged, `n_cells × 8`. With a recirculation two extra states are
appended after the cells:

| Index | State | Unit | Equation |
|---|---|---|---|
| `8 n` | measured mixing chamber pressure p_m | Pa | dp_m/dt = (p_mc − p_m) / τ_p |
| `8 n + 1` | pressure controller integral I | – | `PIController.integral_rate` |

`DrumDryerModel` gains `size` (= 8 n or 8 n + 2), and all code that uses `n * 8` or
`reshape(n, 8)` on the whole vector uses `size` and the cell slice instead (plant slice,
`_physical`, dryer steady state). `inlet(t)` becomes `inlet(t, y)`; with no recirculation `y`
is ignored. `Inlet` gains the fresh-gas fields and `GasPathState`.

### Inlet (extended)

| New field | Unit | Meaning |
|---|---|---|
| `fresh_dry_gas_flow` | kg/s | G_in (flue gas + dilution air, dry) |
| `fresh_humidity`, `fresh_enthalpy` | kg/kg, J/kg | before the return |
| `gas_path` | GasPathState \| None | None without recirculation |
| `damper_position` | – | applied s |
| `duct_heat_loss` | W | Q_duct |

`dry_gas_flow`, `humidity`, `enthalpy`, `temperature` are the **drum inlet** after mixing (as
their names say today). `heat_supplied` stays flue + dilution heat.

## 4. Results (DryerResults columns)

Unchanged columns keep their names; with a recirculation `exhaust_mass_flow` is the stack flow.
New columns only with a recirculation, see
[contracts/results-recirculation.md](contracts/results-recirculation.md).

## 5. Balances

| Check | Boundary | In | Out |
|---|---|---|---|
| dryer (existing, extended) | drum + mixing chamber + return duct + fan | feed, flue gas, dilution air | product, stack exhaust, shell loss, duct loss |
| recirculation loop (new) | return duct | last cell gas × share | gas entering the mixing chamber + duct loss |
| interface, plant | unchanged | | |

Tolerances: `balance_tolerances` of the scenario (0.1 % mass, 1 % energy).

## 6. Flags and warnings

| Name | Kind | Condition |
|---|---|---|
| `setpoint_not_reached` for `mixing_chamber_pressure` | controller flag (existing mechanism) | `not_reached_mask` on p_mc − set point |
| `mixing_chamber_overpressure` | warning, per period | p_mc > 0 Pa |
| `recirculation_backflow` | warning | GasPathState.backflow |
| `exhaust_fan_curve` | range warning | fan volume flow outside the curve's points, or speed outside its validated range |
| `recirculation_share` | range warning | share > `max_share` |
| `drum_inlet_condensation_risk` | warning | T_drum_in − dew point(Y_drum) < `dew_point_margin` |

## 7. Web app view state (`webapp/process_state.py`)

`ProcessState` gains an optional `recirculation` block next to `dryer` (None when the run has
no recirculation columns): damper position (%), share (%), recirculated flow (kg/s), temperature (°C), mixing
chamber pressure and set point (Pa), fan speed (%), fan volume flow (m³/s), stack flow (kg/s),
drum inlet humidity (g/kg) and O₂ (%).
