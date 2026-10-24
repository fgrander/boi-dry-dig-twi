"""Job queue in the HTTP interface (T026; contracts/http-api.md, FR-010, FR-011)."""

from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.jobs import JobQueue


def _queue(web_settings: Any, n: int, view: str = "engineer", kind: str = "run") -> list[str]:
    q = JobQueue(web_settings.app_dir)
    path = web_settings.examples_dir / "boiler_house_only.toml"
    return [q.enqueue(kind, path, view=view).job_id for _ in range(n)]  # type: ignore[arg-type]


def test_list_in_order_with_progress(client: Any, web_settings: Any) -> None:
    ids = _queue(web_settings, 3)
    q = JobQueue(web_settings.app_dir)
    q.mark_running(ids[0])
    q.write_progress(ids[0], "simulating", 1800.0, 3600.0)
    jobs = client("operator").get("/api/jobs").json()["jobs"]
    assert [j["job_id"] for j in jobs] == ids
    assert jobs[0]["progress"]["simulated_s"] == 1800.0 and jobs[1]["progress"] is None
    one = client().get(f"/api/jobs/{ids[1]}").json()
    assert one["state"] == "queued"
    assert client().get("/api/jobs/nope").status_code == 404


def test_start_and_drop_states(client: Any, web_settings: Any) -> None:
    ids = _queue(web_settings, 2)
    c = client()
    assert c.post(f"/api/jobs/{ids[0]}/start").status_code == 409  # queued already
    assert c.post(f"/api/jobs/{ids[0]}/drop").status_code == 200
    assert c.post(f"/api/jobs/{ids[0]}/drop").status_code == 409  # dropped
    JobQueue(web_settings.app_dir).restart_rules()
    assert c.post(f"/api/jobs/{ids[1]}/start").status_code == 202  # not_started → queued


def test_operator_only_own_what_if_jobs(client: Any, web_settings: Any) -> None:
    eng = _queue(web_settings, 1)[0]
    own = _queue(web_settings, 1, view="operator", kind="what_if")[0]
    op = client("operator")
    assert op.post(f"/api/jobs/{eng}/drop").status_code == 403
    assert op.post(f"/api/jobs/{own}/drop").status_code == 200
