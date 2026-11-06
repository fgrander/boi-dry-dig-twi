"""What the single-page interface adds to the HTTP interface (feature 005)."""

import tomllib
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.jobs import JobQueue
from boidrytwin.webapp.steps import meta_path, read_meta, steps_dir
from boidrytwin.webapp.worker import run_pending

UI = Path(__file__).parents[3] / "src" / "boidrytwin" / "webapp" / "ui"


def _form(c: Any, name: str = "plant_reference", source: str = "example") -> dict[str, Any]:
    r = c.get(f"/api/scenarios/{name}?source={source}")
    assert r.status_code == 200
    return r.json()  # type: ignore[no-any-return]


def _field(form: dict[str, Any], section: str, key: str) -> dict[str, Any]:
    for s in form["sections"]:
        if s["name"] == section:
            for f in s["fields"]:
                if f["key"] == key:
                    return f  # type: ignore[no-any-return]
    raise KeyError(key)


def _save(c: Any, name: str, base: str = "plant_reference") -> None:
    body = {"name": name, "derived_from": f"example:{base}", "form": _form(c, base)}
    assert c.post("/api/scenarios", json=body).status_code == 201


# --- the page ---------------------------------------------------------------------------------


def test_the_page_needs_no_view_choice_and_works_as_engineer(client: Any) -> None:
    c = client(view=None)
    r = c.get("/")
    assert r.status_code == 200
    assert '<div id="app"' in r.text and "/ui/js/main.js" in r.text
    assert c.cookies.get("view") == "engineer"
    assert c.get("/api/scenarios").status_code == 200  # the cookie of the page is enough


def test_the_page_keeps_another_view_out_of_engineer_calls_until_it_is_opened(client: Any) -> None:
    c = client("operator")
    assert c.get("/api/scenarios").status_code == 403
    c.get("/")
    assert c.get("/api/scenarios").status_code == 200


def test_the_windows_program_recognises_the_page_as_a_running_instance(client: Any) -> None:
    # desktop.running_instance() looks for this marker at "/" before it starts a second service
    from boidrytwin.webapp import desktop

    assert desktop.APP_MARKER in client(view=None).get("/").content


def test_the_older_home_page_is_still_there(client: Any) -> None:
    page = client(view=None).get("/classic")
    assert page.status_code == 200
    assert "engineer" in page.text.lower() and "operator" in page.text.lower()


def test_every_script_and_style_of_the_page_is_served(client: Any) -> None:
    c = client(view=None)
    files = [p for p in UI.rglob("*") if p.is_file() and p.suffix in {".js", ".css", ".html"}]
    assert len(files) > 15
    for path in files:
        r = c.get("/ui/" + path.relative_to(UI).as_posix())
        assert r.status_code == 200, path
    assert c.get("/static/vendor/temml.mjs").status_code == 200


def test_every_import_of_the_page_exists() -> None:
    """A missing or misspelt module would leave the page empty."""
    import re

    mapped = {"preact", "preact/hooks", "htm", "uplot", "temml"}
    for path in (UI / "js").rglob("*.js"):
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r'^import [^"]*"([^"]+)";', text, re.M):
            if target in mapped:
                continue
            assert (path.parent / target).resolve().is_file(), f"{path.name} imports {target}"


def test_about(client: Any) -> None:
    body = client().get("/api/ui/about").json()
    assert body["guided_by"] and body["ai_work_hours"] > 0 and body["as_of"]


# --- saved scenarios ----------------------------------------------------------------------------


def test_save_over_a_saved_scenario(client: Any, web_settings: Any) -> None:
    c = client()
    _save(c, "plant_a")
    form = _form(c, "plant_a", "saved")
    assert form["read_only"] is False
    field = _field(form, "boiler_house.fuel", "moisture_wet_basis")
    field["value"] = "50"
    assert c.put("/api/scenarios/plant_a", json={"form": form}).json() == {"name": "plant_a"}
    doc = tomllib.loads((web_settings.scenarios_dir / "plant_a.toml").read_text(encoding="utf-8"))
    assert doc["boiler_house"]["fuel"]["moisture_wet_basis"] == "50 %"
    # what it was derived from is kept
    assert (
        read_meta(web_settings.scenarios_dir / "plant_a.toml").derived_from
        == "example:plant_reference"
    )
    assert (
        _field(_form(c, "plant_a", "saved"), "boiler_house.fuel", "moisture_wet_basis")["value"]
        == "50"
    )


