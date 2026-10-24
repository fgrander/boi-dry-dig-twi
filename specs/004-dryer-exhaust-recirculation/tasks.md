---

description: "Task list for feature 004: dryer exhaust gas recirculation with mixing chamber pressure control"
---

# Tasks: Dryer Exhaust Gas Recirculation

**Input**: Design documents from `specs/004-dryer-exhaust-recirculation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: REQUIRED (constitution principle I). Every test task MUST be written and observed
failing before its implementation task is started.

**Organization**: grouped by user story. Runs without `[recirculation]` MUST stay
byte-identical (SC-001); the guard test T004 runs after every task that touches `dryer/`,
`plant/` or `scenario/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 (dryer with recirculation), US2 (coupled plant and pressure control),
  US3 (web app)

---

## Phase 1: Setup

- [X] T001 Create empty modules with module docstrings per plan.md § Source Code: `src/boidrytwin/dryer/gas_path.py` (docstring states the assumptions of research R2/R3: quasi-steady, quadratic fan curve with fan laws, quadratic resistances, damper table, pressures in Pa relative to ambient) and `src/boidrytwin/dryer/recirculation.py` (research R5)
- [X] T002 [P] Store reference results of every example scenario of `examples/*.toml` (all except `invalid_flue_gas.toml` and `out_of_range_inlet.toml`, which do not run) as the guard baseline: a script `scripts/store_reference_results.py` that runs each scenario and writes `tests/data/reference_results/<name>.csv` (results.csv as written today) plus `<name>.json` (balances and flags); run it on the branch start before any model change and commit the files

---

## Phase 2: Foundational (blocking all stories)

**Purpose**: scenario section, gas path physics, dryer state layout, and the guard that existing runs stay unchanged.

### Tests first

- [X] T003 [P] Contract test for the `[recirculation]` section in `tests/contract/test_scenario_recirculation.py` per [contracts/scenario-file-recirculation.md](contracts/scenario-file-recirculation.md): the full example block loads into `RecirculationSpec` with SI values (−200 Pa, 990 rpm → 16.5 1/s, 120 degC → 393.15 K, 70 % → 0.7); defaults (`pressure_sensor_time_constant` 2 s, `duct_heat_loss` 0, `max_share` 0.7, `dew_point_margin` 10 K, `leakage` 0.01, controller `action` "reverse", `not_reached_band` 50 Pa, `not_reached_hold` 600 s); every rejection row of the contract's validation table gives an issue at the right field with file and line ("max_share ≤ 0 or ≥ 100 %", "output_min/max outside 0–100 % or min ≥ max", "setpoint outside [−2000, 0] Pa", "split_value, max_dilution_air present", "curve not 3 points, flows not increasing, pressure not falling", "speed < 0 or > 2 × nominal", "characteristic positions not 0 … 1 increasing, flows decreasing, last ≠ 1", "resistance or damper design ≤ 0 flow or pressure drop; temperature outside (−23, 627) °C", "duct_heat_loss < 0", "pressure_sensor_time_constant ≤ 0 or > 600 s"); every warning row becomes a range warning; `[recirculation]` in a boiler-house-only scenario is rejected with "recirculation: needs a dryer"; a missing sub-table is reported; unknown keys are errors; signals `recirculation.exhaust_fan.speed`, `recirculation.controller.setpoint` (and `.manual_output` with a manual signal) appear in `LoadedScenario.signals`
- [X] T004 [P] Guard test in `tests/integration/test_recirculation_off.py`: for every scenario stored by T002, run it and assert results.csv equal to the stored CSV (same columns, `pandas.testing.assert_frame_equal` with `check_exact=True`) and the same balances and flags (FR-005, SC-001); passes before any model change and must keep passing
- [X] T005 [P] Unit tests for the gas path in `tests/unit/dryer/test_gas_path.py` (FR-016, FR-017), hand values with stated tolerances:
  - the quadratic fit through the 3 contract curve points reproduces them to 1e-9 Pa; fan laws: at 0.9 × nominal speed and 0.9 × flow the pressure rise is 0.81 × (1e-9 relative); density correction ρ/ρ_ref;
  - resistance Δp = Δp_d (ρ_d/ρ)(ṁ/ṁ_d)² at 2 points (1e-12 relative);
  - damper flow: fully open at the design Δp and T gives `open_mass_flow`; PCHIP characteristic is monotone and hits the table points; position 0 gives the leakage; Δp ≤ 0 gives 0;
  - `solve()` for a hand case (given G_in, Y_out, T_out, s, n): residual F(G_rec) < 1e-6 Pa; p_mc = Δp_stack − Δp_fan + Δp_path within 1 Pa of a hand calculation in `tests/validation/recirculation_case.md`; G_drum = G_in + G_rec exactly; opening the damper raises p_mc (less vacuum), raising the speed lowers p_mc;
  - `backflow` is True and G_rec = 0 when the fan is too weak (F(0) ≤ 0); `fan_out_of_curve` when the volume flow leaves the points' range;
  - a non-falling curve is rejected by the constructor

