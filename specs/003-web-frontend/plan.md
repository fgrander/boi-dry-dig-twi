# Implementation Plan: Local Web App for the Plant Twin

**Branch**: `003-web-frontend` | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-web-frontend/spec.md`

## Summary

A local web app, started with `boidrytwin serve`, for engineers and operators. It lists and
plots runs, edits and starts scenarios (including step sequences), runs operator what-if cases
against versioned baselines, and compares runs with uploaded measurements. Design
([research.md](research.md)):

- a FastAPI server with Jinja2 pages and Plotly plots, everything served locally (R1);
- one worker process that runs the queue with the unchanged `records.run` / `records.compare`,
  and a read-only progress callback in the simulators (R2);
- app state as plain files: queue, progress, what-if index, action log (R3); scenarios,
  generated step-sequence CSVs and versioned operator scenarios in a scenario folder (R5, R6);
- validation always through `load_scenario` and `read_measured` (R4);
- `127.0.0.1` only, Host and Origin checks, and server-side view permissions per endpoint (R8).

## Technical Context

**Language/Version**: Python 3.12+; HTML templates with small plain JavaScript files

**Primary Dependencies**: features 001/002 unchanged; new, as the optional extra `web`:
`fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `plotly` (bundles `plotly.min.js`); tests:
`httpx`

**Storage**: files: run folders (unchanged), `<runs>/.app/` state files, `scenarios/` folder

**Testing**: pytest with the FastAPI test client (unit, contract, integration), a `benchmark`
marker for SC-001/SC-006, and a manual usability checklist for SC-002

**Target Platform**: a Windows 11 engineering PC (Linux also works); a current desktop browser
on the same machine; offline

**Project Type**: Python library and CLI, plus a local web application (server-rendered)

**Performance Goals**: run list (200 runs) and run view under 3 s (SC-001); the API answers
under 1 s while a run is going; a run through the app at most 10 % slower than the CLI (SC-006)

**Constraints**: models and run results unchanged (FR-019); bit-identical results to the CLI
(SC-003); served to this machine only; no internet access needed

**Scale/Scope**: about 10 pages, 25 API endpoints, one worker, hundreds of runs, tens of
scenarios

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.1.0.

| Principle / rule | Pre-research | Post-design | How the design complies |
|---|---|---|---|
| I. Tests first, seen failing; every FR mapped to a test | ✅ | ✅ | test-first ordering in `/speckit-tasks`; mapping below |
| I. Contract tests for interfaces | ✅ | ✅ | every endpoint of [http-api.md](contracts/http-api.md), the state file formats of [app-state.md](contracts/app-state.md), and the `serve` command |
| II. All external inputs validated (operator input, files) | ✅ | ✅ | forms and uploads go through `load_scenario` / `read_measured`; release ranges checked in the server; upload type and size limits |
| II. Units explicit, SI internally, one conversion place | ✅ | ✅ | display-unit table (R7) is the only conversion; the stored data stays SI |
| II. UTC timestamps | ✅ | ✅ | all state files and API times are UTC ISO 8601; plots in scenario UTC time |
| II. Reproducible runs; raw data immutable | ✅ | ✅ | jobs run a frozen scenario copy with `records.run`; rerun identical (SC-003); uploads kept unchanged |
| III. Models unchanged; valid range reported | ✅ | ✅ | the app only calls the twin; warnings and flags shown (FR-004). The only twin change is an optional, read-only progress callback (no numeric effect, tested) |
| III. Subsystems separate | ✅ | ✅ | the app is a new package `webapp` that imports the public functions only; no model imports it |
| IV. Structured logging, metrics, errors with context | ✅ | ✅ | structlog events for requests, jobs (`job_queued`, `job_started`, `job_finished` with durations), the action log (FR-021) |
| Stack: new dependencies justified | ✅ | ✅ | research R1; optional extra, so the models and CLI don't depend on it |
| Security: no secrets committed | ✅ | ✅ | no credentials exist; local binding plus Host/Origin checks (R8) |

**Result**: PASS. No violations; Complexity Tracking is not needed.

### Requirement → test mapping

