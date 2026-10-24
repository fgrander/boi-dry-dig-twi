# Data Model: Local Web App for the Plant Twin

**Feature**: [spec.md](spec.md) | **Research**: [research.md](research.md)

The app adds no simulation data. It reads the existing run folders (feature 001/002
run records and result CSVs) and scenario files, and keeps a few small state files of its
own ([contracts/app-state.md](contracts/app-state.md)). Values are SI internally; the
display units are applied only in the views (R7).

## 1. RunSummary (read from a run folder)

| Field | Type | Source |
|---|---|---|
| `run_id` | str | `run_record.json` |
| `scenario_name` | str | `run_record.scenario.name` |
| `created_at` | UTC datetime | `run_record.created_at` |
| `kind` | `dryer` \| `boiler` \| `coupled` | from the files present |
| `status` | `completed` \| `failed` \| `running` \| `queued` \| `not_started` \| `interrupted` | run record, or the job of the queue |
| `checks_passed` | bool \| None | `balance_report` / `plant_balance_report.passed`; the validation report if any |
| `warnings` | int | `range_warnings` |
| `flags` | dict[str, int] | `flags_summary` |
| `origin` | `cli` \| `app` \| `what_if` \| `baseline` \| `comparison` | queue and what-if index |
| `note` | str \| None | e.g. "unreadable run record", "newer record version" |

Rules: a folder without a readable run record is listed with a note (edge case), and never
stops the listing. The list is cached by folder modification time (SC-001).

## 2. RunView (one opened run)

- the summary, plus the result tables: `results.csv` (dryer) and/or `boiler_results.csv`, each
  with its unit row;
- the balance report: entries → quantities → inflow, outflow, storage change, residual,
  relative residual, tolerance, passed;
- the range warnings (quantity, limit type, limit, extreme value, period) and the flag
  columns, as periods;
- the profiles (`profiles.csv`) if present (FR-006);
- the comparison report and table (`validation_report.json`, `comparison.csv`) if present.

## 3. PlotRequest / PlotData

| Field | Type | Rule |
|---|---|---|
| `runs` | list[run_id] | 1 or more; same column plotted for each |
| `columns` | list[str] | must exist in the run's tables; default sets per subsystem |
| `display_unit` | per column | from the display-unit table (R7) |
| `series` | per run and column: times (UTC), values (display unit) | identical to the CSV values converted to display units (SC-007) |
| `periods` | flagged or out-of-range periods | from the warnings and flag columns |

Default sets: the boiler house (oil outlet temperature, fuel feed, O₂ dry measured,
furnace temperature, heat to the oil), the dryer (drum inlet temperature, product
moisture, exhaust temperature, evaporation rate), the controllers (all
`controller_output_*`, bypass position, dilution air flow).

## 4. ScenarioForm (editable view of a scenario file)

| Field | Type | Rule |
|---|---|---|
| `source` | path | an example (read-only), a saved scenario, or an operator scenario version |
| `sections` | ordered list of Section | as in the TOML file; arrays of tables numbered |
| Section.`fields` | list of Field | key, raw text, value, unit, kind (`quantity`, `number`, `text`, `choice`, `series_file`, `steps`) |
| Field.`issues` | list of ValidationIssue | mapped from `load_scenario` by field name |

Saving writes a new scenario file under a new name (examples are never overwritten), with its
generated step files, and records `derived_from`.

## 5. StepSequence (clarification Q1, FR-007a)

| Field | Type | Rule |
|---|---|---|
| `key` | scenario key path | the input must accept a time series |
| `unit` | str | one unit for all values |
| `start_value` | float | inside the input's allowed range |
| `steps` | list of (time offset or UTC time, value) | times strictly increasing, inside the scenario period; values inside the range |

Stored as a CSV `steps_<key>.csv` next to the scenario (R5). A step at t from a to b
becomes the rows (t, a), (t + 1 s, b).

## 6. OperatorScenario and Release (FR-012–FR-015)

**OperatorScenario**: `name`, `versions` (1, 2, …).

**OperatorVersion**:

| Field | Type | Rule |
|---|---|---|
| `version` | int | increasing, never reused |
| `created_at`, `created_by_view` | UTC datetime, `engineer` | |
| `scenario` | frozen scenario file (+ step files) | unchanged after save |
| `releases` | list of Release | at least one |
| `comparison_outputs` | list of column names | default set of FR-014a, adjusted |
| `baseline_job`, `baseline_run_id` | str \| None | queued at save; set when done |

**Release**:

| Field | Type | Rule |
|---|---|---|
| `key` | scenario key path | must exist in the scenario |
| `label` | str | ≤ 60 characters |
| `unit` | str | a unit of the input's dimension |
| `minimum`, `maximum` | float | minimum < maximum; the scenario loads with each (R6) |
| `allow_step` | bool | the input accepts a time series |

State: a version is `baseline pending` → `ready` (baseline completed) or `baseline failed`.
What-if runs are allowed in every state. Without a completed baseline, they are shown
without a comparison, with a note (edge case).

## 7. WhatIfRun (FR-014)

| Field | Type |
|---|---|
| `run_id`, `job_id` | str |
| `operator_scenario`, `version` | str, int |
| `baseline_run_id` | str \| None |
| `changes` | list of (key, value or steps, unit) |

**WhatIfComparison** (computed for display): for each comparison output, the baseline value
and the what-if value (final value and mean over the last hour, in display units), the
absolute and relative difference, plus the warnings and flags present only in the what-if
run. **Summary** (FR-015): oil on set point (yes/no), drum inlet on set point (coupled), the
product moisture, and the number of new warnings, in plain words.

## 8. Job (queue entry, FR-010, FR-011)

| Field | Type | Rule |
|---|---|---|
| `job_id` | str | unique |
| `kind` | `run` \| `baseline` \| `what_if` \| `comparison` | |
| `scenario_path` | path | the frozen file used for this job |
| `measured_path` | path \| None | comparison jobs |
| `state` | see below | |
| `queued_at`, `started_at`, `finished_at` | UTC datetime | |
| `run_id` | str \| None | set when the run folder exists |
| `message` | str \| None | the error of a failed run |
| `view` | `engineer` \| `operator` | who queued it |

State transitions:

```text
queued ──▶ running ──▶ completed
   │          ├──────▶ failed
   │          └─(app closed)─▶ interrupted ──(restart by user)──▶ queued
   └─(app closed)─▶ not_started ──(start by user)──▶ queued
                         └──(drop by user)──▶ dropped
```

A what-if job queued while its baseline is not yet done waits behind it (FIFO already
guarantees this, because the baseline is queued at save).

**Progress** (per running job): `phase` (`initialising`, `simulating`, `writing`),
`simulated_s`, `duration_s`, `updated_at`.

## 9. MeasuredUpload (FR-017, FR-022)

`file name`, `size`, `sha256`, `stored path` (kept unchanged, next to the comparison run), the
`scenario`, and the comparison `job_id`. Checks: a `.csv` extension, at most 50 MB, then
`read_measured` (the twin's rules) before queuing.

## 10. ActionLogEntry (FR-021)

`time` (UTC), `view`, `action` (`run_started`, `scenario_saved`, `operator_version_saved`,
`what_if_started`, `comparison_started`, `job_dropped`, `job_restarted`, `run_deleted`),
`target` (job, run, scenario, version), `details`.
