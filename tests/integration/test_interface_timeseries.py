"""Interface time series as dryer boundary conditions (T046; FR-014)."""

from pathlib import Path

import pytest

from boidrytwin.cli import main

from .conftest import dryer_only_from_interface, make_variant, run_cli


def test_interface_files_validate_as_dryer_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    end = "2026-01-01T01:00:00Z"
    code, folder = run_cli(
        make_variant(tmp_path, base="plant_reference.toml", end=end), tmp_path / "runs", capsys
    )
    assert code == 0
    for name in ("flue_gas_to_dryer.csv", "dilution_air.csv", "results.csv", "boiler_results.csv"):
        assert (folder / name).is_file(), name
    header = (folder / "flue_gas_to_dryer.csv").read_text(encoding="utf-8").splitlines()[0]
    assert header == "time,mass_flow,temperature,pressure,x_N2,x_O2,x_CO2,x_H2O,x_other,quality"
    assert (
        (folder / "dilution_air.csv")
        .read_text(encoding="utf-8")
        .startswith("time,dilution\nunit,kg/s\n")
    )
    swap = dryer_only_from_interface(tmp_path, folder, end)
    assert main(["validate", str(swap)]) == 0
