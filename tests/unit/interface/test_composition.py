"""GasComposition (T018)."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from boidrytwin.errors import InterfaceValidationError
from boidrytwin.interface.composition import GasComposition
from boidrytwin.properties import gas

FLUE = {"x_N2": 0.705, "x_O2": 0.06, "x_CO2": 0.105, "x_H2O": 0.12, "x_other": 0.01}


def _reasons(err: pytest.ExceptionInfo[InterfaceValidationError]) -> str:
    return " | ".join(f"{i.field}: {i.reason}" for i in err.value.issues)


def test_wet_mole_fractions() -> None:
    comp = GasComposition.from_input(FLUE)
    assert comp.as_array() == pytest.approx([0.705, 0.06, 0.105, 0.12, 0.01])
    assert comp.as_array().sum() == 1.0


def test_small_deviation_is_normalised() -> None:
    comp = GasComposition.from_input({**FLUE, "x_N2": 0.709})  # sum 1.004
    assert comp.as_array().sum() == pytest.approx(1.0, abs=1e-15)


def test_sum_outside_tolerance_is_rejected() -> None:
    with pytest.raises(InterfaceValidationError) as err:
        GasComposition.from_input({**FLUE, "x_N2": 0.635})  # sum 0.93
    assert "sums to 0.930" in _reasons(err)
    assert err.value.issues[0].allowed == "0 ≤ x ≤ 1, sum = 1 ± 0.005"


@pytest.mark.parametrize("bad", [-0.01, 1.2])
def test_fraction_out_of_range(bad: float) -> None:
    with pytest.raises(InterfaceValidationError) as err:
        GasComposition.from_input({**FLUE, "x_CO2": bad})
    assert "flue_gas.composition.x_CO2: out of range" in _reasons(err)


def test_missing_component_is_rejected() -> None:
    fractions = {k: v for k, v in FLUE.items() if k != "x_O2"}
    with pytest.raises(InterfaceValidationError) as err:
        GasComposition.from_input(fractions)
    assert "x_O2: required" in _reasons(err)


def test_dry_basis_needs_water_content() -> None:
    dry = {"x_N2": 0.80, "x_O2": 0.07, "x_CO2": 0.12, "x_other": 0.01}
    with pytest.raises(InterfaceValidationError) as err:
        GasComposition.from_input(dry, basis="dry")
    assert "water content required for dry basis" in _reasons(err)


def test_dry_basis_converted_to_wet() -> None:
    dry = {"x_N2": 0.80, "x_O2": 0.07, "x_CO2": 0.12, "x_other": 0.01}
    comp = GasComposition.from_input(dry, basis="dry", water_wet=0.12)
    assert comp.x_N2 == pytest.approx(0.80 * 0.88)
    assert comp.x_H2O == pytest.approx(0.12)
    assert comp.as_array().sum() == pytest.approx(1.0)


def test_mass_fractions_converted_to_mole_fractions() -> None:
    mole = np.array(list(FLUE.values()))
    mass = gas.mass_fractions(mole)
    keys = list(FLUE)
    comp = GasComposition.from_input(dict(zip(keys, mass, strict=True)), fraction_type="mass")
    assert comp.as_array() == pytest.approx(mole)


def test_other_is_represented_by_argon() -> None:
    comp = GasComposition.from_input(FLUE)
    assert comp.as_array()[gas.I_AR] == pytest.approx(0.01)


def test_dry_molar_mass_excludes_water() -> None:
    comp = GasComposition.from_input(FLUE)
    x = comp.as_array()
    expected = np.sum(np.delete(x * gas.MOLAR_MASS, gas.I_H2O)) / (1 - x[gas.I_H2O])
    assert comp.dry_molar_mass == pytest.approx(expected)


@given(st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=5, max_size=5))
def test_any_normalisable_composition_is_accepted_and_sums_to_one(values: list[float]) -> None:
    total = sum(values)
    if total == 0:
        return
    fractions = dict(zip(FLUE, [v / total for v in values], strict=True))
    comp = GasComposition.from_input(fractions)
    arr = comp.as_array()
    assert arr.sum() == pytest.approx(1.0, abs=1e-12)
    assert np.all(arr >= 0)


@given(st.floats(min_value=0.0, max_value=0.9), st.floats(min_value=1.1, max_value=5.0))
def test_compositions_far_from_one_are_rejected(low: float, high: float) -> None:
    for scale in (low, high):
        fractions = {k: v * scale for k, v in FLUE.items()}
        if abs(sum(fractions.values()) - 1) <= 0.005:
            continue
        with pytest.raises(InterfaceValidationError):
            GasComposition.from_input(fractions)
