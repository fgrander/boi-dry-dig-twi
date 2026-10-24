"""Boiler house settles to its own steady state (T022, FR-008)."""

from pathlib import Path

import pytest

from boidrytwin import load_scenario
from boidrytwin.plant.simulate import simulate_plant
from tests.integration.conftest import make_variant

OUTPUTS = ["oil_outlet_temperature", "furnace_temperature", "o2_dry", "fuel_feed", "heat_to_oil"]


def test_cold_start_settles_to_the_steady_state(tmp_path: Path) -> None:
    # the refractory bulk is the slowest store (44 MJ/K over about 1060 W/K, ~11.5 h):
    # 4 days are about 8 time constants
    cold = simulate_plant(load_scenario(make_variant(
        tmp_path, base="boiler_house_only.toml", replace={'kind = "steady_state"': 'kind = "cold"'},
        end="2026-01-05T00:00:00Z",
    )))  # fmt: skip
    steady = simulate_plant(load_scenario(make_variant(
        tmp_path, base="boiler_house_only.toml", name="s.toml", end="2026-01-01T01:00:00Z"
    )))  # fmt: skip
    for col in OUTPUTS:
        assert cold.results[col].iloc[-1] == pytest.approx(steady.results[col].iloc[0], rel=1e-3), (
            col
        )
