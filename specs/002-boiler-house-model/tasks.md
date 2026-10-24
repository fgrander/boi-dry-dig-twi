---

description: "Task list for feature 002: boiler house model supplying flue gas to the dryer"
---

# Tasks: Boiler House Model Supplying Flue Gas to the Dryer

**Input**: Design documents from `specs/002-boiler-house-model/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: REQUIRED (constitution principle I). Every test task MUST be written and observed
failing before its implementation task is started.

**Organization**: grouped by user story. Feature 001 code (`interface/`, `dryer/`) MUST NOT be
changed except where a task says so explicitly.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 (boiler house alone), US2 (coupled plant), US3 (comparison)
- ⚠ **VERIFY**: a default from [research.md Open items](research.md#open-items). Implement it as
  a named, configurable default with the source in the docstring and a `# VERIFY(...)`
  comment.

---

## Phase 1: Setup

- [X] T001 Create empty modules with module docstrings per plan.md § Source Code:
  - `src/boidrytwin/properties/fuel.py`, `src/boidrytwin/properties/thermal_oil.py`;
  - `src/boidrytwin/control/{__init__,pi,split_range}.py`;
  - `src/boidrytwin/boiler_house/{__init__,config,state,fuel_bed,furnace,heaters,bypass,ranges,model}.py`;
  - `src/boidrytwin/plant/{__init__,coupled_supply,model,simulate}.py`;
  - `src/boidrytwin/checks/plant_balances.py`;
  - test packages `tests/unit/boiler_house/`, `tests/unit/control/` (with `__init__.py`).
- [X] T002 [P] Write the import-boundary contract test in `tests/contract/test_import_boundaries.py` (constitution III). Using the stdlib `ast` module on the source files, assert that:
  - `boidrytwin.boiler_house` imports nothing from `boidrytwin.dryer` or `boidrytwin.plant`;
  - `boidrytwin.dryer` imports nothing from `boidrytwin.boiler_house` or `boidrytwin.plant`;
  - `boidrytwin.interface` imports neither.

**Checkpoint**: skeleton imports; ruff and mypy pass; the boundary test passes on the empty modules.

---

## Phase 2: Foundational

**Purpose**: properties and controllers used by both P1 stories.

### Tests (write first, must fail)

- [X] T003 [P] Write `tests/unit/properties/test_fuel.py`:
  - default compositions `wood_chips` (C 51.3, H 6.1, N 0.4, S 0.02, ash 1.3, O by difference) and `bark` (C 49.9, H 5.9, N 0.4, S 0.03, ash 2.5) in wt% dry;
  - custom composition: "the sum must be 1 ± 0.005" when O is given, else O by difference;
  - Channiwala–Parikh HHV_d = 0.3491 C + 1.1783 H + 0.1005 S − 0.1034 O − 0.0151 N − 0.0211 A (MJ/kg, wt% dry), giving ≈ 20.85 MJ/kg for wood chips;
  - LHV_d = HHV_d − 0.2122 H − 0.0008 (O + N), giving ≈ 19.5 MJ/kg, within VTT's 19.0–20.5;
  - LHV_ar = LHV_d (1 − M/100) − 0.02443 M, giving ≈ 8.5 MJ/kg at M = 50;
  - stoichiometric O₂ and air per kg dry fuel (≈ 6.2 kg air/kg for wood chips);
  - flue gas moles of CO₂, H₂O, SO₂, N₂ and O₂ at λ;
  - λ ↔ dry O₂ relation (λ ≈ 1.50 at 7 % dry O₂);
  - element conservation (C, H, O, N, S in = out) to 1e-12;
  - a measured `hhv_dry` or `lhv_dry` overrides the correlation; giving both is rejected.
- [X] T004 [P] Write `tests/unit/properties/test_thermal_oil.py`:
  - Shell S2 fits against the TDS v1.1 table at 20, 100, 200 and 300 °C within 1 % (ρ, c_p, k) and 5 % (ν);
  - Therminol 66 fits against the Eastman table at 20, 200 and 300 °C within 1 % (ρ, c_p, k) and 3 % (ν);
  - enthalpy derivative equals c_p; enthalpy inversion round-trips to 1e-9 K;
  - default limits: S2 bulk 573.15 K / film 593.15 K; Therminol 66 bulk 618.15 K / film 648.15 K.
