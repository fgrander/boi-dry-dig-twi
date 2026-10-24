# Implementation Plan: Boiler House to Dryer Interface and Standalone Dryer Model

**Branch**: `001-boiler-dryer-interface` | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-boiler-dryer-interface/spec.md`

## Summary

Build (1) a validated, unit-aware **flue gas supply interface** between a boiler house and a
dryer, fed in this feature by a constant or time-series boundary condition, and (2) a
**dynamic model of a directly heated, co-current rotary drum dryer for wood chips**.

The dryer model, chosen from a literature search ([research.md](research.md)), is an axial
**cells-in-series** model (default 20 cells), with per cell:
- a two-phase solids hold-up (in flights / airborne) with Matchett–Baker-type transport and
  co-current gas drag;
- gas–solid heat and mass transfer from single-particle correlations with a calibration
  multiplier;
- a two-period characteristic drying curve with the USDA Wood Handbook sorption isotherm;
- a lumped drum shell node for thermal inertia and heat losses;
- in-house NASA-polynomial flue gas properties and IAPWS-IF97 saturation.

It is integrated with scipy's implicit BDF solver. Inputs are validated at the boundary with
pint and pydantic; every run produces a reproducible run record with mass and energy balance
checks.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: numpy 2.x, scipy ≥ 1.18 (`solve_ivp` BDF), pint ≥ 0.26 (boundary
units), pydantic ≥ 2.14 (schemas), pandas ≥ 3.1 (time series I/O), structlog ≥ 26.1
(logging); stdlib `tomllib` and `argparse`. Dev/test only: pytest, hypothesis, ruff, mypy,
cantera ≥ 3.2 and CoolProp ≥ 8.0 (test oracles). Justified in [research.md R7](research.md#r7-python-numerical-and-software-stack).

**Storage**: Files only — TOML scenarios and CSV time series in; JSON run records, CSV results
and JSON final states out. No database.

**Testing**: pytest with explicit `pytest.approx` tolerances; hypothesis for validation rules;
contract tests for the interface; validation tests for reference cases; a benchmark test.

**Target Platform**: Windows 11 and Linux workstations; offline.

**Project Type**: Python library with a command-line interface (`boidrytwin`).

**Performance Goals**: 24 h of operation at 1-minute output in < 60 s (SC-007); one steady
operating point in < 5 s.

**Constraints**: Deterministic results on a given platform and library versions (SC-006);
balances within 0.1 % mass and 1 % energy (SC-002); no unit-less values at the boundary;
SI-only internally.

**Scale/Scope**: One dryer and one flue gas connection; 10–40 cells × 8 states (≈ 160 ODEs at
default); single-user runs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.1.0.

| Principle / rule | Pre-research | Post-design | How the design complies |
|---|---|---|---|
| I. Tests written first, seen failing | ✅ | ✅ | Task order (from `/speckit-tasks`) puts tests before code for every module; every FR maps to tests (see table below) |
| I. Model code tested against reference values with tolerances | ✅ | ✅ | Property tests against Cantera/CoolProp; steady-state hand calculation; literature cases ([research.md R9](research.md#r9-validation-and-reference-cases)) |
| I. Contract/integration tests for interfaces | ✅ | ✅ | `tests/contract/` for the flue gas interface (incl. swap test) and the scenario/CLI contracts |
| II. Boundary validation against explicit schema | ✅ | ✅ | pydantic models; all issues reported with field, value, reason ([scenario-file.md](contracts/scenario-file.md)) |
| II. Explicit units, SI internally | ✅ | ✅ | pint at the boundary only, `"<number> <unit>"` strings, unit row in CSVs; core uses SI floats |
| II. UTC timestamps | ✅ | ✅ | timezone required in input; converted to UTC |
| II. Missing data explicit | ✅ | ✅ | `quality` flags; gaps are errors unless explicitly allowed, then flagged |
| II. Reproducible runs | ✅ | ✅ | RunRecord with normalised scenario, input hashes, versions, solver settings; `rerun` command |
| II. Raw data immutable, derived data traceable | ✅ | ✅ | inputs are only read; run folders reference input hashes |
| III. Assumptions, valid range, accuracy documented; range violations flagged | ✅ | ✅ | `DryerConfiguration` valid ranges; `RangeWarning` periods; model documentation in module docstrings and `docs/model.md` |
| III. Automated validation against reference/measured data | ✅ | ✅ | `tests/validation/`; `compare` command |
| III. Subsystems separate, coupled only via typed interface | ✅ | ✅ | `FlueGasSupply` protocol; dryer never reads source internals |
| III. Mass and energy balances across interfaces checked | ✅ | ✅ | `BalanceReport` for every run, incl. storage terms |
| IV. Structured logging, no `print` for operations | ✅ | ✅ | structlog JSON; ruff rule T20 (no `print`) enabled in `src/` |
| IV. Metrics for key operations | ✅ | ✅ | solver stats, rejected-input counts, balance residuals, range warnings in run record and logs |
| IV. Errors logged with context, not swallowed | ✅ | ✅ | typed exceptions; run status `failed` with solver message |
| IV. Configurable log levels | ✅ | ✅ | `--log-level` and `BOIDRYTWIN_LOG_LEVEL` |
| Stack: Python 3.12+, uv, pytest, ruff, type checker | ✅ | ✅ | `pyproject.toml` with `uv.lock`; mypy strict on `src/` |
| New dependencies justified | ✅ | ✅ | [research.md R6–R7](research.md#r6-flue-gas-and-water-properties) |
| No secrets in repo | ✅ | ✅ | no credentials needed |

**Result**: PASS — no violations; Complexity Tracking not required.

### Requirement → test mapping

| Requirement | Test location |
|---|---|
| FR-001 – FR-004, SC-005 | `tests/unit/interface/`, `tests/contract/test_flue_gas_supply.py` (rejection catalogue) |
| FR-005, SC-008 | `tests/contract/test_flue_gas_supply.py::test_swap_sources` |
| FR-006, FR-015 | `tests/unit/interface/test_timeseries_supply.py` |
| FR-007, FR-008 | `tests/integration/test_run_scenario.py` |
| FR-009, FR-010, SC-004 | `tests/validation/test_step_response.py`, `test_settles_to_steady_state.py` |
| FR-011 | `tests/integration/test_heat_limited.py` |
| FR-012 | `tests/unit/checks/test_ranges.py` |
| FR-013, SC-002 | `tests/unit/checks/test_balances.py`, `tests/integration/test_balances_close.py` |
| FR-014, SC-006 | `tests/integration/test_rerun_identical.py` |
| FR-016, SC-003 | `tests/unit/validation/test_compare.py`, `tests/validation/test_reference_steady_state.py` |
| FR-017 | `tests/integration/test_run_record.py` |
| SC-001 | manual check with [quickstart.md](quickstart.md) |
| SC-007 | `tests/performance/test_benchmark.py` |

## Project Structure

### Documentation (this feature)

```text
specs/001-boiler-dryer-interface/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: literature search and decisions
├── data-model.md        # Phase 1: entities, fields, validation, state transitions
├── quickstart.md        # Phase 1: end-to-end validation guide
├── contracts/
│   ├── flue-gas-interface.md
│   ├── scenario-file.md
│   └── cli.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks; not created by /speckit-plan)
```

### Source Code (repository root)

```text
pyproject.toml           # uv project, dependencies, ruff/mypy/pytest config
uv.lock
src/boidrytwin/
├── __init__.py          # public API: load_scenario, run, compare
├── cli.py               # argparse CLI (contracts/cli.md)
├── logging.py           # structlog configuration
├── units.py             # pint registry; parsing "<number> <unit>" → SI floats
├── interface/           # subsystem coupling (no dryer imports here)
│   ├── composition.py   # GasComposition
│   ├── flue_gas.py      # FlueGasState, FlueGasSupply protocol, errors
│   └── sources.py       # ConstantFlueGasSupply, TimeSeriesFlueGasSupply
├── properties/
│   ├── gas.py           # NASA-7 cp/h/s, mixture rules, transport + Wilke
│   ├── water.py         # IAPWS-IF97 region 4, latent heat, humidity, dew point
│   └── wood.py          # Wood Handbook EMC, heat capacity, sorption heat
├── dryer/
│   ├── config.py        # DryerConfiguration, valid ranges
│   ├── state.py         # DryerState packing/unpacking of the ODE vector
│   ├── transport.py     # two-phase solids transport (R2)
│   ├── heat_transfer.py # gas–solid, gas–shell, shell–ambient (R3, R5)
│   ├── drying.py        # characteristic drying curve (R4)
│   ├── model.py         # vectorised right-hand side, mixing with dilution air
│   └── simulate.py      # solve_ivp driver, initial states, output sampling
├── scenario/
│   ├── schema.py        # pydantic models for the scenario file
│   ├── loader.py        # TOML + CSV loading, validation, normalisation
│   └── timeseries.py    # CSV with unit row, UTC handling, gap detection
├── checks/
│   ├── balances.py      # BalanceReport
│   └── ranges.py        # RangeWarning detection
├── records.py           # RunRecord, hashing, run folder I/O, rerun
└── validation/
    └── compare.py       # ValidationReport, steady-period detection

