---

description: "Task list for feature 003: local web app for the plant twin"
---

# Tasks: Local Web App for the Plant Twin

**Input**: Design documents from `specs/003-web-frontend/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: REQUIRED (constitution principle I). Every test task MUST be written and observed
failing before its implementation task is started.

**Organization**: grouped by user story. The models (`dryer/`, `boiler_house/`, `plant/model.py`,
`interface/`, `properties/`) MUST NOT be changed. The only change to the twin is the read-only
progress callback (T007–T010).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1 (view runs), US2 (start runs), US3 (operator what-if), US4 (comparison)
- Web tests use the FastAPI test client from `tests/webapp_conftest.py` fixtures: `client(view=...)`
  with temporary `runs/`, `scenarios/` and `examples/` folders, and `run_examples` (CLI runs of
  `boiler_house_only.toml`, `plant_reference.toml` and `oil_demand_step.toml` shortened to 2 h,
  made once per session).

---

## Phase 1: Setup

- [X] T001 Add the optional extra `web = ["fastapi>=0.115", "uvicorn>=0.32", "jinja2>=3.1", "python-multipart>=0.0.12", "plotly>=6"]` and `httpx>=0.28` to the dev group in `pyproject.toml`; run `uv sync --all-groups --extra web`; add the `tests/unit/webapp/`, `tests/contract/webapp/`, `tests/integration/webapp/` packages (`__init__.py`).
- [X] T002 Create the package skeleton `src/boidrytwin/webapp/` (`__init__.py`, `settings.py` with an `AppSettings` pydantic model: `runs_dir`, `scenarios_dir`, `examples_dir`, `port` default 8765, `app_dir` = `runs_dir / ".app"`; `templates/`, `static/`), and `tests/webapp_conftest.py` with the fixtures described above (imported by `tests/conftest.py`).
- [X] T003 Extend the import-boundary contract test `tests/contract/test_import_boundaries.py`: no module outside `boidrytwin.webapp` and `boidrytwin.cli` imports `boidrytwin.webapp`, and `webapp` imports only the public twin functions (`load_scenario`, `records`, `scenario.loader`, `validation.compare.read_measured`, `checks`, `units`).

---

## Phase 2: Foundational (blocks all stories)

### Tests (write first, must fail)

- [X] T004 [P] Write `tests/unit/test_progress_callback.py`: `simulate`, `simulate_plant` and `records.run` accept `progress=None|callable`; with a recording callback, (a) results are bit-identical to a run without it (compare `results.csv` / `boiler_results.csv` bytes for `reference_constant.toml` and `plant_reference.toml` at 1 h); (b) the phases arrive in order `initialising` (steady start only) → `simulating` → `writing`; (c) `simulated_s` is non-decreasing and ends at the duration; (d) calls are at most one per second of wall time plus phase changes.
- [X] T005 [P] Write `tests/unit/webapp/test_display_units.py` (FR-003): the display-unit table maps K → °C (555.15 K → 282.0 °C), W → MW, kg/kg and mol/mol → %, Pa → kPa, `fuel_feed` and `product_dry_mass_flow` kg/s → t/h (1 kg/s → 3.6 t/h), other kg/s unchanged; unknown units pass through unchanged; conversions use the project's pint registry; a round trip display → SI is exact to 1e-12.
- [X] T006 [P] Write `tests/unit/webapp/test_run_index.py` (FR-001, edge cases): listing the `run_examples` folders gives RunSummary with `run_id`, `scenario_name`, `created_at` (UTC), `kind` (`dryer` | `boiler` | `coupled`), `status`, `checks_passed`, `warnings`, `flags`; newest first; a folder with an unreadable `run_record.json` is listed with a `note` and does not stop the listing; a second listing without folder changes reads no record again (cache by modification time); filters `q` (name substring), `status`, `kind`.
- [X] T007 [P] Write `tests/unit/webapp/test_queue.py` (FR-010, FR-011, data-model §8): `queue.json` `{"version": 1, "jobs": [...]}` written atomically; transitions queued → running → completed | failed; `restart_rules()` sets `running` → `interrupted` and `queued` → `not_started` and logs each; start allowed only from `not_started`/`interrupted`, drop only from `queued`/`not_started` (others raise); unknown fields are kept on rewrite; a file with a higher `version` is not modified; `jobs/<job_id>/` holds the frozen scenario before the job is queued.
- [X] T008 [P] Write `tests/contract/webapp/test_middleware.py` (R8, contract http-api.md request rules): `Host: evil.example` → 421; `POST` with `Origin: http://evil.example` → 403; no `view` cookie → pages redirect to `/`, API → 401; `GET /` renders the view choice; the plotly script `/static/plotly.min.js` is served from the `plotly` package (FR-020, no external URLs in any template: scan templates for `http://`/`https://`).