- [X] T005 [P] Write `tests/unit/control/test_pi.py`:
  - proportional and integral action;
  - back-calculation: dI/dt = (K_c/T_i)·e + (u_sat − v)/T_t, with T_t defaulting to T_i;
  - output stays within limits with smooth saturation (ε = 0.5 % of span), and the bias at the limit is ≤ ε·span·ln 2;
  - exact-saturation mode;
  - no wind-up: after a long saturation the output leaves the limit within ≈ T_t once the error changes sign;
  - manual mode tracks `manual_output` and the switch to automatic is bumpless;
  - steady-state initialisation I₀ = u₀ − K_c·e₀;
  - direct and reverse action;
  - the `not_reached` flag is set after |e| > band for longer than the hold time, and cleared when back inside the band.
- [X] T006 [P] Write `tests/unit/control/test_split_range.py`:
  - u ≤ s → bypass = (s − u)/s, dilution = 0;
  - u ≥ s → bypass = 0, dilution = (u − s)/(1 − s)·max_dilution_air;
  - the two actuators are never open together;
  - continuity at u = s;
  - "split value 0 < s < 1".

### Implementation

- [X] T007 [P] Implement `src/boidrytwin/properties/fuel.py` per research.md R2: `FuelComposition` (pydantic, frozen), default fuels, an optional measured `hhv_dry` or `lhv_dry` input (at most one) overriding the correlation, `hhv_dry`, `lhv_dry`, `lhv_as_received`, `stoichiometry(fuel, moisture, air_humidity, lambda_) → flue gas species flows per kg dry fuel` (in the species order of `properties.gas`, with SO₂ in "other"), and `lambda_from_o2_dry` / `o2_dry_from_lambda`. ⚠ VERIFY the ISO 18125 coefficients 0.2122 and 0.0008.
- [X] T008 [P] Implement `src/boidrytwin/properties/thermal_oil.py` per research.md R6: `ThermalOil` with `density`, `cp`, `conductivity`, `viscosity`, `enthalpy` (relative to 298.15 K), `temperature_from_enthalpy` (exact inversion of the quadratic), limits, and the registry `{"shell_s2", "therminol_66"}`.
- [X] T009 [P] Implement `src/boidrytwin/control/pi.py`: `PISettings` (pydantic; data-model ControllerSettings rules: "gain > 0", "integral_time > 0", "tracking_time > 0; default = integral_time", "output_min < output_max", "manual output inside the limits"), `pi_output(settings, e, I) → (v, u)` and `pi_integral_rate(...)` (vectorisable), plus `smooth_clip`.
- [X] T010 [P] Implement `src/boidrytwin/control/split_range.py`: `split(u, s, max_dilution) → (bypass_position, dilution_flow)`.

**Checkpoint**: Phase 2 tests pass; feature-001 suite unchanged.

---

## Phase 3: User Story 1 — Simulate the boiler house on its own (P1) 🎯 MVP

**Goal**: a boiler-house-only scenario runs, with the oil and O₂ loops in automatic, and writes `boiler_results.csv`.

**Independent Test**: quickstart §2–4 and §7: combustion hand calculation, boiler hand balance, oil at 282 °C ± 0.5 K, recovery from the oil demand step, and the edge cases.

### Tests for User Story 1 (write first, must fail)

- [X] T011 [P] [US1] Write `tests/unit/boiler_house/test_config.py`:
  - every field of data-model §2 has physical and validated ranges plus a doc string;
  - the reference defaults (rated fuel power 15 MW, min_load_fraction 0.3, bed_time_constant 900 s, water_time_constant 600 s, feed_dead_time 120 s, flame_emissivity 0.5, convective_htc 11, fouling_resistance 0.008, gas_emissivity 0.1, o2_sensor_time_constant 30 s, n_cells 5);
  - "`heaters[0].type` is `radiant`, the others `convective`";
  - "`starts_after_heater` < number of heaters".
