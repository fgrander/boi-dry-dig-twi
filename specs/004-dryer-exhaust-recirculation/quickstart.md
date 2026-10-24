# Quickstart: Dryer Exhaust Gas Recirculation

**Feature**: [spec.md](spec.md) | Validation guide; commands from the repository root.

## Prerequisites

`uv sync` done; features 001–003 work (`uv run pytest -q` passes on the branch start).

## 1. Existing runs are unchanged (SC-001, FR-005)

```powershell
uv run pytest tests/integration/test_recirculation_off.py -q
```

Expected: every example scenario without `[recirculation]` gives the stored results of
before this feature, column by column; a recirculation with the damper held closed (manual,
0 %, no leakage) equals the run without recirculation within the solver tolerance.

## 2. Dryer-only run with recirculation (US1, SC-002, SC-003)

```powershell
uv run boidrytwin validate examples/dryer_recirculation.toml
uv run boidrytwin run examples/dryer_recirculation.toml --out runs
```

Expected:
- validation passes with no issues;
- the run completes; `results.csv` has the columns of
  [contracts/results-recirculation.md](contracts/results-recirculation.md);
- at the end (steady state) `mixing_chamber_pressure` is within 50 Pa of −200 Pa;
  `drum_inlet_humidity` is higher and `drum_inlet_x_O2` lower than in
  `examples/reference_constant.toml`; `exhaust_mass_flow` < `drum_outlet_mass_flow`;
- all balances, including `recirculation_loop`, pass.

Hand calculation: `uv run pytest tests/validation/test_recirculation_hand_mix.py -q`
(case in `tests/validation/recirculation_case.md`): drum inlet temperature, humidity and O₂
within 0.5 K, 1 %, 1 % of the hand mix (SC-002).

## 3. Coupled plant with pressure control (US2, SC-004, SC-005)

```powershell
uv run boidrytwin run examples/plant_recirculation.toml --out runs
uv run pytest tests/validation/test_pressure_loop_steps.py tests/performance/test_plant_benchmark.py -q
```

Expected:
- mixing chamber pressure within 50 Pa and drum inlet within 5 K of their set points after
  start-up;
- after a 10 % step in `recirculation.exhaust_fan.speed` the pressure is back in its band in
  under 5 minutes, the damper opens when the draft gets stronger;
- no `setpoint_not_reached` flag in the reference case; the flag appears in the edge case with
  the fan too weak (`tests/integration/test_recirculation_edge_cases.py`), together with
  `mixing_chamber_overpressure`;
- run time ≤ 1.5 × `plant_reference.toml` (benchmark).

## 4. Web app (US3, SC-006)

```powershell
uv run boidrytwin serve
```

1. Engineer view → Scenarios → copy `plant_reference` → **Rückführung hinzufügen**.
2. Set `recirculation.controller.setpoint` to −250 Pa as steps (−200 Pa, then −250 Pa after
   6 h), save (the check passes), start the run.
3. Open the run → process drawings: plant and dryer show the mixing chamber, the return line
   with damper position, recirculated flow and temperature, the fan and the pressure, in
   German and (after switching) in English; `plant_reference` runs show no return line.
4. Enter `max_share = 120 %` → the check reports the problem at that field.
5. Formulas page: the mixing, damper, fan, resistance and pressure formulas are listed with
   their sources.

Automated: `uv run pytest tests/contract/webapp tests/integration/webapp -q`.

## 5. Quality gates

```powershell
uv run pytest -q
uv run ruff check . ; uv run ruff format --check . ; uv run mypy
```
