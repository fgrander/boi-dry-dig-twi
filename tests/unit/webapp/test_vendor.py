"""Vendored browser libraries are unchanged (T056)."""

import hashlib
import re
from pathlib import Path

VENDOR = Path(__file__).parents[3] / "src" / "boidrytwin" / "webapp" / "static" / "vendor"


def test_hashes_match_the_readme() -> None:
    table = (VENDOR / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (\S+) \| \S+ \| [\d.]+ \| \S+ \| ([0-9a-f]{64}) \|$", table, re.M)
    assert rows
    for name, sha in rows:
        assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == sha, name
    listed = {name for name, _ in rows} | {"README.md"}
    assert {p.name for p in VENDOR.iterdir()} == listed
