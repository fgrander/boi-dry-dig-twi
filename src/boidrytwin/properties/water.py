"""Water: saturation, latent heat, humidity and dew point (research.md R6).

- Saturation line: IAPWS-IF97 region 4 (IAPWS 2007), explicit in both directions,
  valid 273.15-647.096 K.
- Vapour enthalpy: ideal-gas H2O from :mod:`boidrytwin.properties.gas` (sensible, 298.15 K
  reference).
- Liquid enthalpy: constant c_p = 4180 J/(kg K), anchored so that the latent heat at
  373.15 K is 2256.47 kJ/kg. The latent heat is defined as h_vapour - h_liquid, so the
  dryer energy balance stays exactly consistent (error vs. steam tables < 1 % at 20-100 °C).
- Humidity Y is kg water per kg dry gas, with the *actual* dry-gas molar mass (no 0.622).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

from boidrytwin.properties import gas

FloatArray = NDArray[np.float64]

M_WATER = float(gas.MOLAR_MASS[gas.I_H2O])  # kg/mol
CP_LIQUID = 4180.0  # J/(kg K)
T_BOIL = 373.15  # K
LATENT_HEAT_BOIL = 2256.47e3  # J/kg at 373.15 K

# IAPWS-IF97 region 4 coefficients n1..n10
_N = (
    0.11670521452767e4,
    -0.72421316703206e6,
    -0.17073846940092e2,
    0.12020824702470e5,
    -0.32325550322333e7,
    0.14915108613530e2,
    -0.48232657361591e4,
    0.40511340542057e6,
    -0.23855557567849,
    0.65017534844798e3,
)


def p_sat(T: ArrayLike) -> FloatArray:
    """Saturation pressure of water, Pa (IF97 region 4)."""
    n1, n2, n3, n4, n5, n6, n7, n8, n9, n10 = _N
    t = np.asarray(T, dtype=float)
    theta = t + n9 / (t - n10)
    a = theta**2 + n1 * theta + n2
    b = n3 * theta**2 + n4 * theta + n5
    c = n6 * theta**2 + n7 * theta + n8
    return np.asarray((2 * c / (-b + np.sqrt(b**2 - 4 * a * c))) ** 4 * 1e6)


def T_sat(p: ArrayLike) -> FloatArray:
    """Saturation temperature of water, K, for a pressure in Pa (IF97 region 4)."""
    n1, n2, n3, n4, n5, n6, n7, n8, n9, n10 = _N
    beta = (np.asarray(p, dtype=float) / 1e6) ** 0.25
    e = beta**2 + n3 * beta + n6
    f = n1 * beta**2 + n4 * beta + n7
    g = n2 * beta**2 + n5 * beta + n8
    d = 2 * g / (-f - np.sqrt(f**2 - 4 * e * g))
    return np.asarray((n10 + d - np.sqrt((n10 + d) ** 2 - 4 * (n9 + n10 * d))) / 2)


def h_vapour(T: ArrayLike) -> FloatArray:
    """Specific enthalpy of water vapour (ideal gas), J/kg, relative to 298.15 K."""
    return np.asarray(gas.h_sensible_species_mass(T)[..., gas.I_H2O])


_H_VAP_BOIL = float(h_vapour(T_BOIL))


def h_liquid(T: ArrayLike) -> FloatArray:
    """Specific enthalpy of liquid water, J/kg, on the same reference as :func:`h_vapour`."""
    t = np.asarray(T, dtype=float)
    return np.asarray(_H_VAP_BOIL - LATENT_HEAT_BOIL + CP_LIQUID * (t - T_BOIL))


def latent_heat(T: ArrayLike) -> FloatArray:
    """Latent heat of evaporation of free water, J/kg."""
    return np.asarray(h_vapour(T) - h_liquid(T))


def partial_pressure_from_humidity(Y: ArrayLike, p: ArrayLike, M_dry: ArrayLike) -> FloatArray:
    """Water vapour partial pressure, Pa, from humidity Y (kg/kg dry gas)."""
    y = np.asarray(Y, dtype=float)
    return np.asarray(np.asarray(p, dtype=float) * y / (y + M_WATER / np.asarray(M_dry)))


def humidity_from_partial_pressure(p_w: ArrayLike, p: ArrayLike, M_dry: ArrayLike) -> FloatArray:
    """Humidity Y (kg water / kg dry gas) from the water vapour partial pressure, Pa."""
    pw = np.asarray(p_w, dtype=float)
    return np.asarray(M_WATER / np.asarray(M_dry) * pw / (np.asarray(p, dtype=float) - pw))


def dew_point(Y: ArrayLike, p: ArrayLike, M_dry: ArrayLike) -> FloatArray:
    """Dew point temperature, K, of a gas with humidity Y (kg/kg dry gas)."""
    return T_sat(partial_pressure_from_humidity(Y, p, M_dry))
