"""Process drawings and the home page (T058; FR-025, FR-026)."""

import xml.etree.ElementTree as ET
from typing import Any

import pytest

pytest.importorskip("fastapi")

SVG = "{http://www.w3.org/2000/svg}svg"


@pytest.mark.parametrize("name", ["plant", "heaters", "dryer"])
@pytest.mark.parametrize("view", ["engineer", "operator"])
def test_diagrams_are_svg_with_values(
    client: Any, example_runs: dict[str, str], name: str, view: str
) -> None:
    rid = example_runs["plant_reference"]
    r = client(view).get(f"/runs/{rid}/diagram/{name}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    root = ET.fromstring(r.text)
    assert root.tag == SVG
    text = " ".join(t for t in root.itertext())
    assert "°C" in text
    if name in ("plant", "heaters"):
        assert "282" in text  # oil supply on its set point
    if name in ("plant", "dryer"):
        assert "540" in text  # drum inlet on its set point


def test_time_changes_the_values(client: Any, example_runs: dict[str, str]) -> None:
    rid = example_runs["oil_demand_step"]
    c = client()
    before = c.get(f"/runs/{rid}/diagram/heaters?time=2026-01-01T05:00:00Z").text
    after = c.get(f"/runs/{rid}/diagram/heaters?time=2026-01-01T06:30:00Z").text
    assert "240.0" in before and "231.6" in after


def test_boiler_only_drawings(client: Any, example_runs: dict[str, str]) -> None:
    rid = example_runs["boiler_house_only"]
    c = client()
    assert c.get(f"/runs/{rid}/diagram/plant").status_code == 200
    assert c.get(f"/runs/{rid}/diagram/dryer").status_code == 404  # no dryer in this run
    assert c.get(f"/runs/{rid}/diagram/nope").status_code == 404


def test_state_api(client: Any, example_runs: dict[str, str]) -> None:
    body = client("operator").get(f"/api/runs/{example_runs['plant_reference']}/state").json()
    assert body["time"] == "2026-01-01T02:00:00Z"
    assert body["boiler"]["oil_supply"]["unit"] == "°C" and len(body["heaters"]) == 3


def test_run_page_has_the_process_section(client: Any, example_runs: dict[str, str]) -> None:
    page = client().get(f"/runs/{example_runs['plant_reference']}").text
    assert 'id="process"' in page and "diagram/plant" in page and 'id="process-time"' in page


def test_home_page_without_runs(client: Any) -> None:
    page = client(view=None).get("/classic").text
    assert "engineer" in page.lower() and "operator" in page.lower()
    assert "No runs yet" in page


def test_home_page_shows_the_latest_plant_run(client: Any, example_runs: dict[str, str]) -> None:
    page = client().get("/classic").text
    assert "<svg" in page and "Oil supply" in page and "Drum inlet" in page
    assert example_runs["plant_reference"] in page  # the latest coupled run


RECIRCULATION_IDS = ("recirc-line", "recirc-damper", "mixing-chamber", "exhaust-fan")


def _ids(root: ET.Element) -> set[str]:
    return {e.get("id", "") for e in root.iter()}


@pytest.mark.parametrize("name", ["plant", "dryer"])
def test_recirculation_is_drawn(
    client: Any, recirculation_run: str, example_runs: dict[str, str], name: str
) -> None:
    c = client()
    r = c.get(f"/runs/{recirculation_run}/diagram/{name}?time=2026-01-01T00:30:00Z")
    assert r.status_code == 200
    root = ET.fromstring(r.text)  # well-formed
    assert set(RECIRCULATION_IDS) <= _ids(root)
    text = " ".join(root.itertext())
    state = c.get(f"/api/runs/{recirculation_run}/state?time=2026-01-01T00:30:00Z").json()
    rec = state["recirculation"]
    for key in ("damper", "flow", "temperature", "pressure"):
        assert rec[key]["text"] in text, key
    assert "Recirculation" in text and "Mixing chamber" in text and "Exhaust fan" in text
    plain = ET.fromstring(c.get(f"/runs/{example_runs['plant_reference']}/diagram/{name}").text)
    assert not set(RECIRCULATION_IDS) & _ids(plain)
