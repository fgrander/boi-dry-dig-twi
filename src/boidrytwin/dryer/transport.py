"""Two-phase solids transport in a flighted, co-current drum (research.md R2).

Per cell the solids are split into a *passive* phase (in the flights or on the bed) and an
*active* phase (falling through the gas in curtains), following the compartment models of
Schneider et al. (2003), Sheehan et al. (2005, 2008):

- passive -> active (flight unloading):  k2 m_p, k2 = 1 / t_p with t_p = T_rev / f_cap - t_fall,
  so that one full cycle (in the flight, then falling) takes one revolution, scaled by
  ``flight_capacity_factor``;
- active -> passive (curtain return):     k3 m_a, k3 = 1 / t_fall;
- active, cell i -> i+1:  m_a v_a / Δz, with the axial advance per fall from the drum slope
  (h_fall tan S) plus co-current gas drag on the falling chip (Baker 1992 curtain drag:
  single-sphere drag times ``drag_coefficient``);
- passive, cell i -> i+1 (kilning / bouncing): m_p v_p / Δz, with v_p chosen so that without
  gas the steady residence time equals Saeman & Mitchell (1954) with f(H) = π, times
  ``kilning_coefficient``.

Water is carried with the dry solids in proportion to each phase's moisture content.
Fall height h_fall = 0.6 D and the single-sphere drag coefficient C_D = 1 are typical values.
VERIFY(Baker 1988, 1992; Matchett & Baker 1987).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from boidrytwin.dryer.config import DryerConfiguration
from boidrytwin.properties.gas import FloatArray

G_ACCEL = 9.80665
FALL_HEIGHT_FACTOR = 0.6  # mean fall height / diameter. VERIFY(Baker 1988)
SPHERE_DRAG_COEFFICIENT = 1.0  # VERIFY(Baker 1992)


@dataclass(frozen=True)
class TransportRates:
    unload: float  # k2, 1/s
    ret: float  # k3, 1/s
    v_active: FloatArray  # axial velocity of the active phase, m/s, per cell
    v_passive: float  # axial velocity of the passive phase, m/s


@dataclass(frozen=True)
class SolidsFlows:
    """Dry solids flows, kg/s, per cell."""

    unload: FloatArray
    ret: FloatArray
    active_out: FloatArray
    passive_out: FloatArray

    @property
    def outlet(self) -> float:
        return float(self.active_out[-1] + self.passive_out[-1])


def fall_height(cfg: DryerConfiguration) -> float:
    return FALL_HEIGHT_FACTOR * cfg.diameter


def fall_time(cfg: DryerConfiguration) -> float:
    return math.sqrt(2.0 * fall_height(cfg) / G_ACCEL)


def revolutions_per_second(cfg: DryerConfiguration) -> float:
    return cfg.rotation_speed / (2.0 * math.pi)


def passive_time(cfg: DryerConfiguration) -> float:
    """Mean time a chip spends in a flight per cascade, s (at least 10 % of a revolution)."""
    t_rev = 1.0 / revolutions_per_second(cfg)
    return max(t_rev / cfg.flight_capacity_factor - fall_time(cfg), 0.1 * t_rev)


def particle_volume(cfg: DryerConfiguration) -> float:
    return math.pi * cfg.chip_equivalent_diameter**3 / 6.0


def transport_rates(
    cfg: DryerConfiguration, X_active: FloatArray, rho_g: FloatArray | float, u_g: FloatArray
) -> TransportRates:
    """Rates for the current moisture (lighter chips are pushed further by the gas)."""
    t_fall = fall_time(cfg)
    tan_s = math.tan(cfg.slope)
    d = cfg.chip_equivalent_diameter
    m_particle = cfg.particle_density * particle_volume(cfg) * (1.0 + np.asarray(X_active))
    area = math.pi * d**2 / 4.0
    u = np.asarray(u_g, dtype=float)
    force = cfg.drag_coefficient * 0.5 * np.asarray(rho_g) * u * np.abs(u)
    accel = force * SPHERE_DRAG_COEFFICIENT * area / m_particle
    advance = fall_height(cfg) * tan_s + 0.5 * accel * t_fall**2
    v_active = advance / t_fall
    t_passive = passive_time(cfg)
    # advance per cycle = h_fall tan S + v_p t_p = π D tan S  (Saeman-Mitchell, f = π)
    v_passive = (
        cfg.kilning_coefficient * (math.pi - FALL_HEIGHT_FACTOR) * cfg.diameter * tan_s / t_passive
    )
    return TransportRates(
        unload=1.0 / t_passive,
        ret=1.0 / t_fall,
        v_active=np.asarray(v_active, dtype=float),
        v_passive=float(v_passive),
    )


def solids_flows(
    cfg: DryerConfiguration, rates: TransportRates, m_p: FloatArray, m_a: FloatArray
) -> SolidsFlows:
    dz = cfg.cell_length
    return SolidsFlows(
        unload=rates.unload * m_p,
        ret=rates.ret * m_a,
        active_out=m_a * rates.v_active / dz,
        passive_out=m_p * rates.v_passive / dz,
    )


def _shift_in(out: FloatArray, feed: float) -> FloatArray:
    """Inflow per cell: cell 0 gets ``feed``, cell i gets the outflow of cell i-1."""
    inflow = np.empty_like(out)
    inflow[0] = feed
    inflow[1:] = out[:-1]
    return inflow


def mass_derivatives(feed_dry: float, f: SolidsFlows) -> tuple[FloatArray, FloatArray]:
    """d m_p/dt and d m_a/dt from transport alone (feed enters the passive phase of cell 0)."""
    # chips landing from the active phase of cell i-1 arrive in the passive phase of cell i
    dmp = _shift_in(f.passive_out, feed_dry) + _shift_in(f.active_out, 0.0) - f.passive_out
    dmp += f.ret - f.unload
    dma = f.unload - f.ret - f.active_out
    return dmp, dma


def water_derivatives(
    feed_water: float, f: SolidsFlows, X_p: FloatArray, X_a: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Water carried with the dry solids, kg/s, per cell (without evaporation)."""
    wp_out = f.passive_out * X_p
    wa_out = f.active_out * X_a
    dwp = _shift_in(wp_out, feed_water) + _shift_in(wa_out, 0.0) - wp_out
    dwp += f.ret * X_a - f.unload * X_p
    dwa = f.unload * X_p - f.ret * X_a - wa_out
    return dwp, dwa


