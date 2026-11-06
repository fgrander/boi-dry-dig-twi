"""Log of user actions that start, save or delete something (FR-021, data-model §10)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from boidrytwin.logging import get_logger

ACTIONS = (
    "run_started",
    "scenario_saved",
    "scenario_renamed",
    "scenario_deleted",
    "scenario_uploaded",
    "recirculation_added",
    "operator_version_saved",
    "what_if_started",
    "comparison_started",
    "job_dropped",
    "job_restarted",
    "run_deleted",
)

log = get_logger("webapp")


class ActionLog:
    def __init__(self, app_dir: Path) -> None:
        self.path = app_dir / "actions.jsonl"

    def log(self, view: str, action: str, target: str, details: dict[str, Any]) -> None:
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        entry = {
            "time": datetime.now(UTC).isoformat(),
            "view": view,
            "action": action,
            "target": target,
            "details": details,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.info("user_action", view=view, action=action, target=target, **details)
