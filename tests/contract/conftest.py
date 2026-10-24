"""Helpers to write scenario and time series files for contract tests."""

from collections.abc import Callable
from pathlib import Path

import pytest

TIME = """
[time]
start = "2026-01-01T00:00:00Z"
end = "2026-01-01T02:00:00Z"
output_interval = "1 min"
"""

CONSTANT_FLUE_GAS = """
[flue_gas]
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
"""

FLUE_CSV_HEADER = (
    "time,mass_flow,temperature,pressure,x_N2,x_O2,x_CO2,x_H2O,x_other,quality\n"
    "unit,kg/s,degC,kPa,%,%,%,%,%,\n"
)


def flue_csv_rows(minutes: list[int], temperature: float = 650.0) -> str:
    return "".join(
        f"2026-01-01T{m // 60:02d}:{m % 60:02d}:00Z,8.0,{temperature},101.0,"
        "70.5,6.0,10.5,12.0,1.0,good\n"
        for m in minutes
    )


ScenarioWriter = Callable[..., Path]


@pytest.fixture
def write_scenario(tmp_path: Path) -> ScenarioWriter:
    """Write ``scenario.toml`` (and optional extra files) and return its path."""

    def _write(
        flue_gas: str = CONSTANT_FLUE_GAS,
        extra: str = "",
        time: str = TIME,
        files: dict[str, str] | None = None,
    ) -> Path:
        for name, content in (files or {}).items():
            (tmp_path / name).write_text(content, encoding="utf-8")
        path = tmp_path / "scenario.toml"
        path.write_text(
            'schema_version = 1\nname = "contract test"\n' + time + flue_gas + extra,
            encoding="utf-8",
        )
        return path

    return _write
