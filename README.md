# boi-dry-dig-twi

Digital twin of a boiler house and the wood chip rotary drum dryer it feeds. This first
feature provides:

- a validated, unit-aware **flue gas supply interface** between a boiler house and a dryer,
  fed for now by constant values or a time series (a boiler house model follows later);
- a **dynamic model of a directly heated, co-current rotary drum dryer** for wood chips,
  with mass and energy balance checks, range warnings and reproducible run records;
- a **comparison** of model results with measured time series.

> The model is not yet calibrated or validated against plant data; see
> [docs/model.md](docs/model.md#drum-dryer-model).

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --all-groups
```

## Quickstart

```powershell
uv run boidrytwin validate examples/reference_constant.toml
uv run boidrytwin run examples/reference_constant.toml --profiles
uv run boidrytwin rerun runs/<run_id>/run_record.json
uv run boidrytwin compare examples/reference_timeseries.toml examples/synthetic_measured.csv
```

Each run writes `runs/<run_id>/` with `run_record.json`, `results.csv` (second row: units),
optional `profiles.csv` and `final_state.json`. Exit codes: 0 success, 1 input rejected,
2 checks failed (balances or validation tolerances), 3 solver failure. Logs are JSON lines
on stderr (`--log-format console` for humans).

Scenarios are TOML files where every physical value carries its unit, e.g.
`temperature = "650 degC"`; see
[contracts/scenario-file.md](specs/001-boiler-dryer-interface/contracts/scenario-file.md)
and the [examples](examples/README.md). The full end-to-end check list is
[quickstart.md](specs/001-boiler-dryer-interface/quickstart.md).

From Python:

```python
from boidrytwin import load_scenario, run

record = run(load_scenario("examples/reference_constant.toml"), out_dir="runs")
```

## Development

```powershell
uv run ruff check .; uv run ruff format --check .; uv run mypy
uv run pytest                 # unit, contract, integration and validation tests
uv run pytest -m benchmark    # performance (SC-007)
```

Work follows spec-driven development with GitHub Spec Kit: the project
[constitution](.specify/memory/constitution.md) and, for this feature,
[spec](specs/001-boiler-dryer-interface/spec.md),
[plan](specs/001-boiler-dryer-interface/plan.md),
[research](specs/001-boiler-dryer-interface/research.md) and
[tasks](specs/001-boiler-dryer-interface/tasks.md). Tests are written before the code.

## Layout

```text
src/boidrytwin/
  interface/    flue gas supply interface (no dependency on the dryer)
  properties/   flue gas, water and wood properties
  dryer/        configuration, transport, heat transfer, drying, model, simulator
  scenario/     scenario and time series loading and validation
  checks/       balances and range warnings
  validation/   comparison with measurements
  records.py    run folders, rerun, compare
  cli.py        command-line interface
tests/          unit, contract, integration, validation, performance
examples/       example scenarios and data
docs/model.md   model equations, assumptions, calibration parameters
```
