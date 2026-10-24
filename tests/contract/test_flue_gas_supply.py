"""Contract tests of the flue gas supply interface (T022; contracts/flue-gas-interface.md)."""

from pathlib import Path

import numpy as np
import pytest

from boidrytwin.errors import ScenarioValidationError, SupplyCoverageError
from boidrytwin.interface.flue_gas import FlueGasSupply
from boidrytwin.scenario.loader import load_scenario

from .conftest import CONSTANT_FLUE_GAS, FLUE_CSV_HEADER, ScenarioWriter, flue_csv_rows

TIMESERIES_FLUE_GAS = """
[flue_gas]
source = "timeseries"
file = "flue.csv"
max_gap = "5 min"
"""


@pytest.fixture(params=["constant", "timeseries"])
def supply(request: pytest.FixtureRequest, write_scenario: ScenarioWriter) -> FlueGasSupply:
    if request.param == "constant":
        path = write_scenario()
    else:
        csv = FLUE_CSV_HEADER + flue_csv_rows(list(range(0, 121, 1)))
        path = write_scenario(flue_gas=TIMESERIES_FLUE_GAS, files={"flue.csv": csv})
    return load_scenario(path).flue_gas


# --- guarantees of every implementation ------------------------------------------------


def test_is_a_flue_gas_supply(supply: FlueGasSupply) -> None:
    assert isinstance(supply, FlueGasSupply)
    assert supply.source_id


def test_state_at_is_deterministic(supply: FlueGasSupply) -> None:
    assert supply.state_at(1234.5) == supply.state_at(1234.5)
    a, b = supply.conditions_at(1234.5), supply.conditions_at(1234.5)
    assert a.temperature == b.temperature and np.array_equal(a.x, b.x)


def test_returned_states_are_valid_si(supply: FlueGasSupply) -> None:
    s = supply.state_at(600.0)
    assert s.temperature == pytest.approx(923.15)
    assert s.pressure == pytest.approx(101_000.0)
    assert s.mass_flow == pytest.approx(8.0)
    assert s.time.utcoffset() is not None


def test_composition_is_wet_mole_fractions_summing_to_one(supply: FlueGasSupply) -> None:
    x = supply.conditions_at(600.0).x
    assert x.sum() == 1.0 or abs(x.sum() - 1.0) < 1e-15
    assert x == pytest.approx([0.705, 0.06, 0.105, 0.12, 0.01])


def test_conditions_match_state(supply: FlueGasSupply) -> None:
    s, c = supply.state_at(900.0), supply.conditions_at(900.0)
    assert c.mass_flow == s.mass_flow and c.temperature == s.temperature
    assert c.pressure == s.pressure and c.quality == s.quality


def test_coverage(supply: FlueGasSupply) -> None:
    assert supply.covers(0.0, 7200.0)


def test_timeseries_outside_coverage_raises(write_scenario: ScenarioWriter) -> None:
    csv = FLUE_CSV_HEADER + flue_csv_rows(list(range(0, 121, 1)))
    supply = load_scenario(
        write_scenario(flue_gas=TIMESERIES_FLUE_GAS, files={"flue.csv": csv})
    ).flue_gas
    assert not supply.covers(0.0, 7300.0)
    with pytest.raises(SupplyCoverageError) as err:
        supply.state_at(7300.0)
    assert "7300" in str(err.value) and "covered period" in str(err.value)


def test_allowed_gaps_are_flagged_missing(write_scenario: ScenarioWriter) -> None:
    csv = FLUE_CSV_HEADER + flue_csv_rows([0, 1, 30, 120])
    flue = TIMESERIES_FLUE_GAS + "allow_gaps = true\n"
    supply = load_scenario(write_scenario(flue_gas=flue, files={"flue.csv": csv})).flue_gas
    assert supply.state_at(600.0).quality == "missing"
    assert supply.state_at(30.0).quality == "interpolated"


# --- rejection catalogue (SC-005) -----------------------------------------------------


def _reasons(path: Path) -> str:
    with pytest.raises(ScenarioValidationError) as err:
        load_scenario(path)
    return " | ".join(i.reason for i in err.value.issues)


def test_rejection_missing_unit(write_scenario: ScenarioWriter) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"8.0 kg/s"', '"8.0"')
    assert "unit missing" in _reasons(write_scenario(flue_gas=flue))


