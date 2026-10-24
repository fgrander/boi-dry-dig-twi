"""Balances close for representative scenarios (T065; SC-002)."""

import pytest

from boidrytwin import load_scenario
from boidrytwin.checks.balances import QUANTITIES
from boidrytwin.dryer.simulate import simulate

from .conftest import EXAMPLES


@pytest.mark.parametrize(
    "scenario", ["reference_constant.toml", "step_feed_moisture.toml", "heat_limited.toml"]
)
def test_balances_close(scenario: str) -> None:
    sim = simulate(load_scenario(EXAMPLES / scenario))
    report = sim.balance
    assert report.passed
    for q in ("dry_solids", "water", "gas"):
        assert abs(getattr(report, q).relative_residual) <= 0.001, q
    assert abs(report.energy.relative_residual) <= 0.01
    # in practice the residual is the solver tolerance, far below the requirement
    for q in QUANTITIES:
        assert abs(getattr(report, q).relative_residual) < 1e-4, q
