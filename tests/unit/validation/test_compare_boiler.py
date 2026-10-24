"""Comparison of boiler house results with measurements (T056; FR-016, SC-008)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from boidrytwin import load_scenario
from boidrytwin.records import compare
from boidrytwin.validation.compare import (
    BOILER_DEFAULT_TOLERANCES,
    ComparisonSettings,
    compare_frames,
    read_measured,
)
from tests.integration.conftest import EXAMPLES

T0 = pd.Timestamp("2026-01-01T00:00:00Z")
BOILER_COLUMNS = (
    "o2_dry",
    "furnace_temperature",
    "gas_temperature_after_heater_3",
    "oil_outlet_temperature",
)
# offsets written by scripts/make_synthetic_measured.py --boiler (measured = model + offset + noise)
OFFSETS = {"o2_dry": 0.002, "furnace_temperature": -8.0, "gas_temperature_after_heater_3": 4.0,
           "oil_outlet_temperature": -1.0}  # fmt: skip


def test_default_boiler_tolerances() -> None:
    assert BOILER_DEFAULT_TOLERANCES["o2_dry"] == 0.005
    assert BOILER_DEFAULT_TOLERANCES["oil_outlet_temperature"] == 2.0
    for name in (
        "furnace_temperature",
        "gas_temperature_after_heater_3",
        "flue_gas_to_dryer_temperature",
    ):
        assert BOILER_DEFAULT_TOLERANCES[name] == 10.0
    tol = ComparisonSettings().tolerances
    assert tol["o2_dry"] == 0.005 and tol["exhaust_temperature"] == 5.0  # dryer defaults kept


def test_measured_columns_may_name_boiler_outputs(tmp_path: Path) -> None:
    csv = tmp_path / "m.csv"
    csv.write_text(
        "time,o2_dry,furnace_temperature,gas_temperature_after_heater_3,oil_outlet_temperature,quality\n"
        "unit,%,degC,degC,degC,\n2026-01-01T00:00:00Z,7.1,930,300,281.5,good\n",
        encoding="utf-8",
    )
    frame = read_measured(csv)
    assert frame["o2_dry"].iloc[0] == pytest.approx(0.071)
    assert frame["oil_outlet_temperature"].iloc[0] == pytest.approx(554.65)


def test_known_offsets_are_reproduced_in_frames() -> None:
    idx = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=i) for i in range(60)])
    predicted = pd.DataFrame({"o2_dry": 0.07, "oil_outlet_temperature": 555.15}, index=idx)
    measured = pd.DataFrame(
        {"o2_dry": 0.07 + 0.003, "oil_outlet_temperature": 555.15 - 3.0, "quality": "good"},
        index=idx,
    )
    report, _ = compare_frames(predicted, measured, ComparisonSettings(steady_window=0.0), "r")
    assert report.outputs["o2_dry"].bias == pytest.approx(-0.003)
    assert report.outputs["o2_dry"].passed is True  # 3e-3 < 5e-3
    assert report.outputs["oil_outlet_temperature"].passed is False  # 3 K > 2 K


def test_synthetic_boiler_deviations_reproduced(tmp_path: Path) -> None:
    loaded = load_scenario(EXAMPLES / "oil_demand_step.toml")
    _, report = compare(loaded, EXAMPLES / "synthetic_boiler_measured.csv", tmp_path / "runs")
    for name in BOILER_COLUMNS:
        out = report.outputs[name]
        # bias = predicted - measured = -offset, within the noise of the mean
        assert out.bias == pytest.approx(-OFFSETS[name], abs=0.1 * abs(OFFSETS[name]) + 1e-4), name
        assert out.n_excluded >= 3  # the missing and bad samples
    assert report.outputs["furnace_temperature"].passed is True  # 8 K < 10 K
    assert np.isfinite(report.outputs["oil_outlet_temperature"].rmse)
