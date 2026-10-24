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


@pytest.mark.benchmark
def test_recirculation_at_most_one_and_a_half_times_slower() -> None:
    """Feature 004, SC-005: the coupled run with recirculation against the same plant
    without it, both 24 h from their steady starts, on the same machine."""
    timings = {}
    for name in ("plant_reference.toml", "plant_recirculation.toml"):
        loaded = load_scenario(EXAMPLES / name)
        start = time.perf_counter()
        simulate_plant(loaded)
        timings[name] = time.perf_counter() - start
    ratio = timings["plant_recirculation.toml"] / timings["plant_reference.toml"]
    assert ratio <= 1.5, timings
