"""Desktop launcher of the packaged app (T053; FR-024)."""

import http.server
import threading
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp import desktop

EXAMPLES = Path(__file__).parents[3] / "examples"


def test_data_home_default_and_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(desktop.ENV_HOME, raising=False)
    assert desktop.data_home() == Path.home() / "Documents" / "BoiDryTwin"
    monkeypatch.setenv(desktop.ENV_HOME, str(tmp_path / "x"))
    assert desktop.data_home() == tmp_path / "x"


def test_prepare_creates_folders_and_copies_examples(tmp_path: Path) -> None:
    settings = desktop.prepare(tmp_path, bundled=EXAMPLES, version="1.0")
    assert settings.runs_dir == tmp_path / "runs" and settings.runs_dir.is_dir()
    assert settings.scenarios_dir == tmp_path / "scenarios" and settings.scenarios_dir.is_dir()
    assert settings.examples_dir == tmp_path / "examples"
    assert (tmp_path / "examples" / "plant_reference.toml").is_file()
    assert (tmp_path / "examples" / "data" / "oil_return_step.csv").is_file()
    assert (tmp_path / "examples" / desktop.VERSION_FILE).read_text(encoding="utf-8") == "1.0"


def test_examples_refreshed_on_new_version_only(tmp_path: Path) -> None:
    desktop.prepare(tmp_path, bundled=EXAMPLES, version="1.0")
    (tmp_path / "runs" / "keep").mkdir()
    (tmp_path / "scenarios" / "mine.toml").write_text("x", encoding="utf-8")
    marker = tmp_path / "examples" / "plant_reference.toml"
    marker.write_text("edited", encoding="utf-8")
    desktop.prepare(tmp_path, bundled=EXAMPLES, version="1.0")
    assert marker.read_text(encoding="utf-8") == "edited"  # same version: left alone
    desktop.prepare(tmp_path, bundled=EXAMPLES, version="1.1")
    assert marker.read_text(encoding="utf-8") != "edited"  # new version: refreshed
    assert (tmp_path / "runs" / "keep").is_dir()  # user data never touched
    assert (tmp_path / "scenarios" / "mine.toml").read_text(encoding="utf-8") == "x"


class _Twin(http.server.BaseHTTPRequestHandler):
    body = b"<title>Choose a view</title><a class='brand'>Plant twin</a>"

    def do_GET(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args: object) -> None:
        pass


def _serve(handler: type) -> tuple[http.server.HTTPServer, int]:
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, int(server.server_address[1])


def test_running_instance_detected() -> None:
    server, port = _serve(_Twin)
    try:
        assert desktop.running_instance(port) is True
    finally:
        server.shutdown()


def test_other_program_on_the_port_is_not_the_app() -> None:
    class Other(_Twin):
        body = b"something else"

    server, port = _serve(Other)
    try:
        assert desktop.running_instance(port) is False
    finally:
        server.shutdown()


def test_free_port_is_not_an_instance() -> None:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = int(s.getsockname()[1])
    assert desktop.running_instance(port) is False


def test_main_starts_the_server_and_opens_the_browser(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import boidrytwin.webapp.server as server

    calls: dict[str, object] = {}
    monkeypatch.setenv(desktop.ENV_HOME, str(tmp_path))
    monkeypatch.delenv(desktop.ENV_NO_BROWSER, raising=False)
    monkeypatch.setattr(desktop, "running_instance", lambda port: False)
    monkeypatch.setattr(
        server, "serve", lambda settings, **kw: calls.update(settings=settings, **kw) or 0
    )
    assert desktop.main() == 0
    assert calls["open_browser"] is True
    assert calls["settings"].runs_dir == tmp_path / "runs"  # type: ignore[attr-defined]
    assert str(tmp_path) in capsys.readouterr().out
    monkeypatch.setenv(desktop.ENV_NO_BROWSER, "1")
    desktop.main()
    assert calls["open_browser"] is False


def test_main_opens_the_running_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.delenv(desktop.ENV_NO_BROWSER, raising=False)
    monkeypatch.setattr(desktop, "running_instance", lambda port: True)
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url: opened.append(url))
    assert desktop.main() == 0
    assert opened == ["http://127.0.0.1:8765"]