- [X] T012 [P] [US1] Write `tests/unit/boiler_house/test_state.py`: the state layout of data-model §3 (33 values for the reference with 3 heaters and 5 cells each), pack/unpack round trip, invariants "masses ≥ 0, temperatures > 0 K, 0 ≤ O₂ ≤ 0.21", JSON round trip.
- [X] T013 [P] [US1] Write `tests/unit/boiler_house/test_fuel_bed.py`:
  - two-stage feed delay with a steady-state gain of 1 and mean delay `feed_dead_time`;
  - bed water dm_w/dt = w·ṁ_f − m_w/τ_w and dry fuel dm_d/dt = (1 − w)·ṁ_f − m_d/τ_bed;
  - steady inventories m = ṁ·τ;
  - mass conservation: feed in = burnout + evaporation + ash + d(inventory)/dt.
- [X] T014 [P] [US1] Write `tests/unit/boiler_house/test_furnace.py`:
  - the well-stirred zone energy balance closes per evaluation (heat released + air enthalpy = flue gas enthalpy out + Q_rad + Q_refractory + losses + d(storage)/dt);
  - Q_rad = σ·αA_cp·F(ε_fl)·(T_g⁴ − T_w⁴) + h_c·A_t·(T_g − T_w) against a hand value;
  - refractory nodes exchange heat in the right direction;
  - the adiabatic limit (ε_fl = 0, no losses) gives the adiabatic flame temperature, checked against a Cantera equilibrium oracle within 10 K (`oracle` marker).
- [X] T015 [P] [US1] Write `tests/unit/boiler_house/test_heaters.py`:
  - per-cell gas outlet T_w + (T_g,in − T_w)·exp(−UA/(ṁc_p)), with the heat to the wall equal to ṁ·Δh exactly;
  - Žukauskas Nu (staggered, C/m 0.35/0.6 and 0.031/0.8 ranges) against hand values;
  - Gnielinski oil side, with the laminar Nu 3.66 and the 2300–10⁴ blend;
  - the fouling resistance in series;
  - counter-current oil advection (oil enters the last cell of the last heater);
  - film temperature T_film = T_oil + q″_peak/h_i with the peak factor;
  - energy conservation over a heater per evaluation.
- [X] T016 [P] [US1] Write `tests/unit/boiler_house/test_bypass.py`: position 0 → no bypass; position 1 → all gas bypasses the heaters after `starts_after_heater`; mixing conserves mass and enthalpy exactly.
- [X] T017 [P] [US1] Write `tests/unit/boiler_house/test_model.py`:
  - `BoilerHouseModel.rhs` returns state derivatives and `BoilerOutputs` (flue_gas_to_dryer as `FlueGasConditions`);
  - the storage derivative equals the boundary flows per evaluation (mass, C/H/O/N/S, energy) to 1e-9 relative;
  - the Jacobian sparsity pattern covers all non-zero entries found by finite differences.
- [X] T018 [P] [US1] Write `tests/unit/boiler_house/test_ranges.py` (research.md R9):
  - fuel moisture "validated 0.10–0.55", "warning above 55 %, error above 65 %";
  - λ ≥ 1.2;
  - furnace temperature 850–1150 °C (warning band 800–850, invalid < 800);
  - load 30–100 % (warning below 50 %);
  - oil bulk/film limits with the 80 %-of-margin pre-warning;
  - oil velocity ≥ 2.0 m/s and Re ≥ 10⁴.
- [X] T019 [P] [US1] Write `tests/contract/test_scenario_boiler.py` per [scenario-file-boiler.md](contracts/scenario-file-boiler.md):
  - the example sections load and normalise to SI;
  - a boiler-house-only run is detected;
  - `[boiler_house]` together with `flue_gas.source = "constant"` is rejected as ambiguous;
  - every validation rule of the contract, each with field, value, reason and line;
  - `combustion_air.mass_flow` while the O₂ loop is automatic is rejected.
- [X] T020 [P] [US1] Write `tests/validation/test_combustion_hand_calculation.py` and `tests/validation/combustion_case.md` (SC-001):
  - inputs: wood chips at 45 % moisture, 7 % O₂ dry, air 20 °C / 60 % RH;
  - documented hand calculation of air and flue gas flows, wet/dry composition and LHV;
  - assert the model: composition within 0.1 percentage points (vol), flow within 0.1 %.
