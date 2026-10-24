"""Time series CSV input (contracts/scenario-file.md § Time series CSV).

Format: first row column names, second row units (first cell ``unit``), then data rows.
``time`` is ISO 8601 with a timezone and is converted to UTC; timestamps must be strictly
increasing. An optional ``quality`` column holds ``good`` | ``missing`` | ``bad``; empty
cells are ``missing``. Values unchanged for longer than ``stale_after`` in the listed
columns are marked ``stale`` (FR-015). Values are converted to SI.
"""

from __future__ import annotations

import csv
import hashlib
import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from boidrytwin.errors import ScenarioValidationError, ValidationIssue
from boidrytwin.properties.gas import FloatArray
from boidrytwin.units import QuantityError, parse_quantity

QUALITY_INPUT = ("good", "missing", "bad")
FIRST_DATA_LINE = 3


@dataclass(frozen=True)
class TimeSeries:
    """A validated time series in SI units with a UTC index and a ``quality`` column."""

    path: Path
    sha256: str
    frame: pd.DataFrame
    units: dict[str, str]

    def seconds_since(self, start: datetime) -> FloatArray:
        index = pd.DatetimeIndex(self.frame.index)
        return np.asarray((index - pd.Timestamp(start)).total_seconds(), dtype=float)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_timeseries_csv(
    path: Path,
    columns: Mapping[str, str],
    *,
    field_prefix: str = "",
    stale_columns: Collection[str] = (),
    stale_after: float | None = None,
) -> TimeSeries:
    """Read and validate a time series CSV; ``columns`` maps column name to dimension.

    Raises :class:`ScenarioValidationError` with every issue found.
    """
    label = path.name
    issues: list[ValidationIssue] = []

    def add(fieldname: str, value: object, reason: str, allowed: str, line: int | None) -> None:
        issues.append(
            ValidationIssue(
                field=f"{field_prefix}{fieldname}",
                value=str(value),
                reason=reason,
                allowed=allowed,
                location=f"{label}:line {line}" if line else label,
            )
        )

    if not path.is_file():
        add("file", str(path), "file not found", "an existing CSV file", None)
        raise ScenarioValidationError(issues)

    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.reader(handle) if any(cell.strip() for cell in row)]
    if len(rows) < 2 or not rows[1] or rows[1][0].strip().lower() != "unit":
        add("file", label, "second row must hold the units", "row 2 starting with 'unit'", 2)
        raise ScenarioValidationError(issues)

    header = [h.strip() for h in rows[0]]
    unit_row = [u.strip() for u in rows[1]] + [""] * len(header)
    data = rows[2:]
    if "time" not in header:
        add("time", "", "required", "a 'time' column", 1)

    converters: dict[str, tuple[float, float]] = {}
    for name, dimension in columns.items():
        if name not in header:
            add(name, "", "required", f"a '{name}' column", 1)
            continue
        unit = unit_row[header.index(name)]
        if not unit:
            add(name, "", "unit missing", "a unit in row 2", 2)
            continue
        try:
            offset = parse_quantity(f"0 {unit}", dimension)
            scale = parse_quantity(f"1 {unit}", dimension) - offset
        except QuantityError as exc:
            add(name, unit, exc.reason, exc.allowed, 2)
            continue
        converters[name] = (scale, offset)
    if not data:
        add("file", label, "no data rows", "at least one data row", FIRST_DATA_LINE)
    if issues:
        raise ScenarioValidationError(issues)

    i_time = header.index("time")
    i_quality = header.index("quality") if "quality" in header else None
    times: list[datetime] = []
    values: dict[str, list[float]] = {name: [] for name in converters}
    quality: list[str] = []

    for n, row in enumerate(data):
        line = n + FIRST_DATA_LINE
        cells = [c.strip() for c in row] + [""] * len(header)
        stamp = _parse_time(cells[i_time])
        if stamp is None:
            add("time", cells[i_time], "invalid timestamp", "ISO 8601 with timezone", line)
        elif stamp.tzinfo is None:
            add("time", cells[i_time], "timezone required", "ISO 8601 with Z or an offset", line)
        else:
            stamp = stamp.astimezone(UTC)
            if times and stamp <= times[-1]:
                add(
                    "time",
                    cells[i_time],
                    f"timestamps not strictly increasing: {stamp.isoformat()} "
                    f"after {times[-1].isoformat()}",
                    "strictly increasing timestamps",
                    line,
                )
            times.append(stamp)

        row_quality = "good"
        if i_quality is not None and cells[i_quality]:
            row_quality = cells[i_quality].lower()
            if row_quality not in QUALITY_INPUT:
                add("quality", cells[i_quality], "invalid quality", " | ".join(QUALITY_INPUT), line)
        for name, (scale, offset) in converters.items():
            cell = cells[header.index(name)]
            if not cell:
                values[name].append(math.nan)
                if row_quality == "good":
                    row_quality = "missing"
                continue
            try:
                number = float(cell)
            except ValueError:
                add(name, cell, "not a number", "a number", line)
                number = math.nan
            values[name].append(scale * number + offset)
        quality.append(row_quality)

    if issues:
        raise ScenarioValidationError(issues)

    frame = pd.DataFrame(values, index=pd.DatetimeIndex(times, name="time"))
    frame["quality"] = quality
    if stale_after is not None:
        _flag_stale(frame, [c for c in stale_columns if c in converters], stale_after)
    units = {name: unit_row[header.index(name)] for name in converters}
    return TimeSeries(path=path, sha256=sha256_of(path), frame=frame, units=units)


