"""Thermal oil heater heat transfer (research.md R5, R6).

- Gas side of convective cells: quasi-static gas with a dynamic wall,
  T_out = T_w + (T_in − T_w)·exp(−UA/(ṁ c_p)); the heat is ṁ·[h(T_in) − h(T_out)] so the
  energy balance is exact.
- Žukauskas staggered tube bank (Incropera Table 7.5): Nu = C·Re^m·Pr^0.36 with
  C = 0.35·(S_t/S_l)^0.2, m = 0.6 for Re < 2·10⁵, else C = 0.022, m = 0.84;
  gas radiation h_rad = ε_g σ (T_g² + T_w²)(T_g + T_w); fouling resistance R_f in series.
- Oil side: Gnielinski (VDI Heat Atlas), laminar Nu = 3.66, linear blend over Re 2300–10⁴.
- Film temperature (Pelini 2008): T_film = T_oil + q″_peak / h_i.
"""

from __future__ import annotations

import math

import numpy as np

from boidrytwin.properties import gas
from boidrytwin.properties.gas import FloatArray
from boidrytwin.properties.thermal_oil import ThermalOil

SIGMA = 5.670374419e-8
RE_LAMINAR, RE_TURBULENT = 2300.0, 1e4


def gas_cell(
    T_in: float, T_wall: float, mass_flow: float, y: FloatArray, UA: float
) -> tuple[float, float]:
    """(gas outlet temperature, heat from gas to wall) for one quasi-static cell."""
    if mass_flow <= 0.0:
        return T_wall, 0.0
    cp = float(gas.cp_mass(T_in, y))
    T_out = T_wall + (T_in - T_wall) * math.exp(-UA / (mass_flow * cp))
    q = mass_flow * float(gas.h_sensible_mass(T_in, y) - gas.h_sensible_mass(T_out, y))
    return T_out, q


def nu_zukauskas_staggered(re: float, pr: float, pitch_ratio: float = 1.2) -> float:
    if re < 2e5:
        c, m = 0.35 * pitch_ratio**0.2, 0.6
    else:
        c, m = 0.022, 0.84
    return float(c * re**m * pr**0.36)


def _gnielinski(re: float, pr: float) -> float:
    xi = (1.8 * math.log10(re) - 1.5) ** -2
    return float((xi / 8) * (re - 1000) * pr / (1 + 12.7 * math.sqrt(xi / 8) * (pr ** (2 / 3) - 1)))


def nu_tube(re: float, pr: float) -> float:
    if re <= RE_LAMINAR:
        return 3.66
    if re >= RE_TURBULENT:
        return _gnielinski(re, pr)
    w = (re - RE_LAMINAR) / (RE_TURBULENT - RE_LAMINAR)
    return float((1 - w) * 3.66 + w * _gnielinski(RE_TURBULENT, pr))


def overall_gas_side(h_gas: float, fouling_resistance: float) -> float:
    return 1.0 / (1.0 / h_gas + fouling_resistance)


def oil_upstream(h_cells: FloatArray, h_return: float) -> FloatArray:
    """Enthalpy entering each cell; oil flows from the last cell towards cell 0."""
    up = np.empty_like(h_cells)
    up[:-1] = h_cells[1:]
    up[-1] = h_return
    return up


def film_temperature(
    T_oil: float, heat_flux_avg: float, peak_factor: float, h_inner: float
) -> float:
    return T_oil + peak_factor * max(heat_flux_avg, 0.0) / h_inner


def oil_flow(
    mass_flow: float, T: float, oil: ThermalOil, inner_diameter: float, passes: int
) -> tuple[float, float]:
    """(velocity m/s, Reynolds number) in one pass."""
    area = passes * math.pi * inner_diameter**2 / 4.0
    v = mass_flow / (float(oil.density(T)) * area)
    re = v * inner_diameter / float(oil.viscosity(T))
    return v, re


def oil_htc(
    mass_flow: float, T: float, oil: ThermalOil, inner_diameter: float, passes: int
) -> tuple[float, float, float]:
    """(inner coefficient W/(m² K), velocity, Reynolds)."""
    v, re = oil_flow(mass_flow, T, oil, inner_diameter, passes)
    nu = nu_tube(re, float(oil.prandtl(T)))
    return nu * float(oil.conductivity(T)) / inner_diameter, v, re


def gas_htc_bank(
    mass_flow: float,
    T_gas: float,
    T_wall: float,
    x: FloatArray,
    outer_diameter: float,
    free_flow_area: float,
    pitch_ratio: float,
    emissivity: float,
) -> float:
    """Convective + radiative gas-side coefficient of a tube bank, W/(m² K)."""
    mu = float(gas.viscosity(T_gas, x))
    k = float(gas.conductivity(T_gas, x))
    y = gas.mass_fractions(x)
    cp = float(gas.cp_mass(T_gas, y))
    re = max(mass_flow, 1e-9) / free_flow_area * outer_diameter / mu
    nu = nu_zukauskas_staggered(re, cp * mu / k, pitch_ratio)
    h_conv = nu * k / outer_diameter
    h_rad = emissivity * SIGMA * (T_gas**2 + T_wall**2) * (T_gas + T_wall)
    return h_conv + h_rad
