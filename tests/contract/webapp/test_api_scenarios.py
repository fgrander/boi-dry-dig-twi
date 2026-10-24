"""Scenario and job creation in the HTTP interface (T025; contracts/http-api.md, FR-007–FR-009)."""

from typing import Any

import pytest

pytest.importorskip("fastapi")


def _form(c: Any, name: str = "plant_reference", source: str = "example") -> dict[str, Any]:
    r = c.get(f"/api/scenarios/{name}?source={source}")
    assert r.status_code == 200
    return r.json()  # type: ignore[no-any-return]


def _set(form: dict[str, Any], section: str, key: str, value: str, unit: str) -> None:
    for s in form["sections"]:
        if s["name"] == section:
            for f in s["fields"]:
                if f["key"] == key:
                    f["value"], f["unit"] = value, unit
                    return
    raise KeyError(key)


def test_list(client: Any) -> None:
    body = client().get("/api/scenarios").json()
    names = {s["name"] for s in body["examples"]}
    assert {"plant_reference", "boiler_house_only"} <= names
    assert body["saved"] == []
    assert all(s["read_only"] for s in body["examples"])


def test_get_form(client: Any) -> None:
    form = _form(client())
    assert form["read_only"] is True
    fuel = next(s for s in form["sections"] if s["name"] == "boiler_house.fuel")
    moist = next(f for f in fuel["fields"] if f["key"] == "moisture_wet_basis")
    assert moist["value"] == "45" and moist["unit"] == "%" and moist["series_ok"] is True
    assert client().get("/api/scenarios/nope?source=example").status_code == 404


def test_validate(client: Any) -> None:
    c = client()
    form = _form(c)
    assert c.post("/api/scenarios/validate", json={"form": form}).json() == {"valid": True}
    _set(form, "boiler_house.fuel", "moisture_wet_basis", "70", "%")
    r = c.post("/api/scenarios/validate", json={"form": form})
    assert r.status_code == 422
    issues = r.json()["issues"]
    assert any(i["field"].startswith("boiler_house.fuel.moisture_wet_basis") for i in issues)
    assert all({"field", "value", "reason", "allowed", "location"} <= set(i) for i in issues)


def test_save_and_conflict(client: Any, web_settings: Any) -> None:
    c = client()
    form = _form(c)
    _set(form, "boiler_house.fuel", "moisture_wet_basis", "50", "%")
    body = {"name": "plant_wet", "derived_from": "example:plant_reference", "form": form}
    r = c.post("/api/scenarios", json=body)
    assert r.status_code == 201 and r.json() == {"name": "plant_wet"}
    assert (web_settings.scenarios_dir / "plant_wet.toml").is_file()
    assert c.post("/api/scenarios", json=body).status_code == 409
    assert c.post("/api/scenarios", json={**body, "name": "../evil"}).status_code == 422
    saved = c.get("/api/scenarios").json()["saved"]
    assert [s["name"] for s in saved] == ["plant_wet"] and not saved[0]["read_only"]
    example = (web_settings.examples_dir / "plant_reference.toml").read_text(encoding="utf-8")
    assert 'moisture_wet_basis = "45 %"' in example  # examples are never overwritten


def test_save_rejects_invalid(client: Any) -> None:
    c = client()
    form = _form(c)
    _set(form, "boiler_house.fuel", "moisture_wet_basis", "70", "%")
    r = c.post("/api/scenarios", json={"name": "bad", "derived_from": "", "form": form})
    assert r.status_code == 422


def test_create_job(client: Any, web_settings: Any) -> None:
    c = client()
    r = c.post("/api/jobs", json={"scenario": "boiler_house_only", "source": "example"})
    assert r.status_code == 202 and r.json()["job_id"]
    jobs = c.get("/api/jobs").json()["jobs"]
    assert jobs[0]["state"] == "queued" and jobs[0]["kind"] == "run"
    assert c.post("/api/jobs", json={"scenario": "missing", "source": "saved"}).status_code == 404
    (web_settings.scenarios_dir / "broken.toml").write_text(
        'schema_version = 1\n[time]\nstart = "x"\n', encoding="utf-8"
    )
    assert c.post("/api/jobs", json={"scenario": "broken", "source": "saved"}).status_code == 422


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("get", "/api/scenarios"),
        ("get", "/api/scenarios/plant_reference?source=example"),
        ("post", "/api/scenarios/validate"),
        ("post", "/api/scenarios"),
        ("post", "/api/jobs"),
        ("get", "/scenarios"),
        ("get", "/scenarios/plant_reference?source=example"),
    ],
)
def test_engineer_only(client: Any, method: str, url: str) -> None:
    r = getattr(client("operator"), method)(url, **({"json": {}} if method == "post" else {}))
    assert r.status_code == 403
