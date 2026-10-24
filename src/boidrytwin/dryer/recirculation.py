"""Exhaust recirculation loop of the dryer: pressure transmitter and damper controller.

Research R5 of feature 004. The mixing chamber pressure is measured through a first-order
transmitter lag; a PI controller (feature 002) with reverse action sets the recirculation
damper: pressure below the set point (draft too strong) opens the damper. Both are dryer
states, so the loop works the same in dryer-only and coupled runs (research R1).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from boidrytwin.control.pi import PIController, not_reached_mask
from boidrytwin.dryer.gas_path import GasPath
from boidrytwin.logging import get_logger
from boidrytwin.properties.gas import FloatArray
from boidrytwin.range_warnings import LimitType, RangeWarning, detect_periods
from boidrytwin.scenario.schema import BalanceTolerances, RecirculationSpec
from boidrytwin.scenario.timeseries import Signal

LOOP = "mixing_chamber_pressure"
I_MEAS, I_INT = 0, 1  # offsets of the loop states behind the cells
PRESSURE_SCALE = 500.0  # Pa
SATURATION_MARGIN = 0.02  # of the output span, as for the feature-002 loops

log = get_logger("dryer")


class RecirculationLoop:
    """Gas path, transmitter and controller of one dryer; states: [p_measured, integral]."""

    size = 2

    def __init__(self, spec: RecirculationSpec, signals: Mapping[str, Signal]) -> None:
        self.spec = spec
        self.path = GasPath(spec)
        self.pi = PIController(spec.controller)
        self.speed = signals["recirculation.exhaust_fan.speed"]
        self.setpoint = signals.get(
            "recirculation.controller.setpoint",
            Signal(
                name="recirculation.controller.setpoint",
                constant=spec.controller.setpoint.constant or 0.0,
            ),
        )
        self.manual = signals.get("recirculation.controller.manual_output")

    def manual_value(self, t: float) -> float | None:
        c = self.spec.controller
        if c.mode != "manual":
            return None
        return self.manual.value_at(t) if self.manual is not None else c.manual_output

    def position(self, t: float, extra: FloatArray) -> tuple[float, float]:
        """(unsaturated output, applied damper position) for the loop states ``extra``."""
        v, u = self.pi.output(
            self.setpoint.value_at(t), extra[I_MEAS], extra[I_INT], self.manual_value(t)
        )
        return float(v), float(u)

    def derivatives(self, t: float, extra: FloatArray, p_mc: float) -> FloatArray:
        """d/dt of [measured pressure, integral] for the mixing chamber pressure ``p_mc``."""
        rate = self.pi.integral_rate(
            self.setpoint.value_at(t), extra[I_MEAS], extra[I_INT], self.manual_value(t)
        )
        lag = (p_mc - extra[I_MEAS]) / self.spec.pressure_sensor_time_constant
        return np.array([lag, float(rate)])

    def initial_position(self, t: float) -> float:
        manual = self.manual_value(t)
        if manual is not None:
            return manual
        c = self.spec.controller
        return 0.5 * (c.output_min + c.output_max)

    def initial_extra(self, t: float, p_mc: float, position: float) -> FloatArray:
        """Measurement settled on ``p_mc``, integral so that the output is ``position``."""
        integral = self.pi.initial_integral(position, self.setpoint.value_at(t), p_mc)
        return np.array([p_mc, integral])

    def scales(self) -> FloatArray:
        return np.array([PRESSURE_SCALE, 1.0])

    def breakpoints(self) -> FloatArray:
        signals = [self.speed, self.setpoint] + ([self.manual] if self.manual else [])
        return np.unique(np.concatenate([s.breakpoints() for s in signals]))


def loop_flags(loop: RecirculationLoop, t: FloatArray, results: pd.DataFrame) -> None:
    """``controller_saturated`` and ``setpoint_not_reached`` of the pressure loop (FR-008),
    as for the feature-002 loops."""
    s = loop.spec.controller
    v = results[f"_v_{LOOP}"].to_numpy(dtype=float)
    margin = SATURATION_MARGIN * (s.output_max - s.output_min)
    saturated = (v > s.output_max + margin) | (v < s.output_min - margin)
    if s.mode != "automatic":
        saturated = np.zeros(len(results), dtype=bool)
    error = results[f"_e_{LOOP}"].to_numpy(dtype=float)
    not_reached = not_reached_mask(t, error, s.not_reached_band, s.not_reached_hold)
    if s.mode != "automatic":
        not_reached = np.zeros(len(results), dtype=bool)
    for event, mask in (("controller_saturated", saturated), ("setpoint_not_reached", not_reached)):
        log_periods(event, LOOP, results.index, mask)
    results["controller_saturated"] = saturated
    results["setpoint_not_reached"] = not_reached


def log_periods(event: str, loop: str, index: pd.Index, mask: NDArray[np.bool_]) -> None:
    if not mask.any():
        return
    edges = np.flatnonzero(np.diff(np.concatenate([[0], mask.astype(int), [0]])))
    for a, b in zip(edges[::2], edges[1::2], strict=True):
        log.warning(event, loop=loop, period_start=str(index[a]), period_end=str(index[b - 1]))


def loop_warnings(loop: RecirculationLoop, results: pd.DataFrame) -> list[RangeWarning]:
    """Warning periods of FR-011: overpressure, backflow, condensation risk at the drum inlet,
    fan off its curve, share above its maximum."""
    index = pd.DatetimeIndex(results.index)
    spec = loop.spec

    def periods(values: object, limit: float, kind: LimitType, quantity: str) -> list[RangeWarning]:
        return detect_periods(index, np.asarray(values, dtype=float), limit=limit,
                              limit_type=kind, quantity=quantity)  # fmt: skip

    margin = results["drum_inlet_gas_temperature"] - results["drum_inlet_dew_point"]
    return [
        *periods(results["mixing_chamber_pressure"], 0.0, "max", "mixing_chamber_overpressure"),
        *periods(results["_backflow"].astype(float), 0.5, "max", "recirculation_backflow"),
        *periods(margin, spec.dew_point_margin, "min", "drum_inlet_condensation_risk"),
        *periods(results["_fan_out_of_curve"].astype(float), 0.5, "max", "exhaust_fan_curve"),
        *periods(results["recirculation_share"], spec.max_share, "max", "recirculation_share"),
    ]


def loop_balance(results: pd.DataFrame, tolerances: BalanceTolerances) -> dict[str, Any]:
    """Mixing chamber check (research R7): what enters (fresh gas, returned gas) against
    what leaves into the drum (plus the duct loss), largest relative error over the run."""
    mass = float(results["_loop_residual_mass"].max())
    energy = float(results["_loop_residual_energy"].max())
    report = {
        "mass": {"max_relative_residual": mass, "tolerance": tolerances.mass,
                 "passed": mass <= tolerances.mass},
        "energy": {"max_relative_residual": energy, "tolerance": tolerances.energy,
                   "passed": energy <= tolerances.energy},
    }  # fmt: skip
    return {**report, "passed": report["mass"]["passed"] and report["energy"]["passed"]}