- [X] T021 [P] [US1] Write `tests/validation/test_boiler_hand_balance.py` and `tests/validation/boiler_balance_case.md` (SC-002), at a steady state of `examples/boiler_house_only.toml`:
  - oil side by hand: duty = ṁ_oil·[h_oil(T_out) − h_oil(T_return)] from the oil property fits; assert the model's `heat_to_oil` within 1 %;
  - gas side by hand: heat released = ṁ_fuel,dry·LHV-basis enthalpy (R2) from fuel feed and composition; flue gas enthalpy to the dryer = heat released + air enthalpy − oil duty − losses (losses taken from the model output); solve for the temperature; assert `gas_temperature_after_heater_3` within 5 K.
- [X] T022 [P] [US1] Write `tests/validation/test_boiler_settles.py`: from `cold` with constant inputs, the run settles and matches the `steady_state` initial state within 0.1 % (FR-008).
- [X] T023 [P] [US1] Write `tests/validation/test_controller_steps.py` (SC-004):
  - steady oil outlet within ±0.5 K of 282 °C;
  - after a 20 % step in oil heat demand (oil flow or return temperature), back within ±2 K within 4 × (τ_c + θ), using τ_c and θ from the tuning result recorded by T040; overshoot ≤ 5 K; no sustained oscillation (the oscillation amplitude in the last hour < 0.2 K);
  - also report the settling time against the 30-minute plant target, without asserting it (dependency on plant data);
  - after a fuel moisture step, O₂ returns to set point.
- [X] T024 [P] [US1] Write `tests/integration/test_boiler_edge_cases.py`, one test per spec edge case:
  - fuel trip (oil falls, flagged, the run continues);
  - oil demand above capacity (fuel at max, `controller_saturated` and `setpoint_not_reached` flagged, the latter only after the 10-minute hold);
  - oil demand near zero (min load flagged);
  - oil flow stop while hot (film/bulk limit flagged);
  - wet fuel (combustion temperature flagged);
  - combustion air amount fixed while the O₂ loop is automatic (rejected at load).
- [X] T025 [P] [US1] Write `tests/integration/test_boiler_run.py`: `boidrytwin run examples/boiler_house_only.toml` writes `run_record.json`, `boiler_results.csv` (all data-model §4 columns, unit row) and `final_state.json`; the plant balance report for the boiler house and the oil circuit passes; two runs are bit-identical.

### Implementation for User Story 1

- [X] T026 [P] [US1] Implement `src/boidrytwin/boiler_house/config.py`: `BoilerHouseConfiguration` with the groups of data-model §2 (FIELDS table with physical/validated ranges, defaults and sources, as `dryer/config.py`), a `heaters` list (radiant first), `bypass`, `validated_range_violations()`. ⚠ VERIFY: flame_emissivity, convective_htc, gas_emissivity, fouling_resistance, bed/water time constants, feed_dead_time, o2_sensor_time_constant, min_load_fraction.
- [X] T027 [P] [US1] Implement `src/boidrytwin/boiler_house/state.py`: `BoilerHouseState` (data-model §3) with pack/unpack, invariants and JSON I/O.
- [X] T028 [P] [US1] Implement `src/boidrytwin/boiler_house/fuel_bed.py` per research.md R3.
- [X] T029 [P] [US1] Implement `src/boidrytwin/boiler_house/furnace.py` per research.md R4:
  - the well-stirred gas zone with a constant hold-up and an enthalpy state;
  - radiant exchange to the heater-1 wall;
  - two refractory nodes;
  - losses through UA;
  - ash discharge enthalpy (c_p,ash 800 J/(kg K), ⚠ VERIFY).
