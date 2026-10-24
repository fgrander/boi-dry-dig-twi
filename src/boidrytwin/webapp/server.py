"""``boidrytwin serve``: the web server and its worker process (contracts/cli-serve.md, R10)."""

from __future__ import annotations

import socket
import sys
import threading
import webbrowser

from boidrytwin.logging import get_logger
from boidrytwin.webapp.jobs import JobQueue
from boidrytwin.webapp.settings import AppSettings
from boidrytwin.webapp.worker import start_worker

EXIT_OK, EXIT_INPUT, EXIT_FAILURE = 0, 1, 3
HOST = "127.0.0.1"

log = get_logger("webapp")


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
        except OSError:
            return False
    return True


def check_folders(settings: AppSettings) -> str | None:
    if not settings.examples_dir.is_dir():
        return f"examples folder not found: {settings.examples_dir}"
    for folder in (settings.runs_dir, settings.scenarios_dir):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return f"cannot create {folder}: {exc}"
    return None


def serve(settings: AppSettings, *, open_browser: bool = True, log_level: str = "INFO") -> int:
    import uvicorn

    from boidrytwin.webapp.app import create_app

    problem = check_folders(settings)
    if problem:
        sys.stderr.write(f"{problem}\n")
        return EXIT_INPUT
    if not port_free(settings.port):
        sys.stderr.write(f"port {settings.port} is in use; choose another with --port\n")
        return EXIT_FAILURE

    queue = JobQueue(settings.app_dir)
    if not queue.read_only:
        queue.restart_rules()
    worker = start_worker(settings.app_dir, settings.runs_dir, log_level)
    url = f"http://{HOST}:{settings.port}"
    config = uvicorn.Config(
        create_app(settings), host=HOST, port=settings.port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    sys.stdout.write(f"serving {url}\n")
    sys.stdout.flush()
    log.info(
        "app_started", url=url, runs=str(settings.runs_dir), scenarios=str(settings.scenarios_dir)
    )
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        worker.terminate()
        worker.join(10)
        q = JobQueue(settings.app_dir)
        if not q.read_only:
            for job in q.jobs():
                if job.state == "running":
                    q.mark_interrupted(job.job_id)
                    log.warning("job_interrupted", job_id=job.job_id)
        log.info("app_stopped")
    return EXIT_OK if server.started else EXIT_FAILURE
