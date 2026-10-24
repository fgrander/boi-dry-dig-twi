"""Scenario file: boiler house sections (T019; contracts/scenario-file-boiler.md)."""

from pathlib import Path

import pytest

from boidrytwin import load_scenario
from boidrytwin.errors import ScenarioValidationError
from tests.integration.conftest import EXAMPLES, make_variant


def _issues(path: Path) -> list[str]:
    with pytest.raises(ScenarioValidationError) as err:
        load_scenario(path)
    return [f"{i.field}: {i.reason}" for i in err.value.issues]


def test_example_loads_and_normalises() -> None:
    loaded = load_scenario(EXAMPLES / "boiler_house_only.toml")
    bh = loaded.spec.boiler_house
    assert bh is not None and loaded.spec.dryer is None and loaded.spec.flue_gas is None
    assert bh.config.furnace.rated_fuel_power == 15e6
    assert bh.config.furnace.bed_time_constant == 900.0
    assert len(bh.config.heaters) == 3 and bh.config.heaters[2].n_rows == 11
    assert bh.oil == "shell_s2"
    assert bh.controllers.oil_temperature.gain == pytest.approx(0.191)
    assert bh.controllers.oil_temperature.integral_time == 1157.0
    assert bh.controllers.oxygen.output_max == 2.5
    assert loaded.signals["boiler_house.thermal_oil.return_temperature"].value_at(
        0
    ) == pytest.approx(513.15)
    assert loaded.signals["boiler_house.controllers.oil_temperature.setpoint"].value_at(
        0
    ) == pytest.approx(555.15)
    assert loaded.spec.boiler_house.initial_state.kind == "steady_state"


def test_ambiguous_with_flue_gas_source(tmp_path: Path) -> None:
    extra = '\n[flue_gas]\nsource = "constant"\nmass_flow = "8 kg/s"\n'
    path = make_variant(
        tmp_path,
        base="boiler_house_only.toml",
        replace={"[ambient]": extra.strip() + "\n\n[ambient]"},
    )
    assert any("ambiguous" in i for i in _issues(path))


def test_custom_fuel_composition_rules(tmp_path: Path) -> None:
    path = make_variant(
        tmp_path,
        base="boiler_house_only.toml",
        replace={
            'kind = "wood_chips"': 'kind = "custom"\nC = "50 %"\nH = "6 %"\nN = "0.4 %"\nS = "0 %"\nash = "1 %"\nO = "30 %"'
        },
    )
    assert any("composition sum" in i for i in _issues(path))


def test_heater_arrangement_rules(tmp_path: Path) -> None:
    path = make_variant(tmp_path, base="boiler_house_only.toml",
                        replace={'[[boiler_house.heaters]]\ntype = "radiant"': '[[boiler_house.heaters]]\ntype = "convective"'})  # fmt: skip
    assert any("radiant" in i for i in _issues(path))
    path = make_variant(tmp_path, base="boiler_house_only.toml", name="b.toml",
                        replace={"starts_after_heater = 1": "starts_after_heater = 3"})  # fmt: skip
    assert any("starts_after_heater" in i for i in _issues(path))


def test_controller_rules(tmp_path: Path) -> None:
    path = make_variant(
        tmp_path,
        base="boiler_house_only.toml",
        replace={'output_min = "0.47 kg/s"': 'output_min = "3 kg/s"'},
    )
    assert any("output_min" in i for i in _issues(path))


def test_air_mass_flow_only_with_manual_oxygen_loop(tmp_path: Path) -> None:
    replace = {
        'relative_humidity = "60 %"\n\n[boiler_house.furnace]': 'relative_humidity = "60 %"\nmass_flow = "9 kg/s"\n\n[boiler_house.furnace]'
    }
    path = make_variant(tmp_path, base="boiler_house_only.toml", replace=replace)
    assert any("combustion_air.mass_flow" in i and "manual" in i for i in _issues(path))


def test_issues_have_field_value_reason_and_line(tmp_path: Path) -> None:
    path = make_variant(
        tmp_path,
        base="boiler_house_only.toml",
        replace={'rated_fuel_power = "15 MW"': 'rated_fuel_power = "15"'},
    )
    with pytest.raises(ScenarioValidationError) as err:
        load_scenario(path)
    issue = err.value.issues[0]
    assert issue.field == "boiler_house.furnace.rated_fuel_power"
    assert issue.reason == "unit missing"
    assert issue.location and "line" in issue.location


def test_coupled_example_loads() -> None:
    loaded = load_scenario(EXAMPLES / "plant_reference.toml")
    assert loaded.spec.flue_gas is not None and loaded.spec.flue_gas.source == "boiler_house"
    drum = loaded.spec.boiler_house.controllers.drum_inlet_temperature
    assert drum is not None and drum.action == "direct" and drum.max_dilution_air == 6.0


def test_coupled_rejects_dilution_air_section(tmp_path: Path) -> None:
    path = make_variant(tmp_path, base="plant_reference.toml",
                        replace={"[product_feed]": '[dilution_air]\nmass_flow = "2 kg/s"\n\n[product_feed]'})  # fmt: skip
    assert any("set by the drum inlet controller" in i for i in _issues(path))


def test_coupled_needs_max_dilution_air(tmp_path: Path) -> None:
    path = make_variant(
        tmp_path, base="plant_reference.toml", replace={'max_dilution_air = "6 kg/s"\n': ""}
    )
    assert any("max_dilution_air" in i for i in _issues(path))


def test_boiler_source_without_boiler_house(tmp_path: Path) -> None:
    path = make_variant(tmp_path, base="reference_constant.toml",
                        replace={'source = "constant"': 'source = "boiler_house"'})  # fmt: skip
    assert any("requires a [boiler_house] section" in i for i in _issues(path))
