"""Operator what-if flow end to end (T038; US3 scenarios 1–5)."""

from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.worker import run_pending
from tests.webapp_conftest import shortened

RELEASES = [
    {
        "key": "boiler_house.fuel.moisture_wet_basis",
        "label": "Fuel moisture",
        "unit": "%",
        "minimum": 35,
        "maximum": 55,
        "allow_step": True,
    },
    {
        "key": "boiler_house.thermal_oil.return_temperature",
        "label": "Oil return",
        "unit": "degC",
        "minimum": 220,
        "maximum": 260,
    },
]


def test_whatif_flow(client: Any, web_settings: Any) -> None:
    shortened(
        web_settings.examples_dir / "plant_reference.toml",
        web_settings.scenarios_dir,
        end="2026-01-01T02:00:00Z",
        name="plant_short.toml",
    )
    eng, op = client("engineer"), client("operator")
    v1 = eng.post(
        "/api/operator/fuel_oil/versions",
        json={"scenario": "plant_short", "source": "saved", "releases": RELEASES},
    ).json()
    run_pending(web_settings.app_dir, web_settings.runs_dir)
    state = op.get("/api/operator/fuel_oil").json()
    assert state["baseline_state"] == "ready" and state["baseline_run_id"]

    page = op.get("/operator/fuel_oil")
    assert page.status_code == 200 and "Fuel moisture" in page.text and "35" in page.text
    assert "rated_fuel_power" not in page.text  # only released inputs are shown

    job = op.post(
        "/api/operator/fuel_oil/whatif", json={"version": 1, "values": {RELEASES[0]["key"]: 52}}
    ).json()["job_id"]
    run_pending(web_settings.app_dir, web_settings.runs_dir)
    run_id = op.get(f"/api/jobs/{job}").json()["run_id"]
    cmp = op.get(f"/api/whatif/{run_id}").json()
    assert cmp["baseline_run_id"] == state["baseline_run_id"] and cmp["version"] == 1
    cols = [r["column"] for r in cmp["rows"]]
    assert {"oil_outlet_temperature", "fuel_feed", "product_moisture_wet_basis"} <= set(cols)
    fuel = next(r for r in cmp["rows"] if r["column"] == "fuel_feed")
    assert fuel["whatif_final"] > fuel["baseline_final"]  # wetter fuel needs more feed
    assert cmp["summary"]["oil_on_setpoint"] is True
    assert op.get(f"/whatif/{run_id}").status_code == 200

    # a second version gets its own baseline; the first what-if still uses version 1's
    v2 = eng.post(
        "/api/operator/fuel_oil/versions",
        json={"scenario": "plant_short", "source": "saved", "releases": RELEASES[:1]},
    ).json()
    assert v2["version"] == 2 and v2["baseline_job_id"] != v1["baseline_job_id"]
    run_pending(web_settings.app_dir, web_settings.runs_dir)
    assert op.get(f"/api/whatif/{run_id}").json()["baseline_run_id"] == state["baseline_run_id"]
    assert op.get("/api/operator/fuel_oil").json()["baseline_run_id"] != state["baseline_run_id"]


def test_failed_baseline_gives_whatif_without_comparison(
    client: Any, web_settings: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import boidrytwin.records as records
    from boidrytwin.errors import SimulationError

    shortened(
        web_settings.examples_dir / "plant_reference.toml",
        web_settings.scenarios_dir,
        end="2026-01-01T01:00:00Z",
        name="plant_short.toml",
    )
    eng, op = client("engineer"), client("operator")
    eng.post(
        "/api/operator/f/versions",
        json={"scenario": "plant_short", "source": "saved", "releases": RELEASES[:1]},
    )
    original = records.simulate_plant
    monkeypatch.setattr(
        records, "simulate_plant", lambda *a, **k: (_ for _ in ()).throw(SimulationError("boom"))
    )
    run_pending(web_settings.app_dir, web_settings.runs_dir)
    monkeypatch.setattr(records, "simulate_plant", original)
    assert op.get("/api/operator/f").json()["baseline_state"] == "baseline failed"
    job = op.post(
        "/api/operator/f/whatif", json={"version": 1, "values": {RELEASES[0]["key"]: 50}}
    ).json()["job_id"]
    run_pending(web_settings.app_dir, web_settings.runs_dir)
    run_id = op.get(f"/api/jobs/{job}").json()["run_id"]
    cmp = op.get(f"/api/whatif/{run_id}").json()
    assert cmp["rows"] == [] and "baseline" in cmp["note"]
