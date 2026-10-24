---

description: "Task list for feature 001: flue gas interface and dynamic rotary drum dryer model"
---

# Tasks: Boiler House to Dryer Interface and Standalone Dryer Model

**Input**: Design documents from `specs/001-boiler-dryer-interface/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: REQUIRED. Constitution principle I (Test-First, non-negotiable): every test task
MUST be written and observed failing before its implementation task is started.

**Organization**: Tasks are grouped by user story so that each story can be implemented and
tested on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: User story the task belongs to (US1–US4)
- ⚠ **VERIFY**: The task uses a correlation whose coefficients were not checked against the
  original source ([research.md Open item 1](research.md#open-items)). Implement it with the
  coefficient values as named, configurable defaults, cite the source in the docstring, and
  add a `# VERIFY(source)` comment. The defaults are confirmed in T078.

## Path Conventions

Single project: `src/boidrytwin/`, `tests/` and `examples/` at the repository root (see
[plan.md § Project Structure](plan.md#project-structure)).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling

- [X] T001 Create the uv project in `pyproject.toml`:
  - package `boidrytwin`, `src/` layout, `requires-python = ">=3.12"`;
  - runtime dependencies `numpy>=2`, `scipy>=1.18`, `pint>=0.26`, `pydantic>=2.14`, `pandas>=3.1`, `structlog>=26.1`;
  - dev dependency group `pytest`, `hypothesis`, `ruff`, `mypy`, `pandas-stubs`, `cantera>=3.2`, `CoolProp>=8.0`;
  - console script `boidrytwin = "boidrytwin.cli:main"`;
  - run `uv lock` to create `uv.lock`.
- [X] T002 Create the package and test skeleton from plan.md: empty modules with module docstrings under `src/boidrytwin/` (`interface/`, `properties/`, `dryer/`, `scenario/`, `checks/`, `validation/`) and test folders `tests/unit/`, `tests/contract/`, `tests/integration/`, `tests/validation/`, `tests/performance/`, `tests/data/`, plus `examples/` and `docs/`.
- [X] T003 [P] Configure ruff in `pyproject.toml`:
  - line length 100;
  - rule sets `E,F,I,B,UP,N,SIM,T20,PTH,RUF`, with T20 (no `print`) enforced for `src/` only;
  - format settings.
- [X] T004 [P] Configure mypy in `pyproject.toml`: `strict = true` for `src/boidrytwin`, pydantic plugin, `ignore_missing_imports` only for `cantera` and `CoolProp`.
- [X] T005 [P] Configure pytest in `pyproject.toml`: `testpaths = ["tests"]`, markers `benchmark` (excluded by default via `-m "not benchmark"`) and `oracle` (tests needing cantera/CoolProp), `--strict-markers`.
- [X] T006 [P] Add `.gitignore` entries for `.venv/`, `runs/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`.
- [X] T007 [P] Add a CI workflow in `.github/workflows/ci.yml`:
  - on Windows and Ubuntu with Python 3.12: `uv sync --all-groups`, `ruff check`, `ruff format --check`, `mypy src`, `pytest`;
  - a separate job for `pytest -m benchmark`.

**Checkpoint**: `uv sync --all-groups && uv run pytest` runs (no tests yet) and ruff/mypy pass on the skeleton.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Units, errors, logging and physical properties used by every user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (write first, must fail)

- [X] T008 [P] Write unit tests for unit parsing in `tests/unit/test_units.py`:
  - `"450 degC"` → 723.15 K;
  - `"12.5 t/h"` → 3.4722 kg/s;
  - `"101.0 kPa"` → 101000 Pa;
  - `"70.5 %"` → 0.705;
  - `"2 deg"` → 0.034907 rad;
  - `"4 rpm"` → 0.41888 rad/s;
  - `"16 mm"` → 0.016 m;
  - rejection of a value without a unit (`"unit missing"`) and of an incompatible unit such as `"5 kg"` for a temperature (`"incompatible unit"`);
  - gauge pressure with `pressure_reference`.
- [X] T009 [P] Write unit tests for the issue/error types in `tests/unit/test_errors.py`:
  - a `ValidationIssue` carries `field`, `value`, `reason`, `allowed`, `location`;
  - `ScenarioValidationError` and `InterfaceValidationError` collect several issues and render them as text and as JSON.
- [X] T010 [P] Write unit tests for logging in `tests/unit/test_logging.py`:
  - JSON output contains `timestamp` (UTC ISO 8601), `level`, `event`, `component` and bound `run_id`;
  - console renderer selectable;
  - level settable through argument and `BOIDRYTWIN_LOG_LEVEL`.
- [X] T011 [P] Write unit tests for water properties in `tests/unit/properties/test_water.py`:
  - IAPWS-IF97 region 4 saturation pressure at 273.16 K = 611.657 Pa and at 373.15 K = 101418 Pa (±0.01 %);
  - inverse saturation temperature round-trips to < 1e-6 K over 273.15–623.15 K;
  - latent heat at 373.15 K within 0.5 % of 2256.5 kJ/kg;
  - humidity/partial pressure conversion with a CO₂-rich dry-gas molar mass (not the 0.622 air constant);
  - dew point;
  - an `oracle`-marked test comparing p_sat against CoolProp within 0.01 % on a 1 K grid.
- [X] T012 [P] Write unit tests for gas properties in `tests/unit/properties/test_gas.py`:
  - NASA-7 cp, h and s of N₂, O₂, CO₂, H₂O and Ar at 300, 1000 (both ranges must agree to 1e-6) and 1500 K;
  - mixture cp and h of a flue gas composition;
  - `oracle`-marked comparison with Cantera `gri30.yaml` (< 0.1 % on cp and h, 273–1473 K, vectorised over 1000 random compositions);
  - viscosity and conductivity of air at 300 K and 1000 K within 3 % of reference values;
  - Wilke mixture viscosity within 5 % of Cantera mixture-averaged transport.

### Implementation

- [X] T013 Implement `src/boidrytwin/units.py`:
  - a single pint `UnitRegistry` with `degC`, `rpm`, `t/h`, `%` and gauge pressure support;
  - `parse_quantity(text, dimension) -> float` returning SI, raising `ValidationIssue` cases from T008;
  - a `to_si` helper for pandas columns with a unit row.
- [X] T014 [P] Implement `src/boidrytwin/errors.py`: `ValidationIssue` (frozen pydantic model), `ScenarioValidationError`, `InterfaceValidationError`, `SupplyCoverageError`, `SimulationError`.
- [X] T015 [P] Implement `src/boidrytwin/logging.py`: structlog configuration over stdlib logging, JSON and console renderers, `configure_logging(level, fmt)`, contextvars binding for `run_id`.
- [X] T016 [P] Implement `src/boidrytwin/properties/water.py` per [research.md R6](research.md#r6-flue-gas-and-water-properties):
  - IF97 region 4 `p_sat(T)` and `T_sat(p)` (vectorised numpy);
  - `latent_heat(T)`;
  - `humidity_from_partial_pressure` and `partial_pressure_from_humidity(Y, p, M_dry)`;
  - `dew_point(Y, p, M_dry)`;
  - liquid water enthalpy.
- [X] T017 [P] Implement `src/boidrytwin/properties/gas.py` per research.md R6:
  - NASA-7 two-range coefficient table for N₂, O₂, CO₂, H₂O and Ar, copied from GRI-Mech 3.0 (`gri30.yaml`) with the source cited;
  - `cp`, `h` and `s` per species and per mixture, vectorised over cells;
  - molar mass of the mixture and the dry-gas molar mass;
  - Sutherland (N₂, O₂, Ar) and polynomial (CO₂, H₂O) viscosity and conductivity;
  - Wilke mixing rule.
  - ⚠ VERIFY transport coefficients against the VDI Heat Atlas.

**Checkpoint**: All Phase 2 tests pass, including the `oracle` tests.

---

## Phase 3: User Story 1 — Describe the flue gas supply to the dryer (Priority: P1) 🎯 MVP

**Goal**: An engineer can describe the flue gas delivered to the dryer (constant or time series), and the system validates it with units, rejecting invalid input with clear messages.

**Independent Test**: `uv run boidrytwin validate examples/reference_constant.toml` prints `OK` with SI values; `uv run boidrytwin validate examples/invalid_flue_gas.toml` exits with code 1 and lists field, value, reason and allowed range for each issue; `uv run pytest tests/contract -k rejection` passes ([quickstart.md §2](quickstart.md#2-interface-validation-user-story-1-fr-003fr-004-sc-005)).

### Tests for User Story 1 (write first, must fail)

- [X] T018 [P] [US1] Write unit tests for `GasComposition` in `tests/unit/interface/test_composition.py`:
  - "each 0 ≤ x ≤ 1";
  - "the fractions sum to 1 within ±0.005 (reported as an error beyond that) and are then normalised to exactly 1";
  - "dry-basis input needs a separately given `x_H2O` (wet) or humidity, otherwise rejected";
  - `fraction_type = "mass"` converted to mole fractions;
  - `x_other` treated as Ar.
  - Use hypothesis to generate valid and invalid compositions.
- [X] T019 [P] [US1] Write unit tests for `FlueGasState` in `tests/unit/interface/test_flue_gas_state.py`:
  - `mass_flow` "≥ 0";
  - `temperature` "273.15 ≤ T ≤ 1473.15 (0–1200 °C)";
  - `pressure` "50 000 < p < 200 000" Pa absolute;
  - `time` "timezone-aware";
  - `quality` one of `"good" | "interpolated" | "missing" | "bad"`, default `"good"`;
  - derived `heat_content_flow` = ṁ·[h(T) − h(298.15 K)] against a hand calculation;
  - derived `humidity` and `dew_point`.
- [X] T020 [P] [US1] Write unit tests for `ConstantFlueGasSupply` and `TimeSeriesFlueGasSupply` in `tests/unit/interface/test_sources.py`:
  - piecewise-linear interpolation;
  - "a gap longer than `max_gap` (default 300 s) is an error unless `allow_gaps = true`, in which case the gap period is returned with `quality = "missing"`";
  - `covers()`;
  - `SupplyCoverageError` outside the covered period;
  - `state_at` is deterministic.
- [X] T021 [P] [US1] Write unit tests for the time series CSV reader in `tests/unit/scenario/test_timeseries.py`, per [contracts/scenario-file.md](contracts/scenario-file.md#time-series-csv):
  - "the second row holds the units; every column except `time` and `quality` needs one";
  - "`time` is ISO 8601 with a timezone (`Z` or offset); converted to UTC";
  - "timestamps are strictly increasing";
  - "`quality` is optional (`good` | `missing` | `bad`), default `good`; empty cells are `missing`";
  - error locations include the row number;
  - values unchanged for longer than `stale_after` (default 15 min) in flow and temperature columns are marked `stale`.
- [X] T022 [P] [US1] Write contract tests in `tests/contract/test_flue_gas_supply.py`:
  - the shared `FlueGasSupply` contract suite (the 5 guarantees in [contracts/flue-gas-interface.md](contracts/flue-gas-interface.md#guarantees-of-every-implementation)), parametrised over both implementations;
  - the complete rejection catalogue (11 cases, `test_rejection_*`), each asserting the reason text listed in the contract.
- [X] T023 [P] [US1] Write contract tests for scenario-file validation (time, flue_gas and dilution_air sections) in `tests/contract/test_scenario_file.py`:
  - unknown keys are errors;
  - all issues collected and reported together with file and line;
  - the example values from the contract load and normalise to SI.
- [X] T024 [P] [US1] Write a CLI contract test for `validate` in `tests/contract/test_cli_validate.py`: exit code 0/1, `OK` output, `--json` output schema `{ "valid": bool, "issues": [ {field, value, reason, allowed, location} ] }`.

### Implementation for User Story 1

- [X] T025 [P] [US1] Implement `GasComposition` in `src/boidrytwin/interface/composition.py` (frozen pydantic model, rules from T018, wet-basis normalisation, mass→mole conversion).
- [X] T026 [US1] Implement `FlueGasState`, the `FlueGasSupply` protocol and the derived quantities in `src/boidrytwin/interface/flue_gas.py`. Depends on T016, T017 and T025.
- [X] T027 [US1] Implement `src/boidrytwin/scenario/timeseries.py`: read CSV with a unit row into a pandas UTC `DatetimeIndex` frame in SI, quality column handling, monotonicity, gap detection and stale detection.
- [X] T028 [US1] Implement `ConstantFlueGasSupply` and `TimeSeriesFlueGasSupply` in `src/boidrytwin/interface/sources.py`. Depends on T026 and T027. `source_id` = `"constant"` or `"timeseries:<file sha256 prefix>"`.
- [X] T029 [US1] Implement pydantic scenario models for `schema_version`, `name`, `[time]`, `[flue_gas]` and `[dilution_air]` in `src/boidrytwin/scenario/schema.py`:
  - `extra = "forbid"`;
  - `[flue_gas]` includes `composition_basis`, `composition_type` (`"mole"` | `"mass"`, default `"mole"`) and `stale_after` (default `"15 min"`);
  - values as `"<number> <unit>"` strings parsed through `units.py`;
  - `output_interval` rule "1 s–1 h; default 60 s";
  - "end > start; inputs must cover [start, end]";
  - dilution air `mass_flow` "≥ 0; default 0".
- [X] T030 [US1] Implement `load_scenario(path)` in `src/boidrytwin/scenario/loader.py`: TOML via `tomllib`, collect all issues with file/line location, resolve time series paths relative to the scenario file, build the flue gas supply.
- [X] T031 [US1] Implement the `validate` subcommand and the `main` entry point in `src/boidrytwin/cli.py`: `--json`, `--log-level`, `--log-format`; exit codes per [contracts/cli.md](contracts/cli.md).
- [X] T032 [P] [US1] Create the example scenarios `examples/reference_constant.toml` (contract example values; the dryer sections are added in T053), `examples/invalid_flue_gas.toml` (missing unit, composition sum 93 %, negative flow) and `tests/data/flue_gas_valid.csv`, `tests/data/flue_gas_gap.csv`, `tests/data/flue_gas_unordered.csv`.
- [X] T033 [US1] Add structured logging of validation outcomes to `src/boidrytwin/scenario/loader.py`: event `scenario_validated` with issue counts and source id.

**Checkpoint**: User Story 1 works on its own; `validate` covers the flue gas interface.

---

## Phase 4: User Story 2 — Simulate the drum dryer over time (Priority: P1)

**Goal**: An engineer runs the dynamic drum dryer model from a scenario and gets time series of product, exhaust gas, heat use and specific energy, reproducibly.

**Independent Test**: `uv run boidrytwin run examples/reference_constant.toml --out runs --profiles` creates the run folder. From `cold_empty`, the outputs settle to a steady state matching the hand-calculated reference case within tolerance. The step-response and heat-limited scenarios behave as in [quickstart.md §3–4](quickstart.md#3-standalone-dynamic-run-user-story-2-fr-007--fr-011).

### Tests for User Story 2 (write first, must fail)

- [X] T034 [P] [US2] Write unit tests for wood properties in `tests/unit/properties/test_wood.py`:
  - Wood Handbook (2021) Eq. 4-5 EMC at 20 °C/65 % RH ≈ 12 % and at 80 °C/30 % RH against the handbook table;
  - EMC clipped above the 403.15 K data limit with an `extrapolated` flag;
  - dry wood cp Eq. 4-18a `c_p0 = 0.1031 + 0.003867·T`;
  - moist wood cp Eq. 4-19/4-20 below fibre saturation and the rule of mixtures above it;
  - sorption heat → 0 at fibre saturation;
  - wet/dry basis conversion X = w/(1 − w).
- [X] T035 [P] [US2] Write unit tests for `DryerConfiguration` in `tests/unit/dryer/test_config.py`:
  - every field has a `physical_range` (outside → rejected) and a `validated_range` (outside → accepted, reported as RangeWarning);
  - `n_cells` "10–40, default 20";
  - `gas_flow_direction` only `"co-current"`;
  - defaults `fibre_saturation_moisture` 0.30, `shell_emissivity` 0.8, `shell_specific_heat` 500 J/kg·K, `min_dew_point_margin` 10 K, EMC data limit 403.15 K.
- [X] T036 [P] [US2] Write unit tests for `DryerState` packing in `tests/unit/dryer/test_state.py`:
  - 8 values per cell in the order of data-model.md §3;
  - round-trip pack/unpack;
  - invariants "all masses ≥ 0; temperatures > 0 K; humidity ≥ 0";
  - JSON save/load.
- [X] T037 [P] [US2] Write unit tests for solids transport in `tests/unit/dryer/test_transport.py`:
  - total dry mass conserved between phases and cells;
  - water carried in proportion to dry mass;
  - zero feed gives zero flows into an empty drum;
  - drag flow increases with gas velocity and decreasing particle mass;
  - at steady state the mean residence time lies within the Friedman–Marshall/Saeman–Mitchell plausibility band for the reference geometry.
- [X] T038 [P] [US2] Write unit tests for heat transfer in `tests/unit/dryer/test_heat_transfer.py`:
  - Gnielinski Nu → 2 as Re → 0;
  - Ranz–Marshall agrees with Gnielinski within 20 % for 10 < Re < 1000;
  - `Q_gs` = 0 when T_g = T_s;
  - `C_a` scales linearly;
  - Chilton–Colburn k_y consistent with h_p;
  - Churchill–Chu Nu at Ra = 1e9 against the published value;
  - shell loss sign and radiation term;
  - volumetric Ua at the reference case lies within the Friedman–Marshall/McCormick/Myklestad plausibility band.
- [X] T039 [P] [US2] Write unit tests for drying kinetics in `tests/unit/dryer/test_drying.py`:
  - constant-rate evaporation ∝ (Y_s* − Y_g);
  - falling rate `f(Φ) = Φ^n` with `Φ = (X − X_e)/(X_cr − X_e)`;
  - continuity at X = X_cr;
  - rate = 0 at X = X_e;
  - no condensation onto solids when Y_g > Y_s* (rate clipped at 0 and flagged).
- [X] T040 [P] [US2] Write unit tests for the right-hand side in `tests/unit/dryer/test_model.py`:
  - dilution air mixing (mass and enthalpy of the mixed drum inlet gas);
  - with all transfer coefficients set to 0, the gas passes unchanged and the solids are only transported;
  - the RHS is vectorised: it returns the right shape for 10 and 40 cells (the timing assertion was dropped as flaky, analysis finding Q1; speed is covered by T048);
  - the Jacobian sparsity pattern covers all non-zero entries found by finite differences.
- [X] T041 [P] [US2] Write integration test `tests/integration/test_run_scenario.py` for `examples/reference_constant.toml`:
  - the run produces all `DryerResults` columns of data-model.md §4 at a 60 s interval;
  - `run_record.json`, `results.csv` (unit row), `profiles.csv` and `final_state.json` exist.
- [X] T042 [P] [US2] Write validation test `tests/validation/test_settles_to_steady_state.py` (FR-010): from `cold_empty` with constant inputs, all outputs settle (relative change < 1e-4 per hour), and the steady state equals the `steady_state` initial-state solution within 0.1 %.
- [X] T043 [P] [US2] Write validation test `tests/validation/test_step_response.py` (FR-009, SC-004):
  - steps in feed rate, feed moisture and flue gas temperature at t = 6 h;
  - outputs change gradually (no jump larger than 5 % of the total change within the first output step);
  - they settle to the new steady state;
  - settling time within a plausibility band: longer than the mean solids residence time and shorter than mean residence time + 5 × shell time constant (both computed by the model).
  - The quantitative SC-004 check (±20 % of a published or measured response) is part of T079.
- [X] T044 [P] [US2] Write integration test `tests/integration/test_heat_limited.py` (FR-011): with flue gas flow reduced until the heat demand exceeds supply, the `heat_limited` flag is set for the period, product moisture is higher than in the reference case, and energy is not created.
- [X] T045 [P] [US2] Write integration tests for the edge cases of spec.md in `tests/integration/test_edge_cases.py`:
  - flue gas temperature ≤ product temperature → zero drying;
  - flue gas flow drops to zero → the shell cools with inertia and the run continues;
  - zero feed → no evaporation;
  - feed already below target moisture → little or no evaporation;
  - exhaust near dew point → `condensation_risk` flag.
- [X] T046 [P] [US2] Write integration test `tests/integration/test_determinism.py` (FR-014, SC-006): two runs of the same scenario give bit-identical `results.csv`.
- [X] T047 [P] [US2] Write contract test `test_swap_sources` in `tests/contract/test_flue_gas_supply.py` (FR-005, SC-008): `reference_constant.toml` and `reference_timeseries.toml` (same constant values) give identical results with an unchanged dryer configuration.
- [X] T048 [P] [US2] Write benchmark `tests/performance/test_benchmark.py` (marker `benchmark`, SC-007): 24 h at 1-minute output with 20 cells completes in < 60 s wall clock; also assert a single steady operating point in < 5 s.
- [X] T049 [US2] Write the hand-calculated reference case in `tests/validation/reference_case.md` and its test in `tests/validation/test_reference_steady_state.py`:
  - inputs: 10 t/h wet chips from 50 % to 15 % wet basis, the flue gas of the contract example, dilution air 2 kg/s;
  - a documented mass and energy balance by hand (evaporation, exhaust temperature and humidity, specific energy);
  - the hand calculation fixes the product outlet moisture at the model's steady-state value and derives evaporation, exhaust temperature, exhaust humidity and specific energy from the mass and energy balance (including the model's shell loss);
  - assert the model matches within: evaporation ±0.5 %, exhaust temperature ±2 K, exhaust humidity ±1 %, specific energy ±2 %.
  - Independent prediction of outlet moisture is tested in T079.

### Implementation for User Story 2

- [X] T050 [P] [US2] Implement `src/boidrytwin/properties/wood.py` per [research.md R4](research.md#r4-drying-kinetics-and-wood-chip-properties): Hailwood–Horrobin EMC (Wood Handbook 2021 Eq. 4-5 coefficients) with clipping flag, cp Eq. 4-18a/4-19/4-20, sorption heat from Clausius–Clapeyron on the same isotherm, basis conversion.
- [X] T051 [P] [US2] Implement `DryerConfiguration` with all groups, each field with `physical_range` and `validated_range` from data-model.md §2, in `src/boidrytwin/dryer/config.py`, each calibration parameter documented with its source and default.
- [X] T052 [P] [US2] Implement `DryerState` packing, invariants and JSON I/O in `src/boidrytwin/dryer/state.py`.
- [X] T053 [US2] Extend `src/boidrytwin/scenario/schema.py` and `loader.py` with `[product_feed]`, `[ambient]`, `[dryer.*]`, `[initial_state]` and `[balance_tolerances]`:
  - `ProductFeed`: `mass_flow_wet` "≥ 0", `moisture_wet_basis` "0 ≤ w < 0.75", `temperature` "253.15–333.15 (−20 to 60 °C)";
  - `AmbientConditions`: `temperature` "233.15–323.15", `relative_humidity` "0–1", `pressure` "80 000–110 000";
  - `InitialState` `kind` one of `cold_empty | steady_state | explicit`;
  - product key `critical_moisture_dry_basis` (kg water / kg dry wood);
  - each value constant or a time series column.
  - Complete `examples/reference_constant.toml` with the dryer sections of the contract example.
- [X] T054 [US2] Implement two-phase solids transport per [research.md R2](research.md#r2-solids-transport-residence-time-and-hold-up) in `src/boidrytwin/dryer/transport.py`:
  - `k2` (flight unloading, Baker 1988/Ajayi & Sheehan 2012 design load);
  - `k3 ≈ 1/t_fall`;
  - kilning `k4`;
  - curtain drag `C_F·m_a·f(u_g, ρ_g, particle mass)` (Baker 1992);
  - vectorised over cells.
  - ⚠ VERIFY flight-loading and drag coefficients.
- [X] T055 [US2] Implement heat transfer per [research.md R3 and R5](research.md#r3-gassolid-heat-and-mass-transfer) in `src/boidrytwin/dryer/heat_transfer.py`:
  - Gnielinski and Ranz–Marshall single-particle Nu;
  - `a_eff = (6/d_p)·m_a/ρ_p` plus a bed-surface term;
  - Chilton–Colburn k_y;
  - gas→shell convection;
  - shell↔solids contact `h_ws`;
  - Churchill–Chu external convection;
  - shell radiation;
  - Friedman–Marshall/McCormick/Myklestad Ua functions for plausibility checks only.
  - ⚠ VERIFY the Ua correlation coefficients.
- [X] T056 [US2] Implement the characteristic drying curve per research.md R4 in `src/boidrytwin/dryer/drying.py`: constant-rate and falling-rate periods, X_e from `wood.py`, bound-water latent heat, condensation guard and flag.
- [X] T057 [US2] Implement the vectorised right-hand side in `src/boidrytwin/dryer/model.py`:
  - dilution air mixing at the drum inlet;
  - per-cell mass balances for dry solids (both phases), water in solids (both phases), gas humidity and dry gas;
  - energy balances for solids, gas and shell, in flux form so they are conservative by construction;
  - the banded `jac_sparsity` pattern.
  - Depends on T050–T056.
- [X] T058 [US2] Implement the simulator in `src/boidrytwin/dryer/simulate.py`:
  - `solve_ivp` method BDF (Radau fallback) with fixed `rtol`/`atol` from `TimeSettings`;
  - `t_eval` at the output interval;
  - `max_step` ≤ boundary data interval;
  - initial states `cold_empty`, `steady_state` (solve the RHS = 0 with `scipy.optimize.root`, falling back to time-marching) and `explicit`;
  - output sampling to `DryerResults` columns;
  - flags `heat_limited`, `condensation_risk`, `input_quality`;
  - `SimulationError` on solver failure.
- [X] T059 [US2] Implement `RunRecord` in `src/boidrytwin/records.py`:
  - UUID4 `run_id`;
  - model version plus git commit if available;
  - environment versions;
  - normalised scenario plus SHA-256;
  - input file hashes;
  - status transitions `created → validated → running → completed | failed` and `rejected`;
  - solver stats;
  - run folder writer for `run_record.json`, `results.csv` with unit row, `profiles.csv` and `final_state.json`.
- [X] T060 [US2] Implement the `run` subcommand (`--out`, `--profiles`) in `src/boidrytwin/cli.py`, and the library API `run()` in `src/boidrytwin/__init__.py`. Log events `run_started` and `run_completed` with run_id, simulated period, duration and RHS evaluations.
- [X] T061 [P] [US2] Create the example scenarios `examples/reference_timeseries.toml` (with `tests/data/flue_gas_constant.csv`), `examples/step_feed_moisture.toml` and `examples/heat_limited.toml`.
- [X] T062 [US2] Run the benchmark T048 and, if it is over budget, profile and optimise `src/boidrytwin/dryer/model.py`. Record the result in `specs/001-boiler-dryer-interface/research.md` R7 (Performance).

**Checkpoint**: User Stories 1 and 2 both work; the dryer runs standalone with the boundary-condition source.

---

## Phase 5: User Story 3 — Trust the results: balance and range checks (Priority: P2)

**Goal**: Every run reports mass and energy balance residuals with pass/fail and flags periods outside the valid range; recorded runs can be rerun to prove reproducibility.

**Independent Test**: `run_record.json` of the reference run shows all balances `passed: true`. `examples/out_of_range_inlet.toml` produces a `RangeWarning` with limit and period, and exit code 0. `uv run boidrytwin rerun runs/<run_id>/run_record.json` reports `identical: true` ([quickstart.md §5–6](quickstart.md#5-balances-and-range-checks-user-story-3-fr-012fr-013-sc-002)).

### Tests for User Story 3 (write first, must fail)

- [ ] T063 [P] [US3] Write unit tests for `BalanceReport` in `tests/unit/checks/test_balances.py`:
  - for dry solids, water, gas and energy: `residual = in − out − Δstored`;
  - `relative_residual` relative to total inflow;
  - pass/fail against tolerances (default "0.1 % mass, 1 % energy");
  - a deliberately leaky synthetic result fails.
- [ ] T064 [P] [US3] Write unit tests for `RangeWarning` detection in `tests/unit/checks/test_ranges.py`:
  - contiguous out-of-range periods merged;
  - `quantity`, `limit_type` (`min`/`max`), `limit`, `observed_extreme`, `period_start`, `period_end`;
  - drum inlet gas temperature above `max_drum_inlet_gas_temperature`;
  - dew point margin below `min_dew_point_margin`;
  - EMC extrapolation above 403.15 K;
  - configuration and input values outside their `validated_range`.
- [ ] T065 [P] [US3] Write integration test `tests/integration/test_balances_close.py` (SC-002): for the reference, step-response and heat-limited scenarios, the dry solids, water and gas balances close within 0.1 % and energy within 1 %.
- [ ] T066 [P] [US3] Write integration test `tests/integration/test_rerun_identical.py`: `rerun` gives `identical: true`, and fails with exit code 1 when an input file hash has changed.
- [ ] T067 [P] [US3] Write integration test `tests/integration/test_run_record.py` (FR-017): the run record contains `balance_report`, `range_warnings`, `flags_summary`, `solver_stats` and `rejected_inputs` per data-model.md §4. A completed run with failing checks keeps status `completed` and gives CLI exit code 2.

### Implementation for User Story 3

- [ ] T068 [P] [US3] Implement `BalanceReport` in `src/boidrytwin/checks/balances.py`: integrate boundary fluxes over the run (trapezoidal on the dense solver output) and compute storage changes from the initial and final `DryerState`.
- [ ] T069 [P] [US3] Implement `RangeWarning` detection in `src/boidrytwin/checks/ranges.py`, using the valid ranges from `DryerConfiguration`.
- [ ] T070 [US3] Integrate the balance and range checks into `src/boidrytwin/dryer/simulate.py` and `src/boidrytwin/records.py`: `flags_summary`, exit code 2 on failed checks, log event `checks_completed` with residuals and warning counts.
- [ ] T071 [US3] Implement the `rerun` subcommand in `src/boidrytwin/cli.py` and `rerun()` in `src/boidrytwin/records.py`: rebuild from the stored normalised scenario, verify input hashes, compare results bit for bit.
- [ ] T072 [P] [US3] Create `examples/out_of_range_inlet.toml` (drum inlet gas temperature above the valid range for a 2 h period).

**Checkpoint**: User Stories 1–3 work; every run is checked and reproducible.

---

## Phase 6: User Story 4 — Compare the dryer model with plant measurements (Priority: P3)

**Goal**: An engineer compares the model with measured time series and gets per-output deviation statistics and pass/fail, with bad or missing values excluded.

**Independent Test**: `uv run boidrytwin compare examples/reference_timeseries.toml examples/synthetic_measured.csv` writes `validation_report.json`, which reproduces the known deviations of the synthetic dataset and lists the excluded values ([quickstart.md §8](quickstart.md#8-comparison-with-measurements-user-story-4-fr-016-sc-003)).

### Tests for User Story 4 (write first, must fail)

- [ ] T073 [P] [US4] Write unit tests for the comparison in `tests/unit/validation/test_compare.py`:
  - `n_compared`, `n_excluded`, `bias`, `mae`, `rmse`, `max_abs_error` and `fraction_within_tolerance` against hand-computed values;
  - values with quality `missing`/`bad` are "excluded and listed as excluded, not counted as passes or failures";
  - steady-period detection on a synthetic signal;
  - default tolerances "product outlet moisture ±1 percentage point (wet basis), exhaust temperature ±5 K, pass if ≥ 90 % of steady-operation samples are within tolerance".
- [ ] T074 [P] [US4] Write a CLI contract test for `compare` in `tests/contract/test_cli_compare.py`: outputs `validation_report.json` and `comparison.csv`, `--tolerances` file, exit codes 0 and 2.

### Implementation for User Story 4

- [ ] T075 [US4] Implement `MeasuredTimeSeries` loading and `ValidationReport` with steady-period detection in `src/boidrytwin/validation/compare.py`, mapping measured columns to scenario inputs and `DryerResults` outputs by name. Reuse `scenario/timeseries.py`.
- [ ] T076 [US4] Implement the `compare` subcommand in `src/boidrytwin/cli.py` and `compare()` in `src/boidrytwin/__init__.py`.
- [ ] T077 [P] [US4] Create a generator script `scripts/make_synthetic_measured.py` that writes `examples/synthetic_measured.csv`: model output plus known bias and noise (fixed seed), plus some `missing`/`bad` values. Document the expected deviations in `examples/README.md`.

**Checkpoint**: All four user stories work independently.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T078 Verify every ⚠ VERIFY coefficient (T017, T054, T055) against the original publications or Perry's/VDI once the full texts are available ([research.md Open item 1](research.md#open-items)). Update the defaults and source citations, and remove the `VERIFY` comments. **Blocked** until the full texts are provided.
- [ ] T079 [P] Add literature validation cases (SC-003, quantitative SC-004) in `tests/validation/test_literature_cases.py`:
  - Perry's 8th ed. Example 12-23 (steady-state balance and residence time);
  - Kamke & Wilson 1985/1986 (retention time, axial profiles);
  - a qualitative Iguaz 2003 step response.
  - Mark them `skip` with reason "full text needed" until the data is digitised. **Blocked** like T078.
- [ ] T080 [P] Write `docs/model.md`:
  - model equations per cell;
  - state variables;
  - assumptions;
  - valid operating range and expected accuracy (constitution principle III);
  - calibration parameters with defaults and sources;
  - links to research.md.
- [ ] T081 [P] Write `README.md`: purpose, installation with uv, quickstart commands, project structure, link to the constitution and specs.
- [ ] T082 Run all steps of [quickstart.md](quickstart.md) on Windows and record the results (including SC-001 setup time) in `specs/001-boiler-dryer-interface/checklists/quickstart-run.md`.
- [ ] T083 Final quality gate: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest` and `uv run pytest -m benchmark` all pass; fix any findings.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: depends on Setup; blocks all user stories.
- **US1 (Phase 3)**: depends on Foundational.
- **US2 (Phase 4)**: depends on Foundational and on the US1 interface types (T025–T030), because the dryer consumes `FlueGasSupply` and the scenario loader.
- **US3 (Phase 5)**: depends on US2 (it checks simulation results).
- **US4 (Phase 6)**: depends on US2 (it runs the model); independent of US3.
- **Polish (Phase 7)**: after the desired stories; T078 and T079 are blocked on external full texts.

### Story completion order

```text
Setup → Foundational → US1 ──▶ US2 ──┬──▶ US3
                                     └──▶ US4   (US3 and US4 can run in parallel)
```

### Within each story

1. Tests first, observed failing.
2. Data types and properties, then physics modules, then the model and simulator, then records and CLI.
3. Checkpoint validation before the next story.

### Key task dependencies

- T013 → T029, T030 (unit parsing for the scenario)
- T016, T017 → T026 (derived interface quantities) → T028 → T030 → T031
- T050–T056 → T057 → T058 → T059 → T060
- T048 (benchmark test) is written before T057; T062 runs after T058
- T068, T069 → T070; T059 → T071
- T058 → T075 → T076; T060 → T077

---

## Parallel Examples

### Phase 2

```text
Task: "Write unit tests for water properties in tests/unit/properties/test_water.py"   (T011)
Task: "Write unit tests for gas properties in tests/unit/properties/test_gas.py"       (T012)
Task: "Write unit tests for unit parsing in tests/unit/test_units.py"                  (T008)
# then
Task: "Implement src/boidrytwin/properties/water.py"   (T016)
Task: "Implement src/boidrytwin/properties/gas.py"     (T017)
```

### User Story 1

```text
Task: "Write unit tests for GasComposition"            (T018)
Task: "Write unit tests for FlueGasState"              (T019)
Task: "Write unit tests for the supplies"              (T020)
Task: "Write unit tests for the time series reader"    (T021)
Task: "Write contract tests for FlueGasSupply"         (T022)
```

### User Story 2

```text
# all tests T034–T048 are in different files and can be written in parallel
# physics modules in parallel after the tests:
Task: "Implement src/boidrytwin/properties/wood.py"    (T050)
Task: "Implement src/boidrytwin/dryer/config.py"       (T051)
Task: "Implement src/boidrytwin/dryer/state.py"        (T052)
# T054, T055 and T056 are separate files and can also run in parallel once T051 is done
```

### User Stories 3 and 4

```text
# after US2, two developers/agents:
Developer A: T063–T072 (US3)
Developer B: T073–T077 (US4)
```

---

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 Setup and Phase 2 Foundational.
2. Phase 3 (US1): validated flue gas interface and the `validate` command.
3. **Stop and validate**: quickstart §2. This is the contract that every later boiler house and dryer model depends on.

### Incremental delivery

1. US1: interface (MVP).
2. US2: standalone dynamic dryer. This is the first simulation results and the main value; benchmark early.
3. US3: balance and range checks, rerun. This makes the results trustworthy.
4. US4: comparison with measurements, ready for when plant data arrives.
5. Polish: verify coefficients and add literature cases once the full texts are provided.

### Notes

- Commit after each task or logical group (e.g. via `/speckit-git-commit`).
- Do not start an implementation task before its tests exist and fail.
- Keep the `interface` package free of imports from `dryer` (constitution principle III).
