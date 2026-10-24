"""Result columns and run record with a recirculation (T013; contracts/results-recirculation.md)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from boidrytwin import load_scenario, run
from boidrytwin.records import RESULT_UNITS
from tests.recirculation import with_recirculation

NEW_COLUMNS = (
    "drum_outlet_mass_flow", "recirculation_damper_position", "recirculation_share",
    "recirculation_mass_flow", "recirculation_temperature", "mixing_chamber_pressure",
    "mixing_chamber_pressure_setpoint", "mixing_chamber_pressure_measured", "exhaust_fan_speed",
    "exhaust_fan_volume_flow", "exhaust_fan_pressure_rise", "drum_inlet_humidity",
    "drum_inlet_x_O2", "drum_inlet_dew_point", "duct_heat_loss",
)  # fmt: skip
END = "2026-01-01T03:00:00Z"


def _run(path: Path, out: Path) -> tuple[pd.DataFrame, dict]:
    record = run(load_scenario(path), out_dir=out)
    folder = out / record.run_id
    frame = pd.read_csv(folder / "results.csv", skiprows=[1], index_col=0)
    return frame, json.loads((folder / "run_record.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[pd.DataFrame, dict]]:
    tmp = tmp_path_factory.mktemp("results")
    (tmp / "with").mkdir()
    (tmp / "without").mkdir()
    return {
        "with": _run(with_recirculation(tmp / "with", end=END), tmp / "runs"),
        "without": _run(with_recirculation(tmp / "without", block="", end=END), tmp / "runs"),
    }


def test_new_columns_only_with_recirculation(runs: dict) -> None:
    with_frame, without_frame = runs["with"][0], runs["without"][0]
    for col in NEW_COLUMNS:
        assert col in with_frame.columns, col
        assert col not in without_frame.columns, col
        assert col in RESULT_UNITS, col
    assert list(with_frame.columns[: len(without_frame.columns)]) == list(without_frame.columns)


def test_stack_exhaust_is_drum_outlet_minus_returned(runs: dict) -> None:
    f = runs["with"][0]
    stack = f["drum_outlet_mass_flow"] - f["recirculation_mass_flow"]
    pd.testing.assert_series_equal(f["exhaust_mass_flow"], stack, rtol=1e-9, check_names=False)
    assert (f["recirculation_mass_flow"] > 0).iloc[-1]
    share = f["recirculation_mass_flow"] / f["drum_outlet_mass_flow"]
    pd.testing.assert_series_equal(f["recirculation_share"], share, rtol=1e-9, check_names=False)
    assert f["recirculation_damper_position"].between(0, 1).all()


def test_record_has_the_pressure_loop_and_the_loop_balance(runs: dict) -> None:
    record = runs["with"][1]
    settings = record["controller_settings"]["mixing_chamber_pressure"]
    assert settings["gain"] == pytest.approx(1e-4) and settings["action"] == "reverse"
    loop = record["balance_report"]["recirculation_loop"]
    assert loop["passed"] and set(loop) >= {"mass", "energy", "passed"}
    assert "setpoint_not_reached" in record["flags_summary"]
    assert "recirculation_loop" not in runs["without"][1]["balance_report"]
    assert "mixing_chamber_pressure" not in runs["without"][1]["controller_settings"]