- [X] T030 [P] [US1] Implement `src/boidrytwin/boiler_house/heaters.py` per research.md R5–R6: radiant heater wall and oil nodes; convective heaters in n_cells counter-current cells; quasi-static gas; Žukauskas + gas radiation + fouling on the gas side; Gnielinski on the oil side; film temperature and velocity; vectorised over cells.
- [X] T031 [P] [US1] Implement `src/boidrytwin/boiler_house/bypass.py` per research.md R7.
- [X] T032 [P] [US1] Implement `src/boidrytwin/boiler_house/ranges.py` per research.md R9, producing feature-001 `RangeWarning`s and per-sample flags.
- [X] T033 [US1] Implement `src/boidrytwin/boiler_house/model.py`:
  - `BoilerHouseModel.rhs(t, x, inputs) → (dx, BoilerOutputs)`, assembling fuel bed, furnace, heaters and bypass in flux form;
  - `storage()` for mass, elements and energy;
  - `jac_sparsity()`, `initial_cold()`, `scales()`.
  - Depends on T026–T031.
- [X] T034 [US1] Implement the boiler-only part of `src/boidrytwin/plant/model.py`:
  - `Plant` assembling the `BoilerHouseModel` with the oil-temperature PI (fuel feed) and the O₂ PI (λ, fed forward on the current burnout rate);
  - the measured-O₂ lag state;
  - controller integral states in the plant state vector;
  - per-evaluation boundary flows for accumulators.
  - The bypass position and dilution are prescribed (manual) in boiler-only runs.
- [X] T035 [US1] Implement the boiler-only path of `src/boidrytwin/plant/simulate.py`, reusing the feature-001 integration pattern (scaled states, BDF, breakpoints, accumulators, steady-state march + root polish, output sampling): `simulate_plant(loaded) → PlantSimulationResult`, with boiler results, final state and solver stats.
- [X] T036 [US1] Implement `src/boidrytwin/checks/plant_balances.py`: `PlantBalanceReport` with `boiler_house` (mass, C, H, O, N, S, energy) and `oil_circuit` (energy) entries, built from the accumulators and storage, in the feature-001 `QuantityBalance` format.
- [X] T037 [US1] Extend `src/boidrytwin/scenario/schema.py` and `loader.py` with the `[boiler_house]` sections and rules of [scenario-file-boiler.md](contracts/scenario-file-boiler.md) (boiler-house-only detection, heaters array of tables, controllers, initial state, `combustion_air.mass_flow` allowed only with the O₂ loop in manual). The feature-001 contract tests must still pass.
- [X] T038 [US1] Extend `src/boidrytwin/records.py` and `src/boidrytwin/cli.py`:
  - `run` dispatches boiler-house-only scenarios to `simulate_plant`;
  - it writes `boiler_results.csv` (unit row) and `final_state.json` (boiler state plus controller integrals);
  - the run record gains `plant_balance_report` and `controller_settings`;
  - the stdout summary reports balances and controller saturation counts.
- [X] T039 [P] [US1] Create `examples/boiler_house_only.toml` (15 MW reference, wood chips 45 %, oil 60 kg/s with return 240 °C, bypass closed, steady-state start, 24 h) and `examples/oil_demand_step.toml` with `examples/data/oil_return_step.csv` (a return-temperature step giving +20 % oil heat demand at 06:00).
- [X] T040 [US1] Write `scripts/tune_controllers.py`:
  - open-loop step tests on the twin for each loop;
  - FOPDT fit with the half rule;
  - SIMC with τ_c = θ (K_c = τ₁/(k(τ_c + θ)), T_i = min(τ₁, 4(τ_c + θ)));
  - prints the TOML snippets.
  - Then run it on the reference and put the resulting settings as defaults in `examples/*.toml` and the controller defaults, recording k, τ₁ and θ in `specs/002-boiler-house-model/research.md` R8.
- [X] T041 [US1] Add structured log events `plant_run_started`, `controller_saturated` (with loop and period), `setpoint_not_reached` and `checks_completed` (per-subsystem residuals) to `src/boidrytwin/plant/simulate.py`.

**Checkpoint**: US1 works on its own; quickstart §2–4 and §7 (boiler parts) pass.

---

## Phase 4: User Story 2 — Run the boiler house and the dryer as one plant (P1)

**Goal**: a coupled scenario runs with all three loops; the dryer is unchanged; all balances pass.

