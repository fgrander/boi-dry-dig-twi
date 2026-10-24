"""Regression: condensation_risk refers to the exhaust only (quickstart run, T082)."""

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate

from .conftest import EXAMPLES


def test_reference_run_flags_condensation_only_at_cold_start() -> None:
    res = simulate(load_scenario(EXAMPLES / "reference_constant.toml")).results
    flagged = res["condensation_risk"].astype(bool)
    # exhaust 295 °C vs. dew point 60 °C in steady operation: no risk; only t = 0, when the
    # drum is full of ambient air near its dew point
    assert flagged.sum() <= 2
    assert not flagged.iloc[10:].any()
