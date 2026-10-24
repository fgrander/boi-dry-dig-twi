"""Structured logging (T010)."""

import json
import logging
from datetime import datetime

import pytest
import structlog

from boidrytwin.logging import bind_run_id, configure_logging, get_logger


@pytest.fixture(autouse=True)
def _reset() -> None:
    structlog.contextvars.clear_contextvars()


def test_json_output_fields(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", fmt="json")
    bind_run_id("run-123")
    get_logger("dryer").info("run_started", n_cells=20)
    line = capsys.readouterr().err.strip().splitlines()[-1]
    record = json.loads(line)
    assert record["event"] == "run_started"
    assert record["level"] == "info"
    assert record["component"] == "dryer"
    assert record["run_id"] == "run-123"
    assert record["n_cells"] == 20
    ts = datetime.fromisoformat(record["timestamp"])
    assert ts.utcoffset() is not None and ts.utcoffset().total_seconds() == 0


def test_console_renderer(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", fmt="console")
    get_logger("cli").info("hello")
    err = capsys.readouterr().err
    assert "hello" in err
    with pytest.raises(json.JSONDecodeError):
        json.loads(err.strip().splitlines()[-1])


def test_level_filters_messages(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="WARNING", fmt="json")
    get_logger("x").info("hidden")
    get_logger("x").warning("shown")
    err = capsys.readouterr().err
    assert "hidden" not in err and "shown" in err


def test_level_from_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BOIDRYTWIN_LOG_LEVEL", "ERROR")
    configure_logging(fmt="json")
    get_logger("x").warning("hidden")
    get_logger("x").error("shown")
    err = capsys.readouterr().err
    assert "hidden" not in err and "shown" in err


def test_explicit_level_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOIDRYTWIN_LOG_LEVEL", "ERROR")
    configure_logging(level="DEBUG", fmt="json")
    assert logging.getLogger("boidrytwin").getEffectiveLevel() == logging.DEBUG
