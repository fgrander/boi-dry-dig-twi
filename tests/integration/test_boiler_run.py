"""Boiler-house-only run via the CLI (T025)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from boidrytwin.cli import main

from .conftest import EXAMPLES, make_variant

COLUMNS = [
    "fuel_feed", "fuel_burnout_dry", "heat_released", "excess_air_ratio", "o2_dry", "o2_dry_measured",
    "combustion_air_flow", "furnace_temperature", "gas_temperature_after_heater_1",
    "gas_temperature_after_heater_2", "gas_temperature_after_heater_3",
    "oil_temperature_after_heater_1", "oil_temperature_after_heater_2", "oil_temperature_after_heater_3",
    "oil_outlet_temperature", "heat_to_oil_1", "heat_to_oil_2", "heat_to_oil_3", "heat_to_oil",
    "max_film_temperature", "min_oil_velocity", "losses", "bypass_position", "dilution_air_flow",
    "flue_gas_to_dryer_mass_flow", "flue_gas_to_dryer_temperature",
    "controller_output_oil_temperature", "controller_mode_oil_temperature",
    "controller_output_oxygen", "controller_mode_oxygen",
    "oil_limit", "combustion_out_of_range", "load_out_of_range", "controller_saturated",
    "setpoint_not_reached", "out_of_range",
]  # fmt: skip


def _run(path: Path, out: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, Path]:
    code = main(["run", str(path), "--out", str(out)])
    stdout = capsys.readouterr().out
    run_id = next(line.split()[-1] for line in stdout.splitlines() if line.startswith("run_id"))
    return code, out / run_id


def test_boiler_only_run_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = make_variant(tmp_path, base="boiler_house_only.toml", end="2026-01-01T06:00:00Z")
    code, folder = _run(path, tmp_path / "runs", capsys)
    assert code == 0
    for name in ("run_record.json", "boiler_results.csv", "final_state.json"):
        assert (folder / name).is_file(), name
    raw = pd.read_csv(folder / "boiler_results.csv")
    assert raw.iloc[0]["time"] == "unit" and raw.iloc[0]["oil_outlet_temperature"] == "K"
    data = pd.read_csv(folder / "boiler_results.csv", skiprows=[1])
    for col in COLUMNS:
        assert col in data.columns, col
    record = json.loads((folder / "run_record.json").read_text(encoding="utf-8"))
    report = record["plant_balance_report"]
    assert report["passed"] is True
    assert set(report) >= {"boiler_house", "oil_circuit", "passed"}
    assert set(report["boiler_house"]) >= {"mass", "C", "H", "O", "N", "S", "energy"}
    assert "oil_temperature" in record["controller_settings"]


def test_boiler_only_is_deterministic(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = make_variant(tmp_path, base="boiler_house_only.toml", end="2026-01-01T02:00:00Z")
    _, a = _run(path, tmp_path / "a", capsys)
    _, b = _run(path, tmp_path / "b", capsys)
    assert (a / "boiler_results.csv").read_bytes() == (b / "boiler_results.csv").read_bytes()


def test_steady_oil_temperature_on_setpoint() -> None:
    from boidrytwin import load_scenario
    from boidrytwin.plant.simulate import simulate_plant

    sim = simulate_plant(load_scenario(EXAMPLES / "boiler_house_only.toml"))
    oil = sim.results["oil_outlet_temperature"]
    assert abs(oil - 555.15).max() <= 0.5  # SC-004 steady part: within ±0.5 K
