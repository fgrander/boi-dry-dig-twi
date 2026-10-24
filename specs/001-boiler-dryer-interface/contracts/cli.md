# Contract: Command-Line Interface

**Covers**: User Stories 1–4, FR-013 – FR-017 | **Entities**: [data-model.md §4–5](../data-model.md)

Executable: `boidrytwin` (installed by the package; also `uv run boidrytwin`).
All commands write structured logs to stderr (JSON by default, `--log-format console` for
humans) and results to files. Exit codes: `0` success, `1` validation errors (input rejected),
`2` run completed but checks failed (balances or validation tolerances), `3` solver or
internal failure.

## `boidrytwin validate <scenario.toml>`

Validates the scenario and all referenced time series without running (User Story 1).

- stdout: `OK` and a summary of the normalised inputs (SI units), or the list of issues.
- `--json`: machine-readable result `{ "valid": bool, "issues": [ {field, value, reason, allowed, location} ] }`.

## `boidrytwin run <scenario.toml> [--out runs/] [--profiles]`

Runs a simulation (User Stories 2–3).

Creates `runs/<run_id>/` with:

| File | Content |
|---|---|
| `run_record.json` | [RunRecord](../data-model.md#runrecord) |
| `results.csv` | DryerResults time series; second row holds units |
| `profiles.csv` | per-cell profiles (only with `--profiles`) |
| `final_state.json` | final DryerState, usable as an explicit initial state |

stdout: run id, status, balance pass/fail, number of range warnings and flagged periods.

## `boidrytwin rerun <runs/<run_id>/run_record.json>`

Reruns a recorded run from its stored, normalised scenario and input hashes, and reports
whether the results are identical (SC-006). Fails with exit code 1 if an input file hash no
longer matches.

## `boidrytwin compare <scenario.toml> <measured.csv> [--tolerances tol.toml]`

Runs the model with measured inputs and compares outputs with measurements (User Story 4).

Writes `runs/<run_id>/validation_report.json` ([ValidationReport](../data-model.md#validationreport))
and `comparison.csv` (time, predicted, measured, deviation, included/excluded per output).

Default tolerances (SC-003): product outlet moisture ±1 percentage point (wet basis),
exhaust temperature ±5 K, pass if ≥ 90 % of steady-operation samples are within tolerance.

## Library API

The CLI is a thin layer over the library; everything is also callable from Python:

```python
from boidrytwin import load_scenario, run, compare

scenario = load_scenario("scenario.toml")   # raises ScenarioValidationError
record = run(scenario, out_dir="runs")       # returns RunRecord
record, report = compare(scenario, "measured.csv")  # RunRecord and ValidationReport
```
