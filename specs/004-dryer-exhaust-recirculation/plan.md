# Implementation Plan: Dryer Exhaust Gas Recirculation

**Branch**: `004-dryer-exhaust-recirculation` | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-dryer-exhaust-recirculation/spec.md`

## Summary

A recirculation damper returns exhaust from the pressure side of the exhaust fan into the
mixing chamber in front of the drum and holds the mixing chamber pressure on its set point.
The design ([research.md](research.md)):

- the whole recirculation loop (mixing chamber, return duct, damper, exhaust fan, gas path
  resistances, pressure transmitter and PI controller) belongs to the **dryer subsystem**, so it
  works in dryer-only and coupled runs and the boiler house coupling is unchanged (R1);
- the gas path is **quasi-steady**: per evaluation one monotonic equation in the recirculated
  flow, solved by `brentq`, gives drum gas flow, mixing chamber pressure and fan operating
  point (R2), from a quadratic fan curve with fan laws, quadratic resistances and a damper
  table (R3);
- the returned gas (last cell's humidity and enthalpy) is mixed with the fresh gas on a dry gas
  basis; two extra states (pressure measurement, controller integral) (R4, R5);
- coupled steady state gets a joint whole-plant polish when a recirculation is present (R6);
- balances over the dryer boundary including the loop, plus a loop check (R7);
- new result columns only with a recirculation; runs without it stay byte-identical (R8);
- scenario section `[recirculation]`, two examples, "Add recirculation" in the web app,
  drawings, plots, formulas, German texts (R9).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: unchanged (numpy, scipy, pint, pydantic, pandas, structlog;
FastAPI, Jinja2 for the web app). `scipy.optimize.brentq` and
`scipy.interpolate.PchipInterpolator` are already available. No new dependency.

**Storage**: files only (TOML scenarios, CSV results, JSON run records)

**Testing**: pytest: unit (gas path, mixing, controller wiring), contract (scenario section,
result columns, web API), integration (runs, edge cases, unchanged runs), validation (hand mix,
pressure loop steps), benchmark

**Target Platform**: Windows 11 and Linux workstations; offline; the PyInstaller exe

**Project Type**: Python library with the `boidrytwin` CLI and the local web app

**Performance Goals**: coupled run with recirculation ≤ 1.5 × the same run without (SC-005);
dryer-only 24 h well under the feature-001 budget

**Constraints**: runs without `[recirculation]` byte-identical (SC-001); exact balances; smooth
right-hand side for BDF; subsystems only coupled through interfaces

**Scale/Scope**: +2 states per dryer (162 for the reference), 1 new controller, ~15 result
columns, 1 scenario section, 2 examples

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.1.0.

| Principle / rule | Pre-research | Post-design | How the design complies |
|---|---|---|---|
| I. Tests first, seen failing | ✅ | ✅ | `/speckit-tasks` orders tests before code; FR → test table below |
| I. Reference values with tolerances | ✅ | ✅ | hand mix case (SC-002: 0.5 K / 1 % / 1 %), gas path hand solve (fan + resistances, 1 Pa), pressure loop step criteria |
| I. Contract tests for interfaces | ✅ | ✅ | scenario section, result columns, `POST /api/scenarios/{name}/recirculation`, unchanged `FlueGasSupply` coupling |
| II. Boundary validation, units | ✅ | ✅ | `[recirculation]` through the loader with physical/validated ranges, units via pint; Pa relative to ambient stated in names and docs |
| II. Missing data explicit | ✅ | ✅ | fan speed and set point series use the existing gap/quality rules |
| II. Reproducible runs | ✅ | ✅ | new section stored in the normalised scenario of the run record; deterministic solver |
| III. Assumptions, valid range, accuracy | ✅ | ✅ | `dryer/gas_path.py` docstring and `docs/` page: quasi-steady, quadratic characteristics, single dry composition; range warnings for fan curve, speed, share |
| III. Automated validation | ✅ | ✅ | hand mix and gas path cases in `tests/validation` |
| III. Separate subsystems, typed interfaces | ✅ | ✅ | loop inside the dryer (R1); boiler house ↔ dryer interface unchanged; import boundary test unchanged |
| III. Balances across interfaces and plant | ✅ | ✅ | dryer boundary includes the loop; extra loop check; plant check unchanged (R7) |
| IV. Structured logging, summaries | ✅ | ✅ | run summary logs share, pressure deviation, backflow/overpressure periods; no `print` |
| Stack: ruff, mypy strict, uv | ✅ | ✅ | unchanged |
| New dependencies justified | ✅ | ✅ | none |

### FR → test map

| FR | Test(s) |
|---|---|
| FR-001, FR-010 | `tests/contract/test_scenario_recirculation.py` |
| FR-002, FR-003 | `tests/unit/dryer/test_recirculation_mix.py`, `tests/validation/test_recirculation_hand_mix.py` |
| FR-004, FR-006 | `tests/contract/test_results_recirculation.py` |
| FR-005, FR-018 | `tests/integration/test_recirculation_off.py` |
| FR-007, FR-008, FR-009 | `tests/unit/dryer/test_pressure_loop.py`, `tests/validation/test_pressure_loop_steps.py` |
| FR-011 | `tests/integration/test_recirculation_edge_cases.py` |
| FR-012 | `tests/integration/test_recirculation_balances.py` |
| FR-013 | `tests/contract/webapp/test_diagrams.py` (extended), `test_i18n.py` (extended) |
| FR-014 | `tests/contract/webapp/test_recirculation_api.py` |
| FR-015 | `tests/contract/webapp/test_formulas.py` (extended) |
| FR-016, FR-017 | `tests/unit/dryer/test_gas_path.py` |

## Project Structure

### Documentation (this feature)

```text
specs/004-dryer-exhaust-recirculation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── scenario-file-recirculation.md
│   └── results-recirculation.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/boidrytwin/
├── dryer/
│   ├── gas_path.py          # NEW: fan, resistances, damper, quasi-steady solve (R2, R3)
│   ├── recirculation.py     # NEW: loop states, controller wiring, flags/warnings (R5)
│   ├── model.py             # inlet(t, y), mixing, extra states, size, sparsity, results (R4, R8)
│   └── simulate.py          # size instead of n*8, loop flags, loop balance
├── scenario/
│   ├── schema.py            # RecirculationSpec and parts
│   └── loader.py            # [recirculation] section, rules, signals
├── plant/
│   ├── model.py             # dryer size, sparsity with recirculation
│   └── simulate.py          # joint steady-state polish (R6), loop flags
├── checks/balances.py       # dryer boundary incl. loop, loop check (R7)
├── records.py               # RESULT_UNITS for new columns
├── validation/compare.py    # new comparable columns
└── webapp/
    ├── process_state.py     # recirculation view block
    ├── templates/diagrams/plant.svg, dryer.svg, _macros.svg   # mixing chamber, fan, damper, return line
    ├── templates/scenario.html            # "Add recirculation" button
    ├── routes/scenarios.py                # POST /api/scenarios/{name}/recirculation
    ├── recirculation_block.toml           # NEW: default block to append
    ├── plot_data.py         # "Recirculation and draft" group
    ├── formulas.py          # new formulas with sources
    └── i18n.py              # German texts

