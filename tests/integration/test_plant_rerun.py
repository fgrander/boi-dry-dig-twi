"""Rerun of a coupled run (T047; FR-016)."""

import json
from pathlib import Path

import pytest

from boidrytwin.cli import main

from .conftest import make_variant, run_cli


def test_coupled_rerun_is_identical(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = make_variant(tmp_path, base="plant_reference.toml", end="2026-01-01T01:00:00Z")
    code, folder = run_cli(path, tmp_path / "runs", capsys)
    assert code == 0
    record = json.loads((folder / "run_record.json").read_text(encoding="utf-8"))
    assert set(record["controller_settings"]) == {
        "oil_temperature",
        "oxygen",
        "drum_inlet_temperature",
    }
    assert set(record["plant_balance_report"]) >= {
        "boiler_house",
        "oil_circuit",
        "dryer",
        "interface",
        "plant",
    }
    assert record["interface_files"] == ["flue_gas_to_dryer.csv", "dilution_air.csv"]
    assert main(["rerun", str(folder / "run_record.json")]) == 0
    assert "identical true" in capsys.readouterr().out.replace(":", "").lower()
