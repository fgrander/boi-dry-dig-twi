"""Flue gas bypass around heaters and mixing before the dryer (research.md R7).

The damper position sets the bypass share directly (no damper characteristic, leakage or
pressure-driven split). Mixing conserves mass and enthalpy exactly.
"""

from __future__ import annotations

from boidrytwin.boiler_house.furnace import gas_temperature
from boidrytwin.properties import gas
from boidrytwin.properties.gas import FloatArray


def split_flow(mass_flow: float, position: float) -> tuple[float, float]:
    """(through the heaters, through the bypass)."""
    p = min(max(position, 0.0), 1.0)
    return mass_flow * (1.0 - p), mass_flow * p


def mix(
    m_heaters: float, T_heaters: float, m_bypass: float, T_bypass: float, y: FloatArray
) -> tuple[float, float]:
    m = m_heaters + m_bypass
    if m <= 0.0:
        return 0.0, T_heaters
    h = (
        m_heaters * float(gas.h_sensible_mass(T_heaters, y))
        + m_bypass * float(gas.h_sensible_mass(T_bypass, y))
    ) / m
    guess = (m_heaters * T_heaters + m_bypass * T_bypass) / m
    return m, gas_temperature(h, y, T_guess=guess)
