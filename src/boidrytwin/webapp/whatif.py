"""What-if run against its baseline (FR-014, FR-014a, FR-015; data-model §7).

For each comparison output: the final value and the mean of the last hour of the baseline and
of the what-if run (display units), their difference and the relative difference; warnings and
flags that only the what-if run has; and a plain-language summary for operators.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel

from boidrytwin.webapp.display_units import display_unit, to_display
from boidrytwin.webapp.run_view import RunData

LAST_HOUR = pd.Timedelta(hours=1)
NO_BASELINE = "no completed baseline for this version, so no comparison is available"


class Row(BaseModel):
    column: str
    unit: str
    baseline_final: float
    baseline_mean_last_hour: float
    whatif_final: float
    whatif_mean_last_hour: float
    difference: float
    relative: float | None


class Summary(BaseModel):
    oil_on_setpoint: bool | None
    oil_deviation: float | None  # K, final value − set point
    drum_inlet_on_setpoint: bool | None
    drum_inlet_deviation: float | None
    product_moisture: float | None  # %, wet basis
    new_warnings: int
    text: list[str]


class WhatIfComparison(BaseModel):
    rows: list[Row]
    new_warnings: list[str]
    new_flags: list[str]
    summary: Summary
    note: str | None = None


def _series(run: RunData, column: str) -> tuple[np.ndarray, pd.DatetimeIndex] | None:
    try:
        table = run.column_table(column)
    except KeyError:
        return None
    values = to_display(
        column,
        table.units.get(column, ""),
        pd.to_numeric(table.frame[column], errors="coerce").to_numpy(dtype=float),
    )
    return values, pd.DatetimeIndex(table.frame.index)


def _final_and_mean(values: np.ndarray, index: pd.DatetimeIndex) -> tuple[float, float]:
    window = index >= index[-1] - LAST_HOUR
    return float(values[-1]), float(np.nanmean(values[window]))


def _warning_labels(run: RunData) -> set[str]:
    return {f"{w.get('quantity')} {w.get('limit_type')} {w.get('limit')}" for w in run.warnings()}


def _loop(run: RunData, name: str) -> dict[str, Any] | None:
    try:
        loop = run.record["scenario"]["boiler_house"]["controllers"][name]
    except (KeyError, TypeError):
        return None
    return loop if isinstance(loop, dict) else None


def _on_setpoint(run: RunData, loop_name: str, column: str) -> tuple[bool | None, float | None]:
    loop = _loop(run, loop_name)
    series = _series(run, column)
    if loop is None or series is None:
        return None, None
    setpoint = (loop.get("setpoint") or {}).get("constant")
    if setpoint is None:  # a set point time series: use the controller flag at the end
        try:
            flag = run.column_table("setpoint_not_reached").frame["setpoint_not_reached"]
            return not bool(str(flag.iloc[-1]).lower() == "true"), None
        except KeyError:
            return None, None
    # temperatures: display unit °C, set point in K
    deviation = float(series[0][-1]) - (float(setpoint) - 273.15)
    return abs(deviation) <= float(loop.get("not_reached_band", 1.0)), deviation


def _setpoint_text(what: str, on: bool, deviation: float | None, fmt: str) -> str:
    if on:
        return f"{what} is on its set point."
    d = deviation or 0.0
    side = "below" if d < 0 else "above"
    return f"{what} is {fmt.format(abs(d))} K {side} its set point."


def summarize(run: RunData, new_warnings: list[str]) -> Summary:
    oil, oil_dev = _on_setpoint(run, "oil_temperature", "oil_outlet_temperature")
    drum, drum_dev = (None, None)
    if run.summary.kind == "coupled":
        drum, drum_dev = _on_setpoint(run, "drum_inlet_temperature", "drum_inlet_gas_temperature")
    moisture = _series(run, "product_moisture_wet_basis")
    product = float(moisture[0][-1]) if moisture is not None else None
    text: list[str] = []
    if oil is not None:
        text.append(_setpoint_text("Oil outlet", oil, oil_dev, "{:.1f}"))
    if drum is not None:
        text.append(_setpoint_text("Drum inlet", drum, drum_dev, "{:.0f}"))
    if product is not None:
        text.append(f"Product moisture at the end: {product:.1f} % (wet basis).")
    text.append(
        "No new warnings."
        if not new_warnings
        else f"{len(new_warnings)} new warning(s): {', '.join(new_warnings)}."
    )
    return Summary(
        oil_on_setpoint=oil,
        oil_deviation=oil_dev,
        drum_inlet_on_setpoint=drum,
        drum_inlet_deviation=drum_dev,
        product_moisture=product,
        new_warnings=len(new_warnings),
        text=text,
    )


def compare_runs(
    baseline: RunData | None, whatif: RunData, outputs: Sequence[str]
) -> WhatIfComparison:
    if baseline is None:
        new = sorted(_warning_labels(whatif))
        return WhatIfComparison(
            rows=[],
            new_warnings=new,
            new_flags=[],
            summary=summarize(whatif, new),
            note=NO_BASELINE,
        )
    rows: list[Row] = []
    for column in outputs:
        a, b = _series(baseline, column), _series(whatif, column)
        if a is None or b is None:
            continue
        base_final, base_mean = _final_and_mean(*a)
        what_final, what_mean = _final_and_mean(*b)
        diff = what_final - base_final
        unit = display_unit(column, baseline.column_table(column).units.get(column, ""))
        rows.append(
            Row(
                column=column,
                unit=unit,
                baseline_final=base_final,
                baseline_mean_last_hour=base_mean,
                whatif_final=what_final,
                whatif_mean_last_hour=what_mean,
                difference=diff,
                relative=diff / base_final if base_final else None,
            )
        )
    new_warnings = sorted(_warning_labels(whatif) - _warning_labels(baseline))
    base_flags = baseline.record.get("flags_summary") or {}
    new_flags = sorted(
        k
        for k, v in (whatif.record.get("flags_summary") or {}).items()
        if v and not base_flags.get(k)
    )
    return WhatIfComparison(
        rows=rows,
        new_warnings=new_warnings,
        new_flags=new_flags,
        summary=summarize(whatif, new_warnings),
    )


def comparison_csv(cmp: WhatIfComparison, baseline_id: str | None, whatif_id: str) -> str:
    """The comparison table as CSV (display units); the run ids in a last ``#`` line."""
    lines = [
        "output,unit,baseline_final,whatif_final,difference,relative,"
        "baseline_mean_last_hour,whatif_mean_last_hour"
    ]
    for r in cmp.rows:
        cells = [
            r.column,
            r.unit,
            repr(r.baseline_final),
            repr(r.whatif_final),
            repr(r.difference),
            "" if r.relative is None else repr(r.relative),
            repr(r.baseline_mean_last_hour),
            repr(r.whatif_mean_last_hour),
        ]
        lines.append(",".join(cells))
    lines.append(f"# what-if run {whatif_id}, baseline run {baseline_id or '-'}")
    return "\n".join(lines) + "\n"
