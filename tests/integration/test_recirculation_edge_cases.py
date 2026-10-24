"""Edge cases of the recirculation (T029; FR-008, FR-011, acceptance US2-4).

Dryer-only runs of the reference dryer from the recirculation example: the loop and its
warnings are the same in a coupled run (the loop lives in the dryer, research R1).
"""

from pathlib import Path

import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import SimulationResult, simulate
from tests.recirculation import with_recirculation

END = "2026-01-01T02:00:00Z"


def _sim(tmp_path: Path, replace: dict[str, str]) -> SimulationResult:
    return simulate(load_scenario(with_recirculation(tmp_path, replace=replace, end=END)))


def _quantities(sim: SimulationResult) -> set[str]:
    return {w.quantity for w in sim.range_warnings}


def test_fan_too_weak(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {'speed = "990 rpm"': 'speed = "290 rpm"'})
    d = sim.results
    assert d["recirculation_damper_position"].iloc[-1] == pytest.approx(0.0, abs=0.01)
    assert d["setpoint_not_reached"].any() and d["controller_saturated"].any()
    found = _quantities(sim)
    assert {"mixing_chamber_overpressure", "recirculation_backflow"} <= found
    assert "recirculation.exhaust_fan.speed" in found


def test_fan_too_strong(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {'speed = "990 rpm"': 'speed = "1080 rpm"',
                          'open_mass_flow = "18 kg/s"': 'open_mass_flow = "6 kg/s"'})  # fmt: skip
    d = sim.results
    assert d["recirculation_damper_position"].iloc[-1] == pytest.approx(1.0, abs=0.01)
    assert d["setpoint_not_reached"].any()
    assert d["mixing_chamber_pressure"].iloc[-1] < -250.0


def test_share_above_its_maximum(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {'max_share = "70 %"': 'max_share = "20 %"'})
    assert "recirculation_share" in _quantities(sim)


def test_condensation_risk_at_the_drum_inlet(tmp_path: Path) -> None:
    sim = _sim(tmp_path, {'dew_point_margin = "10 K"': 'dew_point_margin = "100 K"',
                          'temperature = "650 degC"': 'temperature = "130 degC"'})  # fmt: skip
    margin = sim.results["drum_inlet_gas_temperature"] - sim.results["drum_inlet_dew_point"]
    assert margin.min() < 100.0
    assert "drum_inlet_condensation_risk" in _quantities(sim)


def test_fan_off_its_curve(tmp_path: Path) -> None:
    curve = 'curve = [["15 m^3/s", "2300 Pa"], ["25 m^3/s", "2000 Pa"], ["35 m^3/s", "1400 Pa"]]'
    narrow = 'curve = [["5 m^3/s", "2300 Pa"], ["12 m^3/s", "2000 Pa"], ["20 m^3/s", "1400 Pa"]]'
    sim = _sim(tmp_path, {curve: narrow})
    assert "exhaust_fan_curve" in _quantities(sim)
