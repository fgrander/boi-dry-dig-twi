"""Load and validate a scenario file (contracts/scenario-file.md).

Every problem is collected and reported together as a :class:`ScenarioValidationError`,
each issue with field, given value, reason, allowed range and file/line.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from boidrytwin.errors import (
    InterfaceValidationError,
    ScenarioValidationError,
    ValidationIssue,
)
from boidrytwin.interface.composition import DRY_KEYS, KEYS, GasComposition
from boidrytwin.interface.flue_gas import FlueGasState, FlueGasSupply, check_state_values
from boidrytwin.interface.sources import ConstantFlueGasSupply, TimeSeriesFlueGasSupply
from boidrytwin.logging import get_logger
from boidrytwin.scenario.schema import (
    OUTPUT_INTERVAL_MAX,
    OUTPUT_INTERVAL_MIN,
    ConstantFlueGasSpec,
    DilutionAirSpec,
    FlueGasSpec,
    ScenarioSpec,
    SignalSpec,
    TimeSeriesFlueGasSpec,
    TimeSettings,
)
from boidrytwin.scenario.timeseries import Signal, TimeSeries, read_timeseries_csv
from boidrytwin.units import QuantityError, parse_quantity

log = get_logger("scenario")

TOP_LEVEL_KEYS = ("schema_version", "name", "time", "flue_gas", "dilution_air")
TIME_KEYS = ("start", "end", "output_interval", "rtol", "atol")
FLUE_COMMON_KEYS = ("source", "composition_basis", "composition_type", "pressure_reference")
FLUE_CONSTANT_KEYS = (*FLUE_COMMON_KEYS, "mass_flow", "temperature", "pressure", *KEYS, "x_H2O_wet")
FLUE_SERIES_KEYS = (*FLUE_COMMON_KEYS, "file", "max_gap", "allow_gaps", "stale_after")
DILUTION_KEYS = ("mass_flow",)

DEFAULT_MAX_GAP = 300.0  # s
DEFAULT_STALE_AFTER = 900.0  # s

Check = Callable[[float], tuple[str, str] | None]


@dataclass
class LoadedScenario:
    """A validated scenario: normalised spec plus the input objects built from it."""

    path: Path
    spec: ScenarioSpec
    flue_gas: FlueGasSupply
    signals: dict[str, Signal] = field(default_factory=dict)
    input_files: dict[str, str] = field(default_factory=dict)  # path -> sha256


def load_scenario(path: str | Path) -> LoadedScenario:
    """Load, validate and normalise a scenario file. Raises ScenarioValidationError."""
    reader = _Reader(Path(path))
    try:
        loaded = reader.load()
    except ScenarioValidationError as exc:
        log.warning("scenario_rejected", file=str(path), issues=len(exc.issues))
        raise
    log.info(
        "scenario_validated",
        file=str(path),
        issues=0,
        flue_gas_source=loaded.flue_gas.source_id,
        input_files=len(loaded.input_files),
    )
    return loaded


class _Reader:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.label = path.name
        self.lines: list[str] = []
        self.issues: list[ValidationIssue] = []
        self.input_files: dict[str, str] = {}

    # --- reporting ----------------------------------------------------------------

    def locate(self, section: str, key: str | None = None) -> str:
        header = re.compile(rf"^\s*\[\s*{re.escape(section)}\s*\]") if section else None
        start = 0
        if header is not None:
            for i, line in enumerate(self.lines):
                if header.match(line):
                    start = i
                    break
            else:
                return self.label
            if key is None:
                return f"{self.label}:line {start + 1}"
        pattern = re.compile(rf"^\s*{re.escape(key or '')}\s*=")
        for i in range(start + (1 if header else 0), len(self.lines)):
            if header is not None and i > start and self.lines[i].lstrip().startswith("["):
                break
            if pattern.match(self.lines[i]):
                return f"{self.label}:line {i + 1}"
        return f"{self.label}:line {start + 1}" if header else self.label

    def add(
        self, fieldname: str, value: object, reason: str, allowed: str, location: str | None
    ) -> None:
        self.issues.append(
            ValidationIssue(
                field=fieldname, value=str(value), reason=reason, allowed=allowed, location=location
            )
        )

    def add_issues(self, issues: list[ValidationIssue], location: str | None = None) -> None:
        for issue in issues:
            self.issues.append(
                issue
                if issue.location or location is None
                else issue.model_copy(update={"location": location})
            )

    def unknown_keys(
        self, table: Mapping[str, Any], section: str, allowed: tuple[str, ...]
    ) -> None:
        for key in table:
            if key not in allowed:
                name = f"{section}.{key}" if section else key
                where = self.locate(section, key) if section else self.locate(key)
                if not section and isinstance(table[key], dict):
                    where = self.locate(key)
                self.add(name, key, "unknown key", "one of: " + ", ".join(allowed), where)

    # --- typed reads ----------------------------------------------------------------

    def quantity(
        self,
        table: Mapping[str, Any],
        section: str,
        key: str,
        dimension: str,
        *,
        default: float | None = None,
        check: Check | None = None,
        gauge_reference: float | None = None,
    ) -> float | None:
        where = self.locate(section, key)
        if key not in table:
            if default is None:
                self.add(f"{section}.{key}", "", "required", f"a {dimension} value", where)
            return default
        raw = table[key]
        try:
            value = parse_quantity(raw, dimension, gauge_reference=gauge_reference)
        except QuantityError as exc:
            self.add(f"{section}.{key}", raw, exc.reason, exc.allowed, where)
            return None
        if check is not None and (problem := check(value)) is not None:
            self.add(f"{section}.{key}", raw, problem[0], problem[1], where)
            return None
        return value

    def choice(
        self,
        table: Mapping[str, Any],
        section: str,
        key: str,
        options: tuple[str, ...],
        default: str,
    ) -> str:
        value = table.get(key, default)
        if value not in options:
            self.add(
                f"{section}.{key}",
                value,
                "invalid value",
                " | ".join(options),
                self.locate(section, key),
            )
            return default
        return str(value)

    def timestamp(self, table: Mapping[str, Any], section: str, key: str) -> datetime | None:
        where = self.locate(section, key)
        raw = table.get(key)
        if raw is None:
            self.add(f"{section}.{key}", "", "required", "ISO 8601 timestamp with timezone", where)
            return None
        if isinstance(raw, datetime):
            stamp = raw
        else:
            try:
                stamp = datetime.fromisoformat(str(raw))
            except ValueError:
                self.add(
                    f"{section}.{key}", raw, "invalid timestamp", "ISO 8601 with timezone", where
                )
                return None
        if stamp.tzinfo is None:
            self.add(
                f"{section}.{key}", raw, "timezone required", "ISO 8601 with Z or offset", where
            )
            return None
        return stamp.astimezone(UTC)

    def series_file(self, name: str, section: str, key: str) -> Path | None:
        path = (self.path.parent / name).resolve()
        if not path.is_file():
            self.add(
                f"{section}.{key}",
                name,
                "file not found",
                "an existing CSV file",
                self.locate(section, key),
            )
            return None
        return path

    # --- sections --------------------------------------------------------------------

    def load(self) -> LoadedScenario:
        if not self.path.is_file():
            self.add("scenario", str(self.path), "file not found", "an existing TOML file", None)
            raise ScenarioValidationError(self.issues)
        text = self.path.read_text(encoding="utf-8")
        self.lines = text.splitlines()
        try:
            doc = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            self.add("scenario", self.label, f"invalid TOML: {exc}", "valid TOML", self.label)
            raise ScenarioValidationError(self.issues) from None

        self.unknown_keys(doc, "", TOP_LEVEL_KEYS)
        if doc.get("schema_version", 1) != 1:
            self.add(
                "schema_version",
                doc["schema_version"],
                "unsupported",
                "1",
                self.locate("", "schema_version"),
            )
        name = str(doc.get("name", self.path.stem))

        time = self.time_section(_table(doc, "time"))
        flue_gas_spec, supply = self.flue_gas_section(_table(doc, "flue_gas"), time)
        dilution_spec, signals = self.dilution_section(_table(doc, "dilution_air"), time)

        if self.issues:
            raise ScenarioValidationError(self.issues)
        assert time is not None and flue_gas_spec is not None and supply is not None
        spec = ScenarioSpec(
            schema_version=1,
            name=name,
            time=time,
            flue_gas=flue_gas_spec,
            dilution_air=dilution_spec,
        )
        return LoadedScenario(
            path=self.path,
            spec=spec,
            flue_gas=supply,
            signals=signals,
            input_files=self.input_files,
        )

    def time_section(self, table: Mapping[str, Any]) -> TimeSettings | None:
        self.unknown_keys(table, "time", TIME_KEYS)
        start = self.timestamp(table, "time", "start")
        end = self.timestamp(table, "time", "end")
        interval = self.quantity(
            table,
            "time",
            "output_interval",
            "time",
            default=60.0,
            check=lambda v: (
                None
                if OUTPUT_INTERVAL_MIN <= v <= OUTPUT_INTERVAL_MAX
                else ("out of range", "1 s – 1 h")
            ),
        )
        if start and end and end <= start:
            self.add(
                "time.end",
                table.get("end"),
                "must be after time.start",
                "end > start",
                self.locate("time", "end"),
            )
            return None
        if start is None or end is None or interval is None:
            return None
        kwargs: dict[str, float] = {}
        for key in ("rtol", "atol"):
            if key in table:
                value = self.quantity(
                    table,
                    "time",
                    key,
                    "dimensionless",
                    check=lambda v: None if v > 0 else ("must be > 0", "> 0"),
                )
                if value is not None:
                    kwargs[key] = value
        return TimeSettings(start=start, end=end, output_interval=interval, **kwargs)

    def flue_gas_section(
        self, table: Mapping[str, Any], time: TimeSettings | None
    ) -> tuple[FlueGasSpec | None, FlueGasSupply | None]:
        section = "flue_gas"
        source = self.choice(table, section, "source", ("constant", "timeseries"), "constant")
        if "source" not in table:
            self.add(
                "flue_gas.source", "", "required", "constant | timeseries", self.locate(section)
            )
            return None, None
        allowed = FLUE_CONSTANT_KEYS if source == "constant" else FLUE_SERIES_KEYS
        self.unknown_keys(table, section, allowed)
        basis = self.choice(table, section, "composition_basis", ("wet", "dry"), "wet")
        ftype = self.choice(table, section, "composition_type", ("mole", "mass"), "mole")
        reference = (
            self.quantity(table, section, "pressure_reference", "pressure")
            if "pressure_reference" in table
            else None
        )
        if source == "constant":
            return self.constant_flue_gas(table, time, basis, ftype, reference)
        return self.timeseries_flue_gas(table, time, basis, ftype, reference)

    def constant_flue_gas(
        self,
        table: Mapping[str, Any],
        time: TimeSettings | None,
        basis: str,
        ftype: str,
        reference: float | None,
    ) -> tuple[FlueGasSpec | None, FlueGasSupply | None]:
        section = "flue_gas"
        values = {
            "mass_flow": self.quantity(table, section, "mass_flow", "mass_flow"),
            "temperature": self.quantity(table, section, "temperature", "temperature"),
            "pressure": self.quantity(
                table, section, "pressure", "pressure", gauge_reference=reference
            ),
        }
        for fieldname, reason, allowed in check_state_values(
            mass_flow=values["mass_flow"] if values["mass_flow"] is not None else 0.0,
            temperature=values["temperature"] if values["temperature"] is not None else 300.0,
            pressure=values["pressure"] if values["pressure"] is not None else 101_325.0,
        ):
            self.add(
                f"{section}.{fieldname}",
                table.get(fieldname),
                reason,
                allowed,
                self.locate(section, fieldname),
            )
            values[fieldname] = None

        keys = DRY_KEYS if basis == "dry" else KEYS
        fractions: dict[str, float] = {}
        ok = True
        for key in keys:
            if key in table:
                value = self.quantity(table, section, key, "fraction")
                if value is None:
                    ok = False
                else:
                    fractions[key] = value
        water_wet = None
        if basis == "dry" and "x_H2O_wet" in table:
            water_wet = self.quantity(table, section, "x_H2O_wet", "fraction")
        composition = None
        if ok:
            try:
                composition = GasComposition.from_input(
                    fractions,
                    basis=basis,  # type: ignore[arg-type]
                    fraction_type=ftype,  # type: ignore[arg-type]
                    water_wet=water_wet,
                    location=self.locate(section),
                )
            except InterfaceValidationError as exc:
                self.add_issues(exc.issues)

        if time is None or composition is None or any(v is None for v in values.values()):
            return None, None
        state = FlueGasState(
            time=time.start,
            mass_flow=values["mass_flow"],
            temperature=values["temperature"],
            pressure=values["pressure"],
            composition=composition,
        )
        spec = ConstantFlueGasSpec(
            mass_flow=state.mass_flow,
            temperature=state.temperature,
            pressure=state.pressure,
            composition=composition.as_tuple(),
        )
        return spec, ConstantFlueGasSupply(state, start=time.start)

    def timeseries_flue_gas(
        self,
        table: Mapping[str, Any],
        time: TimeSettings | None,
        basis: str,
        ftype: str,
        reference: float | None,
    ) -> tuple[FlueGasSpec | None, FlueGasSupply | None]:
        section = "flue_gas"
        max_gap = self.quantity(table, section, "max_gap", "time", default=DEFAULT_MAX_GAP)
        stale_after = self.quantity(
            table, section, "stale_after", "time", default=DEFAULT_STALE_AFTER
        )
        allow_gaps = table.get("allow_gaps", False)
        if not isinstance(allow_gaps, bool):
            self.add(
                "flue_gas.allow_gaps",
                allow_gaps,
                "invalid value",
                "true | false",
                self.locate(section, "allow_gaps"),
            )
            allow_gaps = False
        if "file" not in table:
            self.add("flue_gas.file", "", "required", "path of a CSV file", self.locate(section))
            return None, None
        path = self.series_file(str(table["file"]), section, "file")
        if path is None or time is None or max_gap is None or stale_after is None:
            return None, None

        fraction_keys = [*DRY_KEYS, "x_H2O_wet"] if basis == "dry" else list(KEYS)
        columns = {
            "mass_flow": "mass_flow",
            "temperature": "temperature",
            "pressure": "pressure",
            **{k: "fraction" for k in fraction_keys},
        }
        try:
            series = read_timeseries_csv(
                path,
                columns,
                field_prefix="flue_gas.",
                stale_columns=("mass_flow", "temperature"),
                stale_after=stale_after,
            )
        except ScenarioValidationError as exc:
            self.add_issues(exc.issues)
            return None, None
        self.input_files[str(path)] = series.sha256

        frame = self._wet_mole_frame(series, basis, ftype, reference)
        if frame is None:
            return None, None
        try:
            supply = TimeSeriesFlueGasSupply(
                frame,
                start=time.start,
                max_gap=max_gap,
                allow_gaps=allow_gaps,
                file_label=path.name,
                source_id=f"timeseries:{series.sha256[:12]}",
            )
        except InterfaceValidationError as exc:
            self.add_issues(exc.issues)
            return None, None
        if not supply.covers(0.0, time.duration):
            self.add(
                "flue_gas.file",
                path.name,
                f"does not cover the scenario period {time.start.isoformat()} – "
                f"{time.end.isoformat()}",
                "samples from time.start to time.end",
                self.locate(section, "file"),
            )
            return None, None
        spec = TimeSeriesFlueGasSpec(
            file=str(table["file"]),
            sha256=series.sha256,
            max_gap=max_gap,
            allow_gaps=allow_gaps,
            stale_after=stale_after,
            composition_basis=basis,
            composition_type=ftype,
            pressure_reference=reference,
        )
        return spec, supply

    def _wet_mole_frame(
        self, series: TimeSeries, basis: str, ftype: str, reference: float | None
    ) -> pd.DataFrame | None:
        """Convert composition columns row by row to normalised wet mole fractions."""
        frame = series.frame.copy()
        if reference is not None:
            frame["pressure"] = frame["pressure"] + reference
        keys = DRY_KEYS if basis == "dry" else KEYS
        out = {k: [] for k in KEYS}  # type: dict[str, list[float]]
        before = len(self.issues)
        for row_number, (_, row) in enumerate(frame.iterrows()):
            if row["quality"] in ("missing", "bad") or row[list(keys)].isna().any():
                for k in KEYS:
                    out[k].append(float("nan"))
                continue
            try:
                comp = GasComposition.from_input(
                    {k: float(row[k]) for k in keys},
                    basis=basis,  # type: ignore[arg-type]
                    fraction_type=ftype,  # type: ignore[arg-type]
                    water_wet=float(row["x_H2O_wet"]) if basis == "dry" else None,
                    location=f"{series.path.name}:line {row_number + 3}",
                )
            except InterfaceValidationError as exc:
                self.add_issues(exc.issues)
                for k in KEYS:
                    out[k].append(float("nan"))
                continue
            for k, v in zip(KEYS, comp.as_tuple(), strict=True):
                out[k].append(v)
        if len(self.issues) > before:
            return None
        for k in KEYS:
            frame[k] = out[k]
        return frame

    def signal(
        self,
        table: Mapping[str, Any],
        section: str,
        key: str,
        dimension: str,
        time: TimeSettings | None,
        *,
        default: float | None = None,
        check: Check | None = None,
    ) -> tuple[SignalSpec | None, Signal | None]:
        """Read an input that is a constant quantity or ``{ file = ..., column = ... }``."""
        name = f"{section}.{key}"
        raw = table.get(key)
        if isinstance(raw, dict):
            unknown = set(raw) - {"file", "column"}
            if unknown or "file" not in raw or "column" not in raw:
                self.add(
                    name,
                    raw,
                    "invalid time series reference",
                    "{ file = ..., column = ... }",
                    self.locate(section, key),
                )
                return None, None
            path = self.series_file(str(raw["file"]), section, key)
            if path is None or time is None:
                return None, None
            try:
                series = read_timeseries_csv(
                    path, {raw["column"]: dimension}, field_prefix=f"{name}."
                )
            except ScenarioValidationError as exc:
                self.add_issues(exc.issues)
                return None, None
            self.input_files[str(path)] = series.sha256
            sig = Signal.from_series(name, series, raw["column"], time.start)
            if check is not None:
                for v in sig.all_values():
                    if (problem := check(float(v))) is not None:
                        self.add(name, f"{v:g}", problem[0], problem[1], path.name)
                        return None, None
            if not sig.covers(0.0, time.duration):
                self.add(
                    name,
                    path.name,
                    f"time series does not cover the scenario period {time.start.isoformat()} – "
                    f"{time.end.isoformat()}",
                    "samples from time.start to time.end",
                    self.locate(section, key),
                )
                return None, None
            spec = SignalSpec(
                file=str(raw["file"]), column=str(raw["column"]), sha256=series.sha256
            )
            return spec, sig
        value = self.quantity(table, section, key, dimension, default=default, check=check)
        if value is None:
            return None, None
        return SignalSpec(constant=value), Signal(name=name, constant=value)

    def dilution_section(
        self, table: Mapping[str, Any], time: TimeSettings | None
    ) -> tuple[DilutionAirSpec, dict[str, Signal]]:
        self.unknown_keys(table, "dilution_air", DILUTION_KEYS)
        spec, sig = self.signal(
            table,
            "dilution_air",
            "mass_flow",
            "mass_flow",
            time,
            default=0.0,
            check=lambda v: None if v >= 0 else ("must be ≥ 0", "≥ 0 kg/s"),
        )
        signals = {"dilution_air.mass_flow": sig} if sig is not None else {}
        return DilutionAirSpec(mass_flow=spec or SignalSpec(constant=0.0)), signals


def _table(doc: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = doc.get(key, {})
    return value if isinstance(value, dict) else {}
