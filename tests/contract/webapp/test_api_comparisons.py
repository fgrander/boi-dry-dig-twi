"""Measured uploads in the HTTP interface (T042; FR-017, FR-022)."""

import hashlib
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.jobs import JobQueue
from boidrytwin.webapp.uploads import MAX_BYTES

MEASURED = Path(__file__).parents[3] / "examples" / "synthetic_boiler_measured.csv"


def _post(c: Any, name: str, content: bytes, scenario: str = "oil_demand_step") -> Any:
    return c.post(
        "/api/comparisons",
        data={"scenario": scenario, "source": "example"},
        files={"measured": (name, content, "text/csv")},
    )


def test_engineer_only(client: Any) -> None:
    assert _post(client("operator"), "m.csv", MEASURED.read_bytes()).status_code == 403


def test_type_and_size(client: Any) -> None:
    c = client()
    assert _post(c, "m.xlsx", b"x").status_code == 422
    big = b"time,o2_dry\n" + b"0" * (MAX_BYTES + 1)
    assert _post(c, "m.csv", big).status_code == 413


def test_invalid_content_reports_issues(client: Any) -> None:
    r = _post(client(), "m.csv", b"time,no_such_output\nunit,K\n2026-01-01T00:00:00Z,1\n")
    assert r.status_code == 422
    assert any(i["field"].startswith("measured.") for i in r.json()["issues"])


def test_unknown_scenario(client: Any) -> None:
    assert _post(client(), "m.csv", MEASURED.read_bytes(), scenario="nope").status_code == 404


def test_valid_upload_is_queued_unchanged(client: Any, web_settings: Any) -> None:
    content = MEASURED.read_bytes()
    r = _post(client(), "plant_data.csv", content)
    assert r.status_code == 202
    job = JobQueue(web_settings.app_dir).get(r.json()["job_id"])
    assert job.kind == "comparison" and job.measured_path
    stored = Path(job.measured_path)
    assert stored.name == "plant_data.csv"
    assert hashlib.sha256(stored.read_bytes()).hexdigest() == hashlib.sha256(content).hexdigest()
    assert (job.model_extra or {}).get("measured_sha256") == hashlib.sha256(content).hexdigest()
