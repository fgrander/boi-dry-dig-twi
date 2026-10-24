"""Runs part of the HTTP interface (T017; contracts/http-api.md, FR-001, FR-004)."""

import json
from typing import Any

import pytest

pytest.importorskip("fastapi")

SUMMARY_FIELDS = {"run_id", "scenario_name", "created_at", "kind", "status", "checks_passed",
                  "warnings", "flags", "origin", "note"}  # fmt: skip


@pytest.mark.parametrize("view", ["engineer", "operator"])
def test_list(client: Any, example_runs: dict[str, str], view: str) -> None:
    r = client(view).get("/api/runs")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3 and {x["run_id"] for x in body["runs"]} == set(example_runs.values())
    assert set(body["runs"][0]) >= SUMMARY_FIELDS


def test_filters_and_paging(client: Any, example_runs: dict[str, str]) -> None:
    c = client()
    assert {x["kind"] for x in c.get("/api/runs?kind=boiler").json()["runs"]} == {"boiler"}
    assert c.get("/api/runs?q=plant%20reference").json()["total"] == 1
    page = c.get("/api/runs?limit=2&offset=0").json()
    assert len(page["runs"]) == 2 and page["total"] == 3
    rest = c.get("/api/runs?limit=2&offset=2").json()
    assert len(rest["runs"]) == 1


def test_run_detail(client: Any, example_runs: dict[str, str]) -> None:
    r = client().get(f"/api/runs/{example_runs['plant_reference']}")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["kind"] == "coupled"
    entries = body["balances"]["entries"]
    assert set(entries) >= {"boiler_house", "oil_circuit", "dryer", "interface", "plant"}
    q = entries["boiler_house"]["energy"]
    assert set(q) >= {"residual", "relative_residual", "tolerance", "passed"}
    assert body["balances"]["passed"] is True
    assert isinstance(body["warnings"], list) and isinstance(body["flag_periods"], list)
    assert set(body["files"]) >= {"boiler_results.csv", "results.csv"}


def test_dryer_only_balance_shown_as_one_entry(
    client: Any, web_settings: Any, tmp_path: Any
) -> None:
    from boidrytwin import load_scenario
    from boidrytwin.records import run
    from tests.webapp_conftest import EXAMPLES, shortened

    path = shortened(EXAMPLES / "reference_constant.toml", tmp_path, end="2026-01-01T00:30:00Z")
    record = run(load_scenario(path), out_dir=web_settings.runs_dir)
    body = client().get(f"/api/runs/{record.run_id}").json()
    assert set(body["balances"]["entries"]) == {"dryer"}
    assert set(body["balances"]["entries"]["dryer"]) == {"dry_solids", "water", "gas", "energy"}


def test_unknown_run(client: Any, example_runs: dict[str, str]) -> None:
    assert client().get("/api/runs/does-not-exist").status_code == 404
    assert client().get("/api/runs/..%2F..%2Fetc").status_code == 404


def test_delete(client: Any, web_settings: Any, example_runs: dict[str, str]) -> None:
    rid = example_runs["boiler_house_only"]
    assert client("operator").delete(f"/api/runs/{rid}?confirm=true").status_code == 403
    assert client().delete(f"/api/runs/{rid}").status_code == 400
    assert client().delete(f"/api/runs/{rid}?confirm=true").status_code == 204
    assert not (web_settings.runs_dir / rid).exists()
    actions = (web_settings.app_dir / "actions.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(actions[-1])["action"] == "run_deleted"
