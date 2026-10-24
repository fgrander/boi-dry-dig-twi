"""A run started from the app equals the CLI run of its saved scenario (T027; FR-009, SC-003)."""

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.cli import main
from boidrytwin.webapp.worker import run_pending


def _set(form: dict[str, Any], section: str, key: str, **values: Any) -> None:
    field = next(
        f for s in form["sections"] if s["name"] == section for f in s["fields"] if f["key"] == key
    )
    field.update(values)


def test_app_run_identical_to_cli(
    client: Any, web_settings: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    c = client()
    form = c.get("/api/scenarios/plant_reference?source=example").json()
    _set(form, "time", "end", raw='"2026-01-01T08:00:00Z"', value=None, unit=None)
    _set(form, "boiler_house.fuel", "moisture_wet_basis", value="50", unit="%")
    _set(
        form,
        "boiler_house.thermal_oil",
        "return_temperature",
        kind="steps",
        steps={
            "unit": "degC",
            "start_value": 240.0,
            "steps": [{"time": "2026-01-01T06:00:00Z", "value": 231.6}],
        },
    )
    r = c.post(
        "/api/scenarios",
        json={"name": "plant_wet_fuel", "derived_from": "example:plant_reference", "form": form},
    )
    assert r.status_code == 201, r.text
    job = c.post("/api/jobs", json={"scenario": "plant_wet_fuel", "source": "saved"}).json()[
        "job_id"
    ]
    assert run_pending(web_settings.app_dir, web_settings.runs_dir) == 1
    state = c.get(f"/api/jobs/{job}").json()
    assert state["state"] == "completed", state
    folder = web_settings.runs_dir / state["run_id"]
    assert (folder / "results.csv").is_file() and (folder / "boiler_results.csv").is_file()

    capsys.readouterr()
    assert main(["rerun", str(folder / "run_record.json")]) == 0
    assert "identical: true" in capsys.readouterr().out

    out = Path(web_settings.runs_dir.parent / "cli_runs")
    assert (
        main(["run", str(web_settings.scenarios_dir / "plant_wet_fuel.toml"), "--out", str(out)])
        == 0
    )
    cli_folder = next(out.iterdir())
    for name in ("results.csv", "boiler_results.csv"):
        assert (cli_folder / name).read_bytes() == (folder / name).read_bytes(), name
    record = json.loads((folder / "run_record.json").read_text(encoding="utf-8"))
    assert record["status"] == "completed"
