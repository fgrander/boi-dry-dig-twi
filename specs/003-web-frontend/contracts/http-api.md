# Contract: HTTP Interface of the Web App

**Covers**: FR-001–FR-022 | **Entities**: [data-model.md](../data-model.md)

The app serves HTML pages (`GET`, server-rendered) and a JSON interface under `/api/` that the
pages use and the tests call. All responses are UTF-8. Times are ISO 8601 UTC. Numbers in JSON
are display units with the unit given next to them, except where noted as SI.

## Request rules (all endpoints)

- Only `127.0.0.1` is served. A `Host` that isn't `localhost:<port>` or `127.0.0.1:<port>` →
  `421`.
- State-changing requests (`POST`, `DELETE`): an `Origin` other than the app's own → `403`.
- The view comes from the cookie `view` (`engineer` | `operator`). Without it, pages redirect to
  `/` (view choice) and API calls return `401`. An endpoint not allowed for the view → `403`
  with `{"error": "not allowed in the operator view"}`.
- Validation errors → `422` with `{"issues": [{"field", "value", "reason", "allowed",
  "location"}]}`, the feature-001 issue format.

## Pages

| Path | Views | Content |
|---|---|---|
| `/` | both | view choice; links to runs, scenarios, operator scenarios |
| `/runs` | both | run list (FR-001), search and filters |
| `/runs/{run_id}` | both | run view: plots, balances, warnings, flags, profiles, comparison (FR-002–FR-006, FR-018) |
| `/compare?runs=a,b` | both | several runs plotted together (FR-005) |
| `/scenarios` | engineer | examples and saved scenarios |
| `/scenarios/{name}` | engineer | scenario form (FR-007, FR-007a) |
| `/operator` | both | operator scenarios |
| `/operator/{name}` | both | operator form with only the released inputs (engineer: also the release settings) |
| `/whatif/{run_id}` | both | what-if comparison with its baseline and summary (FR-014, FR-015) |
| `/queue` | both | queue with states and progress |

## JSON interface

| Method and path | Views | Request | Response |
|---|---|---|---|
| `GET /api/runs` | both | `?q=&status=&kind=&limit=&offset=` | `{"runs": [RunSummary], "total": n}` |
| `GET /api/runs/{id}` | both | | RunView metadata: summary, balances, warnings, flag periods, files |
| `GET /api/runs/{id}/plot` | both | `?columns=a,b` (default set if omitted) | PlotData: per column the unit, times, values, periods |
| `GET /api/plot` | both | `?runs=a,b&columns=c` | PlotData for several runs |
| `GET /api/runs/{id}/plot.csv` | both | same as plot | CSV: `time, <run>:<column>…`, a unit row, the run ids in a header comment |
| `GET /api/runs/{id}/profiles` | both | `?time=` | profile per cell at the nearest output time |
| `DELETE /api/runs/{id}` | engineer | `?confirm=true` required | `204`; logged |
| `GET /api/scenarios` | engineer | | examples (read-only) and saved scenarios |
| `GET /api/scenarios/{name}` | engineer | | ScenarioForm |
| `POST /api/scenarios/validate` | engineer | ScenarioForm (edited) | `200 {"valid": true}` or `422` issues mapped to fields |
| `POST /api/scenarios` | engineer | `{"name", "derived_from", "form"}` | `201 {"name"}`; `409` if the name exists; `422` issues |
| `POST /api/jobs` | engineer | `{"scenario": name}` | `202 {"job_id"}`; `422` if the scenario does not load |
| `GET /api/jobs` | both | | `{"jobs": [Job + progress]}` in queue order |
| `GET /api/jobs/{id}` | both | | Job + progress |
| `POST /api/jobs/{id}/start` | engineer, and operator for its own `what_if` jobs | | `202`; only from `not_started` or `interrupted` |
| `POST /api/jobs/{id}/drop` | engineer, and operator for its own `what_if` jobs | | `200`; only from `queued` or `not_started` |
| `GET /api/operator` | both | | operator scenarios with versions and baseline states |
| `GET /api/operator/{name}` | both | `?version=` (default latest) | releases, comparison outputs, baseline state |
| `POST /api/operator/{name}/versions` | engineer | `{"scenario", "releases", "comparison_outputs"}` | `201 {"version", "baseline_job_id"}`; `422` if a release range fails R6 |
| `POST /api/operator/{name}/whatif` | both | `{"version", "values": {key: value or steps}}` | `202 {"job_id"}`; `422` with the released range for any value outside it or any non-released key (SC-005) |
| `GET /api/whatif/{run_id}` | both | | WhatIfComparison and summary |
| `GET /api/whatif/{run_id}.csv` | both | | the comparison table as CSV with units |
| `GET /api/runs/{id}/comparison` | both | | the comparison report and, per output, times, predicted and measured values (display units), included flags and reasons; 404 without a comparison |
| `POST /api/comparisons` | engineer | multipart: `scenario`, `measured` file | `202 {"job_id"}`; `422` with the `read_measured` issues; `413` above 50 MB |

## Guarantees

- A job's run folder is produced by `records.run` or `records.compare`, the same functions as
  the CLI. Rerunning its `run_record.json` from the CLI gives `identical: true` (SC-003).
- No endpoint changes a run folder written by the twin, except `DELETE` (whole folder,
  engineer, confirmed). Uploads are stored next to their comparison run, unchanged.
- Each state-changing call writes one action log entry (FR-021).
