# Data Model: Flue Gas Interface and Dynamic Rotary Drum Dryer Model

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md) | **Date**: 2026-10-24

All quantities are SI internally (K, Pa, kg, s, J, W, m). Units given below are the internal
unit; users may supply any compatible unit at the boundary (see
[contracts/scenario-file.md](contracts/scenario-file.md)). All entities are immutable once
validated. Timestamps are timezone-aware UTC.

## 1. Interface entities

### GasComposition

Mole fractions of the flue gas components.

| Field | Type | Unit | Rule |
|---|---|---|---|
| `x_N2`, `x_O2`, `x_CO2`, `x_H2O`, `x_other` | float | mol/mol | each 0 ≤ x ≤ 1 |
| `basis` | `"wet"` \| `"dry"` | — | boundary only; converted to wet basis on validation |
| `fraction_type` | `"mole"` \| `"mass"` | — | boundary only, default `"mole"`; converted to mole fractions on validation |

Validation:
- the fractions sum to 1 within ±0.005 (reported as an error beyond that) and are then
  normalised to exactly 1;
- dry-basis input needs a separately given `x_H2O` (wet) or humidity, otherwise rejected;
- `fraction_type = "mass"` values are converted to mole fractions.
- `x_other` is treated as Ar for property calculations (research R6).

### FlueGasState

The state of the flue gas crossing the interface at one point in time (FR-001).

| Field | Type | Unit | Rule |
|---|---|---|---|
| `time` | datetime (UTC) | — | timezone-aware |
| `mass_flow` | float | kg/s | ≥ 0 |
| `temperature` | float | K | 273.15 ≤ T ≤ 1473.15 (0–1200 °C); dryer range checks are separate |
| `pressure` | float | Pa (absolute) | 50 000 < p < 200 000 |
| `composition` | GasComposition | — | see above |
| `quality` | `"good"` \| `"interpolated"` \| `"missing"` \| `"stale"` \| `"bad"` | — | default `"good"`; `"stale"` set by the time series reader per FR-015 |

Derived (not stored, computed on demand):
- `heat_content_flow` (W): ṁ · [h(T) − h(T_ref)], T_ref = 298.15 K by default (FR-002);
- `humidity` (kg H₂O / kg dry gas) and `dew_point` (K), using the actual dry-gas molar mass.

### FlueGasSupply (interface)

The only way a dryer obtains its flue gas (FR-005, constitution principle III).

| Member | Meaning |
|---|---|
| `state_at(t) → FlueGasState` | gas state at simulation time t |
| `covers(t_start, t_end) → bool` | whether the source has data for the whole period |
| `source_id: str` | identifier recorded in the run record |

Implementations in this feature:
- **ConstantFlueGasSupply**: one `FlueGasState` for all times.
- **TimeSeriesFlueGasSupply**: ordered, unique samples; piecewise-linear interpolation;
  a gap longer than `max_gap` (default 300 s) is an error unless `allow_gaps = true`, in which
  case the gap period is returned with `quality = "missing"` and the run is flagged (FR-015).
- Later feature: **BoilerHouseModel** implements the same interface.

## 2. Dryer input entities

### DilutionAir

Optional ambient air mixed into the flue gas before the drum.

| Field | Type | Unit | Rule |
|---|---|---|---|
| `mass_flow` | float or time series | kg/s | ≥ 0; default 0 |

Its temperature, humidity and pressure come from **AmbientConditions**.

### ProductFeed

| Field | Type | Unit | Rule |
|---|---|---|---|
| `mass_flow_wet` | float or time series | kg/s | ≥ 0 |
| `moisture_wet_basis` | float or time series | kg/kg (w) | 0 ≤ w < 0.75 |
| `temperature` | float or time series | K | 253.15–333.15 (−20 to 60 °C) |

Internally converted to dry solids flow and dry-basis moisture X = w / (1 − w).

### AmbientConditions

| Field | Type | Unit | Rule |
|---|---|---|---|
| `temperature` | float or time series | K | 233.15–323.15 |
| `relative_humidity` | float or time series | 1 | 0–1 |
| `pressure` | float or time series | Pa | 80 000–110 000 |

### DryerConfiguration

Design, operating and material parameters. Every parameter has two documented ranges
(FR-012):

- `physical_range`: values outside are physically impossible → validation **error**;
- `validated_range`: the range the model is validated for → values outside give a
  **RangeWarning**, and the run proceeds.

Defaults are listed in the scenario-file contract.

| Group | Fields (unit) |
|---|---|
| Geometry | `length` (m), `diameter` (m), `slope` (rad), `n_flights`, `flight_lip_length` (m), `shell_thickness` (m), `shell_mass` (kg, incl. flights), `insulation_thickness` (m), `insulation_conductivity` (W/m·K) |
| Operation | `rotation_speed` (rad/s), `gas_flow_direction` = `"co-current"` (only value in this feature) |
| Discretisation | `n_cells` (10–40, default 20) |
| Product | `chip_equivalent_diameter` (m), `particle_density` (kg/m³), `bulk_density` (kg/m³), `fibre_saturation_moisture` (kg/kg dry, default 0.30), `critical_moisture_dry_basis` (kg/kg dry), `falling_rate_exponent` (–) |
| Shell | `shell_emissivity` (–, default 0.8), `shell_specific_heat` (J/kg·K, default 500) |
| Calibration | `drag_coefficient` C_F, `kilning_coefficient` k4, `flight_capacity_factor`, `heat_transfer_multiplier` C_a, `shell_contact_htc` h_ws (W/m²K) |
| Valid operating range | `max_drum_inlet_gas_temperature` (K), `min_dew_point_margin` (K, default 10), EMC data limit (K, default 403.15) |

