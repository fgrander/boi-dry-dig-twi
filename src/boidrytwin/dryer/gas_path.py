"""Quasi-steady pressure and flow of the dryer gas path with exhaust recirculation.

Research R2/R3 of feature 004. The gas path is mixing chamber -> drum, cyclone and ducts ->
exhaust fan -> stack, with a return line from the fan's pressure side through the
recirculation damper back into the mixing chamber. Assumptions:

- pressures are relative to ambient (Pa) and small, so densities use ambient pressure;
- pressures and flows settle within milliseconds, far faster than the drum: they are
  algebraic in every evaluation (no mixing chamber volume);
- fan curve: a quadratic through 3 points at nominal speed, scaled by the fan laws and by
  density (Carolus 2013, ch. 2; Bleier 1998, ch. 4);
- resistances: constant loss coefficient, dp = dp_d (rho_d / rho) (m / m_d)^2 from one design
  point (Idelchik 2007, ch. 1);
- damper: relative flow coefficient over position from a monotone table (PCHIP), fully open
  design point (ASHRAE Handbook HVAC Systems and Equipment 2020, ch. 47).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

from boidrytwin.properties import gas
from boidrytwin.scenario.schema import RecirculationSpec, ResistancePoint

P_REF = 101_325.0  # Pa, density reference of design points and the fan curve
M_AIR = 0.0289647  # kg/mol, dry air
M_WATER = float(gas.MOLAR_MASS[gas.I_H2O])
# inherent characteristic of an opposed-blade damper (relative flow over position); the
# first value is replaced by the damper's leakage (ASHRAE 2020, ch. 47)
DEFAULT_CHARACTERISTIC = (
    (0.0, 0.01),
    (0.2, 0.05),
    (0.4, 0.15),
    (0.6, 0.35),
    (0.8, 0.65),
    (1.0, 1.0),
)
XTOL = 1e-10  # kg/s


def air_density(T: float) -> float:
    """Dry air at the reference pressure, kg/m³."""
    return P_REF * M_AIR / (gas.R_UNIVERSAL * T)


@dataclass(frozen=True)
class GasPathState:
    """Pressures (Pa, relative to ambient) and flows of the gas path at one time."""

    recirculated_dry_gas: float  # kg/s
    drum_dry_gas: float  # kg/s
    mixing_chamber_pressure: float
    fan_outlet_pressure: float
    fan_volume_flow: float  # m³/s at the fan inlet
    fan_pressure_rise: float
    damper_pressure_drop: float
    backflow: bool  # no driving pressure difference across the damper
    fan_out_of_curve: bool


class GasPath:
    def __init__(self, spec: RecirculationSpec) -> None:
        fan = spec.exhaust_fan
        flows = np.array([v for v, _ in fan.curve])
        rises = np.array([p for _, p in fan.curve])
        a0, a1, a2 = np.linalg.solve(np.vander(flows, 3, increasing=True), rises)
        if a2 >= 0.0 or np.any(np.diff(rises) >= 0.0):
            raise ValueError("the fan curve must fall with the flow, ever more steeply")
        self.coefficients = (float(a0), float(a1), float(a2))
        self.nominal_speed = fan.nominal_speed
        self.curve_flows = (float(flows[0]), float(flows[-1]))
        self.rho_fan = air_density(fan.curve_temperature)
        damper = spec.damper
        table = damper.characteristic or ((0.0, damper.leakage), *DEFAULT_CHARACTERISTIC[1:])
        self._phi = PchipInterpolator([p for p, _ in table], [f for _, f in table])
        self.damper = damper
        self.rho_damper = air_density(damper.design_temperature)
        self.drum_path = spec.resistances.drum_path
        self.stack = spec.resistances.stack

    # --- characteristics -------------------------------------------------------------

    def fan_pressure_rise(self, V: float, n: float, rho: float) -> float:
        """Fan laws on the quadratic curve, scaled by density, Pa."""
        a0, a1, a2 = self.coefficients
        r = n / self.nominal_speed
        return (a0 * r * r + a1 * r * V + a2 * V * V) * rho / self.rho_fan

    def resistance(self, point: ResistancePoint, m: float, rho: float) -> float:
        """Constant loss coefficient through the design point, Pa."""
        rho_d = air_density(point.temperature)
        return point.pressure_drop * (rho_d / rho) * (m / point.mass_flow) ** 2

    def relative_flow(self, s: float) -> float:
        return float(self._phi(min(max(s, 0.0), 1.0)))

    def damper_flow(self, s: float, dp: float, rho: float) -> float:
        """Wet mass flow through the damper at position ``s`` and pressure drop ``dp``."""
        return self._damper_flow(self.relative_flow(s), dp, rho)

    def _damper_flow(self, phi: float, dp: float, rho: float) -> float:
        if dp <= 0.0:
            return 0.0
        d = self.damper
        return (
            phi
            * d.open_mass_flow
            * math.sqrt(rho * dp / (self.rho_damper * d.design_pressure_drop))
        )

    # --- operating point ---------------------------------------------------------------

    def solve(
        self, G_in: float, Y: float, T: float, M_dry: float, s: float, n: float, p_amb: float
    ) -> GasPathState:
        """Operating point for fresh dry gas ``G_in`` and the drum outlet gas (humidity ``Y``,
        temperature ``T``, dry molar mass ``M_dry``) at damper position ``s``, fan speed ``n``
        (research R2). The recirculated dry gas is the root of a strictly decreasing
        function, bracketed between 0 and the flow at the largest damper pressure drop."""
        M_wet = (1.0 + Y) / (1.0 / M_dry + Y / M_WATER)
        rho = p_amb * M_wet / (gas.R_UNIVERSAL * T)
        w = 1.0 + Y
        phi = self.relative_flow(s)
        p_out = self.resistance(self.stack, G_in * w, rho)

        def damper_dp(G_rec: float) -> float:
            m = (G_in + G_rec) * w
            return self.fan_pressure_rise(m / rho, n, rho) - self.resistance(self.drum_path, m, rho)

        def residual(G_rec: float) -> float:
            return self._damper_flow(phi, damper_dp(G_rec), rho) - G_rec * w

        dp0 = damper_dp(0.0)
        G_rec = 0.0
        if dp0 > 0.0:
            hi = self._damper_flow(phi, dp0, rho) / w
            if hi > 0.0:
                G_rec = hi if residual(hi) >= 0.0 else float(brentq(residual, 0.0, hi, xtol=XTOL))
        m = (G_in + G_rec) * w
        V = m / rho
        rise = self.fan_pressure_rise(V, n, rho)
        dp = rise - self.resistance(self.drum_path, m, rho)
        r = n / self.nominal_speed
        return GasPathState(
            recirculated_dry_gas=G_rec,
            drum_dry_gas=G_in + G_rec,
            mixing_chamber_pressure=p_out - dp,
            fan_outlet_pressure=p_out,
            fan_volume_flow=V,
            fan_pressure_rise=rise,
            damper_pressure_drop=dp,
            backflow=dp0 <= 0.0,
            fan_out_of_curve=not (self.curve_flows[0] * r <= V <= self.curve_flows[1] * r),
        )
