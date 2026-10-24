"""Launcher of the packaged desktop app, ``BoiDryTwin.exe`` (FR-024).

Double-clicking the exe starts the server and its worker on ``127.0.0.1`` and opens the
browser. Runs, saved scenarios and a copy of the examples live in the user's data folder
(``Documents\\BoiDryTwin`` or ``$BOIDRYTWIN_HOME``), so they survive updates of the exe and
saved scenarios keep valid file references. The examples are refreshed when the app version
changes; user data is never touched. If the app is already running, the launcher only opens
the browser on it.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import shutil
import sys
import urllib.error
import urllib.request
import webbrowser
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from boidrytwin.webapp.settings import DEFAULT_PORT, AppSettings

ENV_HOME = "BOIDRYTWIN_HOME"
ENV_NO_BROWSER = "BOIDRYTWIN_NO_BROWSER"  # for automated tests of the exe
VERSION_FILE = ".app_version"
APP_MARKER = b"Plant twin"


def data_home() -> Path:
    override = os.environ.get(ENV_HOME)
    return Path(override) if override else Path.home() / "Documents" / "BoiDryTwin"


def bundled_examples() -> Path:
    """The examples shipped with the app (inside the exe, or the source tree)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "examples"
    return Path(__file__).resolve().parents[3] / "examples"


def app_version() -> str:
    try:
        return version("boidrytwin")
    except PackageNotFoundError:
        return "0+unknown"


def prepare(home: Path, *, bundled: Path, version: str) -> AppSettings:
    """Create the data folders and copy the examples (again only on a new version)."""
    runs, scenarios, examples = home / "runs", home / "scenarios", home / "examples"
    runs.mkdir(parents=True, exist_ok=True)
    scenarios.mkdir(parents=True, exist_ok=True)
    stamp = examples / VERSION_FILE
    current = stamp.read_text(encoding="utf-8") if stamp.is_file() else None
    if current != version:
        if examples.exists():
            shutil.rmtree(examples)
        shutil.copytree(bundled, examples)
        stamp.write_text(version, encoding="utf-8")
    return AppSettings(runs_dir=runs, scenarios_dir=scenarios, examples_dir=examples)


def running_instance(port: int) -> bool:
    """True if this app already answers on ``port`` (another program there is not it)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
            return APP_MARKER in r.read(65536)
    except (urllib.error.URLError, OSError, ValueError):
        return False


def main() -> int:
    mp.freeze_support()  # the worker process is started from the exe itself
    from boidrytwin.logging import configure_logging
    from boidrytwin.webapp.server import serve

    configure_logging(level="WARNING", fmt="console")
    url = f"http://127.0.0.1:{DEFAULT_PORT}"
    browser = not os.environ.get(ENV_NO_BROWSER)
    if running_instance(DEFAULT_PORT):
        sys.stdout.write(f"BoiDryTwin is already running: opening {url}\n")
        if browser:
            webbrowser.open(url)
        return 0
    home = data_home()
    settings = prepare(home, bundled=bundled_examples(), version=app_version())
    sys.stdout.write(
        f"BoiDryTwin {app_version()}\n"
        f"Your runs and scenarios: {home}\n"
        "The browser opens by itself. Close this window to stop the app.\n"
    )
    return serve(settings, open_browser=browser, log_level="WARNING")
