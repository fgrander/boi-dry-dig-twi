"""Regression: messages with non-ASCII symbols (≥, ±, °C) must not crash on a cp1252 console."""

import os
import subprocess
import sys
from pathlib import Path

EXAMPLES = Path(__file__).parents[2] / "examples"


def test_validate_prints_symbols_on_cp1252_console() -> None:
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    result = subprocess.run(
        [sys.executable, "-m", "boidrytwin", "validate", str(EXAMPLES / "invalid_flue_gas.toml")],
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 1, result.stderr.decode("utf-8", "replace")
    assert "UnicodeEncodeError" not in result.stderr.decode("utf-8", "replace")
    out = result.stdout.decode("utf-8")
    assert "must be ≥ 0" in out
