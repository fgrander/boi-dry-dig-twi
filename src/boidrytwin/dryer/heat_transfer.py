"""Heat and mass transfer correlations (research.md R3, R5).

- Gas-chip convection: Gnielinski single-sphere correlation (VDI Heat Atlas); Ranz &
  Marshall (1952) as a check.
- Mass transfer: Chilton-Colburn analogy k_y = h / c_p,humid · Le^(-2/3); Le = 1 by default
  (Lewis relation for humid gases).
- Gas to shell: pipe flow (Dittus-Boelter, laminar floor Nu = 3.66).
- Shell to ambient: Churchill & Chu (1975) free convection from a horizontal cylinder plus
  grey-body radiation, with optional insulation as a series resistance.
- Friedman & Marshall (1949) volumetric coefficient for plausibility checks only.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from boidrytwin.properties import gas
from boidrytwin.properties.gas import FloatArray

SIGMA = 5.670374419e-8  # W/(m² K⁴)
G_ACCEL = 9.80665
AIR = np.array([0.7808, 0.2095, 0.0004, 0.0, 0.0093])  # mole fractions, gas.SPECIES order


def nu_sphere_gnielinski(Re: ArrayLike, Pr: ArrayLike) -> FloatArray:
    re = np.maximum(np.asarray(Re, dtype=float), 1e-12)
    pr = np.asarray(Pr, dtype=float)
    nu_lam = 0.664 * np.sqrt(re) * pr ** (1.0 / 3.0)
    nu_turb = 0.037 * re**0.8 * pr / (1.0 + 2.443 * re**-0.1 * (pr ** (2.0 / 3.0) - 1.0))
    return np.asarray(2.0 + np.sqrt(nu_lam**2 + nu_turb**2))


def nu_sphere_ranz_marshall(Re: ArrayLike, Pr: ArrayLike) -> FloatArray:
    re = np.asarray(Re, dtype=float)
    return np.asarray(2.0 + 0.6 * np.sqrt(re) * np.asarray(Pr, dtype=float) ** (1.0 / 3.0))


def nu_cylinder_churchill_chu(Ra: ArrayLike, Pr: ArrayLike) -> FloatArray:
    ra = np.maximum(np.asarray(Ra, dtype=float), 0.0)
    pr = np.asarray(Pr, dtype=float)
    return np.asarray(
        (0.60 + 0.387 * ra ** (1.0 / 6.0) / (1.0 + (0.559 / pr) ** (9.0 / 16.0)) ** (8.0 / 27.0))
        ** 2
    )


def nu_pipe(Re: ArrayLike, Pr: ArrayLike) -> FloatArray:
    re = np.asarray(Re, dtype=float)
    turbulent = 0.023 * np.maximum(re, 0.0) ** 0.8 * np.asarray(Pr, dtype=float) ** 0.4
    return np.asarray(np.where(re < 2300.0, 3.66, np.maximum(turbulent, 3.66)))


def mass_transfer_coefficient(h: ArrayLike, cp_humid: ArrayLike, lewis: float = 1.0) -> FloatArray:
    """k_y, kg/(m² s) per unit humidity difference (kg water / kg dry gas)."""
    return np.asarray(np.asarray(h) / np.asarray(cp_humid) * lewis ** (-2.0 / 3.0))


def gas_solid_heat(
    multiplier: float, hA: FloatArray, T_g: FloatArray, T_s: FloatArray
) -> FloatArray:
    """Q from gas to solids, W, per cell."""
    return np.asarray(multiplier * hA * (T_g - T_s))


def shell_loss(
    T_shell: FloatArray,
    T_amb: float,
    *,
    area: float,
    emissivity: float,
    diameter: float,
    insulation_thickness: float = 0.0,
    insulation_conductivity: float = 0.04,
    pressure: float = 101_325.0,
) -> FloatArray:
    """Heat lost from the shell to ambient, W, per cell (positive when shell is hotter)."""
    t = np.asarray(T_shell, dtype=float)
    film = 0.5 * (t + T_amb)
    mu = gas.viscosity(film, AIR)
    k = gas.conductivity(film, AIR)
    y_air = gas.mass_fractions(AIR)
    cp = gas.cp_mass(film, y_air)
    rho = pressure * float(gas.molar_mass_mixture(AIR)) / (gas.R_UNIVERSAL * film)
    nu = mu / rho
    alpha = k / (rho * cp)
    ra = G_ACCEL * (1.0 / film) * np.abs(t - T_amb) * diameter**3 / (nu * alpha)
    h_conv = nu_cylinder_churchill_chu(ra, nu / alpha) * k / diameter
    h_rad = emissivity * SIGMA * (t**2 + T_amb**2) * (t + T_amb)
    h_out = h_conv + h_rad
    resistance = 1.0 / h_out + insulation_thickness / insulation_conductivity
    return np.asarray(area * (t - T_amb) / resistance)


def friedman_marshall_ua(mass_velocity: float, diameter: float) -> float:
    """Friedman & Marshall (1949) Ua = 0.5 G^0.67 / D, converted to W/(m³ K).

    G in kg/(m² s), D in m. US units: Btu/(h ft³ °F), lb/(h ft²), ft. Plausibility check only.
    VERIFY(Friedman & Marshall 1949, Part II).
    """
    g_us = mass_velocity * 737.338
    d_ft = diameter / 0.3048
    return float(0.5 * g_us**0.67 / d_ft * 67.0661)
