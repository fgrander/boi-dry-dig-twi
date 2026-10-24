# Quickstart run: feature 003 (T048)

**Date**: 2026-10-24 | **Branch**: `003-web-frontend` | **Guide**: [quickstart.md](../quickstart.md)

Steps §2–§7 were run by a script against a real `boidrytwin serve` process (its own worker
process, HTTP on `127.0.0.1`), with full-length 24 h example runs. §1 and §8 are the test gates;
§9 is manual.

- [x] **§1 Quality gates**: see T049 below.
- [x] **§2 Start**: prints `serving http://127.0.0.1:8811`. A second `serve` on the same port exits
  with code 3 ("port 8811 is in use; choose another with --port").
- [x] **§3 View runs**: the three CLI runs are listed in 0.07 s, all with checks passed.
  - The oil step run shows the period of its `load_fraction max 1.0` warning on the load plot.
  - The plotted oil outlet equals `boiler_results.csv` converted to °C (exactly), and the CSV
    download reproduces the plotted values.
  - `/compare` overlays two runs (200).
- [x] **§4 Start a run**:
  - 70 % fuel moisture is rejected (422) with field `boiler_house.fuel.moisture_wet_basis`,
    reason "out of range", allowed "0 ≤ w < 0.70".
  - `plant_wet_fuel` (50 % moisture, oil return step to 231.6 °C at 06:00) is saved, and its run
    completes. The API answered in at most 0.03 s while it ran.
  - `boidrytwin rerun` prints `identical: true`, and `boidrytwin run scenarios/plant_wet_fuel.toml`
    gives byte-identical `results.csv` and `boiler_results.csv` (SC-003).
- [x] **§5 Operator what-if**: the case "Fuel and oil demand" (moisture 35–55 %, oil return
  220–260 °C) is created, and its baseline completes.
  - In the operator view, 60 % is refused with "outside the released range 35–55 %" (SC-005),
    and `/api/scenarios` answers 403.
  - The what-if run at 52 % gives the summary "Oil outlet is on its set point. Drum inlet is on
    its set point. Product moisture at the end: 30.6 % (wet basis). No new warnings."
  - Compared with the baseline: fuel feed 5.02 → 6.38 t/h; evaporation 2.51 → 2.80 t/h;
    product moisture 33.3 → 30.6 %; oil 282 °C, O₂ 7 %, drum inlet 540 °C and heat to the oil
    7.83 MW unchanged.
  - Wetter fuel gives more flue gas, which the drum inlet loop passes to the dryer at 540 °C,
    so the product gets drier.
  - Version 2 queues its own baseline, and the first what-if run still compares with
    version 1's baseline.
- [x] **§6 Restart**: three runs are queued and the app is stopped during the first. After the
  restart they are `interrupted`, `not_started`, `not_started`, and they are unchanged 3 s
  later (nothing starts on its own). Dropping a not-started run gives 200, restarting the
  interrupted one gives 202, and it completes.
- [x] **§7 Comparison upload**: `synthetic_boiler_measured.csv` for `oil_demand_step` gives biases
  O₂ −0.0020, furnace +8.0 K, gas after heater 3 −3.9 K, oil outlet +0.99 K, all passed: the
  same as `boidrytwin compare`.
- [x] **§8 Performance** (`pytest -m benchmark tests/performance/test_webapp_benchmark.py`):
  - 200 runs are listed and one is opened with its default plots in under 3 s (SC-001).
  - The first read of 200 just-written folders costs about 2.7 s more on this Windows machine
    (on-access scanning of new files). The test reads them once before timing, and the
    listing itself takes 0.16–0.18 s.
  - A coupled 24 h run through the worker takes at most 1.1 × the CLI time, and the API answers
    in under 1 s throughout (SC-006).
- [ ] **§9 Operator usability (SC-002)**: manual test with plant operators, still to do. The
  protocol is in [usability.md](usability.md).

Not yet checked: the pages by eye in a browser. The pages and their scripts were exercised over
HTTP only (no browser automation or Node.js on this machine).

## T049 final quality gate

- [x] `ruff check .`: all checks passed. `ruff format --check .`: 197 files formatted.
- [x] `mypy` (strict): no issues in 77 source files.
- [x] `pytest`: 553 passed, 7 deselected (benchmarks), in about 20 min. This includes the
  feature-001/002 suites, whose tests are unchanged.
- [x] `pytest -m benchmark`: 7 passed (features 001, 002 and 003).
