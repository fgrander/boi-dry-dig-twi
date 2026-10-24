# Quickstart: Validate the Flue Gas Interface and Dryer Model

**Feature**: [spec.md](spec.md) | **Contracts**: [contracts/](contracts/) | **Date**: 2026-10-24

This guide lists the end-to-end checks that prove the feature works. Each step names the
requirement or success criterion it verifies.

## Prerequisites

- Python 3.12+ and `uv` installed.
- Repository checked out on branch `001-boiler-dryer-interface`.

```powershell
uv sync --all-groups        # installs runtime and dev/test dependencies
```

## 1. Quality gates

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Expected: all pass. The test suite includes unit, contract, integration and validation tests
(see [plan.md § Project Structure](plan.md#project-structure)).

## 2. Interface validation (User Story 1, FR-003/FR-004, SC-005)

```powershell
uv run boidrytwin validate examples/reference_constant.toml
uv run boidrytwin validate examples/invalid_flue_gas.toml
```

Expected:
- the reference scenario prints `OK` with all values in SI units;
- the invalid scenario exits with code 1 and lists each issue with field, value, reason and
  allowed range (missing unit, composition not summing to 100 %, negative flow);
- `uv run pytest tests/contract -k rejection` runs the full rejection catalogue of
  [flue-gas-interface.md](contracts/flue-gas-interface.md#validation-errors-boundary).

## 3. Standalone dynamic run (User Story 2, FR-007 – FR-011)

```powershell
uv run boidrytwin run examples/reference_constant.toml --out runs --profiles
```

Expected:
- a `runs/<run_id>/` folder with `run_record.json`, `results.csv`, `profiles.csv` and
  `final_state.json` ([cli.md](contracts/cli.md));
- starting from `cold_empty`, the outputs rise and settle to a steady state; the final
  product moisture matches the hand-calculated reference case within its tolerance
  (`tests/validation/test_reference_steady_state.py`);
- the run summary reports the specific energy use per kg of water evaporated.

## 4. Step response (FR-009, SC-004)

```powershell
uv run boidrytwin run examples/step_feed_moisture.toml --out runs
```

Expected: after the step in feed moisture at t = 6 h, the outlet moisture and exhaust
temperature change gradually and settle to a new steady state; the settling time is checked
by `tests/validation/test_step_response.py`.

## 5. Balances and range checks (User Story 3, FR-012/FR-013, SC-002)

- In `run_record.json`, `balance_report` shows each of dry solids, water and gas within
  0.1 % and energy within 1 %, all `passed: true`.
- ```powershell
  uv run boidrytwin run examples/out_of_range_inlet.toml --out runs
  ```
  Expected: run completes; `range_warnings` lists the drum inlet gas temperature with the
  limit and the affected period; exit code 0 (warnings are not failures).
- ```powershell
  uv run boidrytwin run examples/heat_limited.toml --out runs
  ```
  Expected: `heat_limited` flag set for the affected period; product moisture higher than
  in the reference case.

## 6. Reproducibility (FR-014, SC-006)

```powershell
uv run boidrytwin rerun runs/<run_id>/run_record.json
```

Expected: `identical: true`.

## 7. Source swap (FR-005, SC-008)

```powershell
uv run boidrytwin run examples/reference_timeseries.toml --out runs
```

Expected: same results as step 3 (the time series holds the same constant values); verified
automatically by `tests/contract/test_flue_gas_supply.py::test_swap_sources`.

## 8. Comparison with measurements (User Story 4, FR-016, SC-003)

```powershell
uv run boidrytwin compare examples/reference_timeseries.toml examples/synthetic_measured.csv
```

Expected: `validation_report.json` with per-output bias, MAE, RMSE and the fraction within
tolerance; values marked `missing` or `bad` in the CSV are listed under `excluded` and not
counted. The synthetic dataset has known deviations, which the report reproduces.

## 9. Performance (SC-007)

```powershell
uv run pytest tests/performance -m benchmark
```

Expected: 24 h at 1-minute resolution completes in under 60 s of wall-clock time.
