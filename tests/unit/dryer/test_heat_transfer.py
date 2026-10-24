"""Heat and mass transfer correlations (T038; research.md R3, R5)."""

import math

import numpy as np
import pytest

from boidrytwin.dryer import heat_transfer as ht


def test_gnielinski_sphere_limit() -> None:
    assert ht.nu_sphere_gnielinski(1e-8, 0.7) == pytest.approx(2.0, abs=1e-3)


@pytest.mark.parametrize("re", [10.0, 100.0, 1000.0])
def test_ranz_marshall_close_to_gnielinski(re: float) -> None:
    g = ht.nu_sphere_gnielinski(re, 0.7)
    r = ht.nu_sphere_ranz_marshall(re, 0.7)
    assert abs(r / g - 1) < 0.2


def test_churchill_chu_published_value() -> None:
    # Churchill & Chu (1975), horizontal cylinder: Ra = 1e9, Pr = 0.7 → Nu ≈ 115.5
    assert ht.nu_cylinder_churchill_chu(1e9, 0.7) == pytest.approx(115.5, rel=5e-3)


def test_pipe_flow_turbulent_dittus_boelter() -> None:
    assert ht.nu_pipe(1e5, 0.7) == pytest.approx(0.023 * 1e5**0.8 * 0.7**0.4)
    assert ht.nu_pipe(100.0, 0.7) == pytest.approx(3.66)


def test_mass_transfer_coefficient_chilton_colburn() -> None:
    assert ht.mass_transfer_coefficient(50.0, 1100.0) == pytest.approx(50.0 / 1100.0)
    assert ht.mass_transfer_coefficient(50.0, 1100.0, lewis=0.85) == pytest.approx(
        50.0 / 1100.0 * 0.85 ** (-2 / 3)
    )


def test_gas_solid_heat_flow_scales_with_multiplier_and_vanishes_without_difference() -> None:
    hA = np.array([100.0, 200.0])
    q1 = ht.gas_solid_heat(1.0, hA, np.array([600.0, 500.0]), np.array([350.0, 350.0]))
    q2 = ht.gas_solid_heat(2.0, hA, np.array([600.0, 500.0]), np.array([350.0, 350.0]))
    assert q2 == pytest.approx(2 * q1)
    assert ht.gas_solid_heat(1.0, hA, np.array([350.0, 350.0]), np.array([350.0, 350.0])) == (
        pytest.approx([0.0, 0.0])
    )


def test_shell_loss_sign_and_radiation() -> None:
    hot = ht.shell_loss(np.array([400.0]), 283.15, area=10.0, emissivity=0.8, diameter=4.0)
    cold = ht.shell_loss(np.array([270.0]), 283.15, area=10.0, emissivity=0.8, diameter=4.0)
    assert hot[0] > 0 > cold[0]
    no_rad = ht.shell_loss(np.array([400.0]), 283.15, area=10.0, emissivity=0.0, diameter=4.0)
    rad = 0.8 * 5.670374419e-8 * (400.0**4 - 283.15**4) * 10.0
    assert hot[0] - no_rad[0] == pytest.approx(rad, rel=1e-6)


def test_insulation_reduces_loss() -> None:
    bare = ht.shell_loss(np.array([450.0]), 283.15, area=10.0, emissivity=0.8, diameter=4.0)
    ins = ht.shell_loss(
        np.array([450.0]),
        283.15,
        area=10.0,
        emissivity=0.8,
        diameter=4.0,
        insulation_thickness=0.1,
        insulation_conductivity=0.04,
    )
    assert 0 < ins[0] < 0.25 * bare[0]


def test_friedman_marshall_ua_units() -> None:
    # 0.5 G^0.67 / D in Btu/(h ft3 F) with G in lb/(h ft2), D in ft
    G, D = 1.0, 2.0
    g_us = G * 737.338
    expected = 0.5 * g_us**0.67 / (D / 0.3048) * 67.0661
    assert ht.friedman_marshall_ua(G, D) == pytest.approx(expected, rel=1e-4)
    assert math.isfinite(ht.friedman_marshall_ua(0.0, D))
