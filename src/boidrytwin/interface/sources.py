"""Boundary-condition flue gas sources standing in for a boiler house (FR-006)."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from boidrytwin.errors import InterfaceValidationError, SupplyCoverageError, ValidationIssue
from boidrytwin.interface.composition import KEYS, SUM_TOLERANCE
from boidrytwin.interface.flue_gas import (
    FlueGasConditions,
    FlueGasState,
    Quality,
    check_state_values,
    make_state,
)
from boidrytwin.properties.gas import FloatArray

FIRST_DATA_LINE = 3  # CSV: header, unit row, then data


class ConstantFlueGasSupply:
    """The same flue gas state at all times."""

    def __init__(self, state: FlueGasState, *, start: datetime) -> None:
        self.source_id = "constant"
        self._state = state
        self._start = start
        self._conditions = FlueGasConditions(
            mass_flow=state.mass_flow,
            temperature=state.temperature,
            pressure=state.pressure,
            x=state.composition.as_array(),
            quality=state.quality,
        )

    def state_at(self, t: float) -> FlueGasState:
        return self._state.model_copy(update={"time": self._start + timedelta(seconds=t)})

    def conditions_at(self, t: float) -> FlueGasConditions:
        return self._conditions

    def covers(self, t_start: float, t_end: float) -> bool:
        return True


class TimeSeriesFlueGasSupply:
    """Flue gas from measured or prescribed samples, linearly interpolated.

    ``frame`` has a UTC ``DatetimeIndex`` and SI columns ``mass_flow``, ``temperature``,
    ``pressure``, wet mole fractions ``x_N2`` … ``x_other`` and ``quality``. Rows with quality
    ``missing`` or ``bad`` are not used for interpolation; the intervals around them carry
    that quality. Gaps between usable samples longer than ``max_gap`` are an error unless
    ``allow_gaps``; allowed gaps are returned with quality ``missing`` (FR-015).
    """

    def __init__(
        self,
        frame: pd.DataFrame,
        *,
        start: datetime,
        max_gap: float = 300.0,
        allow_gaps: bool = False,
        file_label: str | None = None,
        source_id: str = "timeseries",
    ) -> None:
        self.source_id = source_id
        self._start = start
        label = file_label or "time series"
        issues: list[ValidationIssue] = []

        quality = frame["quality"].to_numpy(dtype=object)
        cols = ["mass_flow", "temperature", "pressure", *KEYS]
        values = frame[cols].to_numpy(dtype=float)
        usable = (quality != "missing") & (quality != "bad") & ~np.isnan(values).any(axis=1)

        for row in np.flatnonzero(usable):
            where = f"{label}:line {row + FIRST_DATA_LINE}"
            mf, temp, p = values[row, :3]
            for fieldname, reason, allowed in check_state_values(
                mass_flow=mf, temperature=temp, pressure=p
            ):
                value = {"mass_flow": mf, "temperature": temp, "pressure": p}[fieldname]
                issues.append(
                    ValidationIssue(
                        field=f"flue_gas.{fieldname}",
                        value=f"{value:g}",
                        reason=reason,
                        allowed=allowed,
                        location=where,
                    )
                )
            x = values[row, 3:]
            if np.any(x < 0) or np.any(x > 1) or abs(x.sum() - 1.0) > SUM_TOLERANCE:
                issues.append(
                    ValidationIssue(
                        field="flue_gas.composition",
                        value=f"sum {x.sum():.4f}",
                        reason=f"composition sums to {x.sum():.3f}, expected 1 ± 0.005",
                        allowed="0 ≤ x ≤ 1, sum = 1 ± 0.005",
                        location=where,
                    )
                )

        index = pd.DatetimeIndex(frame.index)
        seconds = np.asarray((index - pd.Timestamp(start)).total_seconds(), dtype=float)
        t_ok = seconds[usable]
        if len(t_ok) == 0:
            issues.append(
                ValidationIssue(
                    field="flue_gas",
                    value=label,
                    reason="no usable samples",
                    allowed="at least one sample with quality good",
                    location=label,
                )
            )
            raise InterfaceValidationError(issues)

        stamps_ok = index[usable]
        interval_flag: list[Quality | None] = []
        for k in range(len(t_ok) - 1):
            flag: Quality | None = None
            if t_ok[k + 1] - t_ok[k] > max_gap:
                if not allow_gaps:
                    a, b = stamps_ok[k], stamps_ok[k + 1]
                    issues.append(
                        ValidationIssue(
                            field="flue_gas",
                            value=label,
                            reason=(
                                f"gap of {(t_ok[k + 1] - t_ok[k]) / 60:g} min between "
                                f"{a.isoformat()} and {b.isoformat()} exceeds max_gap "
                                f"{max_gap / 60:g} min"
                            ),
                            allowed="allow_gaps = true or a larger max_gap",
                            location=label,
                        )
                    )
                flag = "missing"
            inside = (seconds > t_ok[k]) & (seconds < t_ok[k + 1]) & ~usable
            if inside.any():
                flag = "bad" if np.any(quality[inside] == "bad") else (flag or "missing")
            interval_flag.append(flag)

        if issues:
            raise InterfaceValidationError(issues)

        self._t = t_ok
        self._v = values[usable]
        self._q = quality[usable]
        self._flags = interval_flag
        self._stamps = stamps_ok

    def covers(self, t_start: float, t_end: float) -> bool:
        return bool(self._t[0] <= t_start and t_end <= self._t[-1])

    def conditions_at(self, t: float) -> FlueGasConditions:
        if not self._t[0] <= t <= self._t[-1]:
            raise SupplyCoverageError(
                f"flue gas requested at t = {t:g} s, outside the covered period "
                f"{self._stamps[0].isoformat()} – {self._stamps[-1].isoformat()}"
            )
        k = int(np.searchsorted(self._t, t, side="right")) - 1
        if self._t[k] == t:
            row = self._v[k]
            quality: Quality = self._q[k]
        else:
            w = (t - self._t[k]) / (self._t[k + 1] - self._t[k])
            row = (1.0 - w) * self._v[k] + w * self._v[k + 1]
            flag = self._flags[k]
            if flag is not None:
                quality = flag
            elif "stale" in (self._q[k], self._q[k + 1]):
                quality = "stale"
            else:
                quality = "interpolated"
        x: FloatArray = row[3:] / row[3:].sum()
        return FlueGasConditions(
            mass_flow=float(row[0]),
            temperature=float(row[1]),
            pressure=float(row[2]),
            x=x,
            quality=quality,
        )

    def state_at(self, t: float) -> FlueGasState:
        return make_state(self._start + timedelta(seconds=t), self.conditions_at(t))
