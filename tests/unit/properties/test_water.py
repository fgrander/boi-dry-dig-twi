"""Water and humidity properties (T011)."""

import numpy as np
import pytest

from boidrytwin.properties import water

M_W = 0.018015
M_AIR = 0.028965


@pytest.mark.parametrize(
    ("T", "p_expected"),
    [
        (273.16, 611.657),
        (300.0, 3536.58941),  # IF97 verification table
        (373.15, 101_418.0),
        (500.0, 2_638_897.76),  # IF97 verification table
    ],
)
def test_saturation_pressure(T: float, p_expected: float) -> None:
    assert water.p_sat(T) == pytest.approx(p_expected, rel=1e-4)


def test_saturation_temperature_round_trip() -> None:
    T = np.linspace(273.15, 623.15, 351)
    assert np.max(np.abs(water.T_sat(water.p_sat(T)) - T)) < 1e-6


def test_vectorised() -> None:
    T = np.array([[300.0, 350.0], [400.0, 450.0]])
    assert water.p_sat(T).shape == (2, 2)


def test_latent_heat() -> None:
    assert water.latent_heat(373.15) == pytest.approx(2256.5e3, rel=5e-3)
    assert water.latent_heat(293.15) == pytest.approx(2453.5e3, rel=1e-2)


def test_latent_heat_is_vapour_minus_liquid_enthalpy() -> None:
    # consistency needed for energy balance closure in the dryer model
    T = np.array([290.0, 330.0, 370.0])
    assert water.latent_heat(T) == pytest.approx(water.h_vapour(T) - water.h_liquid(T), rel=1e-12)


def test_humidity_partial_pressure_round_trip_with_air() -> None:
    Y = 0.05
    p_w = water.partial_pressure_from_humidity(Y, 101_325.0, M_AIR)
    assert p_w == pytest.approx(101_325.0 * Y / (Y + M_W / M_AIR))
    assert water.humidity_from_partial_pressure(p_w, 101_325.0, M_AIR) == pytest.approx(Y)


def test_humidity_uses_actual_dry_gas_molar_mass() -> None:
    # a CO2-rich dry flue gas is heavier than air: same humidity gives a lower partial pressure
    m_flue = 0.0305
    p_air = water.partial_pressure_from_humidity(0.1, 101_325.0, M_AIR)
    p_flue = water.partial_pressure_from_humidity(0.1, 101_325.0, m_flue)
    assert p_flue > p_air  # more moles of water relative to fewer moles of heavy dry gas
    assert p_flue == pytest.approx(101_325.0 * 0.1 / (0.1 + M_W / m_flue))


def test_dew_point() -> None:
    p_w = water.p_sat(330.0)
    Y = water.humidity_from_partial_pressure(p_w, 101_325.0, M_AIR)
    assert water.dew_point(Y, 101_325.0, M_AIR) == pytest.approx(330.0, abs=1e-6)


@pytest.mark.oracle
def test_saturation_pressure_against_coolprop() -> None:
    from CoolProp.CoolProp import PropsSI

    T = np.arange(274.0, 620.0, 1.0)
    ref = np.array([PropsSI("P", "T", t, "Q", 0, "Water") for t in T])
    assert np.max(np.abs(water.p_sat(T) / ref - 1)) < 1e-3
