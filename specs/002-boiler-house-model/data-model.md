# Data Model: Boiler House Model Supplying Flue Gas to the Dryer

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md) | **Date**: 2026-10-24

SI units internally, UTC timestamps, immutable validated entities, and two ranges per
configuration field (`physical_range` → error, `validated_range` → RangeWarning), all as in
feature 001 ([data-model](../001-boiler-dryer-interface/data-model.md)). Feature 001
entities (`FlueGasState`, `FlueGasSupply`, `DryerConfiguration`, `DryerState`,
`DryerResults`, `RunRecord`, `ValidationReport`) are reused unchanged.

## 1. Inputs

### Fuel

| Field | Type | Unit | Rule |
|---|---|---|---|
| `kind` | `"wood_chips"` \| `"bark"` \| `"custom"` | — | default `"wood_chips"` (composition from research R2) |
| `C`, `H`, `N`, `S`, `ash` | float | kg/kg dry | each 0 ≤ x ≤ 1; required for `custom`; O by difference |
| `O` | float | kg/kg dry | optional; if given, the sum must be 1 ± 0.005, else error |
| `moisture_wet_basis` | float or time series | kg/kg (w) | physical 0 ≤ w < 0.70; validated 0.10–0.55 |
| `temperature` | float or time series | K | 253.15–333.15 |
| `hhv_dry` / `lhv_dry` | float, optional, at most one | J/kg | 10–25 MJ/kg; if both absent, Channiwala–Parikh; giving both is an error |

Derived: `lhv_dry`, `lhv_as_received(w)` and the stoichiometric air per kg dry fuel (R2).

### CombustionAir

| Field | Type | Unit | Rule |
|---|---|---|---|
| `temperature` | float or time series | K | 253.15–573.15 (preheat allowed) |
| `relative_humidity` | float or time series | 1 | 0–1; defaults to the ambient value |
| `mass_flow` | float or time series, optional | kg/s | ≥ 0; allowed only with the O₂ controller in manual (then it replaces the manual λ) |

The amount comes from the O₂ controller, or from `ControllerSettings.manual_output` when in
manual (excess air ratio λ, physical 1.0–3.0, validated ≥ 1.2).

### ThermalOilCircuit

| Field | Type | Unit | Rule |
|---|---|---|---|
| `oil` | `"shell_s2"` \| `"therminol_66"` | — | default `"shell_s2"` |
| `mass_flow` | float or time series | kg/s | physical ≥ 0; required |
| `return_temperature` | float or time series | K | physical 273.15–623.15 |
| `max_bulk_temperature`, `max_film_temperature` | float | K | defaults from the oil (S2: 573.15 / 593.15 K) |
| `min_velocity` | float | m/s | default 2.0 (warning) |

## 2. Configuration

### BoilerHouseConfiguration

Groups and fields, each with `physical_range`, `validated_range`, default and source (as in
feature 001, `FIELDS` table):

| Group | Fields (unit) |
|---|---|
| Furnace | `rated_fuel_power` (W, reference 15 MW), `min_load_fraction` (–, 0.3), `gas_holdup_volume` (m³), `refractory_mass_hot_face`, `refractory_mass_bulk` (kg), `refractory_specific_heat` (J/(kg K), 1000), `refractory_area` (m²), `refractory_gas_htc` (W/(m² K)), `refractory_conductance` (W/K), `loss_ua` (W/K), `ash_discharge_temperature` (K) |
| Fuel bed | `bed_time_constant` (s, 900), `water_time_constant` (s, 600), `feed_dead_time` (s, 120) |
| Radiant heater (heater 1) | `tube_area` (m²), `cold_plane_area` (m², αA_cp), `flame_emissivity` (–, 0.5), `convective_htc` (W/(m² K), 11), `tube_mass` (kg), `oil_volume` (m³), `tube_inner_diameter` (m), `n_parallel_passes`, `peak_flux_factor` (–, 1.57 × 1.1) |
| Convective heater (heaters 2, 3; list) | `n_cells` (5), `tube_outer_diameter`, `tube_inner_diameter` (m), `transverse_pitch`, `longitudinal_pitch` (m), `n_rows`, `tubes_per_row`, `tube_length` (m), `free_flow_area` (m²), `gas_emissivity` (–, 0.1), `fouling_resistance` (m² K/W, 0.008), `tube_mass` (kg), `oil_volume` (m³), `n_parallel_passes`, `loss_ua` (W/K) |
| Bypass | `starts_after_heater` (1 or 2, default 1), `duct_loss_ua` (W/K, 0) |
| Measurement | `o2_sensor_time_constant` (s, 30) |

`heaters` is an ordered list: element 0 is the radiant heater, then the convective heaters.
The number of heaters is the length of the list (reference: 3).

### ControllerSettings

One per loop: `oil_temperature`, `oxygen`, `drum_inlet_temperature`.

| Field | Type | Unit | Rule |
|---|---|---|---|
| `mode` | `"automatic"` \| `"manual"` | — | default `"automatic"` |
| `setpoint` | float or time series | quantity of the loop | oil 555.15 K; O₂ 0.07 mol/mol dry; drum inlet K (no default: required in coupled runs with automatic mode) |
| `gain` | float | output unit per measured unit | > 0 |
| `integral_time` | float | s | > 0 |
| `tracking_time` | float | s | > 0; default = `integral_time` |
| `output_min`, `output_max` | float | output unit | min < max |
| `manual_output` | float or time series | output unit | inside the limits |
| `split_value` | float | – | drum inlet loop only, 0 < s < 1, default 0.5 |
| `max_dilution_air` | float | kg/s | drum inlet loop only, > 0 |
| `smoothing` | float | – | saturation softness ε as a fraction of span, default 0.005 |
| `not_reached_band` | float | quantity of the loop | > 0; defaults oil 2 K, O₂ 0.005 mol/mol, drum inlet 5 K |
| `not_reached_hold` | float | s | ≥ 0; default 600 |

