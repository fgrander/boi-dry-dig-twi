"""The run list: one summary per run folder (FR-001, data-model §1).

Summaries are read from ``run_record.json`` and cached by its modification time, so a long
list is cheap to show again (SC-001). A folder with an unreadable record is listed with a
note instead of stopping the listing (edge case).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

Kind = Literal["dryer", "boiler", "coupled", "unknown"]
Status = Literal[
    "completed", "failed", "running", "queued", "not_started", "interrupted", "unknown"
]
RECORD = "run_record.json"


class RunSummary(BaseModel):
    run_id: str
    scenario_name: str
    created_at: datetime
    kind: Kind
    status: str
    checks_passed: bool | None
    warnings: int
    flags: dict[str, int]
    origin: str = "cli"
    note: str | None = None


def _kind(folder: Path) -> Kind:
    boiler = (folder / "boiler_results.csv").is_file()
    dryer = (folder / "results.csv").is_file()
    if boiler and dryer:
        return "coupled"
    if boiler:
        return "boiler"
    if dryer:
        return "dryer"
    return "unknown"


def _checks(record: dict[str, Any]) -> bool | None:
    report = record.get("plant_balance_report") or record.get("balance_report")
    if not isinstance(report, dict) or "passed" not in report:
        return None
    return bool(report["passed"])


def _created(record: dict[str, Any], folder: Path) -> datetime:
    try:
        stamp = datetime.fromisoformat(str(record["created_at"]).replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    except (KeyError, ValueError):
        return datetime.fromtimestamp(folder.stat().st_mtime, tz=UTC)


def read_summary(folder: Path) -> RunSummary:
    try:
        record = json.loads((folder / RECORD).read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("not an object")
    except (OSError, ValueError) as exc:
        return RunSummary(
            run_id=folder.name,
            scenario_name="",
            kind=_kind(folder),
            status="unknown",
            created_at=datetime.fromtimestamp(folder.stat().st_mtime, tz=UTC),
            checks_passed=None,
            warnings=0,
            flags={},
            note=f"unreadable run record: {exc}",
        )
    raw = record.get("scenario")
    scenario: dict[str, Any] = raw if isinstance(raw, dict) else {}
    return RunSummary(
        run_id=folder.name,  # the folder is the identity (copied runs keep their record)
        scenario_name=str(scenario.get("name", "")),
        created_at=_created(record, folder),
        kind=_kind(folder),
        status=str(record.get("status", "unknown")),
        checks_passed=_checks(record),
        warnings=len(record.get("range_warnings") or []),
        flags={str(k): int(v) for k, v in (record.get("flags_summary") or {}).items()},
    )


class RunIndex:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir
        self._cache: dict[str, tuple[int, RunSummary]] = {}

    def _folders(self) -> list[Path]:
        if not self.runs_dir.is_dir():
            return []
        return [p for p in self.runs_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

    def summary(self, folder: Path) -> RunSummary:
        record = folder / RECORD
        stamp = record.stat().st_mtime_ns if record.exists() else folder.stat().st_mtime_ns
        cached = self._cache.get(folder.name)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        summary = read_summary(folder)
        self._cache[folder.name] = (stamp, summary)
        return summary

    def list(
        self, *, q: str | None = None, status: str | None = None, kind: str | None = None
    ) -> list[RunSummary]:
        runs = [self.summary(f) for f in self._folders()]
        if q:
            words = q.lower().split()
            runs = [r for r in runs if all(w in r.scenario_name.lower() for w in words)]
        if status:
            runs = [r for r in runs if r.status == status]
        if kind:
            runs = [r for r in runs if r.kind == kind]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    def folder(self, run_id: str) -> Path | None:
        """The folder of a run, or None (also for ids that would leave the runs folder)."""
        if not run_id or "/" in run_id or "\\" in run_id or run_id.startswith("."):
            return None
        path = self.runs_dir / run_id
        return path if path.is_dir() else None
