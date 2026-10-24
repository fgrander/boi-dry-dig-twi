"""Run pages render for both views (T019; US1)."""

import json
from typing import Any

import pytest

pytest.importorskip("fastapi")


@pytest.mark.parametrize("view", ["engineer", "operator"])
def test_pages(client: Any, example_runs: dict[str, str], view: str) -> None:
    c = client(view)
    page = c.get("/runs")
    assert page.status_code == 200 and "Plant reference" in page.text
    rid = example_runs["plant_reference"]
    run = c.get(f"/runs/{rid}")
    assert run.status_code == 200
    assert 'id="plots"' in run.text and "plotly.min.js" in run.text
    assert "toImage" in run.text or "displaylogo" in run.text  # PNG download stays enabled
    other = example_runs["boiler_house_only"]
    both = c.get(f"/compare?runs={rid},{other}")
    assert both.status_code == 200 and rid in both.text and other in both.text


def test_failed_balances_are_visible(
    client: Any, web_settings: Any, example_runs: dict[str, str]
) -> None:
    rid = example_runs["boiler_house_only"]
    path = web_settings.runs_dir / rid / "run_record.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    entry = record["plant_balance_report"]["boiler_house"]["energy"]
    entry["passed"] = False
    record["plant_balance_report"]["passed"] = False
    path.write_text(json.dumps(record), encoding="utf-8")
    c = client()
    assert "failed" in c.get("/runs").text.lower()
    page = c.get(f"/runs/{rid}").text
    assert "boiler_house" in page and "energy" in page and "bad" in page
