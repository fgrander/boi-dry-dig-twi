"""Continuous PI controller with back-calculation anti-windup (research.md R8).

v = K_c e + I,  u = sat(v),  dI/dt = (K_c / T_i) e + (u - v) / T_t

with e = setpoint - measurement (reverse action) or measurement - setpoint (direct action)
and the tracking time T_t defaulting to T_i (Åström & Murray, *Feedback Systems* §10.4;
Modelica LimPID). Saturation is smooth by default (softplus, width ε of the span) so the
ODE right-hand side stays smooth for BDF; an exact clip is available for validation.
In manual mode the integral tracks the manual output (dI/dt = (u_man - v) / T_t), so the
switch back to automatic is bumpless.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from pydantic import BaseModel, ConfigDict, Field, model_validator

from boidrytwin.properties.gas import FloatArray


def _softplus(x: FloatArray) -> FloatArray:
    return np.asarray(np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0.0))


def smooth_clip(v: ArrayLike, lo: float, hi: float, eps_fraction: float) -> FloatArray:
    """Smooth approximation of clip(v, lo, hi); exact clip if ``eps_fraction`` is 0."""
    va = np.asarray(v, dtype=float)
    if eps_fraction <= 0.0:
        return np.asarray(np.clip(va, lo, hi))
    eps = eps_fraction * (hi - lo)
    u = va - eps * _softplus((va - hi) / eps) + eps * _softplus((lo - va) / eps)
    return np.asarray(np.clip(u, lo, hi))


class PISettings(BaseModel):
    """Settings of one PI loop (data-model.md ControllerSettings)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["automatic", "manual"] = "automatic"
    action: Literal["reverse", "direct"] = "reverse"
    gain: float = Field(gt=0.0)
    integral_time: float = Field(gt=0.0)
    tracking_time: float | None = Field(default=None, gt=0.0)
    output_min: float
    output_max: float
    manual_output: float | None = None
    smoothing: float = Field(default=0.005, ge=0.0, lt=0.5)
    exact: bool = False
    not_reached_band: float = Field(default=1.0, gt=0.0)
    not_reached_hold: float = Field(default=600.0, ge=0.0)

    @model_validator(mode="after")
    def _limits(self) -> PISettings:
        if not self.output_min < self.output_max:
            raise ValueError("output_min < output_max required")
        if self.manual_output is not None and not (
            self.output_min <= self.manual_output <= self.output_max
        ):
            raise ValueError("manual output must lie inside the output limits")
        return self

    @property
    def effective_tracking_time(self) -> float:
        return self.tracking_time if self.tracking_time is not None else self.integral_time


class PIController:
    def __init__(self, settings: PISettings) -> None:
        self.settings = settings

    def error(self, setpoint: ArrayLike, measurement: ArrayLike) -> FloatArray:
        sp, y = np.asarray(setpoint, dtype=float), np.asarray(measurement, dtype=float)
        return np.asarray(sp - y if self.settings.action == "reverse" else y - sp)

    def _sat(self, v: FloatArray) -> FloatArray:
        s = self.settings
        return smooth_clip(v, s.output_min, s.output_max, 0.0 if s.exact else s.smoothing)

    def output(
        self,
        setpoint: ArrayLike,
        measurement: ArrayLike,
        integral: ArrayLike,
        manual: float | None = None,
    ) -> tuple[FloatArray, FloatArray]:
        """(unsaturated v, applied output u)."""
        s = self.settings
        v = np.asarray(s.gain * self.error(setpoint, measurement) + np.asarray(integral))
        if s.mode == "manual":
            u_man = manual if manual is not None else s.manual_output
            assert u_man is not None, "manual mode needs a manual output"
            return v, np.asarray(np.clip(u_man, s.output_min, s.output_max), dtype=float)
        return v, self._sat(v)

    def integral_rate(
        self,
        setpoint: ArrayLike,
        measurement: ArrayLike,
        integral: ArrayLike,
        manual: float | None = None,
    ) -> FloatArray:
        s = self.settings
        v, u = self.output(setpoint, measurement, integral, manual)
        tracking = (u - v) / s.effective_tracking_time
        if s.mode == "manual":
            return np.asarray(tracking)
        return np.asarray(s.gain / s.integral_time * self.error(setpoint, measurement) + tracking)

    def initial_integral(self, output: float, setpoint: float, measurement: float) -> float:
        """Integral that gives ``output`` for the current error (steady-state start)."""
        return float(output - self.settings.gain * float(self.error(setpoint, measurement)))


def not_reached_mask(t: ArrayLike, error: ArrayLike, band: float, hold: float) -> NDArray[np.bool_]:
    """True where |error| > band has lasted at least ``hold`` seconds (FR-010)."""
    tt = np.asarray(t, dtype=float)
    outside = np.abs(np.asarray(error, dtype=float)) > band
    mask = np.zeros(len(tt), dtype=bool)
    start = None
    for i in range(len(tt)):
        if outside[i]:
            if start is None:
                start = tt[i]
            mask[i] = tt[i] - start >= hold
        else:
            start = None
    return mask
