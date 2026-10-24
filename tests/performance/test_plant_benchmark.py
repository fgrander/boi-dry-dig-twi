"""Plant performance (T048; SC-007). Run with ``pytest -m benchmark``."""

import time

import pytest

from boidrytwin import load_scenario
from boidrytwin.plant.simulate import simulate_plant
from tests.integration.conftest import EXAMPLES


@pytest.mark.benchmark
def test_coupled_24_hours_under_120_seconds() -> None:
    loaded = load_scenario(EXAMPLES / "plant_reference.toml")
    start = time.perf_counter()
    sim = simulate_plant(loaded)
    elapsed = time.perf_counter() - start
    assert len(sim.results) == 24 * 60 + 1
    assert elapsed < 120.0, f"{elapsed:.1f} s"


@pytest.mark.benchmark
def test_boiler_alone_24_hours_under_30_seconds() -> None:
    loaded = load_scenario(EXAMPLES / "boiler_house_only.toml")
    start = time.perf_counter()
    simulate_plant(loaded)
    elapsed = time.perf_counter() - start
    assert elapsed < 30.0, f"{elapsed:.1f} s"