def _parse_time(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _flag_stale(frame: pd.DataFrame, columns: list[str], stale_after: float) -> None:
    seconds = np.asarray(
        (pd.DatetimeIndex(frame.index) - frame.index[0]).total_seconds(), dtype=float
    )
    quality = frame["quality"].to_numpy(dtype=object)
    for column in columns:
        vals = frame[column].to_numpy(dtype=float)
        run_start = 0
        for i in range(1, len(vals)):
            if vals[i] != vals[run_start]:
                run_start = i
                continue
            if seconds[i] - seconds[run_start] > stale_after and quality[i] == "good":
                quality[i] = "stale"
    frame["quality"] = quality


@dataclass(frozen=True)
class Signal:
    """A scalar input that is either constant or a time series (SI, seconds since start)."""

    name: str
    constant: float | None = None
    times: FloatArray | None = None
    values: FloatArray | None = None
    source: str = "constant"
    sha256: str | None = None
    excluded: int = field(default=0)

    @classmethod
    def from_series(cls, name: str, series: TimeSeries, column: str, start: datetime) -> Signal:
        t = series.seconds_since(start)
        v = series.frame[column].to_numpy(dtype=float)
        q = series.frame["quality"].to_numpy(dtype=object)
        ok = ~np.isnan(v) & (q != "bad") & (q != "missing")
        return cls(
            name=name,
            times=t[ok],
            values=v[ok],
            source=f"{series.path.name}:{column}",
            sha256=series.sha256,
            excluded=int((~ok).sum()),
        )

    def value_at(self, t: float) -> float:
        if self.constant is not None:
            return self.constant
        assert self.times is not None and self.values is not None
        return float(np.interp(t, self.times, self.values))

    def values_at(self, t: FloatArray) -> FloatArray:
        if self.constant is not None:
            return np.full(np.shape(t), self.constant)
        assert self.times is not None and self.values is not None
        return np.asarray(np.interp(t, self.times, self.values))

    def covers(self, t_start: float, t_end: float) -> bool:
        if self.constant is not None:
            return True
        assert self.times is not None
        return len(self.times) > 0 and self.times[0] <= t_start and self.times[-1] >= t_end

    def all_values(self) -> FloatArray:
        if self.constant is not None:
            return np.array([self.constant])
        assert self.values is not None
        return self.values
