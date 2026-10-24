"""Flue gas thermodynamic and transport properties (T012)."""

import numpy as np
import pytest

from boidrytwin.properties import gas

AIR = np.array([0.7808, 0.2095, 0.0004, 0.0, 0.0093])  # N2, O2, CO2, H2O, Ar
FLUE = np.array([0.705, 0.06, 0.105, 0.12, 0.01])


def test_species_order() -> None:
    assert gas.SPECIES == ("N2", "O2", "CO2", "H2O", "AR")


@pytest.mark.parametrize(
    ("species", "cp_298"),
    [("N2", 29.12), ("O2", 29.38), ("CO2", 37.12), ("H2O", 33.59), ("AR", 20.786)],
)
def test_cp_at_298(species: str, cp_298: float) -> None:
    i = gas.SPECIES.index(species)
    assert gas.cp_molar(298.15)[i] == pytest.approx(cp_298, rel=5e-3)


def test_ranges_join_at_1000_k() -> None:
    lo = gas.cp_molar(1000.0 - 1e-9)
    hi = gas.cp_molar(1000.0 + 1e-9)
    assert lo == pytest.approx(hi, rel=1e-3)
    assert gas.h_molar(1000.0 - 1e-9) == pytest.approx(gas.h_molar(1000.0 + 1e-9), rel=1e-4)


def test_sensible_enthalpy_zero_at_reference() -> None:
    assert gas.h_sensible_mass(298.15, gas.mass_fractions(FLUE)) == pytest.approx(0.0, abs=1e-6)


def test_mass_fraction_round_trip() -> None:
    y = gas.mass_fractions(FLUE)
    assert y.sum() == pytest.approx(1.0)
    assert gas.mole_fractions(y) == pytest.approx(FLUE)


def test_vectorised_over_cells() -> None:
    T = np.linspace(300, 1200, 7)
    y = np.tile(gas.mass_fractions(FLUE), (7, 1))
    assert gas.cp_mass(T, y).shape == (7,)
    assert gas.h_sensible_mass(T, y).shape == (7,)
    assert gas.viscosity(T, np.tile(FLUE, (7, 1))).shape == (7,)


def test_cp_mass_is_derivative_of_enthalpy() -> None:
    y = gas.mass_fractions(FLUE)
    T, dT = 700.0, 1e-3
    dh = (gas.h_sensible_mass(T + dT, y) - gas.h_sensible_mass(T - dT, y)) / (2 * dT)
    assert dh == pytest.approx(gas.cp_mass(T, y), rel=1e-6)


@pytest.mark.parametrize(
    ("T", "mu_ref", "k_ref"),
    [(300.0, 184.6e-7, 26.3e-3), (1000.0, 424.4e-7, 66.7e-3)],  # air, Incropera Table A.4
)
def test_air_transport(T: float, mu_ref: float, k_ref: float) -> None:
    # research.md R6 target: 3-5 %. Viscosity meets 3 %; the kinetic-theory conductivity of
    # Cantera's gri30 data (which our fit reproduces to < 1 %) is 3.9 % above the
    # measured value at 1000 K, inside the 5 % target.
    assert gas.viscosity(T, AIR) == pytest.approx(mu_ref, rel=0.03)
    assert gas.conductivity(T, AIR) == pytest.approx(k_ref, rel=0.05)


@pytest.mark.oracle
def test_thermo_against_cantera() -> None:
    import cantera as ct

    ct_gas = ct.Solution("gri30.yaml")
    names = "N2:{},O2:{},CO2:{},H2O:{},AR:{}"
    rng = np.random.default_rng(1)
    for _ in range(200):
        x = rng.dirichlet(np.ones(5))
        T = float(rng.uniform(273.15, 1473.15))
        ct_gas.TPX = T, ct.one_atm, names.format(*x)
        cp_ct = ct_gas.cp_mass
        ct_gas.TP = 298.15, ct.one_atm
        h_ref = ct_gas.enthalpy_mass
        ct_gas.TP = T, ct.one_atm
        y = gas.mass_fractions(x)
        assert gas.cp_mass(T, y) == pytest.approx(cp_ct, rel=1e-3)
        assert gas.h_sensible_mass(T, y) == pytest.approx(ct_gas.enthalpy_mass - h_ref, rel=1e-3)


@pytest.mark.oracle
def test_transport_against_cantera() -> None:
    import cantera as ct

    ct_gas = ct.Solution("gri30.yaml")
    for T in [300.0, 500.0, 800.0, 1100.0, 1400.0]:
        for x in (AIR, FLUE):
            ct_gas.TPX = T, ct.one_atm, "N2:{},O2:{},CO2:{},H2O:{},AR:{}".format(*x)
            assert gas.viscosity(T, x) == pytest.approx(ct_gas.viscosity, rel=0.05)
            assert gas.conductivity(T, x) == pytest.approx(ct_gas.thermal_conductivity, rel=0.05)
