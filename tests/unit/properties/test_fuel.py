"""Fuel composition, heating value and stoichiometry (T003; research.md R2)."""

import numpy as np
import pytest

from boidrytwin.errors import ScenarioValidationError
from boidrytwin.properties import fuel, gas

M_AIR = 0.028965


def test_default_compositions() -> None:
    chips = fuel.FuelComposition.default("wood_chips")
    assert (chips.C, chips.H, chips.N, chips.S, chips.ash) == pytest.approx(
        (0.513, 0.061, 0.004, 0.0002, 0.013)
    )
    assert pytest.approx(1 - 0.513 - 0.061 - 0.004 - 0.0002 - 0.013) == chips.O
    bark = fuel.FuelComposition.default("bark")
    assert (bark.C, bark.H, bark.ash) == pytest.approx((0.499, 0.059, 0.025))


def test_custom_composition_rules() -> None:
    by_difference = fuel.FuelComposition.from_input(C=0.5, H=0.06, N=0.004, S=0.0, ash=0.01)
    assert pytest.approx(0.426) == by_difference.O
    with pytest.raises(ScenarioValidationError, match="sum"):
        fuel.FuelComposition.from_input(C=0.5, H=0.06, N=0.004, S=0.0, ash=0.01, O=0.40)
    with pytest.raises(ScenarioValidationError, match="out of range"):
        fuel.FuelComposition.from_input(C=1.2, H=0.06, N=0.0, S=0.0, ash=0.0)


def test_channiwala_parikh_and_lhv() -> None:
    chips = fuel.FuelComposition.default("wood_chips")
    assert chips.hhv_dry() == pytest.approx(20.85e6, rel=2e-3)
    assert chips.lhv_dry() == pytest.approx(19.5e6, rel=3e-3)
    assert 19.0e6 <= chips.lhv_dry() <= 20.5e6  # VTT Technology 272, Table 4.15
    assert chips.lhv_as_received(0.5) == pytest.approx(chips.lhv_dry() * 0.5 - 0.02443e6 * 50)
    assert chips.lhv_as_received(0.5) == pytest.approx(8.5e6, rel=1e-2)


def test_measured_heating_value_overrides_correlation() -> None:
    hhv = fuel.FuelComposition.from_input(kind="wood_chips", hhv_dry=21.0e6)
    assert hhv.hhv_dry() == 21.0e6
    lhv = fuel.FuelComposition.from_input(kind="wood_chips", lhv_dry=19.0e6)
    assert lhv.lhv_dry() == 19.0e6
    with pytest.raises(ScenarioValidationError, match="at most one"):
        fuel.FuelComposition.from_input(kind="wood_chips", hhv_dry=21e6, lhv_dry=19e6)


def test_stoichiometric_air() -> None:
    chips = fuel.FuelComposition.default("wood_chips")
    st = fuel.stoichiometry(chips, moisture_wet=0.0, air_humidity=0.0, excess_air=1.0)
    assert st.air_dry_mass == pytest.approx(6.23, rel=5e-3)
    assert st.flue_moles[gas.I_O2] == pytest.approx(0.0, abs=1e-12)


def test_flue_gas_species_and_element_conservation() -> None:
    chips = fuel.FuelComposition.default("wood_chips")
    w, Y_air, lam = 0.45, 0.009, 1.5
    st = fuel.stoichiometry(chips, moisture_wet=w, air_humidity=Y_air, excess_air=lam)
    X = w / (1 - w)
    # mass: dry fuel + moisture + humid air = flue gas + ash
    inflow = 1.0 + X + st.air_dry_mass * (1 + Y_air)
    assert st.flue_mass + chips.ash == pytest.approx(inflow, rel=1e-12)
    # carbon: all of it ends up as CO2 (plus the air's CO2)
    air_co2 = st.air_dry_moles * 0.0004
    assert st.flue_moles[gas.I_CO2] == pytest.approx(chips.C / 0.012011 + air_co2, rel=1e-12)
    # hydrogen: fuel H + moisture + air humidity
    water = chips.H / 0.002016 + X / 0.018015 + st.air_dry_moles * fuel.M_DRY_AIR * Y_air / 0.018015
    assert st.flue_moles[gas.I_H2O] == pytest.approx(water, rel=1e-12)
    # oxygen excess
    assert st.flue_moles[gas.I_O2] == pytest.approx((lam - 1) * st.o2_min, rel=1e-12)
    assert st.element_balance_residual() == pytest.approx(0.0, abs=1e-12)


def test_lambda_and_dry_oxygen_are_inverse() -> None:
    chips = fuel.FuelComposition.default("wood_chips")
    lam = fuel.excess_air_from_o2_dry(chips, 0.07, moisture_wet=0.45, air_humidity=0.009)
    assert lam == pytest.approx(1.50, abs=0.02)
    st = fuel.stoichiometry(chips, moisture_wet=0.45, air_humidity=0.009, excess_air=lam)
    assert st.o2_dry == pytest.approx(0.07, rel=1e-10)


def test_wet_mole_fractions_sum_to_one() -> None:
    st = fuel.stoichiometry(
        fuel.FuelComposition.default("bark"), moisture_wet=0.5, air_humidity=0.01, excess_air=1.6
    )
    x = st.mole_fractions()
    assert x.sum() == pytest.approx(1.0)
    assert np.all(x >= 0)
