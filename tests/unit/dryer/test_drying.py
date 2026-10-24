"""Characteristic drying curve (T039; research.md R4)."""

import numpy as np
import pytest

from boidrytwin.dryer import drying
from boidrytwin.properties import water

M_AIR = 0.028965


def test_constant_rate_proportional_to_humidity_difference() -> None:
    e1, _ = drying.evaporation(10.0, np.array([0.3]), np.array([0.1]), np.array([1.0]))
    e2, _ = drying.evaporation(10.0, np.array([0.5]), np.array([0.1]), np.array([1.0]))
    assert e1[0] == pytest.approx(2.0)
    assert e2[0] == pytest.approx(2 * e1[0])


def test_falling_rate_factor() -> None:
    X_e, X_cr, n = 0.05, 0.8, 2.0
    assert drying.rate_factor(1.2, X_e, X_cr, n) == 1.0
    assert drying.rate_factor(X_cr, X_e, X_cr, n) == pytest.approx(1.0)
    phi = (0.4 - X_e) / (X_cr - X_e)
    assert drying.rate_factor(0.4, X_e, X_cr, n) == pytest.approx(phi**n)
    assert drying.rate_factor(X_e, X_e, X_cr, n) == pytest.approx(0.0)
    assert drying.rate_factor(0.01, X_e, X_cr, n) == 0.0


def test_rate_factor_continuous_at_critical_moisture() -> None:
    eps = 1e-9
    below = drying.rate_factor(0.8 - eps, 0.05, 0.8, 1.5)
    above = drying.rate_factor(0.8 + eps, 0.05, 0.8, 1.5)
    assert below == pytest.approx(above, abs=1e-6)


def test_no_condensation_onto_solids() -> None:
    e, condensing = drying.evaporation(
        10.0, np.array([0.05, 0.3]), np.array([0.1, 0.1]), np.array([1.0, 1.0])
    )
    assert e[0] == 0.0 and bool(condensing[0])
    assert e[1] > 0 and not bool(condensing[1])


def test_saturation_humidity() -> None:
    T = 330.0
    p_s = water.p_sat(T)
    expected = water.humidity_from_partial_pressure(p_s, 101_325.0, M_AIR)
    assert drying.saturation_humidity(T, 101_325.0, M_AIR) == pytest.approx(expected)


def test_saturation_humidity_bounded_near_boiling() -> None:
    y = drying.saturation_humidity(np.array([372.0, 380.0, 450.0]), 101_325.0, M_AIR)
    assert np.all(np.isfinite(y))
    assert y[1] == pytest.approx(y[2])  # clipped at 0.95 p
