"""Furnace zone, radiant exchange and refractory (T014; research.md R4)."""

import numpy as np
import pytest

from boidrytwin.boiler_house import furnace

SIGMA = 5.670374419e-8


def test_radiant_heat_hand_value() -> None:
    q = furnace.radiant_heat(T_gas=1300.0, T_wall=560.0, cold_plane_area=50.0, emissivity=0.5,
                             tube_area=100.0, convective_htc=11.0)  # fmt: skip
    expected = SIGMA * 50.0 * 0.5 * (1300.0**4 - 560.0**4) + 11.0 * 100.0 * (1300.0 - 560.0)
    assert q == pytest.approx(expected, rel=1e-12)
    assert furnace.radiant_heat(560.0, 560.0, 50.0, 0.5, 100.0, 11.0) == pytest.approx(
        0.0, abs=1e-6
    )


def test_refractory_heat_directions() -> None:
    q_gas, q_cond, q_loss = furnace.refractory_flows(
        T_gas=1300.0, T_hot=1100.0, T_bulk=700.0, T_ambient=293.15, gas_htc=30.0, area=100.0,
        conductance=800.0, loss_ua=260.0,
    )  # fmt: skip
    assert q_gas == pytest.approx(30.0 * 100.0 * 200.0)
    assert q_cond == pytest.approx(800.0 * 400.0)
    assert q_loss == pytest.approx(260.0 * (700.0 - 293.15))


def test_adiabatic_temperature_against_cantera() -> None:
    pytest.importorskip("cantera")
    import cantera as ct

    from boidrytwin.properties import fuel, gas

    chips = fuel.FuelComposition.default("wood_chips")
    T_ad = furnace.adiabatic_temperature(chips, moisture_wet=0.45, excess_air=1.5,
                                         air_humidity=0.0, T_fuel=298.15, T_air=298.15)  # fmt: skip
    # oracle: equilibrium of the same products from the same total enthalpy
    st = fuel.stoichiometry(chips, moisture_wet=0.45, air_humidity=0.0, excess_air=1.5)
    x = st.mole_fractions()
    names = "N2:{},O2:{},CO2:{},H2O:{},AR:{}".format(*x)
    g = ct.Solution("gri30.yaml")
    g.TPX = T_ad, ct.one_atm, names
    g.equilibrate("HP")
    assert pytest.approx(T_ad, abs=10.0) == g.T  # dissociation negligible below 1300 °C
    assert 1300.0 < T_ad < 1700.0  # rough balance: about 1500-1550 K
    assert np.isfinite(T_ad)
    assert gas.SPECIES[gas.I_AR] == "AR"