**Independent Test**: quickstart §5–6, §8: coupled run, swap test, benchmark.

### Tests for User Story 2 (write first, must fail)

- [X] T042 [P] [US2] Write `tests/contract/test_plant_coupling.py` per [plant-coupling.md](contracts/plant-coupling.md):
  - `CoupledFlueGasSupply` satisfies the feature-001 `FlueGasSupply` protocol;
  - the boiler outlet equals the dryer inlet at every output time (interface residual exactly 0);
  - the dryer configuration of `examples/reference_constant.toml` is used unchanged in `examples/plant_reference.toml`;
  - `test_swap_boiler_for_timeseries` (SC-006): the dryer results within 0.1 % when the boiler is replaced by its `flue_gas_to_dryer.csv` and `dilution_air.csv`.
- [X] T043 [P] [US2] Write `tests/integration/test_drum_inlet_control.py`:
  - gas too hot → dilution opens with the bypass closed;
  - gas too cold → the bypass opens with dilution closed;
  - never both open;
  - the drum inlet within ±5 K of its set point in steady operation (SC-005);
  - with the bypass opening, the fuel feed rises and the oil stays at 282 °C ± 2 K (spec US2 scenario 3).
- [X] T044 [P] [US2] Write `tests/integration/test_plant_edge_cases.py`:
  - drum inlet set point unreachable ("bypass fully open and no dilution air"), flagged and the dryer reports heat-limited;
  - dilution above its maximum, flagged;
  - an oil demand drop gives less heat to the dryer;
  - a boiler outlet outside the interface range gives a RangeWarning, not an exception.
- [X] T045 [P] [US2] Write `tests/integration/test_plant_balances_close.py` (SC-003): for `plant_reference.toml` and the coupled step scenario, the boiler house (mass, C, H, O, N, S within 0.1 %; energy within 1 %), oil circuit, dryer, interface and plant entries all pass.
- [X] T046 [P] [US2] Write `tests/integration/test_interface_timeseries.py` (FR-014): `flue_gas_to_dryer.csv` and `dilution_air.csv` pass `boidrytwin validate` as boundary conditions of a dryer-only scenario.
- [X] T047 [P] [US2] Write `tests/integration/test_plant_rerun.py` (FR-016): `rerun` of a coupled run is `identical: true`, and the controller settings are recorded.
- [X] T048 [P] [US2] Write `tests/performance/test_plant_benchmark.py` (marker `benchmark`, SC-007): coupled 24 h at 1-minute output in < 120 s; boiler alone in < 30 s.

### Implementation for User Story 2

- [X] T049 [P] [US2] Implement `src/boidrytwin/plant/coupled_supply.py`: `CoupledFlueGasSupply` (full `FlueGasSupply` protocol; `state_at` validates the current conditions; `covers` is true; `breakpoints` are the boiler input breakpoints) and `ControlledSignal` (Signal-compatible `value_at`/`values_at`/`breakpoints`/`covers`).
- [X] T050 [US2] Extend `src/boidrytwin/plant/model.py` for coupled runs:
  - global state `[x_boiler, controller states, x_dryer]`;
  - per evaluation: boiler → set the coupled supply and dilution signal → dryer;
  - the drum inlet split-range PI measuring `dryer.inlet(t).temperature`;
  - the block Jacobian pattern (dryer cell 0 depends on the boiler outlet and controller states).
  - No change to `src/boidrytwin/dryer/`.
- [X] T051 [US2] Extend `src/boidrytwin/plant/simulate.py` for coupled runs: dryer results as feature 001 plus boiler results; dryer flow accumulators; the steady state of the whole plant; range warnings of both subsystems.
- [X] T052 [US2] Extend `src/boidrytwin/checks/plant_balances.py` with `dryer`, `interface` and `plant` entries.
- [X] T053 [US2] Extend `src/boidrytwin/scenario/loader.py` for `flue_gas.source = "boiler_house"` (requires `[dryer.*]`; a drum inlet set point is required when that loop is automatic; the maximum dilution air comes only from `controllers.drum_inlet_temperature.max_dilution_air`, and a `[dilution_air]` section in a coupled scenario is rejected with "dilution air is set by the drum inlet controller").
- [X] T054 [US2] Extend `src/boidrytwin/records.py` for coupled runs: write `flue_gas_to_dryer.csv` and `dilution_air.csv` in the feature-001 time-series format; the plant balance report replaces `balance_report`; exit code 2 when any plant balance fails.
- [X] T055 [P] [US2] Create `examples/plant_reference.toml` (boiler reference plus the feature-001 reference dryer, drum inlet set point 540 °C, 24 h, steady-state start) and `examples/plant_oil_step.toml`.

