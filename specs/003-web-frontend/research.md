# Research: Local Web App for the Plant Twin

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-10-24

Decisions for the technical unknowns of the plan. Each entry gives the decision, the
reasons and the alternatives that were considered.

## R1. Web stack

**Decision**: a Python web server (**FastAPI** on **uvicorn**) that renders HTML pages from
**Jinja2** templates, with small plain JavaScript files for the interactive parts. Plots
use **Plotly**: the figures are built in Python (`plotly` package) and drawn in the browser by
the `plotly.min.js` bundled in that package. All assets are served by the app, so it works
offline (FR-020).

**Rationale**:
- One language and one toolchain (uv, pytest, ruff, mypy) for the whole project; no Node
  build. The team writing the models can maintain the app.
- The server owns every decision (validation, view checks, queue), and the browser only shows
  and submits. That keeps FR-016 checkable server-side and testable with HTTP tests.
- FastAPI has a test client (via `httpx`), typed request models (pydantic, already used) and
  file uploads (`python-multipart`).
- Plotly gives zoomable time-series plots, several traces, shaded periods for flags, and a
  built-in "download as PNG" (FR-018a) without a server-side image renderer.

**Alternatives considered**:
- **Streamlit / Dash / NiceGUI**: quick dashboards, but the rerun model (Streamlit) or callback
  graph (Dash) makes a shared background queue, server-side view checks on every action and
  HTTP contract tests awkward.
- **FastAPI + React (or another SPA)**: richer UI, but a second language, a Node build and
  bundling for offline use. Not justified for a handful of screens.
- **htmx**: would save some JavaScript, but adds a vendored asset. Plain `fetch` is enough for
  the few dynamic parts (progress polling, form validation, plot loading).

**New dependencies** (justification required by the constitution): `fastapi`, `uvicorn`,
`jinja2`, `python-multipart` and `plotly` (runtime); `httpx` (tests, via the FastAPI test
client). They are an optional extra `boidrytwin[web]`, so the models and the CLI keep their
current dependencies.

## R2. Running simulations without blocking the app

**Decision**: one **worker process** next to the web server takes runs from a queue one at a
time (FR-010). It calls the existing `records.run` / `records.compare` unchanged and reports
progress through a small progress file per job. The web server never simulates itself.

**Rationale**:
- A run is CPU-bound for 10–40 s (feature 002). In the server process it would block requests
  through the GIL, and SC-006 asks for a responsive app during a coupled 24 h run.
- One worker matches "one at a time" and keeps runs at full speed (SC-006: at most 10 % slower).
- A separate process also isolates a crashing run from the app.

**Progress**: the simulators get an optional, read-only `progress` callback. They call it with
the furthest simulated time evaluated so far, at most once per second, and with the phase
(`initialising` for the steady-state search, `simulating`, `writing`). The callback does not
change the integration: no extra breakpoints, no changed steps. Results stay bit-identical
to the command line (SC-003). The worker writes it to `progress/<job>.json`.

**Alternatives considered**: a thread in the server (blocked by the GIL); a process pool
(parallel runs are not wanted, and they would slow each other); a task queue such as Celery
or RQ (needs a broker, far too heavy for one machine); splitting the integration into chunks
for progress (changes the solver steps, so the results would differ from the command line
and from earlier reruns).

## R3. App state on disk

**Decision**: plain files in an **app folder** (default `<runs>/.app/`), written atomically
(write to a temporary file, then rename):
- `queue.json`: jobs with id, kind, scenario, state, timestamps, run id and message;
- `progress/<job>.json`: phase, simulated time reached, duration;
- `whatif.json`: an index of what-if runs (run id → operator scenario, version, baseline run
  id, changed inputs);
- `actions.jsonl`: the action log (FR-021), one JSON line per action, also sent to the
  structured log.

Saved and operator scenarios are files in a **scenario folder** (default `scenarios/`), see
R5 and R6. The run folders are the existing feature-001/002 run folders, unchanged.

**Rationale**: the whole project is file-based (TOML, CSV, JSON); runs are already folders.
Files are inspectable, survive restarts (clarification Q5), and need no database. One
machine and one worker mean no concurrent writers beyond the server and the worker, and
atomic renames are enough.

**Restart** (FR-011): at start the server sets every `running` job to `interrupted` and every
`queued` job to `not_started`, and nothing starts on its own. The user can start or drop them.

**Alternatives considered**: SQLite (sturdy, but a second storage style next to the run
folders, and it isn't needed at this size); in-memory state (lost at restart, which violates
Q5).

## R4. Showing and editing scenarios

**Decision**: the app reads a scenario TOML into an **editable form model**: sections
(`time`, `ambient`, `boiler_house.fuel`, …, `dryer.geometry`, …), and in each section the keys
with their raw value and unit (`"45 %"` → value 45, unit `%`). Arrays of tables
(`[[boiler_house.heaters]]`) are shown as numbered sub-sections. Edits are written back into
the same TOML structure, and comments of untouched lines are kept as far as possible.
**Validation** always goes through `load_scenario` on the written file. Its
`ScenarioValidationError` issues (field, value, reason, allowed, location) are mapped back
to the form fields (FR-008, SC-004).

**Rationale**: the loader already holds every rule, every unit and every range. Copying them
into the UI would duplicate them and drift. A failed load returns all issues at once, with
the field names the form uses.

**Units in the form**: value and unit are separate inputs. The unit field offers the units the
example uses for that key and accepts any unit pint understands for the dimension. The loader
decides.

**Alternatives considered**: a JSON-schema form generated from pydantic models (the scenario
file is not the pydantic model: units, signals and time series are resolved by the loader);
editing the TOML as text (not usable by operators, and error-prone).

