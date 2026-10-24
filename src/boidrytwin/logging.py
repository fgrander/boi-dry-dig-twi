"""Structured logging configuration.

structlog on top of stdlib logging: JSON lines by default, a console renderer for humans.
Log records go to stderr; the level comes from the argument, else ``BOIDRYTWIN_LOG_LEVEL``,
else INFO (constitution principle IV).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

import structlog

ENV_LEVEL = "BOIDRYTWIN_LOG_LEVEL"
_ROOT = "boidrytwin"

LogFormat = Literal["json", "console"]


def configure_logging(level: str | None = None, fmt: LogFormat = "json") -> None:
    """Configure structlog and the ``boidrytwin`` stdlib logger."""
    level_name = (level or os.environ.get(ENV_LEVEL) or "INFO").upper()

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    renderer: Any = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        foreign_pre_chain=shared,
    )
    handler = logging.StreamHandler()  # binds the current sys.stderr
    handler.setFormatter(formatter)

    root = logging.getLogger(_ROOT)
    for old in list(root.handlers):
        root.removeHandler(old)
    root.addHandler(handler)
    root.setLevel(level_name)
    root.propagate = False


def get_logger(component: str) -> structlog.stdlib.BoundLogger:
    """Return a logger for one component (e.g. ``dryer``, ``scenario``, ``cli``)."""
    # a lazy proxy: binding happens at first use, after configure_logging() has run
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(
        f"{_ROOT}.{component}", component=component
    )
    return logger


def bind_run_id(run_id: str) -> None:
    """Attach ``run_id`` to every log record of the current context."""
    structlog.contextvars.bind_contextvars(run_id=run_id)
