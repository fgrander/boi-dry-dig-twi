"""Balances with a recirculation (T014; FR-012, SC-003, acceptance US1-4)."""

from pathlib import Path

import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from tests.recirculation import with_recirculation

END = "2026-01-01T06:00:00Z"
STEPS = (
    "time,value\nunit,{unit}\n2026-01-01T00:00:00Z,{a}\n2026-01-01T02:59:00Z,{a}\n"
    "2026-01-01T03:00:00Z,{b}\n2026-01-02T00:00:00Z,{b}\n"
)


def _check(path: Path) -> None:
    sim = simulate(load_scenario(path))
    assert sim.balance.passed, sim.balance.to_dict()
    for q in ("dry_solids", "water", "gas"):
        assert abs(getattr(sim.balance, q).relative_residual) <= 1e-3
    assert abs(sim.balance.energy.relative_residual) <= 1e-2
    assert sim.loop_balance is not None and sim.loop_balance["passed"], sim.loop_balance
    f = sim.results
    # the stack takes the fresh gas, the drum more than that
    assert (f["drum_outlet_mass_flow"] >= f["exhaust_mass_flow"]).all()


def test_constant(tmp_path: Path) -> None:
    _check(with_recirculation(tmp_path, end=END))


def test_manual_damper_step(tmp_path: Path) -> None:
    (tmp_path / "pos.csv").write_text(STEPS.format(unit="%", a=30, b=70), encoding="utf-8")
    manual = 'mode = "manual"\nmanual_output = { file = "pos.csv", column = "value" }'
    _check(with_recirculation(tmp_path, replace={'mode = "automatic"': manual}, end=END))


def test_setpoint_step(tmp_path: Path) -> None:
    (tmp_path / "sp.csv").write_text(STEPS.format(unit="Pa", a=-200, b=-300), encoding="utf-8")
    step = 'setpoint = { file = "sp.csv", column = "value" }'
    path = with_recirculation(tmp_path, replace={'setpoint = "-200 Pa"': step}, end=END)
    _check(path)
    sim = simulate(load_scenario(path))
    p = sim.results["mixing_chamber_pressure"]
    assert p.loc["2026-01-01T02:55:00Z"] == pytest.approx(-200.0, abs=10.0)
    assert p.iloc[-1] == pytest.approx(-300.0, abs=10.0)
