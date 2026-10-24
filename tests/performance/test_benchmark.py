"""Performance (T048; SC-007). Run with ``pytest -m benchmark``."""

import time
from pathlib import Path

import pytest

from boidrytwin import load_scenario
from boidrytwin.dryer.simulate import simulate
from tests.integration.conftest import EXAMPLES, make_variant


@pytest.mark.benchmark
def test_24_hours_at_one_minute_under_60_seconds() -> None:
    loaded = load_scenario(EXAMPLES / "reference_constant.toml")
    assert loaded.spec.dryer is not None and loaded.spec.dryer.n_cells == 20
    start = time.perf_counter()
    sim = simulate(loaded)
    elapsed = time.perf_counter() - start
    assert len(sim.results) == 24 * 60 + 1
    assert elapsed < 60.0, f"{elapsed:.1f} s"


@pytest.mark.benchmark
def test_time_series_input_under_60_seconds() -> None:
    start = time.perf_counter()
    simulate(load_scenario(EXAMPLES / "step_feed_moisture.toml"))
    assert time.perf_counter() - start < 60.0


@pytest.mark.benchmark
def test_single_steady_operating_point_under_5_seconds(tmp_path: Path) -> None:
    path = make_variant(
        tmp_path,
        replace={'kind = "cold_empty"': 'kind = "steady_state"'},
        end="2026-01-01T00:01:00Z",
    )
    loaded = load_scenario(path)
    start = time.perf_counter()
    simulate(loaded)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"{elapsed:.1f} s"
