"""Plot data built from run folders (T016; FR-002, FR-004, SC-007, data-model §3)."""

import shutil
from typing import Any

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.display_units import to_display
from boidrytwin.webapp.plot_data import (
    DEFAULT_SETS,
    MAX_DRAWN,
    build_plot,
    default_columns,
    plot_csv,
    reduce_for_drawing,
)
from boidrytwin.webapp.run_view import load_run


def _csv(folder: Any, name: str) -> tuple[pd.DataFrame, dict[str, str]]:
    raw = pd.read_csv(folder / name)
    units = raw.iloc[0].to_dict()
    return pd.read_csv(folder / name, skiprows=[1]), units


def test_default_sets_only_where_present(web_settings: Any, example_runs: dict[str, str]) -> None:
    boiler = load_run(web_settings.runs_dir / example_runs["boiler_house_only"])
    cols = default_columns(boiler)
    assert set(DEFAULT_SETS["boiler_house"]) <= set(cols)
    assert not set(DEFAULT_SETS["dryer"]) & set(cols)
    coupled = load_run(web_settings.runs_dir / example_runs["plant_reference"])
    cols = default_columns(coupled)
    assert (
        set(DEFAULT_SETS["dryer"]) <= set(cols)
        and "controller_output_drum_inlet_temperature" in cols
    )


def test_values_equal_the_csv_in_display_units(
    web_settings: Any, example_runs: dict[str, str]
) -> None:
    folder = web_settings.runs_dir / example_runs["plant_reference"]
    run = load_run(folder)
    plot = build_plot([run], ["oil_outlet_temperature", "product_moisture_wet_basis"])
    data, units = _csv(folder, "boiler_results.csv")
    oil = plot.columns[0]
    assert oil.unit == "°C"
    expected = to_display(
        "oil_outlet_temperature",
        units["oil_outlet_temperature"],
        data["oil_outlet_temperature"].to_numpy(dtype=float),
    )
    assert np.array_equal(np.asarray(oil.traces[0].values), expected)
    dryer, dunits = _csv(folder, "results.csv")
    moist = plot.columns[1]
    assert moist.unit == "%"
    assert np.array_equal(
        np.asarray(moist.traces[0].values),
        to_display(
            "product_moisture_wet_basis",
            dunits["product_moisture_wet_basis"],
            dryer["product_moisture_wet_basis"].to_numpy(dtype=float),
        ),
    )


def test_warnings_and_flags_become_periods(web_settings: Any, example_runs: dict[str, str]) -> None:
    run = load_run(web_settings.runs_dir / example_runs["oil_demand_step"])
    plot = build_plot([run], ["load_fraction", "oil_outlet_temperature"])
    load = plot.columns[0]
    labels = {p.label for p in load.periods}
    assert any("load_fraction" in lab for lab in labels)  # the range warning above rated load
    for p in load.periods:
        assert p.start <= p.end


def test_several_runs_give_one_trace_each(web_settings: Any, example_runs: dict[str, str]) -> None:
    runs = [
        load_run(web_settings.runs_dir / example_runs[n])
        for n in ("boiler_house_only", "plant_reference")
    ]
    plot = build_plot(runs, ["fuel_feed"])
    assert [t.run_id for t in plot.columns[0].traces] == [r.summary.run_id for r in runs]


def test_unknown_column_rejected(web_settings: Any, example_runs: dict[str, str]) -> None:
    run = load_run(web_settings.runs_dir / example_runs["boiler_house_only"])
    with pytest.raises(KeyError):
        build_plot([run], ["no_such_column"])


def test_reduction_for_drawing_keeps_extremes_and_csv_keeps_all() -> None:
    n = 20_000
    t = np.arange(n, dtype=float)
    v = np.sin(t / 100.0)
    v[12_345] = 5.0
    tt, vv = reduce_for_drawing(t, v)
    assert len(tt) <= MAX_DRAWN and 5.0 in vv and v.min() in vv
    _, small_v = reduce_for_drawing(t[:100], v[:100])
    assert np.array_equal(small_v, v[:100])


def test_csv_export(web_settings: Any, example_runs: dict[str, str]) -> None:
    run = load_run(web_settings.runs_dir / example_runs["boiler_house_only"])
    plot = build_plot([run], ["oil_outlet_temperature", "fuel_feed"])
    text = plot_csv(plot)
    lines = text.splitlines()
    assert lines[0].startswith("#") and run.summary.run_id in lines[0]
    rid = run.summary.run_id
    assert lines[1] == f"time,{rid}:oil_outlet_temperature,{rid}:fuel_feed"
    assert lines[2] == "unit,°C,t/h"
    first = lines[3].split(",")
    assert float(first[1]) == plot.columns[0].traces[0].values[0]
    assert len(lines) - 3 == len(plot.columns[0].traces[0].values)


def test_damaged_run_folder_reports_missing_tables(
    web_settings: Any, example_runs: dict[str, str]
) -> None:
    src = web_settings.runs_dir / example_runs["boiler_house_only"]
    dst = web_settings.runs_dir / "copy"
    shutil.copytree(src, dst)
    (dst / "boiler_results.csv").unlink()
    run = load_run(dst)
    assert run.tables == {}
    assert default_columns(run) == []


def test_recirculation_group_only_with_a_recirculation(
    web_settings: Any, recirculation_run: str, example_runs: dict[str, str]
) -> None:
    group = DEFAULT_SETS["recirculation"]
    assert {
        "mixing_chamber_pressure",
        "mixing_chamber_pressure_setpoint",
        "recirculation_damper_position",
        "recirculation_share",
        "recirculation_mass_flow",
        "exhaust_mass_flow",
        "drum_inlet_humidity",
        "drum_inlet_x_O2",
    } <= set(group)
    run = load_run(web_settings.runs_dir / recirculation_run)
    assert set(group) <= set(default_columns(run))
    plot = build_plot([run], ["mixing_chamber_pressure", "recirculation_damper_position"])
    pressure, damper = plot.columns
    assert pressure.unit == "Pa" and pressure.traces[0].values[-1] == pytest.approx(-200, abs=1)
    assert damper.unit == "%" and 0 < damper.traces[0].values[-1] < 100
    plain = load_run(web_settings.runs_dir / example_runs["plant_reference"])
    assert not set(group) - {"exhaust_mass_flow"} & set(default_columns(plain))
