"""Worker process: runs the queued jobs one at a time (FR-010, research R2).

Each job runs its frozen scenario through :func:`boidrytwin.records.run` (or
:func:`boidrytwin.records.compare`), the same functions as the command line, with a progress
callback that writes ``progress/<job_id>.json``. The worker gets only paths, so it can be
started with the ``spawn`` method on Windows.
"""

from __future__ import annotations

import multiprocessing as mp
import time
import uuid
from pathlib import Path

from boidrytwin.errors import ScenarioValidationError, SimulationError
from boidrytwin.logging import configure_logging, get_logger
from boidrytwin.records import compare, run
from boidrytwin.scenario.loader import load_scenario, require_runnable
from boidrytwin.webapp.jobs import Job, JobQueue
from boidrytwin.webapp.uploads import keep_with_run

log = get_logger("webapp")
POLL = 0.5  # s


class AppGone(Exception):  # noqa: N818 - a stop signal, not an error
    """The app process that started this worker has stopped: abandon the run."""


def app_alive() -> bool:
    parent = mp.parent_process()
    return parent is None or parent.is_alive()


def run_job(queue: JobQueue, job: Job, runs_dir: Path) -> None:
    run_id = str(uuid.uuid4())
    queue.mark_running(job.job_id)
    queue.set_run_id(job.job_id, run_id)
    started = time.perf_counter()
    log.info("job_started", job_id=job.job_id, kind=job.kind, run_id=run_id)

    def progress(phase: str, simulated_s: float, duration_s: float) -> None:
        if not app_alive():  # the restarted app marks this job interrupted
            raise AppGone()
        queue.write_progress(job.job_id, phase, simulated_s, duration_s)

    failed, message = False, None
    try:
        loaded = load_scenario(job.scenario_path)
        require_runnable(loaded)
        if job.kind == "comparison":
            assert job.measured_path is not None
            compare(loaded, job.measured_path, runs_dir, progress=progress, run_id=run_id)
            keep_with_run(Path(job.measured_path), runs_dir / run_id)
        else:
            run(loaded, runs_dir, progress=progress, run_id=run_id)
    except AppGone:
        log.warning("job_abandoned", job_id=job.job_id, reason="the app has stopped")
        return
    except ScenarioValidationError as exc:
        failed, message = True, f"scenario rejected: {exc}"
    except SimulationError as exc:
        failed, message = True, str(exc)
    except Exception as exc:  # a failing run must not stop the worker
        failed, message = True, f"{type(exc).__name__}: {exc}"
        log.exception("job_crashed", job_id=job.job_id)
    has_folder = (runs_dir / run_id).is_dir()
    queue.mark_finished(
        job.job_id, run_id=run_id if has_folder else None, failed=failed, message=message
    )
    log.info(
        "job_finished",
        job_id=job.job_id,
        failed=failed,
        duration_s=round(time.perf_counter() - started, 3),
        message=message,
    )


def run_pending(app_dir: Path, runs_dir: Path) -> int:
    """Run every queued job in order (in this process); returns the number run."""
    queue = JobQueue(app_dir)
    count = 0
    while (job := queue.next_queued()) is not None:
        run_job(queue, job, runs_dir)
        count += 1
    return count


def worker_main(app_dir: str, runs_dir: str, log_level: str = "INFO") -> None:
    """Loop of the worker process; it ends when the app process that started it is gone."""
    configure_logging(level=log_level)
    app, runs = Path(app_dir), Path(runs_dir)
    log.info("worker_started", app_dir=app_dir)
    while True:
        if not app_alive():
            log.info("worker_stopped", reason="the app has stopped")
            return
        queue = JobQueue(app)
        job = None if queue.read_only else queue.next_queued()
        if job is None:
            time.sleep(POLL)
            continue
        run_job(queue, job, runs)


def start_worker(app_dir: Path, runs_dir: Path, log_level: str = "INFO") -> mp.process.BaseProcess:
    ctx = mp.get_context("spawn")
    proc = ctx.Process(
        target=worker_main,
        args=(str(app_dir), str(runs_dir), log_level),
        name="boidrytwin-worker",
        daemon=True,
    )
    proc.start()
    return proc
