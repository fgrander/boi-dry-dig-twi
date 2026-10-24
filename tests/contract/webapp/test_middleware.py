"""Request rules of the HTTP interface (T008; contracts/http-api.md, research R8, FR-020)."""

import re
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

TEMPLATES = Path(__file__).parents[3] / "src" / "boidrytwin" / "webapp" / "templates"


def test_foreign_host_rejected(client: Any) -> None:
    c = client()
    assert c.get("/api/runs", headers={"Host": "evil.example"}).status_code == 421
    assert c.get("/", headers={"Host": "127.0.0.1:9999"}).status_code == 421


def test_foreign_origin_rejected_for_state_changes(client: Any) -> None:
    c = client()
    r = c.post("/api/jobs", json={"scenario": "x"}, headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    r = c.post("/api/jobs", json={"scenario": "x"}, headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_view_required(client: Any) -> None:
    c = client(view=None)
    page = c.get("/runs", follow_redirects=False)
    assert page.status_code in (302, 303, 307) and page.headers["location"] == "/"
    assert c.get("/api/runs").status_code == 401
    assert client(view="nonsense").get("/api/runs").status_code == 401


def test_view_choice_page(client: Any) -> None:
    r = client(view=None).get("/")
    assert r.status_code == 200
    assert "engineer" in r.text.lower() and "operator" in r.text.lower()


def test_view_is_set_by_the_choice(client: Any) -> None:
    c = client(view=None)
    r = c.post("/view", data={"view": "operator"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert c.cookies.get("view") == "operator"


def test_assets_are_local(client: Any) -> None:
    r = client().get("/static/plotly.min.js")
    assert r.status_code == 200 and len(r.content) > 1_000_000
    for path in TEMPLATES.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"""(src|href)=["']https?://""", text), path.name
