"""Run record contents and check failures (T067; FR-017)."""

import json
from pathlib import Path

import pytest

from boidrytwin.cli import main

from .conftest import EXAMPLES, make_variant


def _run(path: Path, out: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:  # type: ignore[type-arg]
    code = main(["run", str(path), "--out", str(out)])
    stdout = capsys.readouterr().out
    run_id = next(line.split()[-1] for line in stdout.splitlines() if line.startswith("run_id"))
    record = json.loads((out / run_id / "run_record.json").read_text(encoding="utf-8"))
    return code, record


def test_record_has_checks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = make_variant(tmp_path, end="2026-01-01T04:00:00Z")
    code, record = _run(path, tmp_path / "runs", capsys)
    assert code == 0
    for key in (
        "balance_report",
        "range_warnings",
        "flags_summary",
        "solver_stats",
        "rejected_inputs",
    ):
        assert key in record, key
    report = record["balance_report"]
    assert set(report) >= {"dry_solids", "water", "gas", "energy", "passed"}
    fields = {"inflow", "outflow", "storage_change", "residual", "relative_residual"}
    assert set(report["energy"]) == fields | {"tolerance", "passed"}
    assert report["passed"] is True
    assert set(record["flags_summary"]) >= {"heat_limited", "out_of_range", "condensation_risk"}


def test_failing_checks_keep_status_completed_and_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = make_variant(
        tmp_path,
        replace={'energy = "1 %"': 'energy = "1e-15 %"'},
        end="2026-01-01T04:00:00Z",
    )
    code, record = _run(path, tmp_path / "runs", capsys)
    assert code == 2
    assert record["status"] == "completed"
    assert record["balance_report"]["energy"]["passed"] is False


def test_out_of_range_inlet_is_a_warning_not_a_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, record = _run(EXAMPLES / "out_of_range_inlet.toml", tmp_path / "runs", capsys)
    assert code == 0
    (warning,) = [
        w for w in record["range_warnings"] if w["quantity"] == "drum_inlet_gas_temperature"
    ]
    assert warning["limit"] == pytest.approx(873.15)
    assert warning["period_start"].startswith("2026-01-01T08:0")
    assert warning["period_end"].startswith("2026-01-01T10:0")
    assert record["flags_summary"]["out_of_range"] > 100  # about 2 h of 1-minute samples
