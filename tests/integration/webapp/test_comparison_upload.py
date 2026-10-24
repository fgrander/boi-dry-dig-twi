"""Comparison upload equals the CLI comparison (T043; FR-017, FR-018)."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin import load_scenario
from boidrytwin.records import compare
from boidrytwin.webapp.worker import run_pending
from tests.webapp_conftest import shortened

MEASURED = Path(__file__).parents[3] / "examples" / "synthetic_boiler_measured.csv"


def test_upload_matches_records_compare(client: Any, web_settings: Any, tmp_path: Path) -> None:
    shortened(
        web_settings.examples_dir / "oil_demand_step.toml",
        web_settings.scenarios_dir,
        end="2026-01-01T08:00:00Z",
        name="step_short.toml",
    )
    c = client()
    r = c.post(
        "/api/comparisons",
        data={"scenario": "step_short", "source": "saved"},
        files={"measured": ("plant.csv", MEASURED.read_bytes(), "text/csv")},
    )
    assert r.status_code == 202, r.text
    run_pending(web_settings.app_dir, web_settings.runs_dir)
    job = c.get(f"/api/jobs/{r.json()['job_id']}").json()
    assert job["state"] == "completed", job
    folder = web_settings.runs_dir / job["run_id"]
    app_report = json.loads((folder / "validation_report.json").read_text(encoding="utf-8"))
    kept = folder / "measured" / "plant.csv"
    assert (
        hashlib.sha256(kept.read_bytes()).digest() == hashlib.sha256(MEASURED.read_bytes()).digest()
    )

    loaded = load_scenario(web_settings.scenarios_dir / "step_short.toml")
    _, cli_report = compare(loaded, MEASURED, tmp_path / "cli")
    cli = cli_report.to_dict()
    for name, out in cli["outputs"].items():
        mine = app_report["outputs"][name]
        for key in ("n_compared", "n_excluded", "bias", "rmse", "tolerance", "passed"):
            assert mine[key] == out[key], (name, key)
    assert len(app_report["excluded"]) == len(cli["excluded"])

    body = c.get(f"/api/runs/{job['run_id']}/comparison").json()
    assert body["report"]["outputs"].keys() == cli["outputs"].keys()
    o2 = body["series"]["o2_dry"]
    assert o2["unit"] == "%" and len(o2["times"]) == len(o2["measured"]) == len(o2["predicted"])
    assert any(not x for x in o2["included"])  # excluded samples are marked
    page = c.get(f"/runs/{job['run_id']}")
    assert page.status_code == 200 and 'id="comparison"' in page.text
