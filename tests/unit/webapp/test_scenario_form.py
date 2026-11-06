"""Scenario form: TOML ↔ form, validation through the loader (T023; FR-007, FR-008, SC-004)."""

import tomllib
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from boidrytwin.webapp.scenario_form import (
    ScenarioForm,
    materialize,
    read_form,
    set_field,
    validate_form,
)

EXAMPLES = sorted((Path(__file__).parents[3] / "examples").glob("*.toml"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_every_example_round_trips(path: Path, tmp_path: Path) -> None:
    form = read_form(path)
    assert form.sections and all(s.fields for s in form.sections)
    out = materialize(form, path.parent / f"_roundtrip_{path.name}", dry_run=True)
    assert out == path.read_text(encoding="utf-8")


def test_sections_fields_and_kinds() -> None:
    form = read_form(Path(__file__).parents[3] / "examples" / "plant_oil_step.toml")
    names = [s.name for s in form.sections]
    assert names[:3] == ["", "time", "flue_gas"]  # top-level keys first, then file order
    assert "boiler_house.heaters[1]" in names and "boiler_house.heaters[3]" in names
    fuel = form.section("boiler_house.fuel")
    moist = fuel.field("moisture_wet_basis")
    assert moist.kind == "quantity" and moist.value == "45" and moist.unit == "%"
    assert fuel.field("kind").kind == "text"
    oil = form.section("boiler_house.thermal_oil")
    assert oil.field("return_temperature").kind == "series_file"
    assert form.section("boiler_house.controllers.oxygen").field("gain").kind == "number"


def test_edit_changes_only_its_line(tmp_path: Path) -> None:
    src = Path(__file__).parents[3] / "examples" / "plant_reference.toml"
    form = read_form(src)
    set_field(form, "boiler_house.fuel", "moisture_wet_basis", value="50", unit="%")
    text = materialize(form, src.parent / "x.toml", dry_run=True)
    old, new = src.read_text(encoding="utf-8").splitlines(), text.splitlines()
    assert len(old) == len(new)
    diff = [i for i, (a, b) in enumerate(zip(old, new, strict=True)) if a != b]
    assert len(diff) == 1 and new[diff[0]] == 'moisture_wet_basis = "50 %"'


def _issues(form: ScenarioForm, tmp_path: Path) -> list[Any]:
    return validate_form(form, tmp_path)


@pytest.mark.parametrize(
    ("section", "key", "value", "unit", "field", "reason"),
    [
        (
            "boiler_house.furnace",
            "rated_fuel_power",
            "15",
            "",
            "boiler_house.furnace.rated_fuel_power",
            "unit missing",
        ),
        (
            "boiler_house.fuel",
            "moisture_wet_basis",
            "70",
            "%",
            "boiler_house.fuel.moisture_wet_basis",
            None,
        ),
        (
            "boiler_house.controllers.oil_temperature",
            "output_min",
            "3",
            "kg/s",
            "boiler_house.controllers.oil_temperature",
            None,
        ),
        ("time", "output_interval", "5", "h", "time.output_interval", None),
        ("dryer.geometry", "length", "-3", "m", "dryer.geometry.length", None),
    ],
)
def test_loader_issues_map_to_fields(
    tmp_path: Path, section: str, key: str, value: str, unit: str, field: str, reason: str | None
) -> None:
    form = read_form(Path(__file__).parents[3] / "examples" / "plant_reference.toml")
    set_field(form, section, key, value=value, unit=unit)
    issues = _issues(form, tmp_path)
    assert issues, "the loader must reject the value"
    target = form.section(section).field(key)
    assert any(i.field.startswith(field) for i in target.issues) or any(
        i.field.startswith(field) for i in form.issues
    )
    if reason:
        assert any(i.reason == reason for i in target.issues)


def test_valid_form_has_no_issues(tmp_path: Path) -> None:
    form = read_form(Path(__file__).parents[3] / "examples" / "plant_reference.toml")
    set_field(form, "boiler_house.fuel", "moisture_wet_basis", value="50", unit="%")
    assert _issues(form, tmp_path) == []


def test_coupled_rules_reported(tmp_path: Path) -> None:
    form = read_form(Path(__file__).parents[3] / "examples" / "plant_reference.toml")
    set_field(
        form, "boiler_house.controllers.drum_inlet_temperature", "max_dilution_air", remove=True
    )
    issues = _issues(form, tmp_path)
    assert any("max_dilution_air" in i.field for i in issues)


def test_examples_are_read_only() -> None:
    form = read_form(
        Path(__file__).parents[3] / "examples" / "plant_reference.toml", read_only=True
    )
    with pytest.raises(PermissionError):
        materialize(form, Path(__file__).parents[3] / "examples" / "plant_reference.toml")


def test_a_scenario_with_a_plain_file_key_validates_from_another_folder() -> None:
    # [flue_gas] file = "../tests/data/…" is relative to the example; the check writes the
    # form into a temporary folder and must still find the file (bug found in feature 005)
    path = Path(__file__).parents[3] / "examples" / "reference_timeseries.toml"
    form = read_form(path, read_only=True)
    assert validate_form(form) == []


def test_a_plain_file_key_is_kept_relative_to_the_new_place(tmp_path: Path) -> None:
    path = Path(__file__).parents[3] / "examples" / "reference_timeseries.toml"
    form = read_form(path, read_only=True)
    target = tmp_path / "saved" / "copy.toml"
    materialize(form, target)
    ref = tomllib.loads(target.read_text(encoding="utf-8"))["flue_gas"]["file"]
    assert (target.parent / ref).resolve() == (
        path.parent / "../tests/data/flue_gas_constant.csv"
    ).resolve()
