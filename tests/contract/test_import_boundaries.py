"""Subsystems are coupled only through interfaces (T002; constitution principle III).

The boiler house and the dryer never import each other; only the plant coordinator knows
both. The interface package depends on neither.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src" / "boidrytwin"

FORBIDDEN = {
    "boiler_house": ("boidrytwin.dryer", "boidrytwin.plant"),
    "dryer": ("boidrytwin.boiler_house", "boidrytwin.plant"),
    "interface": ("boidrytwin.dryer", "boidrytwin.boiler_house", "boidrytwin.plant"),
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_package_does_not_import_other_subsystems(package: str) -> None:
    files = sorted((SRC / package).rglob("*.py"))
    assert files, f"no modules in {package}"
    for path in files:
        for name in _imports(path):
            for forbidden in FORBIDDEN[package]:
                assert not (name == forbidden or name.startswith(forbidden + ".")), (
                    f"{path.relative_to(SRC)} imports {name}"
                )


def test_only_the_cli_imports_the_web_app() -> None:
    # feature 003: the web app is an optional layer on top of the twin
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC)
        if rel.parts[0] == "webapp" or rel.as_posix() == "cli.py":
            continue
        for name in _imports(path):
            assert not name.startswith("boidrytwin.webapp"), f"{rel} imports {name}"


WEBAPP_ALLOWED = (
    "boidrytwin.webapp",
    "boidrytwin.records",
    "boidrytwin.scenario",
    "boidrytwin.errors",
    "boidrytwin.logging",
    "boidrytwin.units",
    "boidrytwin.progress",
    "boidrytwin.validation.compare",
    "boidrytwin.checks",
)


def test_web_app_uses_only_public_twin_functions() -> None:
    files = sorted((SRC / "webapp").rglob("*.py"))
    assert files, "no modules in webapp"
    for path in files:
        for name in _imports(path):
            if name == "boidrytwin" or name.startswith("boidrytwin."):
                assert name == "boidrytwin" or name.startswith(WEBAPP_ALLOWED), (
                    f"webapp/{path.relative_to(SRC / 'webapp')} imports {name}"
                )
