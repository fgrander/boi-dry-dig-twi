"""Boiler house edge cases from spec.md (T024)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.errors import ScenarioValidationError
from boidrytwin.plant.simulate import simulate_plant

from .conftest import make_variant

SIX = "2026-01-01T06:00:00Z"


def _sim(
    tmp_path: Path, replace: dict[str, str], end: str = SIX, files: dict[str, str] | None = None
):  # type: ignore[no-untyped-def]
    path = make_variant(
        tmp_path, base="boiler_house_only.toml", replace=replace, end=end, files=files
    )
    return simulate_plant(load_scenario(path))


def _step_csv(col: str, unit: str, a: float, b: float, at: str = "02:00") -> str:
    return (
        f"time,{col}\nunit,{unit}\n2026-01-01T00:00:00Z,{a}\n2026-01-01T{at}:00Z,{a}\n"
        f"2026-01-01T{at[:3]}01:00Z,{b}\n2026-01-01T06:00:00Z,{b}\n"
    )


def test_fuel_trip(tmp_path: Path) -> None:
    # oil loop in manual with zero-ish feed after 2 h: the oil cools, flagged; the run continues
    sim = _sim(tmp_path, {
        'mode = "automatic"\nsetpoint = "282 degC"': 'mode = "manual"\nmanual_output = { file = "f.csv", column = "f" }\nsetpoint = "282 degC"',
    }, files={"f.csv": _step_csv("f", "kg/s", 1.56, 0.47)})  # fmt: skip
    oil = sim.results["oil_outlet_temperature"].to_numpy()
    assert oil[-1] < oil[100] - 10.0
    assert sim.results["setpoint_not_reached"].iloc[-1]


def test_oil_demand_above_capacity(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {'return_temperature = "240 degC"': 'return_temperature = "180 degC"',
                          'kind = "steady_state"': 'kind = "cold"'}, end="2026-01-01T12:00:00Z")  # fmt: skip
    res = sim.results
    assert res["controller_saturated"].iloc[-1]
    assert res["oil_outlet_temperature"].iloc[-1] < 555.15 - 2.0
    flagged = res["setpoint_not_reached"].to_numpy()
    first = int(np.argmax(flagged))
    outside = np.abs(res["oil_outlet_temperature"].to_numpy() - 555.15) > 2.0
    start = int(np.argmax(outside[: first + 1]))
    assert sim.times[first] - sim.times[start] >= 600 - 60  # only after the 10-minute hold


def test_oil_demand_near_zero_min_load(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {'return_temperature = "240 degC"': 'return_temperature = "278 degC"'})
    assert sim.results["load_out_of_range"].iloc[-1]


def test_oil_flow_stop_while_hot(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {'mass_flow = "60 kg/s"': 'mass_flow = { file = "m.csv", column = "m" }'},
               files={"m.csv": _step_csv("m", "kg/s", 60, 3)})  # fmt: skip
    assert sim.results["oil_limit"].iloc[-1]
    assert any(w.quantity in ("oil_film_temperature", "oil_bulk_temperature", "oil_velocity")
               for w in sim.range_warnings)  # fmt: skip


def test_wet_fuel_flags_combustion(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {'moisture_wet_basis = "45 %"': 'moisture_wet_basis = "62 %"'})
    assert sim.results["combustion_out_of_range"].iloc[-1]
    assert any(w.quantity == "fuel_moisture_wet_basis" for w in sim.range_warnings)


def test_air_amount_with_automatic_o2_rejected(tmp_path: Path) -> None:
    replace = {
        'relative_humidity = "60 %"\n\n[boiler_house.furnace]': 'relative_humidity = "60 %"\nmass_flow = "9 kg/s"\n\n[boiler_house.furnace]'
    }
    with pytest.raises(ScenarioValidationError):
        load_scenario(make_variant(tmp_path, base="boiler_house_only.toml", replace=replace))
