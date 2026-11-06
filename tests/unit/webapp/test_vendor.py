"""Vendored browser libraries are unchanged (T056; feature 005 adds the page's libraries)."""

import hashlib
import re
from pathlib import Path

import pytest

WEBAPP = Path(__file__).parents[3] / "src" / "boidrytwin" / "webapp"
VENDOR_DIRS = [WEBAPP / "static" / "vendor", WEBAPP / "ui" / "vendor"]


@pytest.mark.parametrize("vendor", VENDOR_DIRS, ids=lambda p: p.parent.name)
def test_hashes_match_the_readme(vendor: Path) -> None:
    table = (vendor / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\S+) \| \S+ \| [\d.]+ \| \S+ \| ([0-9a-f]{64}) \|$", table, re.M)
    assert rows
    for name, sha in rows:
        assert hashlib.sha256((vendor / name).read_bytes()).hexdigest() == sha, name
    listed = {name for name, _ in rows} | {"README.md"}
    assert {p.name for p in vendor.iterdir()} == listed