def outlet_water(f: SolidsFlows, X_p: FloatArray, X_a: FloatArray) -> float:
    return float(f.passive_out[-1] * X_p[-1] + f.active_out[-1] * X_a[-1])


def steady_residence_time(cfg: DryerConfiguration, rates: TransportRates) -> float:
    """Mean residence time, s, at steady state for uniform rates (uses cell 0 velocity)."""
    t_p, t_a = 1.0 / rates.unload, 1.0 / rates.ret
    v_mean = (rates.v_passive * t_p + float(np.mean(rates.v_active)) * t_a) / (t_p + t_a)
    return float(cfg.length / v_mean)


def saeman_mitchell_residence_time(cfg: DryerConfiguration, f: float = math.pi) -> float:
    """Saeman & Mitchell (1954) without gas: τ = L / (f(H) D n tan S), s."""
    return cfg.length / (f * cfg.diameter * revolutions_per_second(cfg) * math.tan(cfg.slope))


def friedman_marshall_residence_time(cfg: DryerConfiguration) -> float:
    """Friedman & Marshall (1949) without gas term: τ[min] = 0.23 (L/D) / (S N^0.9).

    S is the slope in length/length and N in rpm; L/D is dimensionless so units cancel.
    VERIFY(Friedman & Marshall 1949 / Perry's ch. 12).
    """
    rpm = cfg.rotation_speed * 60.0 / (2.0 * math.pi)
    minutes = 0.23 * (cfg.length / cfg.diameter) / (math.tan(cfg.slope) * rpm**0.9)
    return float(60.0 * minutes)
