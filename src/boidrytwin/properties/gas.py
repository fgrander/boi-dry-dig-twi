"""Ideal-gas properties of flue gas mixtures (research.md R6).

Species order everywhere: N2, O2, CO2, H2O, AR ("other" components are represented by Ar).
All functions are vectorised: temperatures broadcast against the last axis (species) of
composition arrays. SI units throughout (K, J, kg, mol, Pa·s, W/(m·K)).

Sources:
- Thermodynamics: NASA 7-coefficient polynomials of the GRI-Mech 3.0 data set as shipped
  with Cantera 3.2 (``gri30.yaml``), two ranges split at 1000 K. N2 and Ar are tabulated
  from 300 K; the polynomial is used down to 273.15 K (smooth extrapolation).
- Transport: per-species fits ln(prop) = sum_n a_n (ln T)^n, n = 0..4, made for this project
  to Cantera 3.2 ``gri30.yaml`` pure-species mixture-averaged transport at 1 atm over
  250-1600 K (max fit error 1 %). Mixture viscosity by Wilke (1950); mixture conductivity by
  the combination average 0.5 (sum x k + 1 / sum(x / k)) used by Cantera.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]

SPECIES: tuple[str, ...] = ("N2", "O2", "CO2", "H2O", "AR")
N_SPECIES = len(SPECIES)
I_N2, I_O2, I_CO2, I_H2O, I_AR = range(N_SPECIES)

R_UNIVERSAL = 8.314462618  # J/(mol K)
T_REF = 298.15  # K, reference temperature of sensible enthalpy
T_MID = 1000.0  # K, polynomial range split

MOLAR_MASS: FloatArray = np.array([28.014, 31.998, 44.009, 18.015, 39.95]) * 1e-3  # kg/mol

# NASA-7 coefficients a1..a7, gri30.yaml (Cantera 3.2)
_NASA_LOW: FloatArray = np.array(
    [
        [3.298677, 1.4082404e-03, -3.963222e-06, 5.641515e-09, -2.444854e-12, -1020.8999, 3.950372],
        [3.78245636, -2.99673416e-03, 9.84730201e-06, -9.68129509e-09, 3.24372837e-12,
         -1063.94356, 3.65767573],
        [2.35677352, 8.98459677e-03, -7.12356269e-06, 2.45919022e-09, -1.43699548e-13,
         -48371.9697, 9.90105222],
        [4.19864056, -2.0364341e-03, 6.52040211e-06, -5.48797062e-09, 1.77197817e-12,
         -30293.7267, -0.849032208],
        [2.5, 0.0, 0.0, 0.0, 0.0, -745.375, 4.366],
    ]
)  # fmt: skip
_NASA_HIGH: FloatArray = np.array(
    [
        [2.92664, 1.4879768e-03, -5.68476e-07, 1.0097038e-10, -6.753351e-15, -922.7977, 5.980528],
        [3.28253784, 1.48308754e-03, -7.57966669e-07, 2.09470555e-10, -2.16717794e-14,
         -1088.45772, 5.45323129],
        [3.85746029, 4.41437026e-03, -2.21481404e-06, 5.23490188e-10, -4.72084164e-14,
         -48759.166, 2.27163806],
        [3.03399249, 2.17691804e-03, -1.64072518e-07, -9.7041987e-11, 1.68200992e-14,
         -30004.2971, 4.9667701],
        [2.5, 0.0, 0.0, 0.0, 0.0, -745.375, 4.366],
    ]
)  # fmt: skip

# ln(mu / Pa s) and ln(k / W m-1 K-1) as quartic polynomials in ln(T / K), a0..a4
_MU_FIT: FloatArray = np.array(
    [
        [-29.480361191, 8.6510156009, -1.6144555293, 0.1451575592, -0.0049092783695],
        [-31.044796671, 9.5247450431, -1.7832556332, 0.15977189687, -0.0053879353437],
        [-32.754517408, 8.9926483615, -1.4329067221, 0.10938277376, -0.0031389151927],
        [11.580462264, -15.885932216, 3.6417847406, -0.34091830789, 0.011650826682],
        [-35.19281816, 11.67510511, -2.1907466089, 0.19449102335, -0.0065113345028],
    ]
)
_K_FIT: FloatArray = np.array(
    [
        [-4.5840004204, 0.13940624688, -0.19250152821, 0.052921392135, -0.0032135848913],
        [76.229074895, -50.556319629, 11.634191751, -1.1632877554, 0.043340830411],
        [41.17485949, -32.714741278, 8.1276292928, -0.84804588018, 0.032431702381],
        [-164.09779968, 97.90166895, -22.744396762, 2.3678910283, -0.092025462995],
        [-30.946766857, 13.150315312, -2.527911531, 0.22864748674, -0.0078054632277],
    ]
)


def _coeffs(T: FloatArray) -> FloatArray:
    """NASA coefficients per temperature, shape T.shape + (species, 7)."""
    low = (T < T_MID)[..., None, None]
    return np.where(low, _NASA_LOW, _NASA_HIGH)


def cp_molar(T: ArrayLike) -> FloatArray:
    """Species molar heat capacity, J/(mol K), shape T.shape + (5,)."""
    t = np.asarray(T, dtype=float)[..., None]
    a = _coeffs(np.asarray(T, dtype=float))
    poly = a[..., 0] + t * (a[..., 1] + t * (a[..., 2] + t * (a[..., 3] + t * a[..., 4])))
    return np.asarray(R_UNIVERSAL * poly)


def h_molar(T: ArrayLike) -> FloatArray:
    """Species standard molar enthalpy incl. formation, J/mol, shape T.shape + (5,)."""
    t = np.asarray(T, dtype=float)[..., None]
    a = _coeffs(np.asarray(T, dtype=float))
    poly = (
        a[..., 0]
        + t * (a[..., 1] / 2 + t * (a[..., 2] / 3 + t * (a[..., 3] / 4 + t * a[..., 4] / 5)))
        + a[..., 5] / t
    )
    return np.asarray(R_UNIVERSAL * t * poly)


_H_REF = h_molar(T_REF)


def h_sensible_species_mass(T: ArrayLike) -> FloatArray:
    """Species sensible enthalpy h(T) - h(298.15 K), J/kg, shape T.shape + (5,)."""
    return np.asarray((h_molar(T) - _H_REF) / MOLAR_MASS)


def cp_species_mass(T: ArrayLike) -> FloatArray:
    """Species specific heat capacity, J/(kg K), shape T.shape + (5,)."""
    return np.asarray(cp_molar(T) / MOLAR_MASS)


def mass_fractions(x: ArrayLike) -> FloatArray:
    """Convert mole fractions to mass fractions (last axis = species)."""
    xm = np.asarray(x, dtype=float) * MOLAR_MASS
    return np.asarray(xm / xm.sum(axis=-1, keepdims=True))


def mole_fractions(y: ArrayLike) -> FloatArray:
    """Convert mass fractions to mole fractions (last axis = species)."""
    ym = np.asarray(y, dtype=float) / MOLAR_MASS
    return np.asarray(ym / ym.sum(axis=-1, keepdims=True))


def molar_mass_mixture(x: ArrayLike) -> FloatArray:
    """Mean molar mass of a mixture given as mole fractions, kg/mol."""
    return np.asarray(np.sum(np.asarray(x, dtype=float) * MOLAR_MASS, axis=-1))


def cp_mass(T: ArrayLike, y: ArrayLike) -> FloatArray:
    """Mixture specific heat capacity, J/(kg K), from mass fractions."""
    return np.asarray(np.sum(np.asarray(y, dtype=float) * cp_species_mass(T), axis=-1))


def h_sensible_mass(T: ArrayLike, y: ArrayLike) -> FloatArray:
    """Mixture sensible enthalpy relative to 298.15 K, J/kg, from mass fractions."""
    return np.asarray(np.sum(np.asarray(y, dtype=float) * h_sensible_species_mass(T), axis=-1))


def _transport_species(T: ArrayLike, fit: FloatArray) -> FloatArray:
    lt = np.log(np.asarray(T, dtype=float))[..., None]
    ln_prop = fit[:, 0] + lt * (fit[:, 1] + lt * (fit[:, 2] + lt * (fit[:, 3] + lt * fit[:, 4])))
    return np.asarray(np.exp(ln_prop))


def viscosity(T: ArrayLike, x: ArrayLike) -> FloatArray:
    """Mixture dynamic viscosity, Pa s, from mole fractions (Wilke mixing rule)."""
    mu = _transport_species(T, _MU_FIT)  # (..., 5)
    xs = np.asarray(x, dtype=float)
    mu, xs = np.broadcast_arrays(mu, xs)
    m_ratio = MOLAR_MASS[None, :] / MOLAR_MASS[:, None]  # Mj / Mi
    phi = (1.0 + np.sqrt(mu[..., :, None] / mu[..., None, :]) * m_ratio**0.25) ** 2 / np.sqrt(
        8.0 * (1.0 + 1.0 / m_ratio)
    )
    denom = np.einsum("...j,...ij->...i", xs, phi)
    return np.asarray(np.sum(xs * mu / denom, axis=-1))


def conductivity(T: ArrayLike, x: ArrayLike) -> FloatArray:
    """Mixture thermal conductivity, W/(m K), from mole fractions (combination average)."""
    k = _transport_species(T, _K_FIT)
    xs = np.asarray(x, dtype=float)
    k, xs = np.broadcast_arrays(k, xs)
    return np.asarray(0.5 * (np.sum(xs * k, axis=-1) + 1.0 / np.sum(xs / k, axis=-1)))
