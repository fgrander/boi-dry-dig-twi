"""The formula page: every formula linked to the literature (T051; FR-023)."""

import re
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.formulas import FORMULAS, SECTIONS, SOURCES

ROOT = Path(__file__).parents[3]
RESEARCH = "".join(
    (ROOT / f"specs/{feature}/research.md").read_text(encoding="utf-8")
    for feature in (
        "001-boiler-dryer-interface",
        "002-boiler-house-model",
        "004-dryer-exhaust-recirculation",
    )
)


def test_every_formula_has_sources_that_exist() -> None:
    assert len(FORMULAS) >= 25
    for f in FORMULAS:
        assert f.sources, f.title
        for s in f.sources:
            assert s in SOURCES, (f.title, s)
        assert f.section in SECTIONS, f.title


def _balanced(tex: str) -> bool:
    depth = 0
    for i, ch in enumerate(tex):
        if ch == "{" and (i == 0 or tex[i - 1] != "\\"):
            depth += 1
        elif ch == "}" and (i == 0 or tex[i - 1] != "\\"):
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and tex.count(r"\left") == tex.count(r"\right")


def test_equations_and_symbols_are_latex() -> None:
    for f in FORMULAS:
        assert f.equations and f.symbols, f.title
        for tex in [*f.equations, *(s.tex for s in f.symbols)]:
            assert "$" not in tex and _balanced(tex), (f.title, tex)
        for s in f.symbols:
            assert s.meaning and s.unit, (f.title, s.tex)


def test_every_source_is_used_and_linked() -> None:
    used = {s for f in FORMULAS for s in f.sources}
    assert used == set(SOURCES), sorted(set(SOURCES) - used)
    for key, src in SOURCES.items():
        assert src.url.startswith(("https://", "http://")), key
        if src.doi:
            assert src.url == f"https://doi.org/{src.doi}", key
            assert src.link_kind == "doi"
        else:
            assert src.link_kind in ("open access", "search", "publisher"), key


def test_dois_are_the_ones_recorded_in_research() -> None:
    # no DOI is invented here: each must appear in the research notes of features 001/002
    for key, src in SOURCES.items():
        if src.doi:
            assert src.doi in RESEARCH, (key, src.doi)


def test_code_references_exist() -> None:
    for f in FORMULAS:
        module = ROOT / f.module
        assert module.is_file(), (f.title, f.module)
        if f.function:
            assert re.search(
                rf"def {re.escape(f.function)}\b", module.read_text(encoding="utf-8")
            ), (
                f.title,
                f.function,
            )


@pytest.mark.parametrize("view", ["engineer", "operator"])
def test_page(client: Any, view: str) -> None:
    r = client(view).get("/formulas")
    assert r.status_code == 200
    import html

    text = html.unescape(r.text)
    for f in FORMULAS:
        assert f.title in text
        for tex in f.equations:
            assert f'data-tex="{tex}"' in text, tex
    assert "/static/vendor/temml.mjs" in r.text and "/static/vendor/Temml-Local.css" in r.text
    for src in SOURCES.values():
        assert f'href="{src.url}"' in r.text.replace("&amp;", "&")
    assert 'rel="noopener noreferrer"' in r.text
    assert 'href="/formulas"' in client(view).get("/runs").text  # in the navigation


def test_recirculation_formulas() -> None:
    # FR-015: mixing, damper, fan laws, resistance and mixing chamber pressure, with sources
    titles = {f.title: f for f in FORMULAS if f.section == "recirculation"}
    assert SECTIONS["recirculation"]
    for word in ("Mixing", "damper", "Fan", "resistance", "Mixing chamber pressure"):
        assert any(word.lower() in t.lower() for t in titles), word
    used = {s for f in titles.values() for s in f.sources}
    assert {"carolus2013", "bleier1998", "idelchik2007", "ashrae2020", "baehr_kabelac"} <= used
