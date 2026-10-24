# Implementation Plan: Boiler House Model Supplying Flue Gas to the Dryer

**Branch**: `002-boiler-house-model` | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-boiler-house-model/spec.md`

## Summary

This feature adds a dynamic **boiler house**: a biomass furnace, then 3 thermal oil heaters in
series with a damper bypass, then flue gas to the dryer. It becomes a second `FlueGasSupply`
behind the feature-001 interface, and it can run alone or coupled with the unchanged drum
dryer in one **plant** integration. Model choices ([research.md](research.md)):

- lumped fuel-bed balances (Bauer/Böhler) with a feed delay, and complete-combustion
  stoichiometry from the fuel composition (VTT defaults, Channiwala–Parikh HHV);
- a well-stirred furnace zone with two refractory nodes and a radiant heater;
- convective heaters in counter-current cells (Žukauskas gas side, Gnielinski oil side,
  fouling), with Shell S2 thermal oil;
- continuous PI controllers with back-calculation anti-windup for three loops: fuel → oil
  282 °C, air → O₂, and a split range bypass/dilution → drum inlet temperature;
- exact mass, element and energy balances per subsystem, at the interface and for the whole
  plant.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: unchanged from feature 001 (numpy, scipy, pint, pydantic, pandas,
structlog); Cantera stays a test oracle only. No new runtime dependency.

**Storage**: files only (TOML scenarios, CSV time series, JSON run records)

**Testing**: pytest. Unit tests per physics module, contract tests (coupling, scenario
sections), integration tests (runs, edge cases), validation tests (hand calculations,
controller steps), benchmark.

**Target Platform**: Windows 11 and Linux workstations; offline

**Project Type**: Python library with the `boidrytwin` CLI (extended, no new command)

**Performance Goals**: coupled 24 h at 1-minute output in < 2 min (SC-007); boiler house
alone < 30 s

**Constraints**: the dryer and the interface code are unchanged; exact balances; deterministic;
smooth right-hand side (smooth saturation) for BDF

**Scale/Scope**: about 33 boiler house states plus 160 dryer states; one oil circuit; three
controllers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.1.0.

| Principle / rule | Pre-research | Post-design | How the design complies |
|---|---|---|---|
| I. Tests first, seen failing | ✅ | ✅ | `/speckit-tasks` orders tests before code; every FR maps to a test (table below) |
| I. Reference values with tolerances | ✅ | ✅ | combustion and boiler hand calculations, Cantera oracle for the adiabatic temperature, controller step criteria |
| I. Contract tests for interfaces | ✅ | ✅ | `tests/contract/test_plant_coupling.py` (interface equality, swap test), scenario sections |
| II. Boundary validation, units, UTC, missing data explicit | ✅ | ✅ | the feature-001 loader extended to `[boiler_house]` sections, same issue format |
| II. Reproducible runs | ✅ | ✅ | run record with controller settings and states; `rerun` unchanged |
| III. Assumptions, valid range, accuracy; flags | ✅ | ✅ | research R9 ranges; `docs/boiler_house.md`; RangeWarnings and flags |
| III. Automated validation | ✅ | ✅ | `tests/validation/`; `compare` with boiler outputs |
| III. **Subsystems separate, coupled only via typed interfaces** | ✅ | ✅ | `boiler_house` and `dryer` never import each other; `plant` couples through `FlueGasSupply` and `Signal` ([plant-coupling.md](contracts/plant-coupling.md)) |
| III. **Coupled runs check balances across every interface and the whole plant** | ✅ | ✅ | `PlantBalanceReport`: boiler house, oil circuit, dryer, interface, plant |
| IV. Structured logging, metrics, errors with context | ✅ | ✅ | events `plant_run_started`, `controller_saturated`, `checks_completed`; solver stats |
| Stack and dependencies | ✅ | ✅ | no new runtime dependency |

**Result**: PASS. No violations; Complexity Tracking is not needed.

### Requirement → test mapping

| Requirement | Test location |
|---|---|
| FR-001, FR-012, SC-006 | `tests/contract/test_plant_coupling.py` |
| FR-002, FR-004, SC-001 | `tests/unit/boiler_house/test_fuel.py`, `test_combustion.py`, `tests/validation/test_combustion_hand_calculation.py` |
| FR-003, FR-009 (O₂), FR-010 | `tests/unit/control/test_pi.py`, `test_split_range.py`, `tests/integration/test_boiler_controllers.py` |
| FR-005, FR-005a, FR-006, FR-007 | `tests/unit/boiler_house/test_heaters.py`, `test_thermal_oil.py`, `test_bypass.py` |
| FR-008, SC-002 | `tests/validation/test_boiler_hand_balance.py`, `test_boiler_settles.py` |
| FR-009 (oil, drum inlet), SC-004, SC-005 | `tests/validation/test_controller_steps.py` |
| FR-011 | `tests/unit/boiler_house/test_ranges.py`, `tests/integration/test_boiler_edge_cases.py` |
| FR-013, SC-003 | `tests/unit/checks/test_plant_balances.py`, `tests/integration/test_plant_balances_close.py` |
| FR-014 | `tests/integration/test_interface_timeseries.py` |
| FR-015 | `tests/contract/test_scenario_boiler.py` |
| FR-016 | `tests/integration/test_plant_rerun.py` |
| FR-017, SC-008 | `tests/unit/validation/test_compare_boiler.py` (synthetic) |
| SC-007 | `tests/performance/test_plant_benchmark.py` |

## Project Structure

### Documentation (this feature)

```text
specs/002-boiler-house-model/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/  plant-coupling.md, scenario-file-boiler.md, cli.md
├── checklists/ requirements.md
└── tasks.md    (/speckit-tasks)
```

### Source Code (additions)

```text
src/boidrytwin/
├── properties/
│   ├── fuel.py              # compositions, HHV/LHV, stoichiometry
│   └── thermal_oil.py       # Shell S2 and Therminol 66 properties, limits, enthalpy
├── control/
│   ├── pi.py                # continuous PI, back-calculation, smooth saturation, manual mode
│   └── split_range.py       # bypass/dilution mapping
├── boiler_house/            # must not import boidrytwin.dryer
│   ├── config.py            # BoilerHouseConfiguration (FIELDS with two ranges), heaters list
│   ├── state.py             # BoilerHouseState packing, JSON
│   ├── fuel_bed.py          # feed delay, bed water and dry fuel
│   ├── furnace.py           # well-stirred zone, refractory, radiant heater
│   ├── heaters.py           # convective cells, Žukauskas/Gnielinski, film temperature
│   ├── bypass.py            # split and mixing
│   └── model.py             # BoilerHouseModel: rhs, outputs, storage, jac_sparsity
├── plant/
│   ├── coupled_supply.py    # CoupledFlueGasSupply (FlueGasSupply), ControlledSignal
│   ├── model.py             # Plant: assembles boiler, controllers and dryer
│   └── simulate.py          # plant / boiler-only simulation, steady state, outputs
├── checks/plant_balances.py # PlantBalanceReport
├── scenario/                # loader and schema extended for [boiler_house] sections
└── records.py               # run folders extended (boiler results, interface CSVs)