**Checkpoint**: US1 and US2 work; quickstart §5–6 and §8 pass.

---

## Phase 5: User Story 3 — Compare the boiler house with plant measurements (P3)

- [X] T056 [P] [US3] Write `tests/unit/validation/test_compare_boiler.py`: measured columns may name boiler outputs (e.g. `o2_dry`, `furnace_temperature`, `gas_temperature_after_heater_3`, `oil_outlet_temperature`); default tolerances (SC-008) are O₂ ±0.005 mol/mol, flue gas temperatures ±10 K and oil outlet ±2 K; the synthetic deviations are reproduced.
- [X] T057 [US3] Extend `src/boidrytwin/validation/compare.py` (OUTPUT_DIMENSIONS and DEFAULT_TOLERANCES for boiler outputs) and `records.compare` to compare against boiler results in boiler-only and coupled runs.
- [X] T058 [P] [US3] Extend `scripts/make_synthetic_measured.py` with a `--boiler` mode writing `examples/synthetic_boiler_measured.csv` (known offsets and noise, seed 42), and document the expected deviations in `examples/README.md`.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T059 [P] Write `docs/boiler_house.md`: equations as implemented, states, assumptions, valid range, calibration parameters with defaults and sources, the VERIFY list, and the validation status (not validated against plant data).
- [X] T060 [P] Update `README.md` (boiler-only and coupled runs, new examples) and `examples/README.md`.
- [ ] T061 Verify the ⚠ VERIFY defaults against primary sources once available (ISO 18125 text, Channiwala–Parikh paper, plant thermal oil product data sheet, plant DCS step tests), and update the defaults and research.md. **Blocked** until the sources and data are provided.
- [X] T062 Run all steps of [quickstart.md](quickstart.md) and record the results in `specs/002-boiler-house-model/checklists/quickstart-run.md`.
- [X] T063 Final quality gate: ruff, ruff format, mypy, `pytest`, `pytest -m benchmark`; the feature-001 suite is unchanged and passing.

---

## Dependencies & Execution Order

```text
Setup → Foundational → US1 (boiler house alone) → US2 (coupled plant) → US3 (comparison) → Polish
```

- US2 depends on US1 (the coupled plant needs the boiler house model and the plant coordinator).
- US3 depends on US1 (boiler results); with coupled runs also on US2.
- T061 is blocked on external sources and data.

Key task dependencies:
- T007 → T028, T029 (fuel and stoichiometry)
- T008 → T030 (oil)
- T009/T010 → T034, T050
- T026–T032 → T033 → T034 → T035 → T036, T038
- T040 (tuning) after T035; T049 → T050 → T051 → T052, T054

## Parallel Examples

```text
# Phase 2: T003–T006 tests in parallel, then T007–T010 in parallel.
# US1: all tests T011–T025 in parallel; then T026–T032 in parallel; then T033 → T034 → T035.
# US2: tests T042–T048 in parallel; T049 and T055 in parallel with T050.
```

## Implementation Strategy

1. **MVP**: Setup, Foundational and US1. The boiler house runs alone with oil and O₂ control,
   which is already useful for studying oil supply and fuel.
2. **US2**: the coupled plant, the purpose of the twin.
3. **US3**: comparison, ready for when DCS data arrives.
4. **Polish**: documentation and the quickstart run. T061 waits for sources and data.

### Notes

- Do not change `src/boidrytwin/dryer/` or `src/boidrytwin/interface/`. If a change seems
  needed, stop and amend the plan.
- Commit after each logical group.
- Run the feature-001 suite after every phase.
