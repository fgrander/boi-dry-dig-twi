# Quickstart run record (T082)

**Date**: 2026-10-24 | **Platform**: Windows 11 Pro 10.0.26200, Python 3.12.15, uv 0.12.24
**Guide**: [quickstart.md](../quickstart.md) | **Commit**: after `66a8bc5` (Polish phase)

| Step | Command(s) | Expected | Result |
|---|---|---|---|
| 1 Quality gates | `ruff check`, `ruff format --check`, `mypy src`, `pytest` | all pass | ✅ all pass; 274 tests |
| 2 Interface validation | `validate reference_constant.toml` / `invalid_flue_gas.toml`; `pytest tests/contract -k rejection` | `OK`; exit 1 with field, value, reason, allowed; catalogue passes | ✅ `OK` exit 0; 3 issues with line numbers, exit 1; 15 rejection tests pass |
| 3 Standalone run | `run reference_constant.toml --profiles` | run folder with 4 files; settles; hand balance | ✅ 4 files; balances closed (energy 1.6e-8 relative); hand-balance test passes; final moisture 31.7 %, exhaust 295 °C, specific energy 7.6 MJ/kg |
| 4 Step response | `run step_feed_moisture.toml`; `test_step_response.py` | gradual change, settles | ✅ completed, balances passed; 3 step tests pass |
| 5 Balances and ranges | `run out_of_range_inlet.toml`; `run heat_limited.toml` | warning with limit and period, exit 0; `heat_limited` set | ✅ drum inlet warning 08:00-10:00 (limit 873.15 K), exit 0; `heat_limited` in 1429 of 1441 samples |
| 6 Reproducibility | `rerun runs/<id>/run_record.json` | `identical: true` | ✅ `identical: true` |
| 7 Source swap | `test_swap_sources` | same results | ✅ bit-identical |
| 8 Comparison | `compare reference_timeseries.toml synthetic_measured.csv` | known deviations reproduced, exclusions listed | ✅ bias −0.0039 / +2.02 K (expected −0.004 / +2 K), 8 excluded each, both pass |
| 9 Performance | `pytest -m benchmark` | 24 h < 60 s, steady point < 5 s | ✅ 3 benchmarks pass (24 h ≈ 10 s, steady point ≈ 3.5 s) |

## Findings during the run

- **Fixed**: `condensation_risk` was set in every sample of the reference run (1441 of
  1441) because it also fired when cold chips near the inlet were below the dew point of the
  humid gas, which is normal. It now refers to the exhaust only (FR-012); regression test
  `tests/integration/test_condensation_flag.py`. After the fix: 1 sample (t = 0).
- The edge-case test for an exhaust near its dew point had only passed because of that
  inner-cell flag; its scenario (exhaust 106 K above the dew point) was replaced by one whose
  exhaust is 2.7 K above it.
- Every cold-start run reports one `exhaust_dew_point_margin` warning at t = 0 (the drum is
  full of ambient air close to its dew point). This is correct by definition and documented
  in `docs/model.md`.
- `heat_limited.toml` has no dilution air, so its drum inlet (650 °C) is above the validated
  600 °C for the whole run; the range warning is correct.

## SC-001 (set-up time)

Not measurable by the implementing agent: SC-001 is about a process engineer using the tool
for the first time. To be checked by a user with [quickstart.md](../quickstart.md) and the
[examples](../../../examples/README.md).