### Implementation

- [X] T006 Add `RecirculationSpec`, `DamperSpec`, `ExhaustFanSpec`, `ResistancesSpec`, `ResistancePoint` and the field `ScenarioSpec.recirculation: RecirculationSpec | None = None` to `src/boidrytwin/scenario/schema.py` (frozen, extra forbidden) with the fields and rules of data-model.md §1; controller is the feature-002 `ControllerSpec` with the extra rules "output_min ≥ 0, output_max ≤ 1, split_value and max_dilution_air not allowed"
- [X] T007 Parse `[recirculation]` in `src/boidrytwin/scenario/loader.py`: a `recirculation_section()` like `dilution_section()`, with unit conversion via pint (rpm → 1/s, degC → K, % → fraction, `curve` as a list of 3 `[volume flow, pressure]` quantity pairs, `characteristic` as a list of `[position, relative flow]` numbers), physical-range rejection and validated-range warnings via `fields.FieldSpec`, the "needs a dryer" rule, and the three signals; makes T003 pass
- [X] T008 Implement `src/boidrytwin/dryer/gas_path.py`: `GasPath.from_spec(spec, p_ambient)` (quadratic fit, PCHIP damper characteristic with the default opposed-blade table of research R3 when none is given), `fan_pressure_rise`, `resistance`, `damper_flow`, `solve(G_in, Y_out, T_out, s, n, p_ambient) -> GasPathState` with `scipy.optimize.brentq` on [0, G_max] (xtol 1e-10 kg/s; G_max from the damper fully open at the fan's shut-off pressure), densities from the drum outlet gas at ambient pressure; the frozen dataclass `GasPathState` with the fields of data-model.md §2; makes T005 pass
- [X] T009 Refactor `src/boidrytwin/dryer/model.py` without changing results: add `DrumDryerModel.size` (= `n * N_FIELDS` when there is no recirculation) and `cell_slice`, use them in `_cells`, `scales`, `jac_sparsity`, `storage`; replace `dryer.n * 8` / `reshape(n, 8)` on whole vectors in `src/boidrytwin/plant/model.py` (`dryer_slice`), `src/boidrytwin/plant/simulate.py` (`_physical`) and `src/boidrytwin/dryer/simulate.py` (steady state mass check, scaling); change `inlet(t)` to `inlet(t, y=None)` and pass `y` at every call site; T004 must still pass

**Checkpoint**: T003–T005 green, T004 green, ruff and mypy clean.

---

## Phase 3: User Story 1 — Dryer with exhaust recirculation (P1) 🎯 MVP

**Goal**: a dryer-only scenario with `[recirculation]` runs; the damper holds the mixing chamber pressure; drum inlet, stack exhaust and balances are right.

**Independent Test**: `examples/dryer_recirculation.toml` runs; steady state matches the hand mix (SC-002); all balances including the loop close (SC-003); the closed damper case equals the run without recirculation.

### Tests first

- [X] T010 [P] [US1] Unit tests for the mixing in `tests/unit/dryer/test_recirculation_mix.py` (FR-002, FR-003): with a fixed state vector and fixed damper position, `inlet(t, y)` gives G_drum = G_in + G_rec, Y_drum = (G_in Y_fresh + G_rec Y_out)/G_drum and H_drum = (G_in H_fresh + G_rec H_out − Q_duct)/G_drum to 1e-12 relative; the drum inlet temperature is the Newton inverse of H_drum; dry composition equals the fresh mix; drum inlet O₂ mole fraction lower and humidity higher than without return; `heat_supplied` is unchanged by the return; duct loss UA·(T_out − T_ambient) lowers H_drum by exactly Q_duct/G_drum
- [X] T011 [P] [US1] Unit tests for the loop states in `tests/unit/dryer/test_pressure_loop.py` (FR-007–FR-009): the model has `size = 8 n + 2`; dp_m/dt = (p_mc − p_m)/τ_p; with p_m below the set point the controller output rises (reverse action, damper opens), above it falls; output saturates in [output_min, output_max] with back-calculation (integral rate as `PIController.integral_rate`); manual mode with `manual_output` and with a step signal gives that position; the initial state puts the integral so that the output equals the initial position (manual output, else 50 %); the Jacobian sparsity marks every cell row as depending on the last cell and on both loop states
- [X] T012 [P] [US1] Validation case in `tests/validation/recirculation_case.md` and test `tests/validation/test_recirculation_hand_mix.py` (SC-002): steady state of `examples/dryer_recirculation.toml`; from its last-cell outlet values and the fresh gas inputs, a hand mix (written out in the .md, with the enthalpy table used) gives drum inlet temperature, humidity and O₂; the run matches within 0.5 K, 1 % and 1 %; the hand gas path solve gives p_mc within 1 Pa of the result
- [X] T013 [P] [US1] Contract test for the results in `tests/contract/test_results_recirculation.py` per [contracts/results-recirculation.md](contracts/results-recirculation.md): every new column exists with its `RESULT_UNITS` entry only when `[recirculation]` is present; `exhaust_mass_flow` = `drum_outlet_mass_flow` − `recirculation_mass_flow` (1e-9 relative); `recirculation_share` = G_rec/G_drum; stack exhaust temperature, humidity, composition and dew point equal the drum outlet's; the run record has controller `mixing_chamber_pressure` with its settings, and `balances.recirculation_loop`
- [X] T014 [P] [US1] Balance test in `tests/integration/test_recirculation_balances.py` (FR-012, SC-003): dryer-only runs with recirculation (constant, and with a damper step in manual and a set point step in automatic) close the dryer balance (feed + flue gas + dilution air in; product + stack exhaust + shell loss + duct loss out) within 0.1 % mass and 1 % energy, and the recirculation loop check within the same; no jump in the balances across the step (acceptance scenario US1-4)
- [X] T015 [P] [US1] Run test in `tests/integration/test_recirculation_run.py`: `examples/dryer_recirculation.toml` runs from `cold_empty` and from `steady_state` without solver failure (edge case "cold, empty drum at start-up"); at the end p_mc within 50 Pa of −200 Pa; manual damper at 0 % with `leakage = 0` gives the results of the same scenario without `[recirculation]` within rtol 1e-5 (acceptance US1-2); with the time series flue gas source (`reference_timeseries.toml` sections plus `[recirculation]`) it runs the same way

### Implementation

- [X] T016 [US1] Implement `src/boidrytwin/dryer/recirculation.py`: `RecirculationLoop` built from `RecirculationSpec` and the loaded signals (fan speed, set point, manual signal) holding a `GasPath` and a `PIController`; `extra_size = 2`; `measured(y)`, `integral(y)`; `position(t, y)`; `rates(t, y, p_mc)` → (dp_m/dt, dI/dt); `initial_extra(t, p_mc)`; `scales()` (500 Pa, 1.0)
- [X] T017 [US1] Extend `src/boidrytwin/dryer/model.py`: `DrumDryerModel(config, inputs, recirculation: RecirculationLoop | None = None)`; `inlet(t, y)` mixes the fresh gas as today, then (with a loop and `y` given) solves the gas path with the last cell's Y and T, the applied damper position and fan speed, and mixes in the returned gas per research R4; `Inlet` gains the fields of data-model.md §3; `_evaluate` appends the two loop derivatives; the outlet flux of the last cell stays as is (the returned part leaves through the loop); `jac_sparsity` adds the dependence of all cells on the last cell and on the loop states and of the loop states on the last cell; without a loop every code path is unchanged; makes T010, T011 pass
- [X] T018 [US1] Results in `src/boidrytwin/dryer/model.py` `diagnostics()` and `src/boidrytwin/records.py` `RESULT_UNITS`: the new columns of the results contract, only with a loop; `exhaust_mass_flow` = stack flow = G_in (1 + Y_out); `drum_outlet_mass_flow` = G_drum (1 + Y_out); makes T013 pass (columns part)
- [X] T019 [US1] Balances in `src/boidrytwin/dryer/model.py` `_boundary()` and `src/boidrytwin/checks/balances.py`: dryer boundary includes mixing chamber, return duct and fan (gas in = G_in, water in = feed water + G_in Y_fresh, out = product water + G_in Y_out; energy out includes the stack exhaust G_in H_out and Q_duct; the returned flux is internal); new `recirculation_loop` check (last cell flux × share vs. what enters the mixing chamber + duct loss) in the run record; makes T014 pass
- [X] T020 [US1] Wire the loop into the dryer-only run in `src/boidrytwin/dryer/simulate.py`: `build_model` creates the `RecirculationLoop` when `loaded.spec.recirculation` is set; initial states (`cold_empty`, `steady_state`, `explicit` with a missing loop part → loop states from the initial position) include the two loop states; breakpoints include the new signals; the `setpoint_not_reached` flag for `mixing_chamber_pressure` via `not_reached_mask` with the loop's band and hold; controller settings in the run record; structured log summary (mean share, max |p_mc − set point|, backflow and overpressure periods); makes T015 pass
- [X] T021 [US1] Edge-case warnings in `src/boidrytwin/dryer/recirculation.py` and `src/boidrytwin/range_warnings.py` (FR-011): `mixing_chamber_overpressure` (p_mc > 0 Pa) and `recirculation_backflow` and `drum_inlet_condensation_risk` (T_drum_in − dew point(Y_drum) < `dew_point_margin`) as warning periods; range warnings for `exhaust_fan_curve`, `exhaust_fan.speed` and `recirculation_share` > `max_share`; tested in T029
- [X] T022 [US1] Example `examples/dryer_recirculation.toml`: the sections of `examples/reference_constant.toml` plus the `[recirculation]` block of the contract, with fan curve, resistances and damper sized so that at the reference point the damper is near 40–60 % open at −200 Pa (size them from a steady run of `reference_constant.toml`: drum outlet flow and temperature); header comment "example values, not plant data"; `examples/README.md` entry
- [X] T023 [US1] Make T012 pass: write the hand mix numbers into `tests/validation/recirculation_case.md` from the T022 example's steady state and check the tolerances

**Checkpoint**: US1 complete; T004 still green. Report to the user and ask before US2.

---

## Phase 4: User Story 2 — Recirculation in the coupled plant (P1)

**Goal**: the coupled plant runs with the pressure loop inside the dryer and the drum inlet split-range loop in the plant; both hold their set points.

**Independent Test**: `examples/plant_recirculation.toml`: p_mc within 50 Pa, drum inlet within 5 K of their set points; a 10 % fan speed step is corrected in under 5 min (SC-004); run time ≤ 1.5 × `plant_reference.toml` (SC-005).

### Tests first

- [X] T024 [P] [US2] Coupling test in `tests/contract/test_plant_coupling.py` (extend): with `[recirculation]` in a coupled scenario the plant's dryer slice has `8 n + 2` states; `Plant.jac_sparsity` marks the drum inlet measurement row as depending on the last dryer cell and on the loop states; the boiler house still gets only flue gas out / dilution air in through the existing interfaces (no new interface)
- [X] T025 [P] [US2] Steady state test in `tests/integration/test_plant_recirculation.py`: `kind = "steady_state"` start of `examples/plant_recirculation.toml` has all derivatives below the existing steady-state tolerance (joint polish, research R6); the run starts without a transient larger than 2 K at the drum inlet and 20 Pa in the mixing chamber in the first 10 min; plant and interface balances pass
- [X] T026 [P] [US2] Step validation in `tests/validation/test_pressure_loop_steps.py` (SC-004, acceptance US2-1, US2-2): from steady state, +10 % and −10 % fan speed steps: the damper opens on +10 % (draft stronger) and closes on −10 %; p_mc back within 50 Pa of the set point in < 5 min; drum inlet within 5 K; no sustained oscillation (amplitude of p_mc after 15 min < 5 Pa); an oil demand step and a feed moisture step (as in `plant_oil_step.toml`, `step_feed_moisture.toml`) keep both loops in their bands
- [X] T027 [P] [US2] Manual mode test in `tests/integration/test_plant_recirculation.py` (acceptance US2-3): controller `mode = "manual"` with a step signal of the damper position: the position follows the signal, p_mc follows from the flows, no not-reached flag for the manual loop
- [X] T028 [P] [US2] Benchmark in `tests/performance/test_plant_benchmark.py` (extend, `benchmark` marker): `plant_recirculation.toml` takes ≤ 1.5 × `plant_reference.toml` on the same machine (SC-005)
- [X] T029 [P] [US2] Edge cases in `tests/integration/test_recirculation_edge_cases.py` (FR-008, FR-011, acceptance US2-4): fan too weak (speed 30 %) → damper closed at its limit, `setpoint_not_reached` for `mixing_chamber_pressure`, `mixing_chamber_overpressure` and `recirculation_backflow` periods; fan too strong (speed 110 %, small damper) → damper fully open, flag; damper share above 70 % → `recirculation_share` range warning; very humid exhaust (feed moisture 60 %, low inlet temperature) → `drum_inlet_condensation_risk`; fan speed series out of curve → `exhaust_fan_curve` range warning; none of these cases fails the solver

### Implementation

- [X] T030 [US2] Plant model in `src/boidrytwin/plant/model.py`: build the dryer with its `RecirculationLoop` for coupled scenarios with `[recirculation]`; `dryer_slice` from `dryer.size`; `evaluate()` passes the dryer state to `dryer.inlet(t, y_dryer)` so the drum inlet measurement sees the mixed temperature; `with_dryer=False` and `n_upstream` are only used when there is no recirculation (new property `upstream_independent`); `jac_sparsity` adds the drum measurement row's dependence on the dryer's last cell and loop states; breakpoints include the `recirculation.` signals; makes T024 pass
- [X] T031 [US2] Steady state in `src/boidrytwin/plant/simulate.py`: when `not plant.upstream_independent`, run the existing two stages, then `_march_and_polish` on the whole plant (`_Scaled(plant, t, frozen_at=t)`) from that result (research R6); loop flags and controller settings of the dryer's pressure loop in the coupled run record, next to the plant loops; makes T025, T027 pass
- [X] T032 [US2] Tune the pressure loop: extend `scripts/tune_controllers.py` with a step test on the damper position of `examples/plant_recirculation.toml` (first-order plus dead time fit, SIMC with τ_c = τ as in feature 002); put the tuned gain and integral time into both recirculation examples and the contract's example comment; makes T026 pass
- [X] T033 [US2] Example `examples/plant_recirculation.toml`: `examples/plant_reference.toml` plus the `[recirculation]` block sized as in T022 for the coupled operating point, with the tuned controller; `examples/README.md` entry; store its guard results with T002's script only after this feature is complete (it is not part of the "unchanged" set)
- [X] T034 [US2] Make T028 pass: profile the coupled run with recirculation if it exceeds 1.5 ×; acceptable measures: cache the gas path solve per (t, y) evaluation, vectorise the damper PCHIP, warm-start `brentq` bracket from the last root
- [X] T035 [US2] Measured data comparison in `src/boidrytwin/validation/compare.py`: accept `mixing_chamber_pressure` (pressure), `recirculation_damper_position` (fraction) and `recirculation_mass_flow` (mass flow) per the results contract; extend `tests/unit/validation/` with one comparison on a synthetic series

**Checkpoint**: US1 + US2 complete; T004 still green. Report to the user and ask before US3.

---

## Phase 5: User Story 3 — Web app (P2)

**Goal**: see the recirculation in the drawings and plots, add and edit it on the scenario page, release it for operators.

**Independent Test**: a run of `plant_recirculation` shows mixing chamber, fan, return line with damper and values in both drawings, in German and English; `plant_reference` shows none; "Add recirculation" makes a valid scenario; a wrong `max_share` is reported at that field.

### Tests first

- [X] T036 [P] [US3] Process state test in `tests/unit/webapp/test_process_state.py` (extend): for a recirculation run `DryerView.recirculation` holds damper position (%), share (%), recirculated flow (kg/s), temperature (°C), mixing chamber pressure and set point (Pa), fan speed (% of nominal), fan volume flow (m³/s), stack flow (kg/s), drum inlet humidity (g/kg) and O₂ (%); for a run without it the block is None
- [X] T037 [P] [US3] Drawing tests in `tests/contract/webapp/test_diagrams.py` (extend, FR-013): plant and dryer SVGs of a recirculation run contain the elements with ids `recirc-line`, `recirc-damper`, `mixing-chamber`, `exhaust-fan` and the values (damper position, recirculated flow and temperature, mixing chamber pressure); a `plant_reference` run has none of these ids; the SVG stays well-formed XML
- [X] T038 [P] [US3] i18n tests in `tests/contract/webapp/test_i18n.py` (extend): every new `t()` text has a German entry (the existing parametrised test covers the templates); German drawing of a recirculation run contains "Rückführung", "Mischkammer", "Abgasventilator" and the pressure with decimal comma (e.g. "−200,0 Pa")
- [X] T039 [P] [US3] API test in `tests/contract/webapp/test_recirculation_api.py` (FR-014, SC-006): `POST /api/scenarios/{name}/recirculation` as engineer appends the default block to a copy of `plant_reference` and the scenario then validates without issues; 409 when the scenario already has `[recirculation]`; 422 for a boiler-house-only scenario; 403 in the operator view; cross-origin refused (existing rules); the scenario form then shows the recirculation fields; setting `recirculation.max_share` to "120 %" returns the issue at that field (acceptance US3-3); `recirculation.controller.setpoint` can be released for operators and a what-if run with −250 Pa is accepted inside the released range
- [X] T040 [P] [US3] Formula and plot tests: `tests/contract/webapp/test_formulas.py` (extend, FR-015) lists the mixing, damper, fan law, resistance and mixing chamber pressure formulas with a source each; `tests/unit/webapp/test_plot_data.py` (extend) has a "Recirculation and draft" group only for recirculation runs

### Implementation

- [X] T041 [US3] View state in `src/boidrytwin/webapp/process_state.py`: the optional `recirculation` block of data-model.md §7 from the result columns; makes T036 pass
- [X] T042 [US3] Drawings in `src/boidrytwin/webapp/templates/diagrams/_macros.svg` (new macros `fan` and `damper` symbol), `plant.svg` and `dryer.svg`: mixing chamber in front of the drum, exhaust fan behind the drum outlet, return line from the fan's pressure side to the mixing chamber with the damper (position as opening angle and %), value tags for recirculated flow and temperature, mixing chamber pressure with set point, stack flow; viridis colours by gas temperature as the other lines; all texts through `t()`, values through `num()`; drawn only when `s.dryer.recirculation` is set; check German label lengths for overlaps with an Edge screenshot (`scratchpad/shots2.py`); makes T037 pass
- [X] T043 [US3] German texts in `src/boidrytwin/webapp/i18n.py` for all new drawing, plot and button texts ("Recirculation" → "Rückführung", "Mixing chamber" → "Mischkammer", "Exhaust fan" → "Abgasventilator", "Recirculation damper" → "Rückführklappe", "Stack" → "Kamin", "Add recirculation" → "Rückführung hinzufügen", …); makes T038 pass
- [X] T044 [US3] Add-recirculation action: default block `src/boidrytwin/webapp/recirculation_block.toml` (the contract's block with the tuned example values); route `POST /api/scenarios/{name}/recirculation` in `src/boidrytwin/webapp/routes/scenarios.py` (engineer only, entry in `src/boidrytwin/webapp/permissions.py`), appending the block text to the scenario file and validating with the loader; button "Add recirculation" in `src/boidrytwin/webapp/templates/scenario.html` shown when the scenario has a dryer and no `[recirculation]`; include the block file in the PyInstaller spec data files; makes T039 pass
- [X] T045 [US3] Plots in `src/boidrytwin/webapp/plot_data.py` ("Recirculation and draft": mixing chamber pressure with set point, damper position, share, recirculated and stack flow, drum inlet humidity and O₂) and formulas in `src/boidrytwin/webapp/formulas.py` (LaTeX for mixing R4, damper, fan laws, resistance and p_mc R2, with Carolus 2013, Bleier 1998, Idelchik 2007, ASHRAE 2020 and Baehr & Kabelac as sources); makes T040 pass

**Checkpoint**: all stories complete. Report to the user.

---

## Phase 6: Polish & Cross-Cutting

- [X] T046 [P] Documentation: model section "Exhaust recirculation and draft" in `docs/` (assumptions, valid range, accuracy, scenario keys, results; constitution III), the web app page in `docs/webapp.md`, and `examples/README.md`
- [X] T047 [P] Spec bookkeeping: tick the acceptance scenarios against their tests in `specs/004-dryer-exhaust-recirculation/quickstart.md` notes; record deviations (if any) in `plan.md` Complexity Tracking
- [ ] T048 Quality gates: `uv run pytest -q` (all), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`; T004 green
- [ ] T049 Rebuild the exe with `scripts\build_exe.ps1` and smoke-test it: home page, a `plant_recirculation` run with both drawings in German and English, the add-recirculation button
- [ ] T050 Run the quickstart sections 1–5 by hand and note the results in the final report

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T009)** → **US1 (T010–T023)** → **US2 (T024–T035)** → **US3 (T036–T045)** → **Polish (T046–T050)**.
- T002 must run before any model change (it records today's results).
- US2 needs US1 (the loop lives in the dryer). US3 needs result columns from US1 and the plant example from US2 (T033); the drawing and API parts (T037, T039, T042, T044) can start after US1 using `dryer_recirculation`.
- Within each phase: tests [P] first, seen failing, then implementation in the listed order (same files are sequential: T017 → T018 → T019 all touch `dryer/model.py`).

## Parallel Examples

- Foundational tests: T003, T004, T005 together.
- US1 tests: T010, T011, T012, T013, T014, T015 together; then T016 → T017 → T018 → T019 → T020, with T021 and T022 in parallel after T017.
- US2 tests: T024–T029 together; T032 and T035 in parallel after T031.
- US3 tests: T036–T040 together; T041 → T042, while T043, T044 and T045 run in parallel.

## Implementation Strategy

- **MVP = US1**: dryer-only recirculation with pressure control, results and balances; usable from the CLI.
- Then US2 (coupled plant, tuning, benchmark), then US3 (web app). Commit after each task group, report and ask before each user story (project rule).
