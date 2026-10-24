"""Action log (T015; FR-021, data-model §10)."""

import json
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.action_log import ACTIONS, ActionLog


def test_actions_are_appended_as_json_lines(web_settings: Any) -> None:
    log = ActionLog(web_settings.app_dir)
    log.log("engineer", "run_started", "job-1", {"scenario": "plant_reference"})
    log.log("operator", "what_if_started", "job-2", {})
    lines = (web_settings.app_dir / "actions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["view"] == "engineer" and first["action"] == "run_started"
    assert first["target"] == "job-1" and first["details"] == {"scenario": "plant_reference"}
    assert first["time"].endswith("Z") or first["time"].endswith("+00:00")


def test_unknown_action_rejected(web_settings: Any) -> None:
    with pytest.raises(ValueError):
        ActionLog(web_settings.app_dir).log("engineer", "made_coffee", "x", {})
    assert set(ACTIONS) >= {
        "run_started", "scenario_saved", "operator_version_saved", "what_if_started",
        "comparison_started", "job_dropped", "job_restarted", "run_deleted",
    }  # fmt: skip
