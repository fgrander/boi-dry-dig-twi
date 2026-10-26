"""Test scenario pages: one page per example with drawing, explanation and time plots."""

import re
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp import about
from boidrytwin.webapp.showcase import CASES, GROUPS

ROOT = Path(__file__).parents[3]


def test_every_example_has_a_page() -> None:
    examples = {p.stem for p in (ROOT / "examples").glob("*.toml")}
    assert {c.name for c in CASES} == examples
    for c in CASES:
        assert c.group in GROUPS
        for text in (c.de, c.en):
            assert text.title and text.summary and text.purpose and text.setup and text.watch
        for test in c.tests:
            assert (ROOT / test).is_file(), (c.name, test)
        assert c.diagram in ("plant", "heaters", "dryer")


@pytest.mark.parametrize("view", ["engineer", "operator"])
def test_list_shows_every_scenario(client: Any, example_runs: dict[str, str], view: str) -> None:
    page = client(view).get("/test-scenarios")
    assert page.status_code == 200
    for c in CASES:
        assert f'href="/test-scenarios/{c.name}"' in page.text and c.en.title in page.text
    assert ("run-missing" in page.text) == (view == "engineer")  # recirculation runs missing


def test_page_with_a_run(client: Any, example_runs: dict[str, str]) -> None:
    rid = example_runs["plant_reference"]
    page = client("operator").get("/test-scenarios/plant_reference").text
    assert "Coupled plant, reference" in page and "What it checks" in page
    assert f'href="/runs/{rid}"' in page and "<svg" in page  # the drawing, drawn at the end
    assert re.search(r"columns=oil_outlet_temperature,fuel_feed,heat_to_oil,drum_inlet", page)
    assert 'data-diagram="heaters"' in page and "start-run" not in page  # operator: no start


def test_steps_are_marked(client: Any, example_runs: dict[str, str]) -> None:
    page = client().get("/test-scenarios/oil_demand_step").text
    assert '"time": "2026-01-01T06:00:00Z"' in page and "start-run" in page
    assert 'twin.setupProcess("' in page and '"heaters");' in page  # heaters shown first


def test_page_without_a_run(client: Any) -> None:
    page = client().get("/test-scenarios/step_feed_moisture").text
    assert "No completed run of this scenario yet." in page and "Start a run" in page
    assert "<svg" not in page


def test_invalid_scenario_lists_its_problems(client: Any) -> None:
    page = client().get("/test-scenarios/invalid_flue_gas").text
    assert "Problems found by the validation" in page
    assert "flue_gas.mass_flow" in page and "flue_gas.temperature" in page


def test_german_page(client: Any, example_runs: dict[str, str]) -> None:
    page = client(lang=None).get("/test-scenarios/plant_reference").text
    assert "Gekoppelte Anlage, Referenz" in page and "Zeitverläufe" in page


def test_unknown_scenario(client: Any) -> None:
    assert client().get("/test-scenarios/nope").status_code == 404


def test_home_note_and_recirculation_drawing(client: Any, recirculation_run: str) -> None:
    page = client(lang=None).get("/").text
    assert about.GUIDED_BY in page and "Reine Arbeitszeit der KI" in page
    assert 'id="recirculation"' in page and recirculation_run in page
    assert 'id="mixing-chamber"' in page and 'id="recirc-damper"' in page


def test_home_without_a_recirculation_run(client: Any, example_runs: dict[str, str]) -> None:
    page = client().get("/").text
    assert "No run with a recirculation yet." in page and "built with AI" in page
