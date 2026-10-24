"""Plot data of one or several runs (FR-002–FR-005, FR-018a; data-model §3, research R7).

Values are the result CSV values converted to display units, nothing else. Flagged and
out-of-range periods are attached to the plots. Long series are reduced for drawing only
(min/max per bucket); the CSV export always has every sample.
"""

from __future__ import annotations

import io
from collections.abc import Sequence

import numpy as np
import pandas as pd
from pydantic import BaseModel

from boidrytwin.webapp.display_units import display_unit, to_display
from boidrytwin.webapp.run_view import RunData

MAX_DRAWN = 5000

DEFAULT_SETS: dict[str, tuple[str, ...]] = {
    "boiler_house": ("oil_outlet_temperature", "fuel_feed", "o2_dry_measured",
                     "furnace_temperature", "heat_to_oil"),
    "dryer": ("drum_inlet_gas_temperature", "product_moisture_wet_basis", "exhaust_temperature",
              "evaporation_rate"),
    "controllers": ("bypass_position", "dilution_air_flow"),
}  # fmt: skip
# range warning quantity → result column it belongs to
WARNING_COLUMNS = {
    "oil_bulk_temperature": "oil_outlet_temperature",
    "oil_film_temperature": "max_film_temperature",
    "oil_velocity": "min_oil_velocity",
    "oil_reynolds": "min_oil_reynolds",
    "exhaust_dew_point_margin": "exhaust_temperature",
    "solids_temperature": "product_temperature",
}


class Trace(BaseModel):
    run_id: str
    times: list[str]
    values: list[float | None]


class Period(BaseModel):
    run_id: str
    start: str
    end: str
    label: str
    kind: str  # "warning" | "flag"


class ColumnPlot(BaseModel):
    column: str
    unit: str
    si_unit: str
    traces: list[Trace]
    periods: list[Period]


class PlotData(BaseModel):
    runs: list[str]
    columns: list[ColumnPlot]


def default_columns(run: RunData) -> list[str]:
    present = set(run.columns())
    cols = [c for group in ("boiler_house", "dryer") for c in DEFAULT_SETS[group] if c in present]
    cols += sorted(c for c in present if c.startswith("controller_output_"))
    cols += [
        c for c in DEFAULT_SETS["controllers"] if c in present and run.summary.kind == "coupled"
    ]
    return cols


def reduce_for_drawing(t: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """At most ``MAX_DRAWN`` points, keeping each bucket's minimum and maximum."""
    n = len(v)
    if n <= MAX_DRAWN:
        return t, v
    buckets = MAX_DRAWN // 2
    keep: list[int] = []
    for chunk in np.array_split(np.arange(n), buckets):
        seg = v[chunk]
        if np.all(np.isnan(seg)):
            keep.append(int(chunk[0]))
            continue
        keep += sorted({int(chunk[np.nanargmin(seg)]), int(chunk[np.nanargmax(seg)])})
    idx = np.array(sorted(set(keep)))
    return t[idx], v[idx]


def _iso(stamp: pd.Timestamp) -> str:
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _periods(run: RunData, column: str) -> list[Period]:
    rid = run.summary.run_id
    out: list[Period] = []
    for w in run.warnings():
        quantity = str(w.get("quantity", ""))
        target = WARNING_COLUMNS.get(quantity, quantity)
        if target == column or quantity.endswith(f".{column}"):
            label = f"{quantity} {w.get('limit_type')} {w.get('limit')}"
            out.append(Period(run_id=rid, start=str(w["period_start"]), end=str(w["period_end"]),
                              label=label, kind="warning"))  # fmt: skip
    for p in run.flag_periods():
        out.append(Period(run_id=rid, start=_iso(p.start), end=_iso(p.end), label=p.flag,
                          kind="flag"))  # fmt: skip
    return out


def build_plot(runs: Sequence[RunData], columns: Sequence[str], *, reduce: bool = True) -> PlotData:
    """Raises ``KeyError`` for a column that a run does not have."""
    plots: list[ColumnPlot] = []
    for column in columns:
        traces: list[Trace] = []
        periods: list[Period] = []
        si_unit = ""
        for run in runs:
            table = run.column_table(column)
            si_unit = table.units.get(column, "")
            series = pd.to_numeric(table.frame[column], errors="coerce")
            values = to_display(column, si_unit, series.to_numpy(dtype=float))
            times = np.array([_iso(t) for t in table.frame.index], dtype=object)
            if reduce:
                times, values = reduce_for_drawing(times, values)
            traces.append(Trace(
                run_id=run.summary.run_id, times=list(times),
                values=[None if np.isnan(x) else float(x) for x in values],
            ))  # fmt: skip
            periods += _periods(run, column)
        plots.append(ColumnPlot(column=column, unit=display_unit(column, si_unit), si_unit=si_unit,
                                traces=traces, periods=periods))  # fmt: skip
    return PlotData(runs=[r.summary.run_id for r in runs], columns=plots)


def plot_csv(plot: PlotData) -> str:
    """The plotted series as CSV: a ``# runs:`` line, the header, a unit row, the values."""
    frames: list[pd.Series] = []
    units: list[str] = []
    for col in plot.columns:
        for trace in col.traces:
            frames.append(
                pd.Series(trace.values, index=trace.times, name=f"{trace.run_id}:{col.column}")
            )
            units.append(col.unit)
    data = pd.concat(frames, axis=1) if frames else pd.DataFrame()
    out = io.StringIO()
    out.write(f"# runs: {', '.join(plot.runs)}\n")
    out.write("time," + ",".join(str(c) for c in data.columns) + "\n")
    out.write("unit," + ",".join(units) + "\n")
    for stamp, row in data.iterrows():
        cells = [
            "" if v is None or (isinstance(v, float) and np.isnan(v)) else repr(float(v))
            for v in row
        ]
        out.write(f"{stamp}," + ",".join(cells) + "\n")
    return out.getvalue()
