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


FLUE_CONSTANT = """[flue_gas]
source = "constant"
mass_flow = "8.0 kg/s"
temperature = "650 degC"
pressure = "101.0 kPa"
composition_basis = "wet"
composition_type = "mole"
x_N2 = "70.5 %"
x_O2 = "6.0 %"
x_CO2 = "10.5 %"
x_H2O = "12.0 %"
x_other = "1.0 %"

[dilution_air]
mass_flow = "2.0 kg/s"
"""


def run_cli(path: Path, out: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, Path]:
    """``boidrytwin run``; returns the exit code and the run folder."""
    from boidrytwin.cli import main

    code = main(["run", str(path), "--out", str(out)])
    stdout = capsys.readouterr().out
    run_id = next(line.split()[-1] for line in stdout.splitlines() if line.startswith("run_id"))
    return code, out / run_id


def dryer_only_from_interface(
    tmp_path: Path, folder: Path, end: str, name: str = "swap.toml"
) -> Path:
    """The reference dryer fed by a coupled run's interface time series (SC-006, FR-014)."""
    flue = (folder / "flue_gas_to_dryer.csv").resolve().as_posix()
    dilution = (folder / "dilution_air.csv").resolve().as_posix()
    replacement = (
        f'[flue_gas]\nsource = "timeseries"\nfile = "{flue}"\n\n'
        f'[dilution_air]\nmass_flow = {{ file = "{dilution}", column = "dilution" }}\n'
    )
    return make_variant(
        tmp_path,
        base="reference_constant.toml",
        replace={FLUE_CONSTANT: replacement, 'kind = "cold_empty"': 'kind = "steady_state"'},
        end=end,
        name=name,
    )


@pytest.fixture
def variant(tmp_path: Path) -> Variant:
    def _make(**kwargs: object) -> Path:
        return make_variant(tmp_path, **kwargs)  # type: ignore[arg-type]

    return _make
