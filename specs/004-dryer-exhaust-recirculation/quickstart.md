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

## Notes: acceptance scenarios against their tests (T047)

| Scenario | Test | State |
|---|---|---|
| US1-1 no recirculation → results unchanged | `tests/integration/test_recirculation_off.py` (9 examples, stored baselines) | ✅ |
| US1-2 share 0 % → equal to no recirculation | `test_recirculation_run.py::test_closed_damper_without_leakage_equals_no_recirculation` | ✅ |
| US1-3 fixed share at steady state: inlet cooler, more humid, less O₂ | `test_recirculation_run.py::test_example_runs_from_steady_state`, `tests/validation/test_recirculation_hand_mix.py` | ✅ |
| US1-4 share as a step: response without a balance jump | `test_recirculation_balances.py::test_manual_damper_step`, `::test_setpoint_step` | ✅ |
| US1-5 balances of every run | `test_recirculation_balances.py` (all), `recirculation_loop` in every record | ✅ |
| US2-1 coupled reference: pressure and drum inlet on set point | `test_plant_recirculation.py::test_joint_steady_state` | ✅ |
| US2-2 disturbances: damper the right way, pressure back in its band | `tests/validation/test_pressure_loop_steps.py` (fan speed ±10 %, oil demand, feed moisture) | ✅ with the deviations below |
| US2-3 controller in manual | `test_plant_recirculation.py::test_manual_damper_follows_its_steps` | ✅ |
| US2-4 draft the damper cannot hold → flag and warning | `test_recirculation_edge_cases.py::test_fan_too_weak`, `::test_fan_too_strong` | ✅ |
| US3-1 drawings with the recirculation, German and English | `tests/contract/webapp/test_diagrams.py::test_recirculation_is_drawn`, `test_i18n.py::test_recirculation_drawings_in_german` | ✅ |
| US3-2 no return line without a recirculation | same tests (no recirculation ids in `plant_reference`) | ✅ |
| US3-3 share outside its range reported at the field | `tests/contract/webapp/test_recirculation_api.py::test_share_out_of_range_reported_at_the_field` | ✅ |
| SC-005 run time ≤ 1.5 × | `tests/performance/test_plant_benchmark.py` (1.39 ×) | ✅ |
| SC-006 add, release, what-if | `test_recirculation_api.py` | ✅ |

The automated web app tests are in `tests/contract/webapp` and `tests/unit/webapp` (there is no
`tests/integration/webapp`).
