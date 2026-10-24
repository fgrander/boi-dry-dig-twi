"""Coupled plant edge cases from spec.md (T044)."""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from boidrytwin import load_scenario
from boidrytwin.interface.flue_gas import T_MAX
from boidrytwin.plant.simulate import PlantSimulationResult, _interface_warnings, simulate_plant

from .conftest import make_variant

SP = 'setpoint = "540 degC"'
END = "2026-01-01T03:00:00Z"


def _sim(tmp_path: Path, replace: dict[str, str]) -> PlantSimulationResult:
    return simulate_plant(
        load_scenario(make_variant(tmp_path, base="plant_reference.toml", replace=replace, end=END))
    )


def test_drum_setpoint_unreachable(tmp_path: Path) -> None:
    # bypass fully open and no dilution air; a large feed on a well-exchanging dryer
    replace = {
        SP: 'setpoint = "1100 degC"',
        'mass_flow_wet = "10 t/h"': 'mass_flow_wet = "30 t/h"',
        "heat_transfer_multiplier = 1.0": "heat_transfer_multiplier = 5.0",
    }
    sim = _sim(tmp_path, replace)
    last = sim.results.iloc[-1]
    assert last["bypass_position"] > 0.99 and last["dilution_air_flow"] == 0.0
    assert last["controller_saturated"] and last["setpoint_not_reached"]
    assert sim.dryer_results is not None and sim.dryer_results["heat_limited"].iloc[-1]


def test_dilution_above_its_maximum(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {SP: 'setpoint = "250 degC"'})
    last = sim.results.iloc[-1]
    assert abs(last["dilution_air_flow"] - 6.0) < 1e-6
    assert last["controller_saturated"] and last["setpoint_not_reached"]


def test_oil_demand_drop_gives_less_heat_to_the_dryer(tmp_path: Path) -> None:
    ref = _sim(tmp_path, {})
    drop = simulate_plant(load_scenario(make_variant(
        tmp_path, base="plant_reference.toml", name="drop.toml", end=END,
        replace={'return_temperature = "240 degC"': 'return_temperature = "255 degC"'},
    )))  # fmt: skip
    assert ref.dryer_results is not None and drop.dryer_results is not None
    assert drop.results["fuel_feed"].iloc[-1] < ref.results["fuel_feed"].iloc[-1]
    assert (
        drop.dryer_results["heat_supplied"].iloc[-1]
        < 0.9 * ref.dryer_results["heat_supplied"].iloc[-1]
    )


def test_outlet_outside_interface_range_is_a_warning() -> None:
    index = pd.date_range(datetime(2026, 1, 1, tzinfo=UTC), periods=5, freq="1min", name="time")
    frame = pd.DataFrame(
        {"temperature": [900.0, T_MAX + 10, T_MAX + 20, 900.0, 900.0]}, index=index
    )
    warnings = _interface_warnings(frame)
    assert len(warnings) == 1
    assert (
        warnings[0].quantity == "flue_gas_to_dryer_temperature" and warnings[0].limit_type == "max"
    )
