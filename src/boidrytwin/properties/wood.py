"""Wood chip properties (research.md R4).

Source: Glass, S.V. & Zelinka, S.L. (2021), *Wood Handbook*, FPL-GTR-282, ch. 4 (open access).

Moisture content X is on a **dry basis** (kg water / kg dry wood) throughout; inputs and
outputs use the wet basis w = X / (1 + X), converted at the boundary.

Enthalpy of moist wood, per kg dry wood, relative to 298.15 K:

    e(T, X) = h_dry(T) + A(T, X) + X h_liquid(T) - B(X)

- h_dry: integral of the dry heat capacity Eq. 4-18a;
- A: integral of the bound-water correction Ac of Eq. 4-20 (moisture capped at fibre
  saturation, rule of mixtures above it), so that de/dT = (1 + X) c_p,moist(T, X);
- h_liquid: liquid water enthalpy from :mod:`boidrytwin.properties.water`;
- B: energy of bound water, the integral of the sorption heat from X to fibre saturation, so
  that removing bound water costs latent heat plus sorption heat.

The sorption heat uses the quadratic form dh_s = dh_0 (1 - X / X_fsp)^2 below fibre
saturation, which vanishes at saturation (research.md R4 fallback). dh_0 = 1.0 MJ/kg is a
literature-typical value. VERIFY(Skaar 1988, Wood-Water Relations) before calibration.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from boidrytwin.properties import water
from boidrytwin.properties.gas import FloatArray

EMC_DATA_LIMIT = 403.15  # K: the Hailwood-Horrobin fit is data-backed to about 130 °C
FIBRE_SATURATION = 0.30  # kg/kg dry, default
SORPTION_HEAT_DRY = 1.0e6  # J/kg water at X = 0. VERIFY(Skaar 1988)
T_REF = 298.15

# Eq. 4-18a: c_p0 = A0 + A1 T, kJ/(kg K), T in K
_CP0_A0, _CP0_A1 = 0.1031, 0.003867
# Eq. 4-20: Ac = x (b1 + b2 T + b3 x), x in %, T in K, kJ/(kg K)
_B1, _B2, _B3 = -0.06191, 2.36e-4, -1.33e-4
_CP_WATER_HANDBOOK = 4.18  # kJ/(kg K) in Eq. 4-19


def wet_to_dry(w: ArrayLike) -> FloatArray:
    """Moisture content: wet basis → dry basis."""
    wa = np.asarray(w, dtype=float)
    return np.asarray(wa / (1.0 - wa))


def dry_to_wet(X: ArrayLike) -> FloatArray:
    """Moisture content: dry basis → wet basis."""
    xa = np.asarray(X, dtype=float)
    return np.asarray(xa / (1.0 + xa))


def emc(T: ArrayLike, rh: ArrayLike) -> FloatArray:
    """Equilibrium moisture content (dry basis) by Hailwood-Horrobin, Eq. 4-5.

    Temperatures above :data:`EMC_DATA_LIMIT` are clipped to it (see :func:`emc_extrapolated`).
    """
    tc = np.minimum(np.asarray(T, dtype=float), EMC_DATA_LIMIT) - 273.15
    h = np.clip(np.asarray(rh, dtype=float), 0.0, 0.999)
    w = 349.0 + 1.29 * tc + 0.0135 * tc**2
    k = 0.805 + 0.000736 * tc - 0.00000273 * tc**2
    k1 = 6.27 - 0.00938 * tc - 0.000303 * tc**2
    k2 = 1.91 + 0.0407 * tc - 0.000293 * tc**2
    kh = k * h
    percent = (1800.0 / w) * (
        kh / (1.0 - kh) + (k1 * kh + 2.0 * k1 * k2 * kh**2) / (1.0 + k1 * kh + k1 * k2 * kh**2)
    )
    return np.asarray(percent / 100.0)


def emc_extrapolated(T: ArrayLike) -> NDArrayBool:
    """True where the temperature lies above the EMC data range."""
    return np.asarray(np.asarray(T, dtype=float) > EMC_DATA_LIMIT)


NDArrayBool = np.ndarray


def cp_dry(T: ArrayLike) -> FloatArray:
    """Heat capacity of dry wood, J/(kg K), Eq. 4-18a."""
    return np.asarray((_CP0_A0 + _CP0_A1 * np.asarray(T, dtype=float)) * 1000.0)


def h_dry(T: ArrayLike) -> FloatArray:
    """Sensible enthalpy of dry wood (no water, no bound-water term), J/kg, relative to 298.15 K."""
    t = np.asarray(T, dtype=float)
    return np.asarray(1000.0 * (_CP0_A0 * (t - T_REF) + _CP0_A1 / 2.0 * (t**2 - T_REF**2)))


def _bound(X: ArrayLike, X_fsp: float) -> tuple[FloatArray, FloatArray]:
    xa = np.asarray(X, dtype=float)
    xb = np.minimum(xa, X_fsp)
    return xa, xb


def cp_moist(T: ArrayLike, X: ArrayLike, X_fsp: float = FIBRE_SATURATION) -> FloatArray:
    """Heat capacity of moist wood per kg of moist wood, J/(kg K), Eq. 4-19/4-20.

    Below fibre saturation as in the handbook; above it the free water is added by the rule
    of mixtures.
    """
    t = np.asarray(T, dtype=float)
    xa, xb = _bound(X, X_fsp)
    x = 100.0 * xb
    ac = x * (_B1 + _B2 * t + _B3 * x)
    cp_b = (_CP0_A0 + _CP0_A1 * t + _CP_WATER_HANDBOOK * xb) / (1.0 + xb) + ac  # kJ/(kg K)
    total = ((1.0 + xb) * cp_b * 1000.0 + (xa - xb) * water.CP_LIQUID) / (1.0 + xa)
    return np.asarray(total)


def sorption_heat(X: ArrayLike, X_fsp: float = FIBRE_SATURATION) -> FloatArray:
    """Differential heat of sorption, J/kg water, zero at and above fibre saturation."""
    xa = np.asarray(X, dtype=float)
    return np.asarray(np.where(xa < X_fsp, SORPTION_HEAT_DRY * (1.0 - xa / X_fsp) ** 2, 0.0))


def bound_water_energy(X: ArrayLike, X_fsp: float = FIBRE_SATURATION) -> FloatArray:
    """B(X) = integral of the sorption heat from X to fibre saturation, J/kg dry wood."""
    xa = np.minimum(np.maximum(np.asarray(X, dtype=float), 0.0), X_fsp)
    return np.asarray(SORPTION_HEAT_DRY * X_fsp / 3.0 * (1.0 - xa / X_fsp) ** 3)


def enthalpy_coefficients(
    X: ArrayLike, X_fsp: float = FIBRE_SATURATION
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Coefficients (a2, a1, a0) with e(T, X) = a2 T² + a1 T + a0, J/kg dry wood.

    The enthalpy is quadratic in T, so a solids temperature can be recovered from an
    enthalpy analytically (see :mod:`boidrytwin.dryer.model`).
    """
    xa, xb = _bound(X, X_fsp)
    x = 100.0 * xb
    f = (1.0 + xb) * x  # Ac per kg moist wood -> per kg dry wood
    # h_dry = 1000 [A0 (T - Tr) + A1/2 (T² - Tr²)]
    # A = 1000 f [b1 (T - Tr) + b2/2 (T² - Tr²) + b3 x (T - Tr)]
    a2 = 1000.0 * (_CP0_A1 / 2.0 + f * _B2 / 2.0)
    lin = 1000.0 * (_CP0_A0 + f * (_B1 + _B3 * x))
    a0_wood = -lin * T_REF - a2 * T_REF**2
    # X h_liquid(T) = X (c_l T + h_l(0))
    h_l0 = float(water.h_liquid(0.0))
    a1 = lin + xa * water.CP_LIQUID
    a0 = a0_wood + xa * h_l0 - bound_water_energy(xa, X_fsp)
    return np.asarray(a2), np.asarray(a1), np.asarray(a0)


def enthalpy_per_kg_dry(T: ArrayLike, X: ArrayLike, X_fsp: float = FIBRE_SATURATION) -> FloatArray:
    """Enthalpy of moist wood, J per kg dry wood, relative to 298.15 K (see module doc)."""
    a2, a1, a0 = enthalpy_coefficients(X, X_fsp)
    t = np.asarray(T, dtype=float)
    return np.asarray(a2 * t**2 + a1 * t + a0)
