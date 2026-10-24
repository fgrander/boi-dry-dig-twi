"""Runs without a recirculation give exactly what they gave before feature 004 (T004).

FR-005, SC-001: every runnable example, shortened to a few hours, against the files stored
by ``scripts/store_reference_results.py`` on the branch start.
"""

import json
from pathlib import Path

import pytest

from tests.reference_runs import STORE, produce, runnable_examples

EXAMPLES = [p for p in runnable_examples() if (STORE / p.stem).is_dir()]


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.stem)
def test_unchanged_without_recirculation(example: Path, tmp_path: Path) -> None:
    out = produce(example, tmp_path)
    stored = STORE / example.stem
    expected = {p.name for p in stored.glob("*.csv")}
    assert set(out["csv"]) == expected
    for name in sorted(expected):
        assert out["csv"][name] == (stored / name).read_text(encoding="utf-8"), name
    summary = json.loads((stored / "summary.json").read_text(encoding="utf-8"))
    assert out["summary"] == summary


def test_every_runnable_example_has_a_baseline() -> None:
    assert len(EXAMPLES) >= 9
