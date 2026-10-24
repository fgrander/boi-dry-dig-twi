"""Thermal oil heater heat transfer (T015; research.md R5, R6)."""

import math

import numpy as np
import pytest

from boidrytwin.boiler_house import heaters
from boidrytwin.properties import gas
from boidrytwin.properties.thermal_oil import get_oil

FLUE_Y = gas.mass_fractions(np.array([0.70, 0.07, 0.11, 0.11, 0.01]))


def test_quasi_static_cell_is_exact_and_conservative() -> None:
    T_out, q = heaters.gas_cell(T_in=1000.0, T_wall=560.0, mass_flow=9.0, y=FLUE_Y, UA=2000.0)
    cp = float(gas.cp_mass(1000.0, FLUE_Y))
    assert T_out == pytest.approx(560.0 + 440.0 * math.exp(-2000.0 / (9.0 * cp)), rel=1e-12)
    dh = gas.h_sensible_mass(1000.0, FLUE_Y) - gas.h_sensible_mass(T_out, FLUE_Y)
    assert q == pytest.approx(9.0 * float(dh), rel=1e-12)  # energy exactly from enthalpies
    _, q0 = heaters.gas_cell(1000.0, 560.0, 0.0, FLUE_Y, 2000.0)
    assert q0 == 0.0  # no flow, no heat


ZUKAUSKAS_CASES = [(5e3, 0.35 * 1.2**0.2, 0.6), (5e4, 0.35 * 1.2**0.2, 0.6), (3e5, 0.022, 0.84)]


@pytest.mark.parametrize(("re", "c", "m"), ZUKAUSKAS_CASES)
def test_zukauskas_staggered(re: float, c: float, m: float) -> None:
    # Zukauskas staggered banks (Incropera Table 7.5), pitch ratio S_t/S_l = 1.2
    nu = heaters.nu_zukauskas_staggered(re, 0.7, pitch_ratio=1.2)
    assert nu == pytest.approx(c * re**m * 0.7**0.36, rel=1e-12)


def test_gnielinski_oil_side_with_laminar_blend() -> None:
    assert heaters.nu_tube(1000.0, 10.0) == pytest.approx(3.66)
    re, pr = 1e5, 10.0
    xi = (1.8 * math.log10(re) - 1.5) ** -2
    gn = (xi / 8) * (re - 1000) * pr / (1 + 12.7 * math.sqrt(xi / 8) * (pr ** (2 / 3) - 1))
    assert heaters.nu_tube(re, pr) == pytest.approx(gn, rel=1e-12)
    mid = heaters.nu_tube(6150.0, pr)  # halfway through the 2300-1e4 blend
    assert heaters.nu_tube(2300.0, pr) < mid < heaters.nu_tube(1e4, pr)


def test_fouling_in_series() -> None:
    assert heaters.overall_gas_side(60.0, 0.008) == pytest.approx(1 / (1 / 60.0 + 0.008))


def test_counter_current_upwind_inflow() -> None:
    h_cells = np.array([10.0, 20.0, 30.0])
    upstream = heaters.oil_upstream(h_cells, h_return=5.0)
    # oil enters the last cell and flows towards cell 0
    assert upstream.tolist() == [20.0, 30.0, 5.0]


def test_film_temperature() -> None:
    oil = get_oil("shell_s2")
    T_film = heaters.film_temperature(
        T_oil=550.0, heat_flux_avg=30e3, peak_factor=1.727, h_inner=1500.0
    )
    assert T_film == pytest.approx(550.0 + 30e3 * 1.727 / 1500.0)
    assert T_film < oil.max_film_temperature


def test_oil_velocity_and_reynolds() -> None:
    oil = get_oil("shell_s2")
    v, re = heaters.oil_flow(mass_flow=60.0, T=540.0, oil=oil, inner_diameter=0.1, passes=4)
    assert v == pytest.approx(60.0 / (oil.density(540.0) * 4 * math.pi * 0.01 / 4))
    assert re > 1e4
