"""One run folder as the app shows it (data-model §2).

Reads the result tables with their unit rows, the balance report (feature-001 dryer reports
are shown as one ``dryer`` entry), the range warnings and the periods of the flag columns.
Values stay SI here; :mod:`boidrytwin.webapp.display_units` converts them for display.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from boidrytwin.webapp.run_index import RunSummary, read_summary

TABLES = ("boiler_results.csv", "results.csv")  # boiler first: shared columns come from it
FLAG_COLUMNS = (
    "heat_limited",
    "condensation_risk",
    "out_of_range",
    "oil_limit",
    "combustion_out_of_range",
    "load_out_of_range",
    "controller_saturated",
    "setpoint_not_reached",
)
DRYER_QUANTITIES = ("dry_solids", "water", "gas", "energy")


@dataclass
class Table:
    frame: pd.DataFrame  # index: UTC times
    units: dict[str, str]


@dataclass
class FlagPeriod:
    table: str
    flag: str
    start: pd.Timestamp
    end: pd.Timestamp


@dataclass
class RunData:
    folder: Path
    summary: RunSummary
    record: dict[str, Any]
    tables: dict[str, Table] = field(default_factory=dict)

    def column_table(self, column: str) -> Table:
        for name in TABLES:
            table = self.tables.get(name)
            if table is not None and column in table.frame.columns:
                return table
        raise KeyError(column)

    def columns(self) -> list[str]:
        seen: list[str] = []
        for name in TABLES:
            if name in self.tables:
                seen += [c for c in self.tables[name].frame.columns if c not in seen]
        return seen

    def balances(self) -> dict[str, Any]:
        report = self.record.get("plant_balance_report") or self.record.get("balance_report")
        if not isinstance(report, dict):
            return {"entries": {}, "passed": None}
        if self.record.get("plant_balance_report"):
            entries = {k: v for k, v in report.items() if isinstance(v, dict)}
        else:  # feature-001 dryer report: quantities at the top level
            entries = {"dryer": {q: report[q] for q in DRYER_QUANTITIES if q in report}}
        return {"entries": entries, "passed": report.get("passed")}

    def warnings(self) -> list[dict[str, Any]]:
        return list(self.record.get("range_warnings") or [])

    def flag_periods(self) -> list[FlagPeriod]:
        out: list[FlagPeriod] = []
        for name, table in self.tables.items():
            for flag in FLAG_COLUMNS:
                if flag not in table.frame.columns:
                    continue
                mask = table.frame[flag].astype(str).str.lower().eq("true").to_numpy()
                if not mask.any():
                    continue
                idx = table.frame.index
                edges = np.flatnonzero(np.diff(np.concatenate([[0], mask.astype(int), [0]])))
                for a, b in zip(edges[::2], edges[1::2], strict=True):
                    out.append(FlagPeriod(name, flag, idx[a], idx[b - 1]))
        return out

    def files(self) -> list[str]:
        return sorted(p.name for p in self.folder.iterdir() if p.is_file())

    def profiles(self) -> Table | None:
        return read_table(self.folder / "profiles.csv")


def read_table(path: Path) -> Table | None:
    """A result CSV with a unit row; ``None`` if missing or unreadable."""
    if not path.is_file():
        return None
    try:
        head = pd.read_csv(path, nrows=1, dtype=str, keep_default_na=False)
        units = {str(k): str(v) for k, v in head.iloc[0].to_dict().items()}
        frame = pd.read_csv(path, skiprows=[1])
        frame["time"] = pd.to_datetime(frame["time"], utc=True)
        frame = frame.set_index("time")
    except (ValueError, KeyError, IndexError, pd.errors.ParserError):
        return None
    units.pop("time", None)
    return Table(frame=frame, units=units)


def load_run(folder: Path) -> RunData:
    summary = read_summary(folder)
    try:
        record = json.loads((folder / "run_record.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = {}
    run = RunData(folder=folder, summary=summary, record=record if isinstance(record, dict) else {})
    for name in TABLES:
        table = read_table(folder / name)
        if table is not None:
            run.tables[name] = table
    return run
