"""Run queue on disk (FR-010, FR-011; data-model §8, contracts/app-state.md).

``queue.json`` holds the jobs in queue order. The web server and the worker are separate
processes, so every change re-reads the file under a lock file and writes it back atomically
(temporary file, then rename). Unknown fields are kept. A file from a newer app version is
opened read-only.

A job's scenario is *frozen* at enqueue time: the TOML and every file it references are
copied into ``jobs/<job_id>/``, so later edits of the scenario never change a queued run.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from boidrytwin.logging import get_logger

VERSION = 1
JobKind = Literal["run", "baseline", "what_if", "comparison"]
JobState = Literal[
    "queued", "running", "completed", "failed", "interrupted", "not_started", "dropped"
]
LOCK_TIMEOUT = 10.0  # s
STALE_LOCK = 30.0  # s
FILE_REF = re.compile(r'file\s*=\s*"([^"]+)"')

log = get_logger("webapp")


class JobStateError(RuntimeError):
    """A transition that is not allowed from the job's current state."""


class Job(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str
    kind: JobKind
    scenario_path: str
    measured_path: str | None = None
    state: JobState = "queued"
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    run_id: str | None = None
    message: str | None = None
    view: Literal["engineer", "operator"] = "engineer"
    label: str | None = None


def now() -> datetime:
    return datetime.now(UTC)


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def freeze_scenario(source: Path, folder: Path) -> Path:
    """Copy a scenario and the files it references into ``folder``; returns the copy."""
    folder.mkdir(parents=True, exist_ok=True)
    inputs = folder / "inputs"
    text = source.read_text(encoding="utf-8")
    copied: dict[str, str] = {}

    def copy_ref(match: re.Match[str]) -> str:
        ref = match.group(1)
        if ref not in copied:
            original = Path(ref) if Path(ref).is_absolute() else source.parent / ref
            if not original.is_file():
                return match.group(0)  # left for the loader to report
            inputs.mkdir(exist_ok=True)
            target = inputs / f"{len(copied):02d}_{original.name}"
            shutil.copy2(original, target)
            copied[ref] = f"inputs/{target.name}"
        return f'file = "{copied[ref]}"'

    frozen = folder / "scenario.toml"
    frozen.write_text(FILE_REF.sub(copy_ref, text), encoding="utf-8", newline="\n")
    return frozen


class JobQueue:
    def __init__(self, app_dir: Path) -> None:
        self.app_dir = app_dir
        self.path = app_dir / "queue.json"
        self.lock_path = app_dir / "queue.lock"
        self.read_only = False
        self._load()

    # --- file handling ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            self._doc: dict[str, Any] = {"version": VERSION, "jobs": []}
            return self._doc
        doc: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        if int(doc.get("version", 1)) > VERSION:
            self.read_only = True
        self._doc = doc
        return doc

    @contextmanager
    def _locked(self) -> Iterator[dict[str, Any]]:
        if self.read_only:
            raise JobStateError("queue.json was written by a newer app version; read-only")
        self.app_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_TIMEOUT
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - self.lock_path.stat().st_mtime > STALE_LOCK:
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() > deadline:
                    raise TimeoutError("queue.json is locked") from None
                time.sleep(0.02)
        try:
            doc = self._load()
            if self.read_only:
                raise JobStateError("queue.json was written by a newer app version; read-only")
            yield doc
            write_atomic(self.path, json.dumps(doc, indent=2, default=str))
        finally:
            self.lock_path.unlink(missing_ok=True)

    @staticmethod
    def _find(doc: dict[str, Any], job_id: str) -> dict[str, Any]:
        for raw in doc["jobs"]:
            if raw.get("job_id") == job_id:
                return raw  # type: ignore[no-any-return]
        raise KeyError(job_id)

    @staticmethod
    def _set(raw: dict[str, Any], **values: Any) -> None:
        for k, v in values.items():
            raw[k] = v.isoformat() if isinstance(v, datetime) else v

    # --- reading ------------------------------------------------------------------------

    def jobs(self) -> list[Job]:
        return [Job.model_validate(raw) for raw in self._load()["jobs"]]

    def get(self, job_id: str) -> Job:
        return Job.model_validate(self._find(self._load(), job_id))

    def next_queued(self) -> Job | None:
        return next((j for j in self.jobs() if j.state == "queued"), None)

    def job_dir(self, job_id: str) -> Path:
        return self.app_dir / "jobs" / job_id

    # --- changes ------------------------------------------------------------------------

    def enqueue(
        self,
        kind: JobKind,
        scenario: Path,
        *,
        view: str,
        measured: Path | None = None,
        label: str | None = None,
        **extra: Any,
    ) -> Job:
        if self.read_only:
            raise JobStateError("queue.json was written by a newer app version; read-only")
        job_id = uuid.uuid4().hex[:12]
        folder = self.job_dir(job_id)
        frozen = freeze_scenario(scenario, folder)
        measured_copy = None
        if measured is not None:
            measured_copy = folder / "measured" / measured.name
            measured_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(measured, measured_copy)
        job = Job(
            job_id=job_id, kind=kind, scenario_path=str(frozen),
            measured_path=str(measured_copy) if measured_copy else None,
            queued_at=now(), view=view, label=label, **extra,
        )  # fmt: skip
        with self._locked() as doc:
            doc["jobs"].append(json.loads(job.model_dump_json()))
        log.info("job_queued", job_id=job_id, kind=kind, scenario=str(scenario), view=view)
        return job

    def mark_running(self, job_id: str) -> None:
        with self._locked() as doc:
            raw = self._find(doc, job_id)
            if raw["state"] != "queued":
                raise JobStateError(f"job {job_id} is {raw['state']}, not queued")
            self._set(raw, state="running", started_at=now())

    def mark_finished(
        self, job_id: str, *, run_id: str | None, failed: bool, message: str | None = None
    ) -> None:
        with self._locked() as doc:
            raw = self._find(doc, job_id)
            if raw["state"] != "running":
                raise JobStateError(f"job {job_id} is {raw['state']}, not running")
            self._set(raw, state="failed" if failed else "completed", finished_at=now(),
                      run_id=run_id, message=message)  # fmt: skip

    def mark_interrupted(self, job_id: str) -> None:
        with self._locked() as doc:
            raw = self._find(doc, job_id)
            if raw["state"] == "running":
                self._set(raw, state="interrupted", finished_at=now())

    def set_run_id(self, job_id: str, run_id: str) -> None:
        with self._locked() as doc:
            self._set(self._find(doc, job_id), run_id=run_id)

    def restart_rules(self) -> list[str]:
        """At app start: running → interrupted, queued → not_started. Nothing starts."""
        changed: list[str] = []
        with self._locked() as doc:
            for raw in doc["jobs"]:
                if raw["state"] == "running":
                    self._set(raw, state="interrupted")
                elif raw["state"] == "queued":
                    self._set(raw, state="not_started")
                else:
                    continue
                changed.append(raw["job_id"])
                log.warning("job_not_resumed", job_id=raw["job_id"], state=raw["state"])
        return changed

    def start(self, job_id: str) -> None:
        """not_started or interrupted → queued (at the end of the queue)."""
        with self._locked() as doc:
            raw = self._find(doc, job_id)
            if raw["state"] not in ("not_started", "interrupted"):
                raise JobStateError(f"job {job_id} is {raw['state']}; cannot be started")
            doc["jobs"].remove(raw)
            self._set(raw, state="queued", queued_at=now(), started_at=None, finished_at=None)
            doc["jobs"].append(raw)

    def drop(self, job_id: str) -> None:
        with self._locked() as doc:
            raw = self._find(doc, job_id)
            if raw["state"] not in ("queued", "not_started"):
                raise JobStateError(f"job {job_id} is {raw['state']}; cannot be dropped")
            self._set(raw, state="dropped", finished_at=now())

    # --- progress -----------------------------------------------------------------------

    def progress_path(self, job_id: str) -> Path:
        return self.app_dir / "progress" / f"{job_id}.json"

    def write_progress(
        self, job_id: str, phase: str, simulated_s: float, duration_s: float
    ) -> None:
        payload = {"phase": phase, "simulated_s": simulated_s, "duration_s": duration_s,
                   "updated_at": now().isoformat()}  # fmt: skip
        write_atomic(self.progress_path(job_id), json.dumps(payload))

    def read_progress(self, job_id: str) -> dict[str, Any] | None:
        path = self.progress_path(job_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except (OSError, ValueError):
            return None
