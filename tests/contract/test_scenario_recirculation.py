"""Scenario file: the [recirculation] section (T003; contracts/scenario-file-recirculation.md)."""

import math
from pathlib import Path

import pytest

from boidrytwin import load_scenario
from boidrytwin.errors import ScenarioValidationError
from tests.recirculation import BLOCK, with_recirculation


def _issues(path: Path) -> dict[str, str]:
    with pytest.raises(ScenarioValidationError) as err:
        load_scenario(path)
    for issue in err.value.issues:
        assert issue.location and "line" in issue.location, issue
    return {i.field: i.reason for i in err.value.issues}


def test_block_loads_in_si(tmp_path: Path) -> None:
    loaded = load_scenario(with_recirculation(tmp_path))
    rc = loaded.spec.recirculation
    assert rc is not None
    assert rc.pressure_sensor_time_constant == 2.0 and rc.duct_heat_loss == 0.0
    assert rc.max_share == pytest.approx(0.7) and rc.dew_point_margin == 10.0
    assert rc.damper.open_mass_flow == 18.0 and rc.damper.design_pressure_drop == 500.0
    assert rc.damper.design_temperature == pytest.approx(563.15)
    assert rc.damper.leakage == pytest.approx(0.01)
    fan = rc.exhaust_fan
    assert fan.nominal_speed == pytest.approx(990 * 2 * math.pi / 60)
    assert fan.curve == ((15.0, 2300.0), (25.0, 2000.0), (35.0, 1400.0))
    assert fan.curve_temperature == pytest.approx(563.15)
    assert rc.resistances.drum_path.mass_flow == 15.0
    assert rc.resistances.stack.pressure_drop == 300.0
    ctrl = rc.controller
    assert ctrl.action == "reverse" and ctrl.gain == pytest.approx(1e-4)
    assert ctrl.output_min == 0.0 and ctrl.output_max == 1.0
    assert ctrl.not_reached_band == 50.0 and ctrl.not_reached_hold == 600.0
    sp = loaded.signals["recirculation.controller.setpoint"]
    assert sp.value_at(0.0) == -200.0
    speed = loaded.signals["recirculation.exhaust_fan.speed"]
    assert speed.value_at(0.0) == pytest.approx(fan.nominal_speed)


def test_defaults(tmp_path: Path) -> None:
    block = BLOCK
    for line in (
        'pressure_sensor_time_constant = "2 s"',
        'duct_heat_loss = "0 W/K"',
        'max_share = "70 %"',
        'dew_point_margin = "10 K"',
        'speed = "990 rpm"',
        'not_reached_band = "50 Pa"',
        'not_reached_hold = "10 min"',
        'curve_temperature = "290 degC"',
    ):
        block = block.replace(f"\n{line}\n", "\n")
    loaded = load_scenario(with_recirculation(tmp_path, block=block))
    rc = loaded.spec.recirculation
    assert rc is not None
    assert rc.pressure_sensor_time_constant == 2.0 and rc.duct_heat_loss == 0.0
    assert rc.max_share == 0.7 and rc.dew_point_margin == 10.0
    assert rc.exhaust_fan.curve_temperature == 293.15
    assert rc.controller.not_reached_band == 50.0 and rc.controller.not_reached_hold == 600.0
    assert rc.controller.action == "reverse"
    speed = loaded.signals["recirculation.exhaust_fan.speed"]
    assert speed.value_at(0.0) == pytest.approx(rc.exhaust_fan.nominal_speed)


def test_no_section_means_no_recirculation(tmp_path: Path) -> None:
    loaded = load_scenario(with_recirculation(tmp_path, block=""))
    assert loaded.spec.recirculation is None
    assert not any(name.startswith("recirculation.") for name in loaded.signals)


