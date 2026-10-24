"""Rerunning a recorded run (T066; FR-014, SC-006)."""

from pathlib import Path

import pytest

from boidrytwin import load_scenario, run
from boidrytwin.cli import main

from .conftest import make_variant


def test_rerun_is_identical(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = make_variant(tmp_path, end="2026-01-01T04:00:00Z")
    record = run(load_scenario(path), out_dir=tmp_path / "runs")
    record_path = tmp_path / "runs" / record.run_id / "run_record.json"
    code = main(["rerun", str(record_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "identical: true" in out


def test_rerun_refuses_changed_input_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv = "time,m\nunit,t/h\n2026-01-01T00:00:00Z,10\n2026-01-01T04:00:00Z,10\n"
    path = make_variant(
        tmp_path,
        replace={'mass_flow_wet = "10 t/h"': 'mass_flow_wet = { file = "feed.csv", column = "m" }'},
        end="2026-01-01T04:00:00Z",
        files={"feed.csv": csv},
    )
    record = run(load_scenario(path), out_dir=tmp_path / "runs")
    (tmp_path / "feed.csv").write_text(csv.replace(",10\n", ",11\n"), encoding="utf-8")
    code = main(["rerun", str(tmp_path / "runs" / record.run_id / "run_record.json")])
    out = capsys.readouterr().out
    assert code == 1
    assert "input file changed" in out and "feed.csv" in out
