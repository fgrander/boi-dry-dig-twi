"""Worker: order, progress, failures, interruption (T028; FR-010, FR-011)."""

import json
import time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.errors import SimulationError
from boidrytwin.webapp.jobs import JobQueue
from boidrytwin.webapp.worker import run_pending, start_worker
from tests.webapp_conftest import shortened


def _short(web_settings: Any, name: str, end: str = "2026-01-01T00:30:00Z") -> Path:
    return shortened(
        web_settings.examples_dir / f"{name}.toml", web_settings.scenarios_dir, end=end
    )


def test_jobs_run_in_order_with_progress(web_settings: Any) -> None:
    q = JobQueue(web_settings.app_dir)
    path = _short(web_settings, "boiler_house_only")
    ids = [q.enqueue("run", path, view="engineer").job_id for _ in range(3)]
    assert run_pending(web_settings.app_dir, web_settings.runs_dir) == 3
    jobs = JobQueue(web_settings.app_dir).jobs()
    assert [j.state for j in jobs] == ["completed"] * 3
    starts = [j.started_at for j in jobs]
    assert starts == sorted(starts)
    for job_id in ids:
        progress = q.read_progress(job_id)
        assert progress is not None and progress["phase"] == "writing"
        assert progress["simulated_s"] == pytest.approx(1800.0)


def test_solver_failure_is_recorded(web_settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import boidrytwin.records as records

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise SimulationError("solver failed at t = 12.0 s: test")

    monkeypatch.setattr(records, "simulate_plant", boom)
    q = JobQueue(web_settings.app_dir)
    job = q.enqueue("run", _short(web_settings, "boiler_house_only"), view="engineer")
    run_pending(web_settings.app_dir, web_settings.runs_dir)
    done = JobQueue(web_settings.app_dir).get(job.job_id)
    assert done.state == "failed" and "solver failed" in (done.message or "")
    assert done.run_id is not None
    record = json.loads(
        (web_settings.runs_dir / done.run_id / "run_record.json").read_text(encoding="utf-8")
    )
    assert record["status"] == "failed"


def test_rejected_scenario_fails_without_crashing(web_settings: Any) -> None:
    bad = web_settings.scenarios_dir / "bad.toml"
    bad.write_text('schema_version = 1\n[time]\nstart = "nope"\n', encoding="utf-8")
    q = JobQueue(web_settings.app_dir)
    a = q.enqueue("run", bad, view="engineer")
    b = q.enqueue("run", _short(web_settings, "boiler_house_only"), view="engineer")
    run_pending(web_settings.app_dir, web_settings.runs_dir)
    q = JobQueue(web_settings.app_dir)
    assert q.get(a.job_id).state == "failed" and "rejected" in (q.get(a.job_id).message or "")
    assert q.get(b.job_id).state == "completed"


def test_killed_worker_gives_interrupted_and_not_started(web_settings: Any) -> None:
    q = JobQueue(web_settings.app_dir)
    long = _short(web_settings, "plant_reference", end="2026-01-03T00:00:00Z")
    first = q.enqueue("run", long, view="engineer")
    second = q.enqueue("run", long, view="engineer")
    proc = start_worker(web_settings.app_dir, web_settings.runs_dir, log_level="WARNING")
    try:
        deadline = time.monotonic() + 120
        while JobQueue(web_settings.app_dir).get(first.job_id).state != "running":
            assert time.monotonic() < deadline, "worker did not start the job"
            time.sleep(0.2)
    finally:
        proc.terminate()
        proc.join(10)
    JobQueue(web_settings.app_dir).restart_rules()
    q = JobQueue(web_settings.app_dir)
    assert q.get(first.job_id).state == "interrupted"
    assert q.get(second.job_id).state == "not_started"
    assert q.next_queued() is None
