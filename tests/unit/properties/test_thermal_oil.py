"""Thermal oil properties (T004; research.md R6)."""

import numpy as np
import pytest

from boidrytwin.properties.thermal_oil import OILS, get_oil

C = 273.15

# Shell Heat Transfer Oil S2, TDS v1.1 (2014), "Typical Design Data (calculated)"
S2 = {
    20: (857, 2049, 0.135),
    100: (805, 2400, 0.129),
    200: (740, 2838, 0.121),
    300: (675, 3277, 0.114),
}
S2_NU = {40: 29.0, 100: 5.1, 200: 1.4}  # mm²/s
# Therminol 66, Eastman brochure (rho, cp, k, nu mm²/s)
TH66 = {
    20: (1008, 1560, 0.1176, 122),
    200: (885, 2190, 0.1065, 0.972),
    300: (809, 2570, 0.0946, 0.510),
}


def test_registry() -> None:
    assert set(OILS) == {"shell_s2", "therminol_66"}


@pytest.mark.parametrize(("t", "ref"), S2.items())
def test_shell_s2_against_data_sheet(t: float, ref: tuple[float, float, float]) -> None:
    oil = get_oil("shell_s2")
    T = t + C
    assert oil.density(T) == pytest.approx(ref[0], rel=0.01)
    assert oil.cp(T) == pytest.approx(ref[1], rel=0.01)
    assert oil.conductivity(T) == pytest.approx(ref[2], rel=0.01)


@pytest.mark.parametrize(("t", "nu"), S2_NU.items())
def test_shell_s2_viscosity(t: float, nu: float) -> None:
    assert get_oil("shell_s2").viscosity(t + C) * 1e6 == pytest.approx(nu, rel=0.05)


@pytest.mark.parametrize(("t", "ref"), TH66.items())
def test_therminol_66_against_brochure(t: float, ref: tuple[float, float, float, float]) -> None:
    oil = get_oil("therminol_66")
    T = t + C
    assert oil.density(T) == pytest.approx(ref[0], rel=0.01)
    assert oil.cp(T) == pytest.approx(ref[1], rel=0.01)
    assert oil.conductivity(T) == pytest.approx(ref[2], rel=0.01)
    assert oil.viscosity(T) * 1e6 == pytest.approx(ref[3], rel=0.03)


@pytest.mark.parametrize("name", sorted(OILS))
def test_enthalpy_consistent_with_cp_and_invertible(name: str) -> None:
    oil = get_oil(name)
    T, dT = 520.0, 1e-3
    dh = (oil.enthalpy(T + dT) - oil.enthalpy(T - dT)) / (2 * dT)
    assert dh == pytest.approx(oil.cp(T), rel=1e-7)
    temps = np.linspace(300.0, 620.0, 33)
    assert np.max(np.abs(oil.temperature_from_enthalpy(oil.enthalpy(temps)) - temps)) < 1e-9
    assert oil.enthalpy(298.15) == pytest.approx(0.0, abs=1e-9)


def test_default_limits() -> None:
    s2, th = get_oil("shell_s2"), get_oil("therminol_66")
    assert (s2.max_bulk_temperature, s2.max_film_temperature) == (573.15, 593.15)
    assert (th.max_bulk_temperature, th.max_film_temperature) == (618.15, 648.15)
    assert s2.property_range[1] >= 613.15  # fits used up to 340 °C


def test_unknown_oil() -> None:
    with pytest.raises(KeyError, match="unknown thermal oil"):
        get_oil("olive")