def test_rejection_incompatible_unit(write_scenario: ScenarioWriter) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"650 degC"', '"650 kg"')
    assert "incompatible unit" in _reasons(write_scenario(flue_gas=flue))


def test_rejection_negative_mass_flow(write_scenario: ScenarioWriter) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"8.0 kg/s"', '"-1 kg/s"')
    assert "must be ≥ 0" in _reasons(write_scenario(flue_gas=flue))


@pytest.mark.parametrize("pressure", ['"0 kPa"', '"40 kPa"', '"2.5 bar"'])
def test_rejection_pressure_out_of_range(write_scenario: ScenarioWriter, pressure: str) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"101.0 kPa"', pressure)
    assert "out of range" in _reasons(write_scenario(flue_gas=flue))


@pytest.mark.parametrize("temperature", ['"-5 degC"', '"1300 degC"'])
def test_rejection_temperature_out_of_range(
    write_scenario: ScenarioWriter, temperature: str
) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"650 degC"', temperature)
    assert "out of range" in _reasons(write_scenario(flue_gas=flue))


@pytest.mark.parametrize("value", ['"-1 %"', '"120 %"'])
def test_rejection_fraction_out_of_range(write_scenario: ScenarioWriter, value: str) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"10.5 %"', value)
    assert "out of range" in _reasons(write_scenario(flue_gas=flue))


def test_rejection_fractions_not_summing_to_one(write_scenario: ScenarioWriter) -> None:
    flue = CONSTANT_FLUE_GAS.replace('"70.5 %"', '"63.5 %"')
    assert "sums to 0.930" in _reasons(write_scenario(flue_gas=flue))


def test_rejection_dry_basis_without_water(write_scenario: ScenarioWriter) -> None:
    flue = (
        CONSTANT_FLUE_GAS.replace('composition_basis = "wet"', 'composition_basis = "dry"')
        .replace('x_H2O = "12.0 %"\n', "")
        .replace('"70.5 %"', '"80.5 %"')
        .replace('"10.5 %"', '"12.5 %"')
    )
    assert "water content required for dry basis" in _reasons(write_scenario(flue_gas=flue))


def test_rejection_unordered_timestamps(write_scenario: ScenarioWriter) -> None:
    csv = FLUE_CSV_HEADER + flue_csv_rows([0, 2, 1])
    path = write_scenario(flue_gas=TIMESERIES_FLUE_GAS, files={"flue.csv": csv})
    reasons = _reasons(path)
    assert "not strictly increasing" in reasons and "2026-01-01T00:01:00" in reasons


def test_rejection_timestamp_without_timezone(write_scenario: ScenarioWriter) -> None:
    csv = FLUE_CSV_HEADER + flue_csv_rows([0, 1]).replace(":00Z,", ":00,", 1)
    path = write_scenario(flue_gas=TIMESERIES_FLUE_GAS, files={"flue.csv": csv})
    assert "timezone required" in _reasons(path)


def test_rejection_gap_not_allowed(write_scenario: ScenarioWriter) -> None:
    csv = FLUE_CSV_HEADER + flue_csv_rows([0, 1, 30, 120])
    path = write_scenario(flue_gas=TIMESERIES_FLUE_GAS, files={"flue.csv": csv})
    reasons = _reasons(path)
    assert "gap" in reasons and "00:01:00" in reasons and "00:30:00" in reasons


# --- source swap (FR-005, SC-008) ------------------------------------------------------


def test_swap_sources() -> None:
    """Constant and time-series sources with the same values give identical dryer results."""
    from boidrytwin.dryer.simulate import simulate
    from tests.integration.conftest import EXAMPLES

    constant = load_scenario(EXAMPLES / "reference_constant.toml")
    series = load_scenario(EXAMPLES / "reference_timeseries.toml")
    assert constant.spec.dryer == series.spec.dryer  # no change to the dryer configuration
    a = simulate(constant).results
    b = simulate(series).results
    for column in a.columns:
        if column == "input_quality":
            continue  # "good" vs "good"/"interpolated" labels differ by design
        # bit-identical; NaN (no product leaving an empty drum at t = 0) equals NaN
        x, y = a[column].to_numpy(dtype=float), b[column].to_numpy(dtype=float)
        assert np.array_equal(x, y, equal_nan=True), column