def test_save_refuses_invalid_inputs_and_changes_nothing(client: Any, web_settings: Any) -> None:
    c = client()
    _save(c, "plant_a")
    before = (web_settings.scenarios_dir / "plant_a.toml").read_bytes()
    form = _form(c, "plant_a", "saved")
    _field(form, "boiler_house.fuel", "moisture_wet_basis")["value"] = "70"
    r = c.put("/api/scenarios/plant_a", json={"form": form})
    assert r.status_code == 422
    assert any(
        i["field"].startswith("boiler_house.fuel.moisture_wet_basis") for i in r.json()["issues"]
    )
    assert (web_settings.scenarios_dir / "plant_a.toml").read_bytes() == before


def test_save_refuses_a_file_that_was_changed_elsewhere(client: Any, web_settings: Any) -> None:
    c = client()
    _save(c, "plant_a")
    form = _form(c, "plant_a", "saved")
    path = web_settings.scenarios_dir / "plant_a.toml"
    path.write_text(path.read_text(encoding="utf-8") + "# edited by hand\n", encoding="utf-8")
    r = c.put("/api/scenarios/plant_a", json={"form": form})
    assert r.status_code == 409 and "changed elsewhere" in r.json()["error"]


def test_examples_cannot_be_saved_over_renamed_or_deleted(client: Any) -> None:
    c = client()
    form = _form(c)
    assert c.put("/api/scenarios/plant_reference", json={"form": form}).status_code == 404
    assert c.delete("/api/scenarios/plant_reference").status_code == 404
    assert c.post("/api/scenarios/plant_reference/rename", json={"name": "x"}).status_code == 404


def test_rename_moves_the_scenario_with_its_steps(client: Any, web_settings: Any) -> None:
    c = client()
    form = _form(c)
    field = _field(form, "boiler_house.fuel", "moisture_wet_basis")
    field["kind"] = "steps"
    field["steps"] = {
        "unit": "%",
        "start_value": 45.0,
        "steps": [{"time": "2026-01-01T06:00:00Z", "value": 50.0}],
    }
    body = {"name": "with_steps", "derived_from": "example:plant_reference", "form": form}
    assert c.post("/api/scenarios", json=body).status_code == 201
    r = c.post("/api/scenarios/with_steps/rename", json={"name": "renamed"})
    assert r.json() == {"name": "renamed"}
    folder = web_settings.scenarios_dir
    assert not (folder / "with_steps.toml").exists()
    assert not steps_dir(folder / "with_steps.toml").exists()
    assert (
        steps_dir(folder / "renamed.toml").is_dir() and meta_path(folder / "renamed.toml").is_file()
    )
    renamed = _form(c, "renamed", "saved")
    assert _field(renamed, "boiler_house.fuel", "moisture_wet_basis")["kind"] == "steps"
    assert c.post("/api/scenarios/validate", json={"form": renamed}).json() == {"valid": True}


def test_rename_refuses_a_taken_or_bad_name(client: Any) -> None:
    c = client()
    _save(c, "plant_a")
    _save(c, "plant_b")
    assert c.post("/api/scenarios/plant_a/rename", json={"name": "plant_b"}).status_code == 409
    assert c.post("/api/scenarios/plant_a/rename", json={"name": "../x"}).status_code == 422


def test_delete_removes_the_scenario_and_what_belongs_to_it(client: Any, web_settings: Any) -> None:
    c = client()
    _save(c, "plant_a")
    assert c.delete("/api/scenarios/plant_a").status_code == 204
    assert list(web_settings.scenarios_dir.glob("plant_a*")) == []
    assert c.get("/api/scenarios").json()["saved"] == []
    assert c.delete("/api/scenarios/plant_a").status_code == 404


def test_download_and_upload(client: Any, web_settings: Any) -> None:
    c = client()
    r = c.get("/api/scenarios/boiler_house_only/file?source=example")
    assert r.status_code == 200
    assert r.text == (web_settings.examples_dir / "boiler_house_only.toml").read_text(
        encoding="utf-8"
    )
    up = c.post("/api/scenarios/upload", files={"file": ("copy_1.toml", r.content, "text/plain")})
    assert up.status_code == 201 and up.json() == {"name": "copy_1"}
    assert [s["name"] for s in c.get("/api/scenarios").json()["saved"]] == ["copy_1"]
    again = c.post(
        "/api/scenarios/upload", files={"file": ("copy_1.toml", r.content, "text/plain")}
    )
    assert again.status_code == 409


