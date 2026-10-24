"""Every route is in the permission table and checked for both views (T037; FR-016)."""

from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.app import api_routes, create_app
from boidrytwin.webapp.permissions import PERMISSIONS, allowed


def test_every_route_has_an_entry(web_settings: Any) -> None:
    app = create_app(web_settings)
    names = {r.name for r in api_routes(app)}
    assert names, "no routes"
    assert names <= set(PERMISSIONS), sorted(names - set(PERMISSIONS))
    assert set(PERMISSIONS) <= names, sorted(set(PERMISSIONS) - names)


def test_table() -> None:
    for name, access in PERMISSIONS.items():
        assert allowed(name, "engineer") is True, name
        assert allowed(name, "operator") is (access != "engineer"), name
        assert allowed(name, None) is (access == "public"), name
    assert allowed("not_a_route", "engineer") is False


def _url(path: str) -> str:
    return (
        path.replace("{run_id}", "r")
        .replace("{name}", "n")
        .replace("{job_id}", "j")
        .replace("{path:path}", "x")
    )


def test_operator_refused_on_engineer_routes(client: Any, web_settings: Any) -> None:
    app = create_app(web_settings)
    c = client("operator")
    checked = 0
    for route in api_routes(app):
        if PERMISSIONS[route.name] != "engineer":
            continue
        for method in route.methods:
            r = c.request(method, _url(route.path), json={})
            assert r.status_code == 403, (method, route.path, r.status_code)
            checked += 1
    assert checked >= 8
