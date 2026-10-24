"""Bypass split and mixing (T016; research.md R7)."""

import numpy as np
import pytest

from boidrytwin.boiler_house import bypass
from boidrytwin.properties import gas

Y = gas.mass_fractions(np.array([0.70, 0.07, 0.11, 0.11, 0.01]))


def test_split() -> None:
    assert bypass.split_flow(10.0, 0.0) == (10.0, 0.0)
    assert bypass.split_flow(10.0, 1.0) == (0.0, 10.0)
    assert bypass.split_flow(10.0, 0.25) == (7.5, 2.5)


def test_mixing_conserves_mass_and_enthalpy() -> None:
    m, T = bypass.mix(m_heaters=7.0, T_heaters=600.0, m_bypass=3.0, T_bypass=1100.0, y=Y)
    assert m == 10.0
    h_mix = gas.h_sensible_mass(T, Y)
    expected = (7.0 * gas.h_sensible_mass(600.0, Y) + 3.0 * gas.h_sensible_mass(1100.0, Y)) / 10.0
    assert float(h_mix) == pytest.approx(float(expected), rel=1e-10)
    assert 600.0 < T < 1100.0


def test_mixing_limits() -> None:
    assert bypass.mix(5.0, 700.0, 0.0, 1200.0, Y)[1] == pytest.approx(700.0, abs=1e-8)
    assert bypass.mix(0.0, 700.0, 5.0, 1200.0, Y)[1] == pytest.approx(1200.0, abs=1e-8)