scripts/tune_controllers.py  # step tests → FOPDT → SIMC defaults
docs/boiler_house.md         # equations, assumptions, valid range, calibration parameters
examples/                    # boiler_house_only, oil_demand_step, plant_reference, ...
tests/                       # unit/boiler_house, unit/control, contract, integration, validation, performance
```

**Structure Decision**: same single package. The new `boiler_house` and `plant` packages
follow the `interface`/`dryer` separation of feature 001: `plant` is the only place that knows
both subsystems.

## Implementation phasing (input for `/speckit-tasks`)

1. **Foundational**: fuel properties and stoichiometry, thermal oil properties, PI and split
   range controllers (each test-first).
2. **User Story 1 (P1)**: fuel bed, furnace, heaters, bypass, the boiler house model,
   controllers in the boiler loop, the boiler-only simulation, scenario sections, run outputs,
   hand-balance and controller-step validation, the tuning script.
3. **User Story 2 (P1)**: plant coordinator, coupled supply, drum inlet split range, plant
   balances, interface time series, swap test, benchmark.
4. **User Story 3 (P3)**: comparison with boiler outputs, synthetic dataset.
5. **Polish**: `docs/boiler_house.md`, README, quickstart run.

## Risks

| Risk | Mitigation |
|---|---|
| No plant data; many VERIFY defaults (flame emissivity, fouling, bed time constants) | configurable, cited defaults; plausibility checks against Lienz; DCS data request listed in research.md |
| Controller interaction and limit cycles in the coupled plant | SIMC from the twin's own step tests; loop speeds separated by 3–5×; split-range anti-windup on combined limits |
| Smooth saturation biases outputs near limits | ε = 0.5 % of span; exact mode for validation runs |
| Stiffness from fast O₂ and gas states with slow refractory | quasi-static gas in the heaters; BDF with banded/block Jacobian; early benchmark |
| The uncalibrated dryer (feature 001) makes coupled results unrealistic | report both; calibration as a separate feature once data exists |

## Complexity Tracking

No constitution violations; nothing to justify.
