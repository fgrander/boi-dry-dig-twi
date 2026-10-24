"""Dynamic model settles to its own steady state (T042; FR-010)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from tests.integration.conftest import make_variant

OUTPUTS = [
    "product_moisture_wet_basis",
    "exhaust_temperature",
    "evaporation_rate",
    "product_temperature",
]


def test_cold_start_settles_and_matches_steady_state(tmp_path: Path) -> None:
    cold = simulate(load_scenario(make_variant(tmp_path, end="2026-01-04T00:00:00Z")))
    res = cold.results
    # settled: relative change over the last 6 hours below 1e-4 per hour
    for col in OUTPUTS:
        tail = res[col].iloc[-361:].to_numpy()
        change_per_hour = abs(tail[-1] - tail[0]) / abs(tail[-1]) / 6.0
        assert change_per_hour < 1e-4, col

    steady = simulate(
        load_scenario(
            make_variant(
                tmp_path,
                name="steady.toml",
                replace={'kind = "cold_empty"': 'kind = "steady_state"'},
                end="2026-01-01T01:00:00Z",
            )
        )
    )
    for col in OUTPUTS:
        assert steady.results[col].iloc[0] == pytest.approx(res[col].iloc[-1], rel=1e-3), col
        # starting in steady state, nothing moves
        assert np.ptp(steady.results[col].to_numpy()) <= 1e-3 * abs(res[col].iloc[-1]), col
