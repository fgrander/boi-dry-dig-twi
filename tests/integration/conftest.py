"""Scenario variants built from the example files."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).parents[2] / "examples"

Variant = Callable[..., Path]


def make_variant(
    tmp_path: Path,
    base: str = "reference_constant.toml",
    replace: dict[str, str] | None = None,
    end: str | None = None,
    name: str = "variant.toml",
    files: dict[str, str] | None = None,
) -> Path:
    """Copy an example with text replacements; relative data paths stay valid."""
    text = (EXAMPLES / base).read_text(encoding="utf-8")
    for old, new in (replace or {}).items():
        assert old in text, f"{old!r} not in {base}"
        text = text.replace(old, new)
    if end is not None:
        text = re.sub(r'end = "[^"]+"', f'end = "{end}"', text, count=1)
    for fname, content in (files or {}).items():
        (tmp_path / fname).write_text(content, encoding="utf-8")

    def absolute(match: re.Match[str]) -> str:
        target = match.group(1)
        if (tmp_path / target).exists():
            return match.group(0)
        return f'file = "{(EXAMPLES / target).resolve().as_posix()}"'

    text = re.sub(r'file = "([^"]+)"', absolute, text)
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def variant(tmp_path: Path) -> Variant:
    def _make(**kwargs: object) -> Path:
        return make_variant(tmp_path, **kwargs)  # type: ignore[arg-type]

    return _make
