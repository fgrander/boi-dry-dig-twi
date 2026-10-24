"""Page language (FR-027): German by default, English on request."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from boidrytwin.webapp import i18n
from boidrytwin.webapp.process_state import Value

TEMPLATES = Path(i18n.__file__).parent / "templates"
TRANSLATED = [
    "base.html",
    "index.html",
    *(f"diagrams/{n}.svg" for n in ("plant", "heaters", "dryer")),
]


@pytest.mark.parametrize("name", TRANSLATED)
def test_every_text_has_a_german_entry(name: str) -> None:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    keys = re.findall(r"""\bt\((["'])(.+?)\1\)""", text)
    assert keys or name == "base.html"
    missing = [k for _, k in keys if k not in i18n.DE]
    assert not missing


def test_values_get_a_decimal_comma_in_german() -> None:
    v = Value(282.04, "°C", 1)
    assert i18n.number(v, "de") == "282,0 °C" and i18n.number(v, "en") == "282.0 °C"
    assert i18n.number(Value(None, "°C"), "de") == "–"
    assert i18n.number(12.345, "de", 1) == "12,3"
    assert i18n.translate("Fuel", "de") == "Brennstoff" and i18n.translate("Fuel", "en") == "Fuel"
    assert i18n.translate("not translated", "de") == "not translated"


def test_german_is_the_default(client: Any) -> None:
    page = client(view=None, lang=None).get("/").text
    assert '<html lang="de">' in page and "Anlagenzwilling" in page and "Noch keine Läufe" in page
    assert 'href="/lang/en?next=/"' in page  # the switch to English


def test_home_and_drawings_in_german(client: Any, example_runs: dict[str, str]) -> None:
    c = client(lang=None)
    page = c.get("/").text
    assert "Ölvorlauf" in page and "282,0 °C" in page and "Rauchgas" in page
    svg = c.get(f"/runs/{example_runs['plant_reference']}/diagram/heaters").text
    assert "Thermalölerhitzer" in svg and "Strahlung" in svg and "240,0 °C" in svg


def test_switch_to_english_and_back(client: Any) -> None:
    c = client(view=None, lang=None)
    r = c.get("/lang/en", params={"next": "/formulas"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/formulas"
    assert c.cookies.get("lang") == "en"
    page = c.get("/").text
    assert '<html lang="en">' in page and "No runs yet" in page
    c.get("/lang/de")
    assert "Noch keine Läufe" in c.get("/").text


@pytest.mark.parametrize("target", ["//evil.example", r"/\evil.example", "https://evil.example"])
def test_switch_only_goes_back_into_the_app(client: Any, target: str) -> None:
    r = client().get("/lang/de", params={"next": target}, follow_redirects=False)
    assert r.headers["location"] == "/"


def test_unknown_language(client: Any) -> None:
    assert client().get("/lang/fr").status_code == 404
