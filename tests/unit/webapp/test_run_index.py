"""Run list of the web app (T006; FR-001, edge cases)."""

from datetime import UTC
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp import run_index


def test_lists_runs_newest_first(web_settings: Any, example_runs: dict[str, str]) -> None:
    index = run_index.RunIndex(web_settings.runs_dir)
    runs = index.list()
    assert {r.run_id for r in runs} == set(example_runs.values())
    times = [r.created_at for r in runs]
    assert times == sorted(times, reverse=True)
    assert all(
        r.created_at.tzinfo is not None and r.created_at.utcoffset() == UTC.utcoffset(None)
        for r in runs
    )
    by_id = {r.run_id: r for r in runs}
    assert by_id[example_runs["boiler_house_only"]].kind == "boiler"
    assert by_id[example_runs["plant_reference"]].kind == "coupled"
    ref = by_id[example_runs["plant_reference"]]
    assert ref.status == "completed" and ref.checks_passed is True
    assert ref.scenario_name.startswith("Plant reference")
    step = by_id[example_runs["oil_demand_step"]]
    assert isinstance(step.warnings, int) and isinstance(step.flags, dict)


def test_damaged_record_is_listed_with_a_note(
    web_settings: Any, example_runs: dict[str, str]
) -> None:
    bad = web_settings.runs_dir / "broken-run"
    bad.mkdir()
    (bad / "run_record.json").write_text("{not json", encoding="utf-8")
    runs = run_index.RunIndex(web_settings.runs_dir).list()
    broken = [r for r in runs if r.run_id == "broken-run"]
    assert len(broken) == 1 and broken[0].note
    assert len(runs) == len(example_runs) + 1


def test_app_folder_is_not_a_run(web_settings: Any, example_runs: dict[str, str]) -> None:
    (web_settings.runs_dir / ".app").mkdir()
    runs = run_index.RunIndex(web_settings.runs_dir).list()
    assert ".app" not in {r.run_id for r in runs}


def test_cached_by_modification_time(
    web_settings: Any, example_runs: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    index = run_index.RunIndex(web_settings.runs_dir)
    index.list()
    reads: list[Path] = []
    original = run_index.read_summary
    monkeypatch.setattr(run_index, "read_summary", lambda p: reads.append(p) or original(p))
    index.list()
    assert reads == []


def test_filters(web_settings: Any, example_runs: dict[str, str]) -> None:
    index = run_index.RunIndex(web_settings.runs_dir)
    assert {r.kind for r in index.list(kind="boiler")} == {"boiler"}
    assert [r.run_id for r in index.list(q="plant ref")] == [example_runs["plant_reference"]]
    assert index.list(status="failed") == []
