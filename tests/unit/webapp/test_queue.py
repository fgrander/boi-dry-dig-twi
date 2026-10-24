"""Job queue file and state transitions (T007; FR-010, FR-011, data-model §8)."""

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.jobs import JobQueue, JobStateError


@pytest.fixture
def queue(web_settings: Any) -> JobQueue:
    return JobQueue(web_settings.app_dir)


def _scenario(web_settings: Any) -> Path:
    return web_settings.examples_dir / "boiler_house_only.toml"


def test_enqueue_freezes_the_scenario_and_writes_the_file(
    queue: JobQueue, web_settings: Any
) -> None:
    job = queue.enqueue("run", _scenario(web_settings), view="engineer")
    frozen = Path(job.scenario_path)
    assert frozen.is_file() and frozen.parent == web_settings.app_dir / "jobs" / job.job_id
    doc = json.loads((web_settings.app_dir / "queue.json").read_text(encoding="utf-8"))
    assert doc["version"] == 1 and doc["jobs"][0]["state"] == "queued"
    assert not list(web_settings.app_dir.glob("*.tmp"))  # atomic write leaves no temporaries


def test_transitions(queue: JobQueue, web_settings: Any) -> None:
    a = queue.enqueue("run", _scenario(web_settings), view="engineer")
    b = queue.enqueue("run", _scenario(web_settings), view="engineer")
    assert queue.next_queued().job_id == a.job_id  # FIFO
    queue.mark_running(a.job_id)
    queue.mark_finished(a.job_id, run_id="r1", failed=False)
    assert queue.get(a.job_id).state == "completed" and queue.get(a.job_id).run_id == "r1"
    queue.mark_running(b.job_id)
    queue.mark_finished(b.job_id, run_id=None, failed=True, message="solver failed")
    assert queue.get(b.job_id).state == "failed" and queue.get(b.job_id).message == "solver failed"
    with pytest.raises(JobStateError):
        queue.mark_running(a.job_id)


def test_restart_rules(queue: JobQueue, web_settings: Any) -> None:
    a = queue.enqueue("run", _scenario(web_settings), view="engineer")
    b = queue.enqueue("run", _scenario(web_settings), view="engineer")
    queue.mark_running(a.job_id)
    changed = JobQueue(web_settings.app_dir).restart_rules()
    assert set(changed) == {a.job_id, b.job_id}
    q = JobQueue(web_settings.app_dir)
    assert q.get(a.job_id).state == "interrupted" and q.get(b.job_id).state == "not_started"
    assert q.next_queued() is None  # nothing starts on its own


def test_start_and_drop_only_from_allowed_states(queue: JobQueue, web_settings: Any) -> None:
    a = queue.enqueue("run", _scenario(web_settings), view="engineer")
    with pytest.raises(JobStateError):
        queue.start(a.job_id)  # already queued
    queue.mark_running(a.job_id)
    with pytest.raises(JobStateError):
        queue.drop(a.job_id)  # running
    JobQueue(web_settings.app_dir).restart_rules()
    q = JobQueue(web_settings.app_dir)
    q.start(a.job_id)  # interrupted → queued
    assert q.get(a.job_id).state == "queued"
    q.drop(a.job_id)
    assert q.get(a.job_id).state == "dropped"


def test_unknown_fields_kept_and_newer_version_untouched(
    queue: JobQueue, web_settings: Any
) -> None:
    job = queue.enqueue("run", _scenario(web_settings), view="engineer")
    path = web_settings.app_dir / "queue.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["jobs"][0]["extra_field"] = 42
    path.write_text(json.dumps(doc), encoding="utf-8")
    q = JobQueue(web_settings.app_dir)
    q.mark_running(job.job_id)
    assert json.loads(path.read_text(encoding="utf-8"))["jobs"][0]["extra_field"] == 42

    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["version"] = 99
    path.write_text(json.dumps(doc), encoding="utf-8")
    before = path.read_bytes()
    q = JobQueue(web_settings.app_dir)
    assert q.read_only
    with pytest.raises(JobStateError):
        q.enqueue("run", _scenario(web_settings), view="engineer")
    assert path.read_bytes() == before
