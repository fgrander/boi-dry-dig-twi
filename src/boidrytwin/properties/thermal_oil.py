"""Thermal oil properties and limits (research.md R6).

- Shell Heat Transfer Oil S2 (mineral, DIN 51522): linear fits made for this project to the
  "Typical Design Data (calculated)" table of TDS v1.1 (2014-01-27), error ≤ 1 %; kinematic
  viscosity by ASTM D341 (Walther) through the 40/100 °C values. Limits from TDS v1.1/v1.4:
  bulk 300 °C, film 320 °C. VERIFY against the oil actually used in the plant. The older
  Thermia B sheet (2007) gives c_p about 10 % lower (sensitivity case).
- Therminol 66 (Eastman brochure, 2025): fit equations checked against the SI table
  (ρ, c_p, k ≤ 1 %, ν ≤ 3 %). Limits: bulk 345 °C, film 375 °C.

Polynomials are in the Celsius temperature t; enthalpy is relative to 298.15 K.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.polynomial import polynomial as npoly
from numpy.typing import ArrayLike

from boidrytwin.properties.gas import FloatArray

C0 = 273.15
T_REF_C = 25.0


def _walther_s2(T: FloatArray) -> FloatArray:
    loglog = 9.5208 - 3.7474 * np.log10(T)
    return np.asarray((10.0 ** (10.0**loglog) - 0.7) * 1e-6)


def _exp_th66(T: FloatArray) -> FloatArray:
    t = T - C0
    return np.asarray(np.exp(586.375 / (t + 62.5) - 2.2809) * 1e-6)


@dataclass(frozen=True)
class ThermalOil:
    name: str
    rho_poly: tuple[float, ...]  # kg/m³, in t (°C)
    cp_poly: tuple[float, ...]  # J/(kg K), in t
    k_poly: tuple[float, ...]  # W/(m K), in t
    nu_func: Callable[[FloatArray], FloatArray]  # m²/s, of T (K)
    max_bulk_temperature: float  # K
    max_film_temperature: float  # K
    property_range: tuple[float, float]  # K, range of the underlying data
    source: str

    def density(self, T: ArrayLike) -> FloatArray:
        return np.asarray(npoly.polyval(np.asarray(T, dtype=float) - C0, self.rho_poly))

    def cp(self, T: ArrayLike) -> FloatArray:
        return np.asarray(npoly.polyval(np.asarray(T, dtype=float) - C0, self.cp_poly))

    def conductivity(self, T: ArrayLike) -> FloatArray:
        return np.asarray(npoly.polyval(np.asarray(T, dtype=float) - C0, self.k_poly))

    def viscosity(self, T: ArrayLike) -> FloatArray:
        """Kinematic viscosity, m²/s."""
        return self.nu_func(np.asarray(T, dtype=float))

    def dynamic_viscosity(self, T: ArrayLike) -> FloatArray:
        return np.asarray(self.viscosity(T) * self.density(T))

    def prandtl(self, T: ArrayLike) -> FloatArray:
        return np.asarray(self.dynamic_viscosity(T) * self.cp(T) / self.conductivity(T))

    def enthalpy(self, T: ArrayLike) -> FloatArray:
        """Specific enthalpy relative to 298.15 K, J/kg."""
        integ = npoly.polyint(self.cp_poly)
        t = np.asarray(T, dtype=float) - C0
        return np.asarray(npoly.polyval(t, integ) - npoly.polyval(T_REF_C, integ))

    def temperature_from_enthalpy(self, h: ArrayLike) -> FloatArray:
        """Exact inverse of :meth:`enthalpy` (Newton, quadratically convergent)."""
        hh = np.asarray(h, dtype=float)
        T = 298.15 + hh / self.cp_poly[0]
        for _ in range(8):
            T = T - (self.enthalpy(T) - hh) / self.cp(T)
        return np.asarray(T)

    def outside_data_range(self, T: ArrayLike) -> FloatArray:
        lo, hi = self.property_range
        t = np.asarray(T, dtype=float)
        return np.asarray((t < lo) | (t > hi))


OILS: dict[str, ThermalOil] = {
    "shell_s2": ThermalOil(
        name="Shell Heat Transfer Oil S2",
        rho_poly=(870.0, -0.65),
        cp_poly=(1962.0, 4.385),
        k_poly=(0.136, -7.35e-5),
        nu_func=_walther_s2,
        max_bulk_temperature=573.15,
        max_film_temperature=593.15,
        property_range=(273.15, 613.15),
        source="Shell TDS v1.1 (2014-01-27), calculated design data; limits TDS v1.1/v1.4",
    ),
    "therminol_66": ThermalOil(
        name="Therminol 66",
        rho_poly=(1020.62, -0.614254, -0.000321),
        cp_poly=(1496.005, 3.313, 8.97785e-4),
        k_poly=(0.118294, -3.3e-5, -1.5e-7),
        nu_func=_exp_th66,
        max_bulk_temperature=618.15,
        max_film_temperature=648.15,
        property_range=(270.15, 643.15),
        source="Eastman Therminol 66 brochure (2025); fit equations checked against its table",
    ),
}


def get_oil(name: str) -> ThermalOil:
    try:
        return OILS[name]
    except KeyError:
        raise KeyError(f"unknown thermal oil {name!r}; one of {sorted(OILS)}") from None