REJECTED = [
    ('max_share = "70 %"', 'max_share = "100 %"', "recirculation.max_share"),
    ('max_share = "70 %"', 'max_share = "0 %"', "recirculation.max_share"),
    ('output_max = "100 %"', 'output_max = "120 %"', "recirculation.controller.output_max"),
    ('output_min = "0 %"', 'output_min = "-5 %"', "recirculation.controller.output_min"),
    ('setpoint = "-200 Pa"', 'setpoint = "50 Pa"', "recirculation.controller.setpoint"),
    ('setpoint = "-200 Pa"', 'setpoint = "-2500 Pa"', "recirculation.controller.setpoint"),
    (
        'mode = "automatic"',
        'mode = "automatic"\nsplit_value = 0.5',
        "recirculation.controller.split_value",
    ),
    (
        'mode = "automatic"',
        'mode = "automatic"\nmax_dilution_air = "6 kg/s"',
        "recirculation.controller.max_dilution_air",
    ),
    (', ["35 m^3/s", "1400 Pa"]]', "]", "recirculation.exhaust_fan.curve"),
    ('["35 m^3/s", "1400 Pa"]', '["20 m^3/s", "1400 Pa"]', "recirculation.exhaust_fan.curve"),
    ('["35 m^3/s", "1400 Pa"]', '["35 m^3/s", "2100 Pa"]', "recirculation.exhaust_fan.curve"),
    ('["35 m^3/s", "1400 Pa"]', '["35 m^3/s", "many Pa"]', "recirculation.exhaust_fan.curve"),
    ('speed = "990 rpm"', 'speed = "2500 rpm"', "recirculation.exhaust_fan.speed"),
    ('speed = "990 rpm"', 'speed = "-1 rpm"', "recirculation.exhaust_fan.speed"),
    (
        'design_temperature = "290 degC"',
        'design_temperature = "290 degC"\ncharacteristic = [[0, 0.1], [0.5, 0.05], [1, 1]]',
        "recirculation.damper.characteristic",
    ),
    (
        'design_temperature = "290 degC"',
        'design_temperature = "290 degC"\ncharacteristic = [[0, 0.1], [0.5, 0.5], [1, 0.9]]',
        "recirculation.damper.characteristic",
    ),
    (
        'design_temperature = "290 degC"',
        'design_temperature = "290 degC"\ncharacteristic = [[0.1, 0.1], [1, 1]]',
        "recirculation.damper.characteristic",
    ),
    (
        'design_temperature = "290 degC"',
        'design_temperature = "290 degC"\nleakage = "30 %"',
        "recirculation.damper.leakage",
    ),
    (
        'open_mass_flow = "18 kg/s"',
        'open_mass_flow = "0 kg/s"',
        "recirculation.damper.open_mass_flow",
    ),
    (
        'mass_flow = "15 kg/s"',
        'mass_flow = "-1 kg/s"',
        "recirculation.resistances.drum_path.mass_flow",
    ),
    (
        'pressure_drop = "300 Pa"',
        'pressure_drop = "0 Pa"',
        "recirculation.resistances.stack.pressure_drop",
    ),
    (
        'design_temperature = "290 degC"',
        'design_temperature = "700 degC"',
        "recirculation.damper.design_temperature",
    ),
    ('duct_heat_loss = "0 W/K"', 'duct_heat_loss = "-1 W/K"', "recirculation.duct_heat_loss"),
    (
        'pressure_sensor_time_constant = "2 s"',
        'pressure_sensor_time_constant = "0 s"',
        "recirculation.pressure_sensor_time_constant",
    ),
    (
        'pressure_sensor_time_constant = "2 s"',
        'pressure_sensor_time_constant = "11 min"',
        "recirculation.pressure_sensor_time_constant",
    ),
    (
        "[recirculation.damper]",
        "[recirculation.damper]\nunknown = 1",
        "recirculation.damper.unknown",
    ),
    ('max_share = "70 %"', 'max_share = "70 %"\nfoo = 1', "recirculation.foo"),
]


@pytest.mark.parametrize(
    ("old", "new", "field"), REJECTED, ids=[f"{r[2]}-{i}" for i, r in enumerate(REJECTED)]
)
def test_rejected(tmp_path: Path, old: str, new: str, field: str) -> None:
    issues = _issues(with_recirculation(tmp_path, replace={old: new}))
    assert field in issues, issues


def test_missing_sub_table(tmp_path: Path) -> None:
    head, rest = BLOCK.split("[recirculation.exhaust_fan]")
    block = (
        head
        + "[recirculation.resistances.drum_path]"
        + rest.split("[recirculation.resistances.drum_path]")[1]
    )
    issues = _issues(with_recirculation(tmp_path, block=block))
    assert issues.get("recirculation.exhaust_fan") == "required", issues


def test_needs_a_dryer(tmp_path: Path) -> None:
    issues = _issues(with_recirculation(tmp_path, base="boiler_house_only.toml"))
    assert issues.get("recirculation") == "needs a dryer", issues


WARNED = [
    ('setpoint = "-200 Pa"', 'setpoint = "-1500 Pa"', "recirculation.controller.setpoint"),
    ('speed = "990 rpm"', 'speed = "1200 rpm"', "recirculation.exhaust_fan.speed"),
    ('duct_heat_loss = "0 W/K"', 'duct_heat_loss = "20 kW/K"', "recirculation.duct_heat_loss"),
    (
        'pressure_sensor_time_constant = "2 s"',
        'pressure_sensor_time_constant = "60 s"',
        "recirculation.pressure_sensor_time_constant",
    ),
]


@pytest.mark.parametrize(("old", "new", "field"), WARNED, ids=[w[2] for w in WARNED])
def test_validated_range_warnings(tmp_path: Path, old: str, new: str, field: str) -> None:
    loaded = load_scenario(with_recirculation(tmp_path, replace={old: new}))
    assert field in {w.field for w in loaded.config_warnings}


def test_valid_block_has_no_warnings(tmp_path: Path) -> None:
    loaded = load_scenario(with_recirculation(tmp_path))
    assert not [w for w in loaded.config_warnings if w.field.startswith("recirculation")]


def test_manual_mode_with_steps(tmp_path: Path) -> None:
    csv = (
        "time,position\nunit,%\n2026-01-01T00:00:00Z,40\n"
        "2026-01-01T02:00:00Z,60\n2026-01-03T00:00:00Z,60\n"
    )
    (tmp_path / "pos.csv").write_text(csv, encoding="utf-8")
    manual = 'mode = "manual"\nmanual_output = { file = "pos.csv", column = "position" }'
    loaded = load_scenario(with_recirculation(tmp_path, replace={'mode = "automatic"': manual}))
    rc = loaded.spec.recirculation
    assert rc is not None and rc.controller.mode == "manual"
    assert rc.controller.manual_signal is not None
    sig = loaded.signals["recirculation.controller.manual_output"]
    assert sig.value_at(0.0) == pytest.approx(0.4)


def test_manual_constant_output(tmp_path: Path) -> None:
    manual = 'mode = "manual"\nmanual_output = "35 %"'
    loaded = load_scenario(with_recirculation(tmp_path, replace={'mode = "automatic"': manual}))
    rc = loaded.spec.recirculation
    assert rc is not None and rc.controller.manual_output == pytest.approx(0.35)


def test_manual_mode_needs_an_output(tmp_path: Path) -> None:
    replace = {'mode = "automatic"': 'mode = "manual"'}
    issues = _issues(with_recirculation(tmp_path, replace=replace))
    assert "recirculation.controller.manual_output" in issues
