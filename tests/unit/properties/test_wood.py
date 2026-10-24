"""Wood chip properties (T034; Wood Handbook 2021, ch. 4)."""

import numpy as np
import pytest

from boidrytwin.properties import wood


@pytest.mark.parametrize(
    ("T_c", "rh", "emc_percent"),
    [
        (21.1, 0.50, 9.2),  # Wood Handbook Table 4-2, 70 °F
        (21.1, 0.90, 20.5),
        (20.0, 0.65, 12.0),
    ],
)
def test_emc_against_handbook_table(T_c: float, rh: float, emc_percent: float) -> None:
    assert wood.emc(T_c + 273.15, rh) * 100 == pytest.approx(emc_percent, abs=0.15)


def test_emc_decreases_with_temperature_and_is_zero_for_dry_gas() -> None:
    assert wood.emc(353.15, 0.3) < wood.emc(293.15, 0.3)
    assert wood.emc(353.15, 0.0) == pytest.approx(0.0, abs=1e-12)


def test_emc_clipped_above_data_limit() -> None:
    assert wood.emc(450.0, 0.2) == pytest.approx(wood.emc(wood.EMC_DATA_LIMIT, 0.2))
    assert bool(wood.emc_extrapolated(450.0))
    assert not bool(wood.emc_extrapolated(390.0))


def test_emc_vectorised() -> None:
    assert wood.emc(np.array([300.0, 320.0]), np.array([0.5, 0.4])).shape == (2,)


def test_dry_heat_capacity() -> None:
    # Eq. 4-18a: c_p0 = 0.1031 + 0.003867 T (kJ/kg K)
    assert wood.cp_dry(300.0) == pytest.approx((0.1031 + 0.003867 * 300.0) * 1000)


def test_moist_heat_capacity_below_fibre_saturation() -> None:
    T, X = 320.0, 0.20
    x = 20.0
    ac = x * (-0.06191 + 2.36e-4 * T - 1.33e-4 * x)
    expected = ((0.1031 + 0.003867 * T + 4.18 * x / 100) / (1 + x / 100) + ac) * 1000
    assert wood.cp_moist(T, X) == pytest.approx(expected)


def test_moist_heat_capacity_rule_of_mixtures_above_fibre_saturation() -> None:
    T, X = 320.0, 0.80
    at_fsp = wood.cp_moist(T, 0.30)
    expected = (1.30 * at_fsp + 0.50 * 4180.0) / 1.80
    assert wood.cp_moist(T, X) == pytest.approx(expected)


@pytest.mark.parametrize("X", [0.0, 0.1, 0.3, 0.9])
def test_enthalpy_derivative_is_heat_capacity(X: float) -> None:
    T, dT = 330.0, 1e-3
    dh = (wood.enthalpy_per_kg_dry(T + dT, X) - wood.enthalpy_per_kg_dry(T - dT, X)) / (2 * dT)
    assert dh == pytest.approx((1 + X) * wood.cp_moist(T, X), rel=1e-6)


def test_enthalpy_coefficients_reproduce_enthalpy() -> None:
    X = np.array([0.05, 0.25, 1.0])
    a2, a1, a0 = wood.enthalpy_coefficients(X)
    T = 345.0
    assert a2 * T**2 + a1 * T + a0 == pytest.approx(wood.enthalpy_per_kg_dry(T, X))


def test_sorption_heat_vanishes_at_fibre_saturation() -> None:
    assert wood.sorption_heat(0.30) == pytest.approx(0.0)
    assert wood.sorption_heat(0.50) == 0.0
    assert wood.sorption_heat(0.0) == pytest.approx(wood.SORPTION_HEAT_DRY)
    assert wood.sorption_heat(0.1) > wood.sorption_heat(0.2) > 0.0


def test_bound_water_energy_matches_sorption_heat() -> None:
    # removing bound water lowers the enthalpy by exactly the sorption heat (dB/dX = -dh_s)
    X, dX = 0.15, 1e-6
    b = (wood.bound_water_energy(X - dX) - wood.bound_water_energy(X + dX)) / (2 * dX)
    assert b == pytest.approx(wood.sorption_heat(X), rel=1e-6)


def test_basis_conversion() -> None:
    assert wood.wet_to_dry(0.5) == pytest.approx(1.0)
    assert wood.dry_to_wet(1.0) == pytest.approx(0.5)
    assert wood.dry_to_wet(wood.wet_to_dry(0.15)) == pytest.approx(0.15)
