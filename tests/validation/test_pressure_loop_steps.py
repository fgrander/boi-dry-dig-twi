"""Pressure loop step responses in the coupled plant (T026; SC-004, acceptance US2-1, US2-2).

From the steady start of ``plant_recirculation.toml``, steps at 01:00 of the exhaust fan
speed (+/- 10 %), the oil demand and the feed moisture. Criteria: the damper moves the right
way, the mixing chamber pressure is back within 50 Pa of its set point in under 5 minutes, the
drum inlet is within 5 K after 5 minutes (fan steps) or 20 minutes (load and feed steps),
and the pressure is quiet (within 5 Pa) in the last hour.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from boidrytwin import load_scenario
from boidrytwin.plant.simulate import simulate_plant
from tests.integration.conftest import make_variant

STEP = pd.Timestamp("2026-01-01T01:00:00Z")
END = "2026-01-01T03:00:00Z"


def _series(tmp_path: Path, name: str, unit: str, before: float, after: float) -> str:
    csv = (
        f"time,value\nunit,{unit}\n2026-01-01T00:00:00Z,{before}\n2026-01-01T00:59:00Z,{before}\n"
        f"2026-01-01T01:00:00Z,{after}\n2026-01-02T00:00:00Z,{after}\n"
    )
    (tmp_path / f"{name}.csv").write_text(csv, encoding="utf-8")
    return f'{{ file = "{name}.csv", column = "value" }}'


def _run(tmp_path: Path, replace: dict[str, str]) -> pd.DataFrame:
    path = make_variant(tmp_path, "plant_recirculation.toml", end=END)
    text = path.read_text(encoding="utf-8")
    for old, new in replace.items():
        assert old in text, old
        text = new.join(text.rsplit(old, 1))
    path.write_text(text, encoding="utf-8")
    sim = simulate_plant(load_scenario(path))
    assert sim.dryer_results is not None
    return sim.dryer_results


def _settles(d: pd.DataFrame, inlet_after: float = 5.0) -> None:
    error = (d["mixing_chamber_pressure"] - d["mixing_chamber_pressure_setpoint"]).abs()
    after = error[d.index >= STEP + pd.Timedelta(minutes=5)]
    assert after.max() < 50.0, after.max()
    # the drum inlet loop (integral time 5 min) moves the fresh gas flow for a while; the
    # pressure must be quiet once it has settled, in the last hour
    late = d.loc[d.index >= STEP + pd.Timedelta(hours=1), "mixing_chamber_pressure"]
    assert np.ptp(late) < 5.0
    inlet = d["drum_inlet_gas_temperature"] - 813.15
    assert inlet[d.index >= STEP + pd.Timedelta(minutes=inlet_after)].abs().max() < 5.0
    assert not d["setpoint_not_reached"].any()


@pytest.mark.parametrize(("factor", "opens"), [(1.1, True), (0.9, False)])
def test_fan_speed_step(tmp_path: Path, factor: float, opens: bool) -> None:
    speed = _series(tmp_path, "speed", "rpm", 990, round(990 * factor, 1))
    d = _run(tmp_path, {'speed = "990 rpm"': f"speed = {speed}"})
    _settles(d)
    before = d.loc[d.index < STEP, "recirculation_damper_position"].iloc[-1]
    after = d["recirculation_damper_position"].iloc[-1]
    assert (after > before) if opens else (after < before)


def test_oil_demand_step(tmp_path: Path) -> None:
    oil = _series(tmp_path, "oil", "degC", 240, 231.6)
    # a load step moves the drum inlet for a while also without a recirculation (9.4 K peak in
    # plant_reference.toml); with it the peak is larger, but it is back within 5 K in 20 min
    d = _run(tmp_path, {'return_temperature = "240 degC"': f"return_temperature = {oil}"})
    _settles(d, inlet_after=20.0)


def test_feed_moisture_step(tmp_path: Path) -> None:
    feed = _series(tmp_path, "feed", "%", 50, 55)
    _settles(
        _run(tmp_path, {'moisture_wet_basis = "50 %"': f"moisture_wet_basis = {feed}"}),
        inlet_after=20.0,
    )
