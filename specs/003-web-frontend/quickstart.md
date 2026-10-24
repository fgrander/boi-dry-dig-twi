# Quickstart: Validate the Local Web App

**Feature**: [spec.md](spec.md) | **Contracts**: [contracts/](contracts/)

Prerequisites: features 001 and 002 pass (`uv run pytest`); the web extra is installed with
`uv sync --all-groups --extra web`.

## 1. Quality gates

`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` and `uv run pytest` pass,
including the feature-001/002 suites, unchanged.

## 2. Start the app

`uv run boidrytwin serve --runs runs --scenarios scenarios`. Expected: `serving
http://127.0.0.1:8765` and the browser opens the view choice. A second `serve` on the same
port exits with code 3.

## 3. View runs (User Story 1)

Run `examples/boiler_house_only.toml`, `plant_reference.toml` and `oil_demand_step.toml` from
the CLI, then open `/runs` in the engineer view. Expected:
- all three are listed, with status and checks passed;
- the oil step run shows the `load_fraction` warning period shaded on the load plot;
- the plotted oil outlet temperature equals `boiler_results.csv` in °C (SC-007), and the
  downloaded CSV reproduces the plotted values;
- `/compare?runs=<plant>,<oil step>` overlays both runs.

## 4. Start a run (User Story 2)

In `/scenarios`, open `plant_reference`, change the fuel moisture to 50 %, add a step of the oil
return temperature to 231.6 °C at 06:00, save it as `plant_wet_fuel`, and start it. Expected:
- a value of 70 % moisture is rejected with field, reason and allowed range, and no run starts;
- the run shows progress on `/queue`, and `/runs` stays responsive (SC-006);
- `uv run boidrytwin rerun runs/<run_id>/run_record.json` prints `identical: true` (SC-003),
  and `uv run boidrytwin run scenarios/plant_wet_fuel.toml` runs from the CLI.

## 5. Operator what-if (User Story 3)

As engineer, create the operator scenario "Fuel and oil demand" from `plant_reference` with
fuel moisture 35–55 % and oil return temperature 220–260 °C released. Expected: its baseline is
queued and completes. Switch to the operator view and start a what-if run with 52 % moisture.
Expected:
- the form shows only the two released inputs; 60 % is refused with the range (SC-005);
- the what-if page shows the default outputs against the baseline with differences, and the
  summary (oil and drum inlet on set point, product moisture, new warnings);
- the operator view has no access to `/scenarios` (403 on the API).

Save a second version with another range: a new baseline is queued, and earlier what-if runs
still compare with version 1's baseline.

## 6. Restart (FR-011)

Queue three runs and stop the app with `Ctrl+C` while the first is running. Restart. Expected:
the first is `interrupted`, the others `not_started`, nothing runs until started, and each can
be started or dropped.

## 7. Comparison upload (User Story 4)

Upload `examples/synthetic_boiler_measured.csv` for `oil_demand_step`. Expected: the same biases
and pass/fail as `boidrytwin compare` (O₂ −0.0020, furnace +8.0 K, …), with measured and
predicted curves.

## 8. Performance (SC-001, SC-006)

`uv run pytest -m benchmark tests/performance/test_webapp_benchmark.py`. Expected: 200 runs
listed and one opened in < 3 s; a coupled 24 h run through the app at most 10 % slower than the
CLI, while the API answers in < 1 s.

## 9. Operator usability (SC-002, manual)

Five people who haven't used the app before each complete a what-if run from the operator
start page. Record the times in `checklists/usability.md`. Target: under 5 minutes in at least
4 of 5 trials.