| Requirement | Test location |
|---|---|
| FR-001, edge cases (damaged record, many runs) | `tests/unit/webapp/test_run_index.py`, `tests/contract/webapp/test_api_runs.py` |
| FR-002, FR-003, FR-004, FR-005, FR-006, SC-007 | `tests/unit/webapp/test_display_units.py`, `test_plot_data.py`, `tests/contract/webapp/test_api_plot.py` |
| FR-007, FR-008, SC-004 | `tests/unit/webapp/test_scenario_form.py`, `tests/contract/webapp/test_api_scenarios.py` |
| FR-007a | `tests/unit/webapp/test_step_sequence.py`, `tests/integration/webapp/test_saved_scenario_runs_from_cli.py` |
| FR-009, SC-003 | `tests/integration/webapp/test_app_run_identical.py` |
| FR-010, FR-011 (queue, progress, restart) | `tests/unit/webapp/test_queue.py`, `tests/integration/webapp/test_worker.py`, `tests/unit/test_progress_callback.py` |
| FR-012, FR-013, FR-014, FR-014a, FR-015, SC-005 | `tests/unit/webapp/test_operator.py`, `test_whatif_comparison.py`, `tests/contract/webapp/test_api_operator.py`, `tests/integration/webapp/test_whatif_flow.py` |
| FR-016 (view checks), R8 (Host/Origin) | `tests/contract/webapp/test_permissions.py` (each endpoint × view) |
| FR-017, FR-018, FR-022 | `tests/contract/webapp/test_api_comparisons.py`, `tests/integration/webapp/test_comparison_upload.py` |
| FR-018a | `tests/contract/webapp/test_api_plot.py` (CSV), page smoke test (PNG button present) |
| FR-019 | the feature-001/002 suites unchanged; `tests/unit/test_progress_callback.py` (identical results with and without callback) |
| FR-020 | `tests/contract/webapp/test_cli_serve.py`, `tests/unit/webapp/test_assets_offline.py` |
| FR-021 | `tests/unit/webapp/test_action_log.py` |
| SC-001, SC-006 | `tests/performance/test_webapp_benchmark.py` (`benchmark`) |
| SC-002 | manual: `checklists/usability.md` |

## Project Structure

### Documentation (this feature)

```text
specs/003-web-frontend/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── http-api.md
│   ├── app-state.md
│   └── cli-serve.md
└── tasks.md            # /speckit-tasks
```

### Source Code (additions)

```text
src/boidrytwin/
├── progress.py               # Progress protocol (phase, simulated time); used by the simulators
├── dryer/simulate.py         # + optional progress callback (read-only)
├── plant/simulate.py         # + optional progress callback (read-only)
├── records.py                # + progress passed through run / compare
├── cli.py                    # + `serve` command
└── webapp/
    ├── __init__.py
    ├── app.py                # FastAPI app factory, middleware (Host/Origin, view), routes
    ├── permissions.py        # endpoint → allowed views (FR-016)
    ├── settings.py           # folders, port
    ├── run_index.py          # RunSummary listing with cache (FR-001)
    ├── run_view.py           # RunView: tables, balances, warnings, periods
    ├── display_units.py      # the one SI → display conversion (FR-003)
    ├── plot_data.py          # PlotData, default sets, periods, CSV export (FR-002–FR-005, FR-018a)
    ├── scenario_form.py      # TOML ↔ ScenarioForm, issue mapping (FR-007, FR-008)
    ├── steps.py              # StepSequence ↔ CSV (FR-007a)
    ├── operator.py           # operator scenarios, versions, releases (FR-012–FR-014a)
    ├── whatif.py             # WhatIfComparison and summary (FR-014, FR-015)
    ├── jobs.py               # queue file, states, restart rules, progress files (FR-010, FR-011)
    ├── worker.py             # worker process loop: records.run / records.compare
    ├── uploads.py            # measured uploads (FR-017, FR-022)
    ├── action_log.py         # FR-021
    ├── templates/            # Jinja2 pages
    └── static/               # app.js, style.css (plotly.min.js served from the plotly package)

tests/
├── unit/webapp/  ├── contract/webapp/  ├── integration/webapp/
├── unit/test_progress_callback.py
└── performance/test_webapp_benchmark.py
```

**Structure Decision**: a single project. The web app is a subpackage `boidrytwin.webapp` with
an optional dependency extra, because it is a thin layer over the library and is tested
with the same tools. There are no separate frontend and backend projects: the pages are
rendered by the server, and the little JavaScript there is is static and has no build step.

## Implementation phasing (input for `/speckit-tasks`)

1. **Setup**: the `web` extra, the package skeleton, the app factory with the Host/Origin/view
   middleware and the permission table, `serve` (no worker yet), offline assets.
2. **Foundational**: the progress callback in the simulators and records (tested for identical
   results), display units, the run index, the job queue file and the worker loop.
3. **US1** (P1): run list, run view, plots with periods, several runs, CSV export, profiles.
4. **US2** (P1): scenario form, validation mapping, step sequences, save, start jobs, progress,
   failures, restart.
5. **US3** (P2): operator scenarios with versions, release checks, baselines, the operator
   view, the what-if comparison and summary.
6. **US4** (P3): measured upload and comparison view.
7. **Polish**: benchmark, docs (README, `docs/webapp.md`), the quickstart run, the usability
   checklist.

## Risks

- **Comments in TOML on save**: the standard library only reads TOML. Writing back with
  comments kept needs a careful line-based writer, or `tomlkit` (another dependency). Plan: a
  small writer that changes only the edited lines, tested on all examples; fall back to
  `tomlkit` if it gets complicated.
- **Progress granularity**: with constant inputs, a whole run can be one solver segment. The
  callback reports the solver's time as it evaluates, so progress still moves, but it can
  jump. That is acceptable for 10–40 s runs.
- **Windows process start**: the worker uses the `spawn` start method; the run functions and
  their arguments must be importable and picklable, so the worker gets only paths.
- **Browser support**: tested on current Edge and Chrome only.

## Complexity Tracking

No constitution violations to justify.
