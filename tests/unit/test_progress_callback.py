"""Read-only progress callback of the simulators (T004; feature 003 research R2, FR-019)."""

import time
from pathlib import Path

import pytest

from boidrytwin import load_scenario
from boidrytwin.records import run
from tests.webapp_conftest import EXAMPLES, shortened

END = "2026-01-01T01:00:00Z"


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, float, float]] = []

    def __call__(self, phase: str, simulated_s: float, duration_s: float) -> None:
        self.calls.append((phase, simulated_s, duration_s, time.perf_counter()))


@pytest.mark.parametrize(
    ("example", "results", "steady"),
    [("reference_constant", "results.csv", False), ("plant_reference", "boiler_results.csv", True)],
)
def test_progress_is_read_only_and_ordered(
    tmp_path: Path, example: str, results: str, steady: bool
) -> None:
    path = shortened(EXAMPLES / f"{example}.toml", tmp_path, end=END)
    plain = run(load_scenario(path), out_dir=tmp_path / "a")
    rec = Recorder()
    started = time.perf_counter()
    watched = run(load_scenario(path), out_dir=tmp_path / "b", progress=rec)
    wall = time.perf_counter() - started

    # (a) bit-identical results
    a = (tmp_path / "a" / plain.run_id / results).read_bytes()
    b = (tmp_path / "b" / watched.run_id / results).read_bytes()
    assert a == b

    # (b) phases in order
    phases = [c[0] for c in rec.calls]
    order = [p for i, p in enumerate(phases) if i == 0 or phases[i - 1] != p]
    expected = ["initialising", "simulating", "writing"] if steady else ["simulating", "writing"]
    assert order == expected

    # (c) simulated time non-decreasing while simulating, ending at the duration
    sim = [c[1] for c in rec.calls if c[0] == "simulating"]
    assert sim == sorted(sim)
    assert sim[-1] == pytest.approx(3600.0)
    assert all(c[2] == pytest.approx(3600.0) for c in rec.calls)

    # (d) throttled: at most one call per second of wall time, plus phase changes
    assert len(rec.calls) <= int(wall) + 1 + len(order) + 1