### InitialState

| Variant | Meaning |
|---|---|
| `cold_empty` | no solids in the drum; gas, solids and shell at ambient temperature |
| `steady_state` | the model's own steady state for the inputs at `t_start` |
| `explicit` | user-given per-cell hold-up, moisture and temperatures (or a saved final state from a previous run) |

### TimeSettings

| Field | Type | Unit | Rule |
|---|---|---|---|
| `start`, `end` | datetime (UTC) | — | end > start; inputs must cover [start, end] |
| `output_interval` | duration | s | 1 s–1 h; default 60 s |
| `rtol`, `atol` | float | — | solver tolerances, recorded; defaults fixed |

### Scenario

The complete input of one run: `name`, `FlueGasSupply` source, `DilutionAir`,
`ProductFeed`, `AmbientConditions`, `DryerConfiguration`, `InitialState`, `TimeSettings`,
and the balance tolerances (defaults from SC-002: 0.1 % mass, 1 % energy).

## 3. Model state

### DryerState

The internal state of the drum at one time; ODE state vector, 8 values per cell (research
R1):

| Per-cell field | Unit |
|---|---|
| `dry_mass_passive`, `dry_mass_active` | kg |
| `water_mass_passive`, `water_mass_active` | kg |
| `solids_temperature` | K |
| `gas_temperature` | K |
| `gas_humidity` | kg/kg dry gas |
| `shell_temperature` | K |

Invariants: all masses ≥ 0; temperatures > 0 K; humidity ≥ 0. The final DryerState of a run
is saved so it can be used as an `explicit` initial state.

## 4. Output entities

### DryerResults

Time series at `output_interval` (FR-008):

| Column | Unit |
|---|---|
| `product_dry_mass_flow` | kg/s |
| `product_moisture_wet_basis` | kg/kg |
| `product_temperature` | K |
| `evaporation_rate` | kg/s |
| `exhaust_mass_flow` | kg/s |
| `exhaust_temperature` | K |
| `exhaust_humidity` | kg/kg dry gas |
| `exhaust_composition` (x_N2 … x_other) | mol/mol |
| `exhaust_dew_point` | K |
| `drum_inlet_gas_temperature` | K (after dilution) |
| `heat_supplied` | W (flue gas + dilution air, relative to T_ref) |
| `heat_used_for_drying` | W |
| `shell_heat_loss` | W |
| `specific_energy` | J/kg water evaporated |
| `solids_holdup` | kg |
| flags: `heat_limited`, `out_of_range`, `condensation_risk`, `input_quality` | bool / str |

Optional per-cell profiles (temperature, moisture, hold-up) at the output interval.

### BalanceReport

| Field | Meaning |
|---|---|
| `dry_solids`, `water`, `gas`, `energy` | each: `inflow`, `outflow`, `storage_change`, `residual = in − out − Δstored`, `relative_residual`, `tolerance`, `passed` |

`relative_residual` is relative to the total inflow of that quantity over the run (SC-002).

### RangeWarning

| Field | Meaning |
|---|---|
| `quantity`, `limit_type` (`min`/`max`), `limit`, `observed_extreme`, `period_start`, `period_end` | one contiguous period outside the valid range (FR-012) |

### RunRecord

Everything needed to reproduce and audit a run (FR-014, FR-017):

| Field | Meaning |
|---|---|
| `run_id` | UUID4 |
| `created_at` | UTC timestamp |
| `model_version` | package version + git commit if available |
| `environment` | Python, numpy, scipy versions, platform |
| `scenario` | the full validated scenario (normalised, SI) and a SHA-256 hash of it |
| `input_files` | paths and SHA-256 hashes of referenced time series files |
| `status` | see state transitions below |
| `results_file`, `final_state_file` | paths of the outputs |
| `balance_report`, `range_warnings`, `flags_summary` | see above |
| `solver_stats` | wall-clock duration, number of RHS evaluations, steps, solver method and tolerances |
| `rejected_inputs` | list of input validation errors (for failed runs) |

**State transitions**:

```text
created ──validate──▶ validated ──simulate──▶ running ──▶ completed
   │                                             │
   └──(validation errors)──▶ rejected            └──(solver failure)──▶ failed
```

A completed run with failing balances or range warnings stays `completed` and carries the
flags; it is not silently discarded.

## 5. Validation entities

### MeasuredTimeSeries

Measured plant inputs and outputs (User Story 4): one column per quantity, each with a unit
and a per-value `quality` (`good` / `missing` / `bad`). Inputs map onto the scenario inputs;
outputs map onto `DryerResults` columns by name.

### ValidationReport

| Field | Meaning |
|---|---|
| `run_id` | the model run used |
| per output: `n_compared`, `n_excluded`, `bias`, `mae`, `rmse`, `max_abs_error`, `fraction_within_tolerance`, `tolerance`, `passed` | deviation statistics (FR-016) |
| `steady_periods` | periods detected as steady operation, used for SC-003 |
| `excluded` | list of excluded timestamps with the reason |

## 6. Relationships

```text
Scenario ──uses──▶ FlueGasSupply (Constant | TimeSeries | later: BoilerHouseModel)
   │                    └──produces──▶ FlueGasState ──has──▶ GasComposition
   ├── DilutionAir, ProductFeed, AmbientConditions, DryerConfiguration
   ├── InitialState ──may reference──▶ DryerState (from an earlier run)
   └── TimeSettings
Scenario ──run──▶ RunRecord ──has──▶ DryerResults, BalanceReport, RangeWarning[*], DryerState (final)
MeasuredTimeSeries + RunRecord ──compare──▶ ValidationReport
```
