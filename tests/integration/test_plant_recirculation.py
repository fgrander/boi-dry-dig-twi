"""Coupled plant with exhaust recirculation (T025, T027; US2, research R6)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.plant.model import Plant
from boidrytwin.plant.simulate import _Scaled, simulate_plant, steady_state
from tests.integration.conftest import EXAMPLES, make_variant

EXAMPLE = EXAMPLES / "plant_recirculation.toml"


def test_joint_steady_state() -> None:
    loaded = load_scenario(EXAMPLE)
    plant = Plant(loaded)
    ts = loaded.spec.time
    z = steady_state(plant, 0.0, ts.rtol, ts.atol)
    sys = _Scaled(plant, 0.0, frozen_at=0.0)
    acc = np.zeros(sys.n_acc)
    rates = sys.rhs(0.0, np.concatenate([z, acc]) / sys.scale)[: sys.n]
    assert np.max(np.abs(rates)) < 1e-6


def test_starts_without_a_jump_and_balances_close(tmp_path: Path) -> None:
    path = make_variant(tmp_path, "plant_recirculation.toml", end="2026-01-01T01:00:00Z")
    sim = simulate_plant(load_scenario(path))
    d = sim.dryer_results
    assert d is not None
    first = d.iloc[:11]
    assert np.ptp(first["drum_inlet_gas_temperature"]) < 2.0
    assert np.ptp(first["mixing_chamber_pressure"]) < 20.0
    assert sim.balance.passed, sim.balance.to_dict()
    assert sim.loop_balance is not None and sim.loop_balance["passed"]
    assert sim.controller_settings["mixing_chamber_pressure"]["action"] == "reverse"


def test_manual_damper_follows_its_steps(tmp_path: Path) -> None:
    csv = (
        "time,position\nunit,%\n2026-01-01T00:00:00Z,40\n2026-01-01T00:29:00Z,40\n"
        "2026-01-01T00:30:00Z,60\n2026-01-02T00:00:00Z,60\n"
    )
    (tmp_path / "pos.csv").write_text(csv, encoding="utf-8")
    path = make_variant(tmp_path, "plant_recirculation.toml", end="2026-01-01T01:00:00Z")
    head, tail = path.read_text(encoding="utf-8").rsplit("[recirculation.controller]", 1)
    manual = 'mode = "manual"\nmanual_output = { file = "pos.csv", column = "position" }'
    tail = tail.replace('mode = "automatic"', manual, 1)
    path.write_text(head + "[recirculation.controller]" + tail, encoding="utf-8")
    sim = simulate_plant(load_scenario(path))
    d = sim.dryer_results
    assert d is not None
    assert d["recirculation_damper_position"].iloc[0] == pytest.approx(0.4)
    assert d["recirculation_damper_position"].iloc[-1] == pytest.approx(0.6)
    assert not d["setpoint_not_reached"].any()
