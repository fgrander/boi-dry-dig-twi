"""Adding a recirculation to a scenario in the web app (T039; FR-014, SC-006, acceptance US3-3)."""

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin import load_scenario
from boidrytwin.webapp.jobs import JobQueue


def _copy(c: Any, example: str = "plant_reference", name: str = "plant_rec") -> None:
    form = c.get(f"/api/scenarios/{example}?source=example").json()
    body = {"name": name, "derived_from": f"example:{example}", "form": form}
    assert c.post("/api/scenarios", json=body).status_code == 201


def _field(form: dict[str, Any], section: str, key: str) -> dict[str, Any]:
    for s in form["sections"]:
        if s["name"] == section:
            for f in s["fields"]:
                if f["key"] == key:
                    return f  # type: ignore[no-any-return]
    raise KeyError(f"{section}.{key}")


def test_add_to_a_copy(client: Any, web_settings: Any) -> None:
    c = client()
    _copy(c)
    r = c.post("/api/scenarios/plant_rec/recirculation")
    assert r.status_code == 201, r.text
    path = web_settings.scenarios_dir / "plant_rec.toml"
    loaded = load_scenario(path)
    assert loaded.spec.recirculation is not None and not loaded.config_warnings
    assert loaded.spec.recirculation.controller.setpoint is not None
    form = c.get("/api/scenarios/plant_rec").json()
    names = {s["name"] for s in form["sections"]}
    assert {"recirculation", "recirculation.exhaust_fan", "recirculation.controller"} <= names
    assert _field(form, "recirculation.controller", "setpoint")["series_ok"] is True
    assert c.post("/api/scenarios/validate", json={"form": form}).json() == {"valid": True}
    assert c.post("/api/scenarios/plant_rec/recirculation").status_code == 409  # has one


def test_needs_a_dryer_and_a_saved_scenario(client: Any) -> None:
    c = client()
    _copy(c, "boiler_house_only", "boiler_copy")
    assert c.post("/api/scenarios/boiler_copy/recirculation").status_code == 422
    assert c.post("/api/scenarios/plant_reference/recirculation").status_code == 404  # example


def test_engineer_only_and_same_origin(client: Any) -> None:
    _copy(client())
    assert client("operator").post("/api/scenarios/plant_rec/recirculation").status_code == 403
    r = client().post(
        "/api/scenarios/plant_rec/recirculation", headers={"Origin": "http://evil.example"}
    )
    assert r.status_code == 403


def test_share_out_of_range_reported_at_the_field(client: Any) -> None:
    c = client()
    _copy(c)
    c.post("/api/scenarios/plant_rec/recirculation")
    form = c.get("/api/scenarios/plant_rec").json()
    share = _field(form, "recirculation", "max_share")
    share["value"], share["unit"] = "120", "%"
    r = c.post("/api/scenarios/validate", json={"form": form})
    assert r.status_code == 422
    assert any(i["field"] == "recirculation.max_share" for i in r.json()["issues"])
    flagged = _field(r.json()["form"], "recirculation", "max_share")
    assert flagged["issues"]


def test_setpoint_released_for_operators(client: Any, web_settings: Any) -> None:
    c = client()
    _copy(c)
    c.post("/api/scenarios/plant_rec/recirculation")
    release = {
        "key": "recirculation.controller.setpoint",
        "label": "Mixing chamber pressure",
        "unit": "Pa",
        "minimum": -300,
        "maximum": -100,
        "allow_step": True,
    }
    r = c.post(
        "/api/operator/draft/versions",
        json={"scenario": "plant_rec", "source": "saved", "releases": [release]},
    )
    assert r.status_code == 201, r.text
    op = client("operator")
    ok = op.post(
        "/api/operator/draft/whatif", json={"version": 1, "values": {release["key"]: -250}}
    )
    assert ok.status_code == 202, ok.text
    job = JobQueue(web_settings.app_dir).get(ok.json()["job_id"])
    assert 'setpoint = "-250 Pa"' in Path(job.scenario_path).read_text(encoding="utf-8")
    bad = op.post(
        "/api/operator/draft/whatif", json={"version": 1, "values": {release["key"]: -400}}
    )
    assert bad.status_code == 422


def test_button_only_where_it_applies(client: Any) -> None:
    c = client()
    _copy(c)
    assert 'id="add-recirculation"' in c.get("/scenarios/plant_rec?source=saved").text
    assert 'id="add-recirculation"' not in c.get("/scenarios/plant_reference?source=example").text
    german = client(lang=None).get("/scenarios/plant_rec?source=saved").text
    assert "Rückführung hinzufügen" in german
    c.post("/api/scenarios/plant_rec/recirculation")
    assert 'id="add-recirculation"' not in c.get("/scenarios/plant_rec?source=saved").text
