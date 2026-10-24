"""``boidrytwin serve`` (T029; contracts/cli-serve.md, FR-020)."""

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _serve(tmp_path: Path, port: int, *extra: str) -> subprocess.Popen[str]:
    cmd = [
        sys.executable,
        "-m",
        "boidrytwin",
        "serve",
        "--no-browser",
        "--port",
        str(port),
        "--runs",
        str(tmp_path / "runs"),
        "--scenarios",
        str(tmp_path / "scenarios"),
        "--examples",
        str(Path(__file__).parents[3] / "examples"),
        *extra,
    ]
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8"
    )


def test_serve_answers(tmp_path: Path) -> None:
    port = _free_port()
    proc = _serve(tmp_path, port)
    try:
        assert proc.stdout is not None
        line = proc.stdout.readline()
        assert line.strip() == f"serving http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:
                    assert r.status == 200
                    break
            except OSError:
                assert time.monotonic() < deadline
                time.sleep(0.3)
    finally:
        proc.terminate()
        proc.wait(15)


def test_busy_port_exits_3(tmp_path: Path) -> None:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = int(s.getsockname()[1])
        proc = _serve(tmp_path, port)
        assert proc.wait(60) == 3


def test_invalid_folder_exits_1(tmp_path: Path) -> None:
    from boidrytwin.cli import main

    assert main(["serve", "--no-browser", "--examples", str(tmp_path / "missing")]) == 1


def test_without_web_extra(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    from boidrytwin.cli import main

    monkeypatch.setitem(sys.modules, "fastapi", None)
    monkeypatch.setitem(sys.modules, "uvicorn", None)
    assert main(["serve", "--no-browser"]) == 1
    assert "web" in capsys.readouterr().err