### Implementation

- [X] T009 Create `src/boidrytwin/progress.py` (a `Progress` protocol `__call__(phase: str, simulated_s: float, duration_s: float)` and a throttling wrapper, at most once per second plus phase changes) and add the optional `progress` parameter to `src/boidrytwin/dryer/simulate.py` (`simulate`, `steady_state`), `src/boidrytwin/plant/simulate.py` (`simulate_plant`, steady state) and `src/boidrytwin/records.py` (`run`, `run_with_result`, `compare`): report the largest `t` seen by the right-hand side wrapper, never changing the integration (no new breakpoints or steps).
- [X] T010 [P] Implement `src/boidrytwin/webapp/display_units.py`: the single SI → display table per unit and per column override, `to_display(column, unit, values)`, `to_si(...)`, using `boidrytwin.units`.
- [X] T011 [P] Implement `src/boidrytwin/webapp/run_index.py`: RunSummary model, listing with mtime cache, filters, damaged-record notes; status from the run record or, for app jobs, from the queue.
- [X] T012 Implement `src/boidrytwin/webapp/jobs.py`: Job model (data-model §8), atomic `queue.json` and `progress/<job_id>.json` I/O, state transitions, restart rules, freezing a scenario into `jobs/<job_id>/` (copying referenced step files).
- [X] T013 Implement `src/boidrytwin/webapp/worker.py`: a worker process (`spawn`) that takes the next `queued` job, marks it `running`, calls `records.run` (or `records.compare` for comparison jobs) on the frozen scenario with a progress callback writing `progress/<job_id>.json`, then marks it `completed`/`failed` with `run_id` and message; logs `job_started`/`job_finished` with durations; gets only paths as arguments.
- [X] T014 Implement `src/boidrytwin/webapp/permissions.py` (endpoint name → allowed views, data from contracts/http-api.md) and `src/boidrytwin/webapp/app.py`: `create_app(settings)` with the Host check, Origin check, view cookie, permission check per route, the issue-format error handler (422), Jinja2 templates `templates/base.html` and `templates/index.html` (view choice), and static files (`static/app.js`, `static/style.css`, `plotly.min.js` from `plotly`'s package data).
- [X] T015 Implement `src/boidrytwin/webapp/action_log.py` (FR-021): `log_action(view, action, target, details)` appending to `actions.jsonl` and emitting a structlog event; actions as listed in data-model §10. Test in `tests/unit/webapp/test_action_log.py` (write first).

**Checkpoint**: the app starts in tests, enforces Host/Origin/view rules, runs a queued job in the worker, and the twin's results are unchanged.

---

## Phase 3: User Story 1 — View the results of a run (P1) 🎯 MVP

**Goal**: list runs and show their plots, balances, warnings and flags.

**Independent Test**: CLI runs of the examples are listed, and their plots and balances match the run folders.

### Tests (write first, must fail)

- [X] T016 [P] [US1] Write `tests/unit/webapp/test_plot_data.py` (FR-002, FR-004, SC-007): default column sets per subsystem (data-model §3) present only where the run has them; values equal the CSV values converted to display units exactly; flag columns and range warnings become periods (start, end, label); several runs give one series per run and column; above 5000 points the drawn series are min/max-reduced while the CSV export keeps all points.
- [X] T017 [P] [US1] Write `tests/contract/webapp/test_api_runs.py` (contract http-api.md): `GET /api/runs` (both views) returns all `run_examples` with the RunSummary fields, `total`, filters, paging; `GET /api/runs/{id}` gives balances (every entry and quantity with residual and tolerance), warnings and flag periods; unknown id → 404; `DELETE /api/runs/{id}` → 403 for operators, 400 without `confirm=true`, 204 for engineers and logged.
- [X] T018 [P] [US1] Write `tests/contract/webapp/test_api_plot.py` (FR-002, FR-005, FR-006, FR-018a): `GET /api/runs/{id}/plot` default and chosen columns with units; unknown column → 422; `GET /api/plot?runs=a,b&columns=c` overlays; `GET /api/runs/{id}/plot.csv` has `time,<run>:<column>` header, a unit row, the run ids in a `#` comment line, and values equal to the plot data; `GET /api/runs/{id}/profiles?time=` returns per-cell profiles for a coupled run with profiles, 404 otherwise.
- [X] T019 [P] [US1] Write `tests/integration/webapp/test_pages_runs.py`: `/runs`, `/runs/{id}` and `/compare?runs=a,b` render for both views (200, the run name, the plot containers and the PNG download control present); a failed run shows its failing balance entries.

### Implementation

- [X] T020 [US1] Implement `src/boidrytwin/webapp/run_view.py`: RunView (tables with unit rows, balance report entries, warnings, flag periods, profiles and comparison files if present).
- [X] T021 [US1] Implement `src/boidrytwin/webapp/plot_data.py`: default sets, PlotData builder, periods, multi-run overlay, reduction for drawing, CSV export with unit row and run ids.
- [X] T022 [US1] Add the runs routes to `src/boidrytwin/webapp/app.py` (`/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/plot`, `/api/plot`, `/api/runs/{id}/plot.csv`, `/api/runs/{id}/profiles`, `DELETE /api/runs/{id}`) and the pages `templates/runs.html`, `templates/run.html`, `templates/compare.html`, with plot rendering and period shading in `static/app.js` (Plotly figures from PlotData; Plotly's PNG button enabled).

**Checkpoint**: US1 works on its own (quickstart §2–3).

---

## Phase 4: User Story 2 — Start a simulation from the browser (P1)

**Goal**: edit scenarios with units and step sequences, validate, save, queue and follow runs.

**Independent Test**: a run started from the app is identical to the CLI run of its saved scenario.

### Tests (write first, must fail)

- [X] T023 [P] [US2] Write `tests/unit/webapp/test_scenario_form.py` (FR-007, FR-008, SC-004): every example in `examples/` reads into a ScenarioForm (sections in file order, arrays of tables numbered, fields with value and unit) and writes back byte-identically when unchanged; an edited value changes only its line; `validate(form)` maps every `ScenarioValidationError` issue to its field (one test per rule family: unit missing, out of range, unknown key, composition sum, heater arrangement, controller limits, coupled rules); examples are read-only.
- [X] T024 [P] [US2] Write `tests/unit/webapp/test_step_sequence.py` (FR-007a, data-model §5): a StepSequence with start value and steps writes the feature-001 CSV (`time,value`, unit row, rows (t, a), (t + 1 s, b), last row at the scenario end); times must be strictly increasing and inside the scenario period; values outside the input's allowed range are rejected through the loader; the CSV round-trips to the same StepSequence via `<name>.meta.json`.
- [X] T025 [P] [US2] Write `tests/contract/webapp/test_api_scenarios.py`: `GET /api/scenarios`, `GET /api/scenarios/{name}`, `POST /api/scenarios/validate` (200 or 422 with field-mapped issues), `POST /api/scenarios` (201; 409 for an existing name; examples never overwritten), `POST /api/jobs` (202; 422 if the scenario does not load); all → 403 in the operator view.
- [X] T026 [P] [US2] Write `tests/contract/webapp/test_api_jobs.py`: `GET /api/jobs` in queue order with progress; `POST /api/jobs/{id}/start` and `/drop` with the allowed source states only (409 otherwise); operators may start or drop only their own what-if jobs.
- [X] T027 [P] [US2] Write `tests/integration/webapp/test_app_run_identical.py` (FR-009, SC-003): save `plant_reference` with fuel moisture 50 % and an oil return step at 06:00 as `plant_wet_fuel` (end shortened to 08:00), queue it, run the worker in-process; the run folder exists, `rerun` of its record gives `identical: true`, and `boidrytwin run scenarios/plant_wet_fuel.toml` gives byte-identical result CSVs.
- [X] T028 [P] [US2] Write `tests/integration/webapp/test_worker.py` (FR-010, FR-011): three queued jobs run in order; progress files appear and end at the duration; a scenario that fails in the solver ends `failed` with its message and a kept run record; killing the worker during a run and restarting the app gives `interrupted` and `not_started`, and nothing starts until started.
- [X] T029 [P] [US2] Write `tests/contract/webapp/test_cli_serve.py` (contract cli-serve.md): `serve --no-browser` prints `serving http://127.0.0.1:<port>` and answers `GET /`; a busy port → exit 3; an invalid folder → exit 1; without the `web` extra (simulated by blocking the import) → exit 1 with the install hint.

### Implementation

- [X] T030 [US2] Implement `src/boidrytwin/webapp/scenario_form.py`: TOML → ScenarioForm (raw text kept), a line-based writer that changes only edited lines, validation through `load_scenario` on a temporary file and issue mapping to fields; read-only examples.
- [X] T031 [US2] Implement `src/boidrytwin/webapp/steps.py`: StepSequence model, CSV writer in `<name>.steps/steps_<key>.csv`, `<name>.meta.json`, and replacement of the scenario value by `{ file, column = "value" }`.
- [X] T032 [US2] Add the scenario and job routes to `src/boidrytwin/webapp/app.py` and the pages `templates/scenarios.html`, `templates/scenario.html` (sections, value/unit inputs, step editor, inline issues), `templates/queue.html` (states, progress polling in `static/app.js`, start/drop buttons); log every state-changing action.
- [X] T033 [US2] Add the `serve` command to `src/boidrytwin/cli.py` (options of contracts/cli-serve.md): start the worker process and uvicorn on `127.0.0.1`, apply the restart rules, print the URL, open the browser unless `--no-browser`, mark a running job `interrupted` on `Ctrl+C`, exit codes 0/1/3.

**Checkpoint**: US1 and US2 work (quickstart §4, §6).

---

## Phase 5: User Story 3 — What-if runs for operators (P2)

**Goal**: operator scenarios with released inputs, versions and baselines; the operator view and the comparison with the baseline.

**Independent Test**: an operator changes a released input within range and gets a comparison with the version's baseline; out-of-range values are refused.

### Tests (write first, must fail)

- [X] T034 [P] [US3] Write `tests/unit/webapp/test_operator.py` (FR-012, FR-014, data-model §6): creating a version writes `scenarios/operator/<name>/v<N>/` with a frozen `scenario.toml`, step files and `operator.toml` (contract app-state.md); versions increase and are never reused; a release needs `minimum < maximum`, a `label` of at most 60 characters, an existing key and a unit of its dimension, and is accepted only if the scenario loads with the input at the minimum and at the maximum (R6); `comparison_outputs` default to the FR-014a set minus outputs the scenario does not have; the baseline job is queued at save; states `baseline pending` → `ready` | `baseline failed`.
- [X] T035 [P] [US3] Write `tests/unit/webapp/test_whatif_comparison.py` (FR-014, FR-014a, FR-015): for a baseline and a what-if run, each comparison output has the baseline and what-if values (final value and mean of the last hour, display units), absolute and relative differences; warnings and flags only in the what-if run are listed as new; the summary says whether the oil (and, coupled, the drum inlet) is on its set point (within its controller's `not_reached_band` at the end), the product moisture and the number of new warnings; without a completed baseline the comparison is empty with the note.
- [X] T036 [P] [US3] Write `tests/contract/webapp/test_api_operator.py` (FR-013, SC-005): `POST /api/operator/{name}/versions` engineer only (403 operator), 422 for a release failing R6; `POST /api/operator/{name}/whatif` in both views: 422 with the released range for each value below the minimum, above the maximum, and for every non-released key; a step is accepted only where `allow_step`; 202 otherwise, and the job's frozen scenario differs from the version's only in the released inputs; `GET /api/whatif/{run_id}` and `.csv`.
- [X] T037 [P] [US3] Write `tests/contract/webapp/test_permissions.py` (FR-016): for every route in the permission table and both views, the response is allowed or 403 exactly as in contracts/http-api.md; the table covers every registered route (no route without an entry).
- [X] T038 [P] [US3] Write `tests/integration/webapp/test_whatif_flow.py` (US3 scenarios 1–5): engineer creates "Fuel and oil demand" from `plant_reference` (end shortened) with fuel moisture 35–55 % and oil return 220–260 °C; the baseline runs; the operator starts 52 % moisture; the comparison shows the default outputs and the summary; a second version gets its own baseline, and the first what-if run still compares with version 1's baseline; a failing baseline gives what-if runs without comparison and with the note.

### Implementation

- [X] T039 [US3] Implement `src/boidrytwin/webapp/operator.py`: OperatorScenario/OperatorVersion/Release models, version folders, release checks (R6), default comparison outputs, baseline queuing and state; `whatif.json` index (contract app-state.md).
- [X] T040 [US3] Implement `src/boidrytwin/webapp/whatif.py`: WhatIfComparison and the plain-language summary.
- [X] T041 [US3] Add the operator routes to `src/boidrytwin/webapp/app.py` and the pages `templates/operator_list.html`, `templates/operator.html` (operator: released inputs only, with ranges and optional step; engineer: release settings and comparison outputs) and `templates/whatif.html` (summary first, then the output table and overlaid plots of what-if and baseline).

**Checkpoint**: US1–US3 work (quickstart §5).

---

## Phase 6: User Story 4 — Compare a run with plant measurements (P3)

**Goal**: upload a measured series and show the comparison like the CLI.

**Independent Test**: the synthetic boiler measurements give the same biases and pass/fail as `boidrytwin compare`.

### Tests (write first, must fail)

- [X] T042 [P] [US4] Write `tests/contract/webapp/test_api_comparisons.py` (FR-017, FR-022): `POST /api/comparisons` engineer only; a non-CSV or a file above 50 MB → 413/422; an invalid measured file → 422 with the `read_measured` issues; a valid one → 202, stored unchanged (same sha256) in the job folder, then next to the comparison run.
- [X] T043 [P] [US4] Write `tests/integration/webapp/test_comparison_upload.py` (FR-017, FR-018): uploading `examples/synthetic_boiler_measured.csv` for `oil_demand_step` (end shortened) gives a run with `validation_report.json` equal to `records.compare` on the same inputs (biases, tolerances, pass/fail, excluded samples), and its plot data has measured and predicted series with excluded samples marked.

### Implementation

- [X] T044 [US4] Implement `src/boidrytwin/webapp/uploads.py` (type and size checks, sha256, storage, `read_measured` validation) and the comparison job kind in `src/boidrytwin/webapp/worker.py`; add `POST /api/comparisons` and the comparison section of `templates/run.html` (measured and predicted overlay, statistics table, excluded samples).

**Checkpoint**: all stories work (quickstart §7).

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T045 [P] Write `tests/performance/test_webapp_benchmark.py` (marker `benchmark`; SC-001, SC-006): 200 copied run folders are listed and one run opened with its default plots in < 3 s; a coupled 24 h run through the worker takes at most 1.1 × the CLI time while `GET /api/runs` answers in < 1 s throughout.
- [X] T046 [P] Write `docs/webapp.md` (start, views, pages, scenario editing and step sequences, operator scenarios and versions, files written, the local-only access and that the view is not a security boundary) and update `README.md` (serve, the `web` extra) and `.gitignore` (`runs/.app/`, `scenarios/` if wanted).
- [X] T047 Create `specs/003-web-frontend/checklists/usability.md` (SC-002 protocol: 5 first-time users, task script, time limit 5 min, results table) for the manual test.
- [X] T048 Run all steps of [quickstart.md](quickstart.md) (§1–8) and record the results in `specs/003-web-frontend/checklists/quickstart-run.md`.
- [X] T049 Final quality gate: ruff, ruff format, mypy, `pytest`, `pytest -m benchmark`; the feature-001/002 suites pass unchanged.

---

## Addendum: formula page (FR-023, requested after the polish phase)

- [X] T050 Write `tests/unit/webapp/test_formulas.py`: every formula has existing sources and an existing implementing function; every source is used and linked (`https://doi.org/<doi>` for DOIs); every DOI appears in the research notes of features 001/002; `/formulas` renders for both views with every formula and link, and is in the navigation.
- [X] T051 Implement `src/boidrytwin/webapp/formulas.py` (formulas by section, sources) and `templates/formulas.html`, route `formulas_page` (both views), navigation link; DOIs not yet in the research notes looked up in Crossref and recorded in `specs/002-boiler-house-model/research.md`.
- [X] T052 Mention the page in `docs/webapp.md`.

## Addendum: desktop program (FR-024)

- [X] T053 Write `tests/unit/webapp/test_desktop.py`: data folder default and override, folders and examples set up, examples refreshed only on a new version and user data never touched, detection of a running instance (and not of another program), `main()` starts the server with the browser (or only opens the browser on a running instance).
- [X] T054 Implement `src/boidrytwin/webapp/desktop.py` and `packaging/launcher.py` (with `freeze_support` for the worker process), the PyInstaller recipe `packaging/BoiDryTwin.spec` and `scripts/build_exe.ps1`; PyInstaller in the `build` dependency group only.
- [X] T055 Build `dist/BoiDryTwin.exe` and smoke-test it: pages, a run through the worker, second launch, stop by the console break signal, no processes left.

---

## Dependencies & Execution Order

```text
Setup → Foundational → US1 (view runs) → US2 (start runs) → US3 (operator what-if) → US4 (comparison) → Polish
```

- US1 depends only on Foundational (it also works for CLI runs).
- US2 depends on US1 (a finished run opens in the run view) and on the worker (T013).
- US3 depends on US2 (scenario form, steps, jobs) and US1 (plots).
- US4 depends on US1 (run view) and the worker; it is independent of US3.

Key task dependencies:
- T009 → T013 (progress in the worker)
- T010 → T021; T011 → T022; T012 → T013 → T027, T028
- T014 → every route task (T022, T032, T041, T044)
- T030, T031 → T032 → T039 (operator versions reuse forms and steps)
- T039 → T040 → T041

## Parallel Examples

```text
# Phase 2: tests T004–T008 in parallel; then T010, T011 in parallel with T009 → T012 → T013.
# US1: T016–T019 in parallel; T020 and T021 in parallel; then T022.
# US2: T023–T029 in parallel; T030 and T031 in parallel; then T032, T033.
# US3: T034–T038 in parallel; T039 → T040 → T041.
# US4 (T042–T044) can run in parallel with US3 after US2.
```

## Implementation Strategy

1. **MVP**: Setup, Foundational and US1. Runs from the command line can be browsed and
   plotted, which is useful at once for engineers and in shift meetings.
2. **US2**: runs started from the browser; the app replaces the command line for everyday work.
3. **US3**: what-if runs for operators, the main reason for the app's second user group.
4. **US4**: comparisons with plant data, ready for calibration work.
5. **Polish**: benchmark, docs, the quickstart run and the usability test.

### Notes

- Do not change the model code. If a change seems needed beyond the progress callback, stop and
  amend the plan.
- Commit after each phase.
- Run the feature-001/002 suites after every phase.
