"""Two runs of the same scenario give bit-identical results (T046; FR-014, SC-006)."""

from pathlib import Path

from boidrytwin import load_scenario, run

from .conftest import make_variant


def test_bit_identical_results(tmp_path: Path) -> None:
    path = make_variant(tmp_path, end="2026-01-01T06:00:00Z")
    a = run(load_scenario(path), out_dir=tmp_path / "a")
    b = run(load_scenario(path), out_dir=tmp_path / "b")
    assert a.run_id != b.run_id
    res_a = (tmp_path / "a" / a.run_id / "results.csv").read_bytes()
    res_b = (tmp_path / "b" / b.run_id / "results.csv").read_bytes()
    assert res_a == res_b
    state_a = (tmp_path / "a" / a.run_id / "final_state.json").read_bytes()
    assert state_a == (tmp_path / "b" / b.run_id / "final_state.json").read_bytes()
