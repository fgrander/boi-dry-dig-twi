# Quickstart run: feature 002 (T062)

**Date**: 2026-10-24 | **Branch**: `002-boiler-house-model` | **Guide**: [quickstart.md](../quickstart.md)

Results of running every quickstart step. Numbers are from the reference examples, which
are illustrative values, not plant data.

- [x] **§1 Quality gates**: `ruff check`, `ruff format --check`, `mypy` (strict) and
  `pytest` pass; the feature-001 suite is unchanged and passes. See T063 below.
- [x] **§2 Combustion reference (SC-001)**: `tests/validation/test_combustion_hand_calculation.py`
  passes. The flue gas composition is within 0.1 percentage points, the flow within 0.1 % and
  λ within 0.2 % of the hand calculation (wood chips, 45 % moisture, 7 % O₂ dry). The
  adiabatic temperature agrees with the Cantera oracle
  (`tests/unit/boiler_house/test_furnace.py`).
- [x] **§3 Boiler house only**: `boidrytwin run examples/boiler_house_only.toml` exits 0 and
  writes `boiler_results.csv` with all data-model columns. The oil outlet holds 282 °C (max
  deviation 0.000 K over 24 h; target ±0.5 K), the hand balance passes (SC-002), and the plant
  balance report passes (max |relative residual| 4·10⁻¹⁶). Wall time 7.6 s.
- [x] **§4 Oil demand step (SC-004)**: `boidrytwin run examples/oil_demand_step.toml` exits 0.
  The oil is back within ±2 K 12 min after the step (target 30 min; the test limit
  4(τ_c + θ) is 19.6 min), it dips by 7.1 K first, and it overshoots by 0.3 K (limit 5 K).
  Two findings:
  - After the step the furnace runs at 114 % of its 15 MW rating (fuel 1.77 kg/s), flagged
    by a `load_fraction` range warning. The base point is at 89 % load, so +20 % oil demand
    exceeds the rating.
  - For 10 min after the step, the fuel loop is saturated at its 2.2 kg/s limit, which is
    141 % of rated fuel power at 45 % moisture. The example's output limit allows overfiring.
- [x] **§5 Coupled plant**: `boidrytwin run examples/plant_reference.toml --profiles` exits 0
  and writes `results.csv`, `profiles.csv`, `boiler_results.csv`, `flue_gas_to_dryer.csv`,
  `dilution_air.csv`, `final_state.json` and `dryer_final_state.json`.
  - The drum inlet holds 540 °C (max deviation 0.000 K; SC-005 ±5 K), with the bypass 1.9 %
    open and no dilution.
  - All balances pass: boiler house, oil circuit, dryer, interface (residual exactly 0)
    and plant (max |relative residual| 1.6·10⁻¹⁵).
  - The dryer's specific energy is 7.46 MJ/kg of water, which is **outside** the plausibility
    band of 2.8–3.5 MJ/kg. As the quickstart notes, that band applies only once the dryer is
    calibrated; the uncalibrated reference dryer uses little of the heat (exhaust 288 °C).
    Not a coupling issue.
- [x] **§6 Source swap (SC-006)**: `tests/contract/test_plant_coupling.py::test_swap_boiler_for_timeseries`
  passes. Across the 06:00 oil step, the dryer results agree within 0.1 % when it is fed the
  boiler's own interface time series.
- [x] **§7 Edge cases**: `tests/integration/test_boiler_edge_cases.py` and
  `tests/integration/test_plant_edge_cases.py` pass: fuel trip, oil demand above capacity,
  near-zero demand, oil flow stop, wet fuel, drum inlet set point unreachable (dryer
  heat-limited), dilution at its maximum, oil demand drop, outlet outside the interface
  range.
- [x] **§8 Performance (SC-007)**: `pytest -m benchmark` passes. The coupled 24 h run at a
  1-minute output interval takes 35.4 s (limit 120 s), the boiler house alone 18.2 s (limit 30 s).
- [x] **Comparison (US3, SC-008)**: `boidrytwin compare examples/oil_demand_step.toml
  examples/synthetic_boiler_measured.csv` reproduces the known offsets (O₂ bias −0.0020,
  furnace +8.0 K, gas after heater 3 −3.9 K, oil +0.99 K), and all four outputs pass their
  default tolerances.

## T063 final quality gate

- [x] `ruff check .`: all checks passed. `ruff format --check .`: all 143 files formatted,
  after reformatting one test file.
- [x] `mypy` (strict): no issues in 54 source files.
- [x] `pytest`: 409 passed, 5 deselected (the benchmarks), in about 14 min. This includes the
  feature-001 suite, whose tests are unchanged.
- [x] `pytest -m benchmark`: 5 passed (feature 001 and feature 002).