def test_upload_refuses_what_the_twin_cannot_load(client: Any, web_settings: Any) -> None:
    c = client()
    bad = (web_settings.examples_dir / "invalid_flue_gas.toml").read_bytes()
    r = c.post("/api/scenarios/upload", files={"file": ("bad.toml", bad, "text/plain")})
    assert r.status_code == 422 and r.json()["issues"]
    assert not (web_settings.scenarios_dir / "bad.toml").exists()
    r = c.post("/api/scenarios/upload", files={"file": ("bad name.toml", b"x = 1\n", "text/plain")})
    assert r.status_code == 422
    r = c.post(
        "/api/scenarios/upload", files={"file": ("big.toml", b"#" * 1_000_001, "text/plain")}
    )
    assert r.status_code == 413


# --- running the scenario in the editor ---------------------------------------------------------


def test_run_the_form_without_saving_it(client: Any, web_settings: Any) -> None:
    c = client()
    form = _form(c, "boiler_house_only")
    _field(form, "time", "end")["value"] = "2026-01-01T01:00:00Z"
    _field(form, "boiler_house.fuel", "moisture_wet_basis")["value"] = "40"
    body = {"form": form, "derived_from": "example:boiler_house_only", "label": "wet fuel"}
    r = c.post("/api/jobs/draft", json=body)
    assert r.status_code == 202
    job = JobQueue(web_settings.app_dir).get(r.json()["job_id"])
    assert job.kind == "run" and job.label == "wet fuel" and job.state == "queued"
    frozen = tomllib.loads(Path(job.scenario_path).read_text(encoding="utf-8"))
    assert frozen["boiler_house"]["fuel"]["moisture_wet_basis"] == "40 %"
    assert frozen["time"]["end"] == "2026-01-01T01:00:00Z"
    # nothing is saved, the examples are untouched and the draft folder is gone
    assert c.get("/api/scenarios").json()["saved"] == []
    assert "45 %" in (web_settings.examples_dir / "boiler_house_only.toml").read_text(
        encoding="utf-8"
    )
    assert not list((web_settings.app_dir / "drafts").glob("*"))


def test_a_draft_run_is_computed_with_profiles(client: Any, web_settings: Any) -> None:
    c = client()
    form = _form(c, "reference_constant")
    _field(form, "time", "end")["value"] = "2026-01-01T00:30:00Z"
    job_id = c.post("/api/jobs/draft", json={"form": form}).json()["job_id"]
    assert run_pending(web_settings.app_dir, web_settings.runs_dir) == 1
    job = c.get(f"/api/jobs/{job_id}").json()
    assert job["state"] == "completed" and job["run_id"]
    record = c.get(f"/api/runs/{job['run_id']}/record").json()
    assert record["has_profiles"] is True and record["status"] == "completed"
    assert record["end"] == "2026-01-01T00:30:00Z"
    profiles = c.get(f"/api/runs/{job['run_id']}/profiles").json()
    assert len(profiles["cells"]) == 20


def test_a_draft_with_invalid_inputs_is_not_queued(client: Any, web_settings: Any) -> None:
    c = client()
    form = _form(c, "boiler_house_only")
    _field(form, "boiler_house.fuel", "moisture_wet_basis")["value"] = "70"
    r = c.post("/api/jobs/draft", json={"form": form})
    assert r.status_code == 422 and r.json()["form"]["sections"]
    assert JobQueue(web_settings.app_dir).jobs() == []


# --- report and formulas ------------------------------------------------------------------------


def test_run_record(client: Any, example_runs: dict[str, str]) -> None:
    c = client("operator")
    record = c.get(f"/api/runs/{example_runs['plant_reference']}/record").json()
    assert record["run_id"] == example_runs["plant_reference"]
    assert record["scenario_name"].startswith("Plant reference")
    assert len(record["scenario_sha256"]) == 64
    assert record["model_version"] and record["created_at"] and record["python"]
    assert record["start"] == "2026-01-01T00:00:00Z"
    assert record["has_profiles"] is False
    assert c.get("/api/runs/nope/record").status_code == 404


def test_formulas(client: Any) -> None:
    body = client("operator").get("/api/formulas").json()
    sections = body["sections"]
    assert len(sections) >= 8 and sum(len(s["formulas"]) for s in sections) >= 40
    formula = sections[0]["formulas"][0]
    assert {"title", "equations", "symbols", "module", "function", "sources", "note"} <= set(
        formula
    )
    numbers = sorted(s["number"] for s in body["sources"].values())
    assert numbers == list(range(1, len(numbers) + 1))
    for section in sections:
        for f in section["formulas"]:
            assert f["equations"] and all(key in body["sources"] for key in f["sources"])
