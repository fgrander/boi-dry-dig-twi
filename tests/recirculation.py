"""A `[recirculation]` block for tests (feature 004), sized for the reference dryer."""

from __future__ import annotations

from pathlib import Path

from tests.integration.conftest import make_variant

BLOCK = """
[recirculation]
pressure_sensor_time_constant = "2 s"
duct_heat_loss = "0 W/K"
max_share = "70 %"
dew_point_margin = "10 K"

[recirculation.damper]
open_mass_flow = "18 kg/s"
design_pressure_drop = "500 Pa"
design_temperature = "290 degC"

[recirculation.exhaust_fan]
nominal_speed = "990 rpm"
speed = "990 rpm"
curve_temperature = "290 degC"
curve = [["15 m^3/s", "2300 Pa"], ["25 m^3/s", "2000 Pa"], ["35 m^3/s", "1400 Pa"]]

[recirculation.resistances.drum_path]
mass_flow = "15 kg/s"
pressure_drop = "1200 Pa"
temperature = "290 degC"

[recirculation.resistances.stack]
mass_flow = "10.7 kg/s"
pressure_drop = "300 Pa"
temperature = "290 degC"

[recirculation.controller]
mode = "automatic"
setpoint = "-200 Pa"
gain = "0.0001 1/Pa"
integral_time = "5 s"
output_min = "0 %"
output_max = "100 %"
not_reached_band = "50 Pa"
not_reached_hold = "10 min"
"""


def with_recirculation(
    tmp_path: Path,
    base: str = "reference_constant.toml",
    replace: dict[str, str] | None = None,
    block: str = BLOCK,
    end: str | None = None,
) -> Path:
    """An example scenario with the recirculation block appended. Each replacement changes
    the last occurrence of its text, so it hits the block before the base scenario."""
    path = make_variant(tmp_path, base, end=end, name="base.toml")
    text = path.read_text(encoding="utf-8") + block
    for old, new in (replace or {}).items():
        assert old in text, f"{old!r} not in scenario"
        text = new.join(text.rsplit(old, 1))
    out = tmp_path / "recirculation.toml"
    out.write_text(text, encoding="utf-8")
    return out
