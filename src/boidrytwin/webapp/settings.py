"""Folders and port of a web app instance (contracts/cli-serve.md)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PORT = 8765


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    runs_dir: Path = Path("runs")
    scenarios_dir: Path = Path("scenarios")
    examples_dir: Path = Path("examples")
    port: int = Field(default=DEFAULT_PORT, ge=1, le=65535)

    @property
    def app_dir(self) -> Path:
        """App state: queue, progress, what-if index, action log (contracts/app-state.md)."""
        return self.runs_dir / ".app"

    @property
    def allowed_hosts(self) -> frozenset[str]:
        return frozenset({f"localhost:{self.port}", f"127.0.0.1:{self.port}"})

    @property
    def origins(self) -> frozenset[str]:
        return frozenset(f"http://{h}" for h in self.allowed_hosts)