tests/
├── unit/                # per module, incl. property tests vs. Cantera/CoolProp
├── contract/            # flue gas interface, scenario file, CLI
├── integration/         # full runs from scenario files
├── validation/          # reference cases with documented derivations
├── performance/         # benchmark (marker: benchmark)
└── data/                # small fixed input files

examples/                # scenario files used by quickstart.md
docs/
└── model.md             # model equations, assumptions, valid ranges, sources
```

**Structure Decision**: A single Python package (`src/` layout) with a thin CLI. The
`interface` package has no dependency on `dryer`, so a future `boiler_house` package can
implement `FlueGasSupply` without touching the dryer (constitution principle III).

## Implementation phasing (input for `/speckit-tasks`)

1. **Foundation**: project setup (uv, ruff, mypy, pytest), units, logging.
2. **User Story 1 (P1)**: properties needed by the interface (gas, water), interface types,
   constant and time-series sources, scenario validation, `validate` command.
3. **User Story 2 (P1)**: wood properties, transport, heat transfer, drying, shell, RHS,
   simulator, run record, `run` command; benchmark test early in this phase.
4. **User Story 3 (P2)**: balance report, range warnings, `rerun` command.
5. **User Story 4 (P3)**: measured time series, comparison, `compare` command, synthetic
   dataset.
6. **Validation and documentation**: hand-calculation reference case, literature cases once
   full texts are available ([research.md Open items](research.md#open-items)), `docs/model.md`.

## Risks

| Risk | Mitigation |
|---|---|
| Correlation coefficients not verified against originals | Open item 1 in research.md; coefficients isolated in `DryerConfiguration` with sources; blocked tasks marked |
| No measured wood chip drum data yet | Synthetic and literature validation first; calibration in a later feature |
| Stiffness from small gas hold-up slows the solver | Early benchmark; fallback to quasi-steady gas balances or numba |
| EMC isotherm extrapolated above 130 °C | Clipped and flagged; only affects the drum outlet region |

## Complexity Tracking

No constitution violations; nothing to justify.
