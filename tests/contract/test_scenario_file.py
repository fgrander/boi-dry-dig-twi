"""Scenario file contract: time, flue_gas and dilution_air sections (T023)."""

from pathlib import Path

import pytest

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.scenario.loader import load_scenario

from .conftest import CONSTANT_FLUE_GAS, TIME, ScenarioWriter


def _issues(path: Path) -> list[str]:
    with pytest.raises(ScenarioValidationError) as err:
        load_scenario(path)
    return [f"{i.field}: {i.reason} @ {i.location}" for i in err.value.issues]


def test_contract_example_normalises_to_si(write_scenario: ScenarioWriter) -> None:
    loaded = load_scenario(write_scenario(extra='\n[dilution_air]\nmass_flow = "2.0 kg/s"\n'))
    spec = loaded.spec
    assert spec.name == "contract test"
    assert spec.time.output_interval == 60.0
    assert spec.time.duration == 7200.0
    assert spec.flue_gas.source == "constant"
    assert spec.flue_gas.mass_flow == pytest.approx(8.0)
    assert spec.flue_gas.temperature == pytest.approx(923.15)
    assert spec.flue_gas.pressure == pytest.approx(101_000.0)
    assert sum(spec.flue_gas.composition) == pytest.approx(1.0)
    assert loaded.signals["dilution_air.mass_flow"].value_at(0.0) == pytest.approx(2.0)


def test_dilution_air_defaults_to_zero(write_scenario: ScenarioWriter) -> None:
    loaded = load_scenario(write_scenario())
    assert loaded.signals["dilution_air.mass_flow"].value_at(100.0) == 0.0


def test_unknown_keys_are_errors(write_scenario: ScenarioWriter) -> None:
    flue = CONSTANT_FLUE_GAS + 'mas_flow = "1 kg/s"\n'
    issues = _issues(write_scenario(flue_gas=flue, extra="\n[surprise]\nx = 1\n"))
    assert any(i.startswith("flue_gas.mas_flow: unknown key") for i in issues)
    assert any(i.startswith("surprise: unknown key") for i in issues)


def test_all_issues_reported_together_with_line(write_scenario: ScenarioWriter) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"8.0 kg/s"', '"-1 kg/s"').replace('"650 degC"', '"650"')
    issues = _issues(write_scenario(flue_gas=flue))
    assert len(issues) == 2
    assert "flue_gas.mass_flow: must be ≥ 0 @ scenario.toml:line 11" in issues
    assert "flue_gas.temperature: unit missing @ scenario.toml:line 12" in issues


def test_time_rules(write_scenario: ScenarioWriter) -> None:
    bad_time = TIME.replace('"2026-01-01T02:00:00Z"', '"2025-12-31T00:00:00Z"').replace(
        '"1 min"', '"2 h"'
    )
    issues = _issues(write_scenario(time=bad_time))
    assert any(i.startswith("time.end: must be after time.start") for i in issues)
    assert any(i.startswith("time.output_interval: out of range") for i in issues)


def test_time_requires_timezone(write_scenario: ScenarioWriter) -> None:
    issues = _issues(write_scenario(time=TIME.replace("00:00:00Z", "00:00:00", 1)))
    assert any(i.startswith("time.start: timezone required") for i in issues)


def test_gauge_pressure_with_reference(write_scenario: ScenarioWriter) -> None:
    flue = CONSTANT_FLUE_GAS.replace(
        'pressure = "101.0 kPa"', 'pressure = "-2 mbar"\npressure_reference = "101.325 kPa"'
    )
    loaded = load_scenario(write_scenario(flue_gas=flue))
    assert loaded.spec.flue_gas.pressure == pytest.approx(101_125.0)


def test_mass_fraction_composition(write_scenario: ScenarioWriter) -> None:
    flue = CONSTANT_FLUE_GAS.replace('composition_type = "mole"', 'composition_type = "mass"')
    loaded = load_scenario(write_scenario(flue_gas=flue))
    # same numbers read as mass fractions give fewer moles of heavy CO2
    assert loaded.spec.flue_gas.composition[2] < 0.105


def test_dilution_air_from_time_series(write_scenario: ScenarioWriter) -> None:
    csv = "time,dilution\nunit,kg/s\n2026-01-01T00:00:00Z,1.0\n2026-01-01T02:00:00Z,3.0\n"
    extra = '\n[dilution_air]\nmass_flow = { file = "air.csv", column = "dilution" }\n'
    loaded = load_scenario(write_scenario(extra=extra, files={"air.csv": csv}))
    assert loaded.signals["dilution_air.mass_flow"].value_at(3600.0) == pytest.approx(2.0)


def test_time_series_must_cover_period(write_scenario: ScenarioWriter) -> None:
    csv = "time,dilution\nunit,kg/s\n2026-01-01T00:00:00Z,1.0\n2026-01-01T01:00:00Z,3.0\n"
    extra = '\n[dilution_air]\nmass_flow = { file = "air.csv", column = "dilution" }\n'
    issues = _issues(write_scenario(extra=extra, files={"air.csv": csv}))
    assert any("does not cover" in i and "02:00:00" in i for i in issues)


def test_missing_time_series_file(write_scenario: ScenarioWriter) -> None:
    extra = '\n[dilution_air]\nmass_flow = { file = "nope.csv", column = "x" }\n'
    issues = _issues(write_scenario(extra=extra))
    assert any("file not found" in i for i in issues)


def test_invalid_toml(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text("name = \n", encoding="utf-8")
    issues = _issues(path)
    assert issues[0].startswith("scenario: invalid TOML")
