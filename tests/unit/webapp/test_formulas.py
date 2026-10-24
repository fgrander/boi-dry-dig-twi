"""The formula page: every formula linked to the literature (T051; FR-023)."""

import re
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.formulas import FORMULAS, SECTIONS, SOURCES

ROOT = Path(__file__).parents[3]
RESEARCH = (ROOT / "specs/001-boiler-dryer-interface/research.md").read_text(encoding="utf-8") + (
    ROOT / "specs/002-boiler-house-model/research.md"
).read_text(encoding="utf-8")


def test_every_formula_has_sources_that_exist() -> None:
    assert len(FORMULAS) >= 25
    for f in FORMULAS:
        assert f.sources, f.title
        for s in f.sources:
            assert s in SOURCES, (f.title, s)
        assert f.section in SECTIONS, f.title


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
    for f in FORMULAS:
        assert f.title in r.text
    for src in SOURCES.values():
        assert f'href="{src.url}"' in r.text.replace("&amp;", "&")
    assert 'rel="noopener noreferrer"' in r.text
    assert 'href="/formulas"' in client(view).get("/runs").text  # in the navigation