examples/dryer_recirculation.toml, examples/plant_recirculation.toml   # NEW
scripts/tune_controllers.py                                            # + pressure loop
docs/                                                                   # model page section

tests/
├── unit/dryer/test_gas_path.py, test_recirculation_mix.py, test_pressure_loop.py
├── contract/test_scenario_recirculation.py, test_results_recirculation.py
├── contract/webapp/test_recirculation_api.py (+ diagrams, i18n, formulas extended)
├── integration/test_recirculation_off.py, test_recirculation_balances.py,
│   test_recirculation_edge_cases.py, test_recirculation_run.py
├── validation/recirculation_case.md, test_recirculation_hand_mix.py, test_pressure_loop_steps.py
└── performance/test_plant_benchmark.py (+ recirculation case)
```

**Structure Decision**: the existing single-package layout; the feature adds two modules to
`dryer/` and extends the existing loader, plant, checks and web app modules.

## Implementation order (for /speckit-tasks)

1. Foundational: schema + loader section (contract tests first), `GasPath` with unit tests,
   dryer `size` refactor with the "unchanged results" test as a guard.
2. US1: mixing in `inlet(t, y)`, loop states, results, balances, dryer-only example.
3. US2: plant integration (sparsity, joint steady state, flags), tuning, plant example,
   step validation, benchmark.
4. US3: web app (view state, drawings, add-block API, plots, formulas, i18n), exe smoke test.

## Complexity Tracking

No constitution violations.