Outputs: oil loop → fuel feed (kg/s wet); O₂ loop → excess air ratio λ (fed forward on the
current burnout); drum inlet loop → split-range signal u ∈ [0, 1], giving the bypass position
and the dilution air flow.

Validation: in automatic mode, `manual_output` is optional (it initialises the output). A fixed
combustion air amount given together with the O₂ controller in automatic is rejected (spec
edge case). In coupled runs, `max_dilution_air` of the drum inlet controller is the only
definition of the dilution air limit; a `[dilution_air]` section is then rejected.

## 3. State

### BoilerHouseState

The ODE state of the boiler house, for initial and final states (JSON, like `DryerState`):

| Field | Unit | Count |
|---|---|---|
| `feed_stage_1`, `feed_stage_2` | kg/s (fuel in transport) | 2 |
| `bed_water`, `bed_dry_fuel` | kg | 2 |
| `furnace_gas_enthalpy` | J (internal; reported as `furnace_temperature`, K) | 1 |
| `refractory_hot_face`, `refractory_bulk` | K | 2 |
| `heater_wall` | K, per heater and cell | 1 + Σ n_cells |
| `heater_oil` | K, per heater and cell | 1 + Σ n_cells |
| `o2_measured` | mol/mol dry | 1 |
| `controller_integral` | output unit, per loop | 3 |

Reference size: 2 + 2 + 1 + 2 + (1 + 10) × 2 + 1 + 3 = 33 states. Invariants: masses ≥ 0,
temperatures > 0 K, 0 ≤ O₂ ≤ 0.21.

### InitialState (boiler house)

`cold` (everything at ambient, empty bed, controllers at their manual output), `steady_state`
(frozen-input steady state, as in feature 001), or `explicit` (from `final_state.json`).
In coupled runs the plant initial state is the pair (boiler house, dryer) with one `kind`.

## 4. Outputs

### BoilerHouseResults

Time series at the output interval (`boiler_results.csv`, unit row):

| Column | Unit |
|---|---|
| `fuel_feed`, `fuel_burnout_dry` | kg/s |
| `heat_released` | W (burnout × LHV basis, R2) |
| `excess_air_ratio`, `o2_dry`, `o2_dry_measured` | –, mol/mol |
| `combustion_air_flow` | kg/s |
| `furnace_temperature` | K |
| `gas_temperature_after_heater_{i}` | K, i = 1 … n |
| `oil_temperature_after_heater_{i}` | K |
| `oil_outlet_temperature` | K (after heater 1) |
| `heat_to_oil_{i}`, `heat_to_oil` | W |
| `max_film_temperature`, `min_oil_velocity` | K, m/s |
| `losses` | W (furnace, heaters, ash, bypass duct) |
| `bypass_position`, `dilution_air_flow` | –, kg/s |
| `flue_gas_to_dryer_mass_flow`, `flue_gas_to_dryer_temperature` | kg/s, K |
| `controller_output_{loop}`, `controller_mode_{loop}` | –, str |
| flags: `oil_limit`, `combustion_out_of_range`, `load_out_of_range`, `controller_saturated`, `setpoint_not_reached`, `out_of_range` | bool |

### Interface time series (FR-014)

- `flue_gas_to_dryer.csv`: columns `time, mass_flow, temperature, pressure, x_N2, x_O2,
  x_CO2, x_H2O, x_other, quality`, plus a unit row. This is exactly the feature-001
  flue-gas time-series format.
- `dilution_air.csv`: columns `time, dilution` (kg/s).

### PlantBalanceReport

`{ boiler_house, oil_circuit, dryer, interface, plant }`. Each entry has the feature-001
`BalanceReport` fields per quantity. The boiler house also has element balances `C`, `H`,
`O`, `N`, `S`. The interface checks that the boiler outlet equals the dryer inlet (mass and
energy). `passed` = all passed.

### RunRecord additions

`boiler_results_file`, `interface_files`, `controller_settings`, and `plant_balance_report`
(replaces `balance_report` for coupled and boiler-only runs; a dryer-only run is unchanged).

## 5. Relationships

```text
Scenario
 ├─ flue_gas.source = "constant" | "timeseries"          → dryer-only run (feature 001)
 ├─ flue_gas.source = "boiler_house" + [boiler_house]    → coupled run (requires [dryer.*])
 └─ [boiler_house] without [dryer.*]                     → boiler-house-only run
BoilerHouse = Fuel + CombustionAir + Furnace + Heaters[*] + Bypass + ThermalOilCircuit
              + Controllers{oil_temperature, oxygen, drum_inlet_temperature}
Plant (coordinator)
 ├─ BoilerHouseModel ──outlet FlueGasConditions──▶ CoupledFlueGasSupply (FlueGasSupply) ──▶ DrumDryerModel
 └─ drum inlet controller ──dilution air──▶ ControlledSignal ──▶ DrumDryerModel.inputs.dilution_air
Run ──▶ RunRecord + DryerResults + BoilerHouseResults + interface CSVs + PlantBalanceReport
```
