# Quickstart: Validate the Boiler House and the Coupled Plant

**Feature**: [spec.md](spec.md) | **Contracts**: [contracts/](contracts/) | **Date**: 2026-10-24

Prerequisite: feature 001 is installed and passes (`uv sync --all-groups`, `uv run pytest`).

## 1. Quality gates

`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` and `uv run pytest` all
pass. That includes the feature-001 suite unchanged: the dryer is not modified.

## 2. Combustion reference (SC-001)

`uv run pytest tests/validation/test_combustion_hand_calculation.py`. Expected: flue gas
composition within 0.1 percentage points and flow within 0.1 % of the hand calculation for
wood chips at 45 % moisture and 7 % O₂ dry; adiabatic temperature consistent with the Cantera
oracle.

## 3. Boiler house only (User Story 1)

`uv run boidrytwin run examples/boiler_house_only.toml --out runs`. Expected:
- `boiler_results.csv` with all data-model columns;
- oil outlet at 282 °C ± 0.5 K in steady operation (SC-004);
- the steady energy split matches the hand balance (SC-002,
  `tests/validation/test_boiler_hand_balance.py`);
- plant balance report passed (SC-003).

## 4. Oil demand step (SC-004)

`uv run boidrytwin run examples/oil_demand_step.toml --out runs`. Expected: a 20 % step in oil
heat demand at 06:00; the fuel feed rises and the oil outlet returns within ±2 K within 30 min
with an overshoot ≤ 5 K (`tests/validation/test_controller_steps.py`).

## 5. Coupled plant (User Story 2)

`uv run boidrytwin run examples/plant_reference.toml --out runs --profiles`. Expected:
- dryer results as in feature 001, plus `boiler_results.csv`, `flue_gas_to_dryer.csv` and
  `dilution_air.csv`;
- drum inlet temperature within ±5 K of its set point (SC-005);
- balances passed for the boiler house, oil circuit, dryer, interface and plant;
- dryer specific energy within the plausibility band of 2.8–3.5 MJ/kg of water
  (research R11). This holds only once the dryer is calibrated; see feature 001.

## 6. Source swap (SC-006)

`uv run pytest tests/contract/test_plant_coupling.py::test_swap_boiler_for_timeseries`.
Expected: dryer results within 0.1 % when the boiler house is replaced by its own interface
time series.

## 7. Edge cases

`uv run pytest tests/integration/test_boiler_edge_cases.py`. Covered: fuel trip, oil demand
above capacity (fuel saturated, oil below set point, flagged), oil flow stop (film
temperature flagged), drum inlet set point unreachable, wet fuel (combustion temperature
flagged).

## 8. Performance (SC-007)

`uv run pytest -m benchmark tests/performance/test_plant_benchmark.py`. Expected: coupled 24 h
at 1-minute output in < 2 min.
