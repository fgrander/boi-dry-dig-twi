"""Process state of a run at one time, for the process drawings (T057; FR-025)."""

import itertools
from typing import Any

import pandas as pd
import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.process_state import colour, snapshot
from boidrytwin.webapp.run_view import load_run


def _row(folder: Any, name: str, index: int) -> pd.Series:
    return pd.read_csv(folder / name, skiprows=[1]).iloc[index]


def test_coupled_snapshot_values(web_settings: Any, example_runs: dict[str, str]) -> None:
    folder = web_settings.runs_dir / example_runs["plant_reference"]
    state = snapshot(load_run(folder), "2026-01-01T01:00:00Z")
    assert state.time == "2026-01-01T01:00:00Z" and len(state.times) == 121
    b, d = state.boiler, state.dryer
    assert b is not None and d is not None
    row = _row(folder, "boiler_results.csv", 60)
    assert b["oil_supply"].value == pytest.approx(row["oil_outlet_temperature"] - 273.15)
    assert b["oil_supply"].unit == "°C"
    assert (
        b["fuel_feed"].value == pytest.approx(row["fuel_feed"] * 3.6)
        and b["fuel_feed"].unit == "t/h"
    )
    assert b["heat_to_oil"].value == pytest.approx(row["heat_to_oil"] / 1e6)
    assert b["oil_return"].value == pytest.approx(240.0)  # from the scenario at that time
    assert b["oil_flow"].value == pytest.approx(60.0)
    drow = _row(folder, "results.csv", 60)
    assert d["drum_inlet"].value == pytest.approx(drow["drum_inlet_gas_temperature"] - 273.15)
    assert d["product_moisture"].value == pytest.approx(100 * drow["product_moisture_wet_basis"])
    assert d["feed_flow"].value == pytest.approx(10.0)  # 10 t/h in the scenario


def test_heater_chain_is_counter_current(web_settings: Any, example_runs: dict[str, str]) -> None:
    state = snapshot(load_run(web_settings.runs_dir / example_runs["plant_reference"]), None)
    heaters = state.heaters
    assert [h.kind for h in heaters] == ["radiant", "convective", "convective"]
    assert heaters[0].gas_in.value == pytest.approx(state.boiler["furnace"].value)  # type: ignore[index]
    for a, b in itertools.pairwise(heaters):
        assert b.gas_in.value == pytest.approx(a.gas_out.value)  # gas: heater 1 → n
        assert a.oil_in.value == pytest.approx(b.oil_out.value)  # oil: heater n → 1
    assert heaters[-1].oil_in.value == pytest.approx(state.boiler["oil_return"].value)  # type: ignore[index]
    assert sum(h.duty.value for h in heaters) == pytest.approx(state.boiler["heat_to_oil"].value)  # type: ignore[index]
    assert state.bypass_after == 1


def test_latest_time_by_default_and_nearest_time(
    web_settings: Any, example_runs: dict[str, str]
) -> None:
    run = load_run(web_settings.runs_dir / example_runs["plant_reference"])
    assert snapshot(run, None).time == "2026-01-01T02:00:00Z"
    assert snapshot(run, "2026-01-01T00:30:20Z").time == "2026-01-01T00:30:00Z"


def test_boiler_only_has_no_dryer(web_settings: Any, example_runs: dict[str, str]) -> None:
    state = snapshot(load_run(web_settings.runs_dir / example_runs["boiler_house_only"]), None)
    assert state.boiler is not None and state.dryer is None and state.profile is None


def test_inputs_follow_time_series(web_settings: Any, example_runs: dict[str, str]) -> None:
    run = load_run(web_settings.runs_dir / example_runs["oil_demand_step"])
    before = snapshot(run, "2026-01-01T05:00:00Z").boiler
    after = snapshot(run, "2026-01-01T06:30:00Z").boiler
    assert before is not None and after is not None
    assert before["oil_return"].value == pytest.approx(240.0)
    assert after["oil_return"].value == pytest.approx(231.6)


def test_dryer_profile_used_when_present(web_settings: Any, tmp_path: Any) -> None:
    from boidrytwin import load_scenario
    from boidrytwin.records import run
    from tests.webapp_conftest import EXAMPLES, shortened

    path = shortened(EXAMPLES / "plant_reference.toml", tmp_path, end="2026-01-01T00:10:00Z")
    record = run(load_scenario(path), out_dir=web_settings.runs_dir, profiles=True)
    state = snapshot(load_run(web_settings.runs_dir / record.run_id), None)
    assert state.profile is not None and len(state.profile["gas_temperature"]) == 20
    assert state.profile["gas_temperature"][0] > state.profile["gas_temperature"][-1]


def test_colour_scale() -> None:
    assert colour(None, 0, 100) == "#9aa0a6"
    lo, hi = colour(0, 0, 100), colour(100, 0, 100)
    assert (
        lo != hi
        and lo.startswith("rgb(")
        and colour(-50, 0, 100) == lo
        and colour(500, 0, 100) == hi
    )
