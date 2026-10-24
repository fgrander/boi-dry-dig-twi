"""Comparison of model results with measurements (T073; FR-016, SC-003)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.validation.compare import (
    DEFAULT_TOLERANCES,
    ComparisonSettings,
    compare_frames,
    load_settings,
    read_measured,
    steady_mask,
)

T0 = pd.Timestamp("2026-01-01T00:00:00Z")


def _index(n: int, step_min: int = 1) -> pd.DatetimeIndex:
    return pd.DatetimeIndex([T0 + pd.Timedelta(minutes=step_min * i) for i in range(n)])


def test_default_tolerances() -> None:
    assert DEFAULT_TOLERANCES == {"product_moisture_wet_basis": 0.01, "exhaust_temperature": 5.0}
    s = ComparisonSettings()
    assert s.required_fraction == 0.9
    assert s.steady_window == 1800.0


def test_statistics_against_hand_values() -> None:
    idx = _index(5)
    predicted = pd.DataFrame({"exhaust_temperature": [400.0] * 5}, index=idx)
    measured = pd.DataFrame(
        {"exhaust_temperature": [398.0, 401.0, 404.0, 400.0, 392.0], "quality": ["good"] * 5},
        index=idx,
    )
    settings = ComparisonSettings(steady_window=0.0)
    report, table = compare_frames(predicted, measured, settings, run_id="r1")
    out = report.outputs["exhaust_temperature"]
    dev = np.array([2.0, -1.0, -4.0, 0.0, 8.0])  # predicted - measured
    assert out.n_compared == 5 and out.n_excluded == 0
    assert out.bias == pytest.approx(dev.mean())
    assert out.mae == pytest.approx(np.abs(dev).mean())
    assert out.rmse == pytest.approx(np.sqrt((dev**2).mean()))
    assert out.max_abs_error == pytest.approx(8.0)
    assert out.fraction_within_tolerance == pytest.approx(0.8)  # |8| > 5 K
    assert out.tolerance == 5.0
    assert out.passed is False  # 80 % < 90 %
    assert not report.passed
    assert list(table.columns) == [
        "time", "output", "predicted", "measured", "deviation", "included", "steady", "reason"
    ]  # fmt: skip


def test_missing_bad_and_stale_values_are_excluded_not_counted() -> None:
    idx = _index(6)
    predicted = pd.DataFrame({"product_moisture_wet_basis": [0.30] * 6}, index=idx)
    measured = pd.DataFrame(
        {
            "product_moisture_wet_basis": [0.30, np.nan, 0.90, 0.301, 0.90, 0.299],
            "quality": ["good", "missing", "bad", "good", "stale", "good"],
        },
        index=idx,
    )
    report, table = compare_frames(predicted, measured, ComparisonSettings(steady_window=0.0), "r")
    out = report.outputs["product_moisture_wet_basis"]
    assert out.n_compared == 3 and out.n_excluded == 3
    assert out.fraction_within_tolerance == 1.0 and out.passed
    reasons = sorted(e.reason for e in report.excluded)
    assert reasons == ["bad", "missing", "stale"]
    assert table.loc[~table["included"], "reason"].tolist() == ["missing", "bad", "stale"]


def test_measurements_outside_the_simulated_period_are_excluded() -> None:
    predicted = pd.DataFrame({"exhaust_temperature": [400.0, 400.0]}, index=_index(2))
    measured = pd.DataFrame(
        {"exhaust_temperature": [400.0, 400.0, 400.0], "quality": ["good"] * 3}, index=_index(3)
    )
    report, _ = compare_frames(predicted, measured, ComparisonSettings(steady_window=0.0), "r")
    assert report.outputs["exhaust_temperature"].n_excluded == 1
    assert report.excluded[0].reason == "outside simulated period"


def test_model_is_interpolated_to_measurement_times() -> None:
    predicted = pd.DataFrame({"exhaust_temperature": [400.0, 410.0]}, index=_index(2, 10))
    measured = pd.DataFrame(
        {"exhaust_temperature": [405.0], "quality": ["good"]},
        index=pd.DatetimeIndex([T0 + pd.Timedelta(minutes=5)]),
    )
    _, table = compare_frames(predicted, measured, ComparisonSettings(steady_window=0.0), "r")
    assert table["predicted"].iloc[0] == pytest.approx(405.0)


def test_steady_mask() -> None:
    # ramp for 30 minutes, then constant
    values = np.concatenate([np.linspace(300, 400, 31), np.full(90, 400.0)])
    idx = _index(len(values))
    mask = steady_mask(pd.Series(values, index=idx), window=1800.0, band=5.0)
    assert not mask[:40].any()  # within 30 min after the ramp still includes the ramp
    assert mask[62:].all()


def test_unsteady_samples_do_not_count_for_the_fraction() -> None:
    values = np.concatenate([np.linspace(300, 400, 31), np.full(90, 400.0)])
    idx = _index(len(values))
    predicted = pd.DataFrame({"exhaust_temperature": values}, index=idx)
    measured_values = values.copy()
    measured_values[:31] += 20.0  # large error only during the transient
    measured = pd.DataFrame(
        {"exhaust_temperature": measured_values, "quality": ["good"] * len(values)}, index=idx
    )
    report, _ = compare_frames(predicted, measured, ComparisonSettings(), "r")
    out = report.outputs["exhaust_temperature"]
    assert out.fraction_within_tolerance == 1.0 and out.passed
    assert report.steady_periods  # at least one steady period detected


def test_outputs_without_tolerance_get_statistics_only() -> None:
    idx = _index(3)
    predicted = pd.DataFrame({"evaporation_rate": [1.0, 1.0, 1.0]}, index=idx)
    measured = pd.DataFrame(
        {"evaporation_rate": [1.1, 0.9, 1.0], "quality": ["good"] * 3}, index=idx
    )
    report, _ = compare_frames(predicted, measured, ComparisonSettings(steady_window=0.0), "r")
    out = report.outputs["evaporation_rate"]
    assert out.tolerance is None and out.passed is None
    assert out.rmse == pytest.approx(np.sqrt(0.02 / 3))
    assert report.passed  # outputs without tolerance do not fail the comparison


def test_read_measured_converts_units_and_rejects_unknown_columns(tmp_path: Path) -> None:
    path = tmp_path / "m.csv"
    path.write_text(
        "time,exhaust_temperature,product_moisture_wet_basis\nunit,degC,%\n"
        "2026-01-01T00:00:00Z,120,15\n",
        encoding="utf-8",
    )
    frame = read_measured(path)
    assert frame["exhaust_temperature"].iloc[0] == pytest.approx(393.15)
    assert frame["product_moisture_wet_basis"].iloc[0] == pytest.approx(0.15)
    path.write_text("time,nonsense\nunit,K\n2026-01-01T00:00:00Z,1\n", encoding="utf-8")
    with pytest.raises(ScenarioValidationError, match="unknown output column"):
        read_measured(path)


def test_tolerance_file(tmp_path: Path) -> None:
    path = tmp_path / "tol.toml"
    path.write_text(
        'required_fraction = "80 %"\nsteady_window = "1 h"\n'
        '[tolerances]\nexhaust_temperature = "3 K"\nevaporation_rate = "0.05 kg/s"\n',
        encoding="utf-8",
    )
    s = load_settings(path)
    assert s.required_fraction == pytest.approx(0.8)
    assert s.steady_window == 3600.0
    assert s.tolerances["exhaust_temperature"] == pytest.approx(3.0)
    assert s.tolerances["evaporation_rate"] == pytest.approx(0.05)
    assert s.tolerances["product_moisture_wet_basis"] == 0.01  # default kept


def test_recirculation_outputs_can_be_compared(tmp_path: Path) -> None:
    """Feature 004 (T035): mixing chamber pressure, damper position, recirculated flow."""
    path = tmp_path / "m.csv"
    path.write_text(
        "time,mixing_chamber_pressure,recirculation_damper_position,recirculation_mass_flow\n"
        "unit,mbar,%,t/h\n2026-01-01T00:00:00Z,-2,45,18\n2026-01-01T00:01:00Z,-2.1,46,18\n",
        encoding="utf-8",
    )
    measured = read_measured(path)
    assert measured["mixing_chamber_pressure"].iloc[0] == pytest.approx(-200.0)
    assert measured["recirculation_damper_position"].iloc[0] == pytest.approx(0.45)
    assert measured["recirculation_mass_flow"].iloc[0] == pytest.approx(5.0)
    predicted = pd.DataFrame(
        {
            "mixing_chamber_pressure": [-195.0, -195.0],
            "recirculation_damper_position": [0.45, 0.46],
            "recirculation_mass_flow": [5.0, 5.0],
        },
        index=_index(2),
    )
    report, _ = compare_frames(predicted, measured, ComparisonSettings(), "run")
    assert report.outputs["mixing_chamber_pressure"].bias == pytest.approx(0.5 * (5.0 + 15.0))
