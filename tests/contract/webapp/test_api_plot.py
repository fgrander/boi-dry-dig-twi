"""Plots, CSV export and profiles in the HTTP interface (T018; FR-002, FR-005, FR-006, FR-018a)."""

from typing import Any

import pytest

pytest.importorskip("fastapi")


def test_default_plot(client: Any, example_runs: dict[str, str]) -> None:
    body = client().get(f"/api/runs/{example_runs['boiler_house_only']}/plot").json()
    names = [c["column"] for c in body["columns"]]
    assert "oil_outlet_temperature" in names and "fuel_feed" in names
    col = body["columns"][names.index("oil_outlet_temperature")]
    assert col["unit"] == "°C"
    trace = col["traces"][0]
    assert len(trace["times"]) == len(trace["values"]) == 121  # 2 h at 1 min
    assert trace["times"][0].startswith("2026-01-01T00:00:00")


def test_chosen_columns_and_unknown(client: Any, example_runs: dict[str, str]) -> None:
    rid = example_runs["boiler_house_only"]
    body = client("operator").get(f"/api/runs/{rid}/plot?columns=losses,o2_dry").json()
    assert [c["column"] for c in body["columns"]] == ["losses", "o2_dry"]
    r = client().get(f"/api/runs/{rid}/plot?columns=nope")
    assert r.status_code == 422


def test_overlay(client: Any, example_runs: dict[str, str]) -> None:
    a, b = example_runs["boiler_house_only"], example_runs["oil_demand_step"]
    body = client().get(f"/api/plot?runs={a},{b}&columns=fuel_feed").json()
    assert [t["run_id"] for t in body["columns"][0]["traces"]] == [a, b]
    assert client().get(f"/api/plot?runs={a},missing&columns=fuel_feed").status_code == 404


def test_csv_matches_plot(client: Any, example_runs: dict[str, str]) -> None:
    rid = example_runs["boiler_house_only"]
    c = client()
    plot = c.get(f"/api/runs/{rid}/plot?columns=oil_outlet_temperature").json()
    r = c.get(f"/api/runs/{rid}/plot.csv?columns=oil_outlet_temperature")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.splitlines()
    assert lines[0].startswith("# runs:") and rid in lines[0]
    assert lines[1] == f"time,{rid}:oil_outlet_temperature" and lines[2] == "unit,°C"
    values = [float(x.split(",")[1]) for x in lines[3:]]
    assert values == plot["columns"][0]["traces"][0]["values"]


def test_profiles(
    client: Any, web_settings: Any, tmp_path: Any, example_runs: dict[str, str]
) -> None:
    from boidrytwin import load_scenario
    from boidrytwin.records import run
    from tests.webapp_conftest import EXAMPLES, shortened

    path = shortened(EXAMPLES / "plant_reference.toml", tmp_path, end="2026-01-01T00:10:00Z")
    record = run(load_scenario(path), out_dir=web_settings.runs_dir, profiles=True)
    body = client().get(f"/api/runs/{record.run_id}/profiles?time=2026-01-01T00:05:20Z").json()
    assert body["time"].startswith("2026-01-01T00:05:00")
    assert len(body["cells"]) == 20
    assert {"solids_temperature", "gas_temperature", "moisture_wet_basis"} <= set(body["columns"])
    assert body["units"]["gas_temperature"] == "°C"
    no_profiles = example_runs["boiler_house_only"]
    assert client().get(f"/api/runs/{no_profiles}/profiles").status_code == 404
