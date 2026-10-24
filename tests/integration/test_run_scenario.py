"""Full run of the reference scenario (T041; FR-007, FR-008)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from boidrytwin import load_scenario, run
from boidrytwin.cli import main

from .conftest import EXAMPLES

RESULT_COLUMNS = [
    "product_dry_mass_flow",
    "product_moisture_wet_basis",
    "product_temperature",
    "evaporation_rate",
    "exhaust_mass_flow",
    "exhaust_temperature",
    "exhaust_humidity",
    "exhaust_x_N2",
    "exhaust_x_O2",
    "exhaust_x_CO2",
    "exhaust_x_H2O",
    "exhaust_x_other",
    "exhaust_dew_point",
    "drum_inlet_gas_temperature",
    "heat_supplied",
    "heat_used_for_drying",
    "shell_heat_loss",
    "specific_energy",
    "solids_holdup",
    "heat_limited",
    "out_of_range",
    "condensation_risk",
    "input_quality",
]


@pytest.fixture(scope="module")
def reference_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, object]:
    out = tmp_path_factory.mktemp("runs")
    record = run(load_scenario(EXAMPLES / "reference_constant.toml"), out_dir=out, profiles=True)
    return out / record.run_id, record


def test_run_folder_contents(reference_run: tuple[Path, object]) -> None:
    folder, _ = reference_run
    for name in ("run_record.json", "results.csv", "profiles.csv", "final_state.json"):
        assert (folder / name).is_file(), name


def test_results_columns_units_and_interval(reference_run: tuple[Path, object]) -> None:
    folder, _ = reference_run
    raw = pd.read_csv(folder / "results.csv")
    units = raw.iloc[0]
    assert units["time"] == "unit"
    assert units["exhaust_temperature"] == "K"
    assert units["evaporation_rate"] == "kg/s"
    assert units["product_moisture_wet_basis"] == "kg/kg"
    data = pd.read_csv(folder / "results.csv", skiprows=[1], parse_dates=["time"])
    assert list(data.columns[1:]) == RESULT_COLUMNS
    assert len(data) == 24 * 60 + 1
    assert (data["time"].diff().dropna() == pd.Timedelta(minutes=1)).all()


def test_outputs_are_physical(reference_run: tuple[Path, object]) -> None:
    folder, _ = reference_run
    data = pd.read_csv(folder / "results.csv", skiprows=[1])
    last = data.iloc[-1]
    assert 0.0 < last["product_moisture_wet_basis"] < 0.5  # drier than the feed
    assert last["evaporation_rate"] > 0.1
    assert (
        last["product_temperature"]
        < last["exhaust_temperature"]
        < last["drum_inlet_gas_temperature"]
    )
    assert last["exhaust_dew_point"] < last["exhaust_temperature"]
    assert last["specific_energy"] > 2.26e6  # at least the latent heat per kg of water


def test_run_record_contents(reference_run: tuple[Path, object]) -> None:
    folder, record = reference_run
    payload = json.loads((folder / "run_record.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == record.run_id  # type: ignore[attr-defined]
    assert payload["status"] == "completed"
    assert len(payload["scenario_sha256"]) == 64
    assert payload["scenario"]["name"].startswith("Reference case")
    assert payload["solver_stats"]["method"] == "BDF"
    assert payload["solver_stats"]["nfev"] > 0
    assert "numpy" in payload["environment"] and "scipy" in payload["environment"]


def test_profiles_have_one_row_per_cell_and_time(reference_run: tuple[Path, object]) -> None:
    folder, _ = reference_run
    profiles = pd.read_csv(folder / "profiles.csv", skiprows=[1])
    assert set(profiles["cell"]) == set(range(20))
    assert len(profiles) == 20 * (24 * 60 + 1)


def test_cli_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["run", str(EXAMPLES / "reference_constant.toml"), "--out", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "completed" in out
    run_id = next(line.split()[-1] for line in out.splitlines() if line.startswith("run_id"))
    assert (tmp_path / run_id / "results.csv").is_file()


def test_run_requires_dryer_sections(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = (EXAMPLES / "reference_constant.toml").read_text(encoding="utf-8")
    path = tmp_path / "no_dryer.toml"
    path.write_text(text[: text.index("[product_feed]")], encoding="utf-8")
    assert main(["run", str(path), "--out", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "product_feed: required for run" in out and "dryer: required for run" in out