## R5. Step sequences (clarification Q1, FR-007a)

**Decision**: a step sequence is stored as a **time-series CSV file** in the feature-001
format (time and unit rows) next to the saved scenario, and referenced from the TOML as
`{ file = "...", column = "..." }`. The file is generated by the app, written once per
scenario save and never edited in place. A step at time t from value a to b becomes the rows
`(t, a)`, `(t + 1 s, b)`, the same pattern the examples use. The app keeps the sequence
itself in a small metadata table in the scenario folder so it can show it as steps again.

**Rationale**: the loader and the simulators already accept time series, so the command line
runs the scenario unchanged (FR-009, SC-003). There's no new scenario syntax and no loader
change.

**Alternatives considered**: a new `steps = [...]` syntax in the TOML (needs loader changes in
features 001/002 and a new contract); expanding steps into the TOML inline (not supported
by the loader).

## R6. Operator scenarios, releases and versions (clarifications Q3, Q4; FR-012–FR-015)

**Decision**: an operator scenario is a folder `scenarios/operator/<name>/` with numbered
versions `v<N>/`. Each version holds `scenario.toml` (frozen), its generated step files,
and `operator.toml`:
- the released inputs: key path (e.g. `boiler_house.fuel.moisture_wet_basis`), label, unit,
  minimum, maximum, and whether a step is allowed;
- the comparison outputs (default set of FR-014a, plus or minus the engineer's changes);
- the baseline run id, once the baseline has run.

Saving creates `v<N+1>` and queues its baseline (Q3). A what-if run copies the version's
scenario with the operator's values into the run's scenario file and records the version in
`whatif.json`.

**Release check** (FR-012): a released range is accepted only if the scenario loads with the
input at its minimum and at its maximum, so the twin's own valid ranges apply. Operator
values are checked against the released range in the server before the run is queued
(FR-013, SC-005). Everything else in the scenario is fixed by the version.

**Rationale**: frozen versions make every comparison exact (a what-if run differs from its
baseline only in the released inputs), and they make the history visible. Plain files keep
them usable from the command line too.

## R7. Plots, display units and export (FR-002–FR-005, FR-018a)

**Decision**:
- **Display units in one place** (FR-003): a table maps each result column's SI unit (from the
  unit row of the result CSV) to a display unit: K → °C, W → MW, kg/kg and mol/mol → %,
  kg/s stays kg/s except the product and fuel flows → t/h, Pa → kPa. The conversion uses the
  project's pint registry. Nothing else converts units.
- **Default plot sets** per subsystem (boiler house, dryer, controllers, oil heaters), as in
  the spec. Any other column can be added from a list.
- **Flags and warnings** are drawn as shaded periods on the affected plots: range warnings from
  the run record, flag columns from the results.
- **Several runs**: traces of the same column from several runs on one time axis, aligned on
  simulated time.
- **Export**: PNG through Plotly's built-in button. The CSV of exactly the plotted series is a
  server endpoint that writes the same values with a unit row (display units) and the run
  ids (SC-007).
- **Size**: a 24 h run at 1 min has 1441 samples, which is drawn as is. Longer runs are reduced
  for drawing only (min/max per pixel bucket) above 5000 points; the CSV export always has the
  full data.

## R8. Local-only access and the two views (clarification Q-FR-016)

**Decision**:
- The server binds to `127.0.0.1` only. It rejects requests whose `Host` header isn't
  `localhost`/`127.0.0.1` with its port (against DNS rebinding), and rejects state-changing
  requests whose `Origin` is not the app itself (against cross-site requests from other web
  pages in the same browser).
- The view (engineer or operator) is chosen on the start page and kept in a cookie. Every
  endpoint declares the views allowed to call it, and the server checks this on each request
  (FR-016). Operator calls are limited to listing and viewing runs, starting what-if runs
  within released ranges, and downloading.
- The view is a convenience, not a security boundary, until sign-in comes in a later feature.
  The per-endpoint permission table is the point where that feature attaches.

**Rationale**: a local web server is reachable from any web page the user visits in the same
browser. The Host and Origin checks close the known attacks without accounts.

## R9. Testing strategy (constitution I)

- **Unit tests**: form model (TOML ↔ fields, with comments kept), step-sequence CSV writer,
  display-unit table, release-range checks, queue state transitions, restart rules, the
  what-if difference table, the plot-data builder (values identical to the CSV, SC-007).
- **Contract tests**: every HTTP endpoint of [contracts/http-api.md](contracts/http-api.md)
  through the FastAPI test client (status codes, payloads, view permissions for each
  endpoint and view, Host/Origin rejection), the app-state file formats
  ([contracts/app-state.md](contracts/app-state.md)) and the `serve` CLI command.
- **Integration tests**: start a run from the app API with the worker running in-process, and
  check that the run folder equals a CLI run of the saved scenario (SC-003); queue order;
  progress; restart; operator what-if against its baseline; comparison upload against
  `records.compare` (FR-017).
- **Performance**: 200 runs listed and opened in < 3 s (SC-001); a coupled run through the
  worker at most 10 % slower than the CLI while the API answers in < 1 s (SC-006). Marker
  `benchmark`.
- **Browser**: a smoke test that the pages render and the plot script loads, without a full
  browser automation stack. SC-002 (operators finish a what-if in under 5 min) is a manual
  usability test, recorded in a checklist.

## R10. Starting the app

**Decision**: a new CLI command `boidrytwin serve [--runs runs] [--scenarios scenarios]
[--port 8765] [--no-browser]` starts the server and the worker, and opens the browser. If
the port is busy, it says so and exits with code 3. `Ctrl+C` stops both, and a run in
progress is then marked interrupted.
