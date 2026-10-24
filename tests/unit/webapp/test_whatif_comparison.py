"""What-if comparison with the baseline (T035; FR-014, FR-014a, FR-015)."""

import json
import shutil
from typing import Any

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.run_view import load_run
from boidrytwin.webapp.whatif import compare_runs

OUTPUTS = ["oil_outlet_temperature", "fuel_feed", "product_moisture_wet_basis"]


def _whatif(web_settings: Any, baseline_id: str) -> Any:
    """A copy of the baseline with a changed fuel feed and an extra warning."""
    src = web_settings.runs_dir / baseline_id
    dst = web_settings.runs_dir / "whatif-run"
    shutil.copytree(src, dst)
    path = dst / "boiler_results.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    col = header.index("fuel_feed")
    out = lines[:2]
    for line in lines[2:]:
        cells = line.split(",")
        cells[col] = repr(float(cells[col]) * 1.1)
        out.append(",".join(cells))
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    record = json.loads((dst / "run_record.json").read_text(encoding="utf-8"))
    record["run_id"] = "whatif-run"
    record["range_warnings"] = [
        {
            "quantity": "load_fraction",
            "limit_type": "max",
            "limit": 1.0,
            "observed_extreme": 1.1,
            "period_start": "2026-01-01T01:00:00Z",
            "period_end": "2026-01-01T02:00:00Z",
        }
    ]
    (dst / "run_record.json").write_text(json.dumps(record), encoding="utf-8")
    return load_run(dst)


def test_rows_and_differences(web_settings: Any, example_runs: dict[str, str]) -> None:
    base = load_run(web_settings.runs_dir / example_runs["plant_reference"])
    what = _whatif(web_settings, example_runs["plant_reference"])
    cmp = compare_runs(base, what, OUTPUTS)
    rows = {r.column: r for r in cmp.rows}
    fuel = rows["fuel_feed"]
    assert fuel.unit == "t/h"
    assert fuel.whatif_final == pytest.approx(fuel.baseline_final * 1.1, rel=1e-9)
    assert fuel.difference == pytest.approx(fuel.whatif_final - fuel.baseline_final)
    assert fuel.relative == pytest.approx(0.1, rel=1e-9)
    data = pd.read_csv(
        web_settings.runs_dir / example_runs["plant_reference"] / "boiler_results.csv", skiprows=[1]
    )
    last_hour = data["fuel_feed"].to_numpy()[-61:] * 3.6
    assert fuel.baseline_mean_last_hour == pytest.approx(float(np.mean(last_hour)))
    assert rows["oil_outlet_temperature"].difference == pytest.approx(0.0, abs=1e-9)
    assert cmp.new_warnings == ["load_fraction max 1.0"]


def test_summary(web_settings: Any, example_runs: dict[str, str]) -> None:
    base = load_run(web_settings.runs_dir / example_runs["plant_reference"])
    what = _whatif(web_settings, example_runs["plant_reference"])
    s = compare_runs(base, what, OUTPUTS).summary
    assert s.oil_on_setpoint is True and s.drum_inlet_on_setpoint is True
    assert s.product_moisture == pytest.approx(
        load_run(what.folder)
        .column_table("product_moisture_wet_basis")
        .frame["product_moisture_wet_basis"]
        .iloc[-1]
        * 100
    )
    assert s.new_warnings == 1
    assert "oil" in s.text[0].lower() and "set point" in s.text[0].lower()


def test_outputs_missing_in_a_run_are_left_out(
    web_settings: Any, example_runs: dict[str, str]
) -> None:
    base = load_run(web_settings.runs_dir / example_runs["boiler_house_only"])
    cmp = compare_runs(base, base, OUTPUTS)
    assert [r.column for r in cmp.rows] == ["oil_outlet_temperature", "fuel_feed"]
    assert cmp.summary.drum_inlet_on_setpoint is None and cmp.summary.product_moisture is None


def test_without_baseline(web_settings: Any, example_runs: dict[str, str]) -> None:
    what = load_run(web_settings.runs_dir / example_runs["plant_reference"])
    cmp = compare_runs(None, what, OUTPUTS)
    assert cmp.rows == [] and cmp.note and "baseline" in cmp.note
    assert cmp.summary.oil_on_setpoint is True  # the summary works without a baseline
