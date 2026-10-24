"""Fixtures for the web app tests (feature 003).

- ``web_settings``: an :class:`AppSettings` with temporary ``runs/``, ``scenarios/`` and a copy
  of ``examples/`` (so tests can never modify the real examples).
- ``run_examples``: CLI runs of three examples shortened (2 h; the oil step to 07:00), made
  once per session; each test that asks for ``example_runs`` gets them copied into its own
  ``runs/``.
- ``client``: a factory for a FastAPI test client in a given view (``engineer`` | ``operator`` |
  ``None`` for no view cookie), addressed as ``http://127.0.0.1:<port>``.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

EXAMPLES = Path(__file__).parents[1] / "examples"
SHORT_END = "2026-01-01T02:00:00Z"
# name → end time; the oil step runs past its 06:00 step so its load warning is included
RUN_EXAMPLES = {
    "boiler_house_only": SHORT_END,
    "plant_reference": SHORT_END,
    "oil_demand_step": "2026-01-01T07:00:00Z",
}


def shortened(src: Path, dst_dir: Path, end: str = SHORT_END, name: str | None = None) -> Path:
    """Copy an example with a shorter end time; relative data paths are made absolute."""
    text = src.read_text(encoding="utf-8")
    text = re.sub(r'end = "[^"]+"', f'end = "{end}"', text, count=1)
    text = re.sub(
        r'file = "([^"]+)"',
        lambda m: f'file = "{(src.parent / m.group(1)).resolve().as_posix()}"',
        text,
    )
    path = dst_dir / (name or src.name)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def web_settings(tmp_path: Path) -> Any:
    pytest.importorskip("fastapi")
    from boidrytwin.webapp.settings import AppSettings

    examples = tmp_path / "examples"
    shutil.copytree(EXAMPLES, examples)
    (tmp_path / "runs").mkdir()
    (tmp_path / "scenarios").mkdir()
    return AppSettings(
        runs_dir=tmp_path / "runs", scenarios_dir=tmp_path / "scenarios", examples_dir=examples
    )


@pytest.fixture(scope="session")
def run_examples(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """name → run folder, CLI runs of the shortened examples (made once)."""
    from boidrytwin import load_scenario
    from boidrytwin.logging import configure_logging
    from boidrytwin.records import run

    configure_logging(level="WARNING")
    base = tmp_path_factory.mktemp("example_runs")
    runs = base / "runs"
    out: dict[str, Path] = {}
    for name, end in RUN_EXAMPLES.items():
        path = shortened(EXAMPLES / f"{name}.toml", base, end=end)
        record = run(load_scenario(path), out_dir=runs)
        out[name] = runs / record.run_id
    return out


@pytest.fixture
def example_runs(web_settings: Any, run_examples: dict[str, Path]) -> dict[str, str]:
    """name → run id, copied into the test's runs folder."""
    ids: dict[str, str] = {}
    for name, folder in run_examples.items():
        shutil.copytree(folder, web_settings.runs_dir / folder.name)
        ids[name] = folder.name
    return ids


@pytest.fixture
def client(web_settings: Any) -> Iterator[Callable[..., Any]]:
    from fastapi.testclient import TestClient

    from boidrytwin.webapp.app import create_app

    clients: list[TestClient] = []

    def make(view: str | None = "engineer", settings: Any = None) -> TestClient:
        s = settings or web_settings
        c = TestClient(create_app(s), base_url=f"http://127.0.0.1:{s.port}")
        if view is not None:
            c.cookies.set("view", view)
        clients.append(c)
        return c

    yield make
    for c in clients:
        c.close()
