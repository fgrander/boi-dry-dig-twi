"""Operator scenarios and what-if runs in the HTTP interface (T036; FR-012–FR-015, SC-005)."""

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.jobs import JobQueue

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
        "allow_step": False,
    },
]


def _create(c: Any, name: str = "fuel_oil") -> dict[str, Any]:
    r = c.post(
        f"/api/operator/{name}/versions",
        json={"scenario": "plant_reference", "source": "example", "releases": RELEASES},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def test_versions_engineer_only(client: Any) -> None:
    body = {"scenario": "plant_reference", "source": "example", "releases": RELEASES}
    assert client("operator").post("/api/operator/x/versions", json=body).status_code == 403
    created = _create(client())
    assert created["version"] == 1 and created["baseline_job_id"]
    bad = {**body, "releases": [{**RELEASES[0], "maximum": 70}]}
    r = client().post("/api/operator/x/versions", json=bad)
    assert r.status_code == 422 and "issues" in r.json()


def test_listing(client: Any) -> None:
    _create(client())
    listing = client("operator").get("/api/operator").json()
    assert [o["name"] for o in listing["operator_scenarios"]] == ["fuel_oil"]
    one = client("operator").get("/api/operator/fuel_oil").json()
    assert one["version"] == 1 and one["baseline_state"] == "baseline pending"
    assert [r["key"] for r in one["releases"]] == [r["key"] for r in RELEASES]
    assert client().get("/api/operator/nope").status_code == 404


@pytest.mark.parametrize(
    ("values", "status"),
    [
        ({"boiler_house.fuel.moisture_wet_basis": 34.9}, 422),
        ({"boiler_house.fuel.moisture_wet_basis": 55.1}, 422),
        ({"boiler_house.fuel.moisture_wet_basis": 35}, 202),
        ({"boiler_house.fuel.moisture_wet_basis": 55}, 202),
        ({"boiler_house.furnace.rated_fuel_power": 10}, 422),  # not released
        (
            {
                "boiler_house.thermal_oil.return_temperature": {
                    "start_value": 240,
                    "steps": [{"time": "2026-01-01T06:00:00Z", "value": 230}],
                }
            },
            422,
        ),  # steps not allowed here
        (
            {
                "boiler_house.fuel.moisture_wet_basis": {
                    "start_value": 45,
                    "steps": [{"time": "2026-01-01T06:00:00Z", "value": 50}],
                }
            },
            202,
        ),
        (
            {
                "boiler_house.fuel.moisture_wet_basis": {
                    "start_value": 45,
                    "steps": [{"time": "2026-01-01T06:00:00Z", "value": 60}],
                }
            },
            422,
        ),  # step outside the range
    ],
)
def test_whatif_ranges(client: Any, values: dict[str, Any], status: int) -> None:
    _create(client())
    r = client("operator").post(
        "/api/operator/fuel_oil/whatif", json={"version": 1, "values": values}
    )
    assert r.status_code == status, r.text
    if status == 422:
        issue = r.json()["issues"][0]
        assert issue["field"] in values and issue["allowed"]


def test_whatif_changes_only_released_inputs(client: Any, web_settings: Any) -> None:
    _create(client())
    r = client("operator").post(
        "/api/operator/fuel_oil/whatif",
        json={"version": 1, "values": {"boiler_house.fuel.moisture_wet_basis": 52}},
    )
    job = JobQueue(web_settings.app_dir).get(r.json()["job_id"])
    assert job.kind == "what_if" and job.view == "operator"
    version = (web_settings.scenarios_dir / "operator/fuel_oil/v1/scenario.toml").read_text(
        encoding="utf-8"
    )
    frozen = Path(job.scenario_path).read_text(encoding="utf-8")
    a, b = version.splitlines(), frozen.splitlines()
    assert len(a) == len(b)
    diff = [(x, y) for x, y in zip(a, b, strict=True) if x != y and "file =" not in x]
    assert diff == [('moisture_wet_basis = "45 %"', 'moisture_wet_basis = "52 %"')]


def test_whatif_result_endpoints(
    client: Any, example_runs: dict[str, str], web_settings: Any
) -> None:
    created = _create(client())
    q = JobQueue(web_settings.app_dir)
    q.mark_running(created["baseline_job_id"])
    q.mark_finished(
        created["baseline_job_id"], run_id=example_runs["plant_reference"], failed=False
    )
    r = client("operator").post(
        "/api/operator/fuel_oil/whatif",
        json={"version": 1, "values": {"boiler_house.fuel.moisture_wet_basis": 50}},
    )
    job_id = r.json()["job_id"]
    q = JobQueue(web_settings.app_dir)
    q.mark_running(job_id)
    q.mark_finished(job_id, run_id=example_runs["plant_reference"], failed=False)
    body = client("operator").get(f"/api/whatif/{example_runs['plant_reference']}").json()
    assert body["baseline_run_id"] == example_runs["plant_reference"]
    assert [row["column"] for row in body["rows"]][:2] == ["oil_outlet_temperature", "fuel_feed"]
    assert body["summary"]["text"]
    csv = client("operator").get(f"/api/whatif/{example_runs['plant_reference']}.csv")
    assert csv.status_code == 200 and csv.text.splitlines()[0].startswith("output,unit")
    assert client().get("/api/whatif/not-a-whatif-run").status_code == 404
