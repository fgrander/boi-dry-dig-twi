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

from boidrytwin.dryer.config import FIELDS as DRYER_FIELDS
from boidrytwin.dryer.config import GROUPS as DRYER_GROUPS
from boidrytwin.dryer.config import DryerConfiguration, FieldSpec, RangeViolation
from boidrytwin.dryer.state import DryerState
from boidrytwin.errors import (
    InterfaceValidationError,
    ScenarioValidationError,
    ValidationIssue,
)
from boidrytwin.interface.composition import DRY_KEYS, KEYS, GasComposition
from boidrytwin.interface.flue_gas import FlueGasState, FlueGasSupply, check_state_values
from boidrytwin.interface.sources import (
    ConstantFlueGasSupply,
    ExternallySetFlueGasSupply,
    TimeSeriesFlueGasSupply,
)
from boidrytwin.logging import get_logger
from boidrytwin.scenario.schema import (
    OUTPUT_INTERVAL_MAX,
    OUTPUT_INTERVAL_MIN,
    AmbientSpec,
    BalanceTolerances,
    BoilerFlueGasSpec,
    ConstantFlueGasSpec,
    DilutionAirSpec,
    FlueGasSpec,
    InitialStateSpec,
    ProductFeedSpec,
    ScenarioSpec,
    SignalSpec,
    TimeSeriesFlueGasSpec,
    TimeSettings,
)
from boidrytwin.scenario.timeseries import Signal, TimeSeries, read_timeseries_csv, sha256_of
from boidrytwin.units import QuantityError, parse_quantity

log = get_logger("scenario")

TOP_LEVEL_KEYS = (
    "schema_version",
    "name",
    "time",
    "flue_gas",
    "dilution_air",
    "product_feed",
    "ambient",
    "dryer",
    "initial_state",
    "balance_tolerances",
    "boiler_house",
)
TIME_KEYS = ("start", "end", "output_interval", "rtol", "atol")
FLUE_COMMON_KEYS = ("source", "composition_basis", "composition_type", "pressure_reference")
FLUE_CONSTANT_KEYS = (*FLUE_COMMON_KEYS, "mass_flow", "temperature", "pressure", *KEYS, "x_H2O_wet")
FLUE_SERIES_KEYS = (*FLUE_COMMON_KEYS, "file", "max_gap", "allow_gaps", "stale_after")
DILUTION_KEYS = ("mass_flow",)
FEED_KEYS = ("mass_flow_wet", "moisture_wet_basis", "temperature")
AMBIENT_KEYS = ("temperature", "relative_humidity", "pressure")
INITIAL_KEYS = ("kind", "file")
TOLERANCE_KEYS = ("mass", "energy")
DRYER_KEYS = {
    group: tuple(name for name, f in DRYER_FIELDS.items() if f.group == group)
    + (("gas_flow_direction",) if group == "operation" else ())
    for group in DRYER_GROUPS
}

# data-model.md §2 rules for time-varying inputs: dimension, lower, upper, upper inclusive
Rule = tuple[str, float, float, bool, str]
FEED_RULES: dict[str, Rule] = {
    "mass_flow_wet": ("mass_flow", 0.0, float("inf"), True, "≥ 0 kg/s"),
    "moisture_wet_basis": ("fraction", 0.0, 0.75, False, "0 ≤ w < 0.75"),
    "temperature": ("temperature", 253.15, 333.15, True, "253.15-333.15 K (-20 to 60 °C)"),
}
AMBIENT_RULES: dict[str, Rule] = {
    "temperature": ("temperature", 233.15, 323.15, True, "233.15-323.15 K"),
    "relative_humidity": ("fraction", 0.0, 1.0, True, "0-1"),
    "pressure": ("pressure", 80_000.0, 110_000.0, True, "80-110 kPa"),
}


def _range_check(lo: float, hi: float, hi_inclusive: bool, allowed: str) -> Check:
    def check(v: float) -> tuple[str, str] | None:
        if lo <= v and (v <= hi if hi_inclusive else v < hi):
            return None
        return ("must be ≥ 0" if lo == 0.0 and hi == float("inf") else "out of range", allowed)

    return check


def _physical_check(spec: FieldSpec) -> Check:
    lo, hi = spec.physical
    bracket = "[" if spec.lower_inclusive else "("

    def check(v: float) -> tuple[str, str] | None:
        ok = (v >= lo if spec.lower_inclusive else v > lo) and v <= hi
        return None if ok else ("outside physical range", f"{bracket}{lo:g}, {hi:g}] (SI)")

    return check


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
    initial_state: DryerState | None = None
    config_warnings: list[RangeViolation] = field(default_factory=list)


def require_runnable(loaded: LoadedScenario) -> None:
    """A run needs the product feed, ambient conditions and the dryer configuration.

    A boiler-house-only scenario (feature 002) needs only the ambient conditions.
    """
    sections: tuple[tuple[str, object], ...] = (
        ("product_feed", loaded.spec.product_feed),
        ("ambient", loaded.spec.ambient),
        ("dryer", loaded.spec.dryer),
    )
    if loaded.spec.boiler_house is not None and loaded.spec.dryer is None:
        sections = (("ambient", loaded.spec.ambient),)
    missing = [name for name, value in sections if value is None]
    if missing:
        raise ScenarioValidationError(
            ValidationIssue(
                field=name,
                value="",
                reason="required for run",
                allowed="[dryer.*] sections" if name == "dryer" else f"a [{name}] section",
                location=loaded.path.name,
            )
            for name in missing
        )


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
        flue_gas_spec: FlueGasSpec | None
        supply: FlueGasSupply | None
        if "boiler_house" in doc:
            flue_gas_spec, supply = self.boiler_flue_gas(doc, time)
        else:
            flue_gas_spec, supply = self.flue_gas_section(_table(doc, "flue_gas"), time)
        dilution_spec, signals = self.dilution_section(_table(doc, "dilution_air"), time)
        from boidrytwin.scenario.boiler_sections import read_boiler_house

        boiler_house = read_boiler_house(self, doc, time, signals)
        feed = self.signal_section(doc, "product_feed", FEED_KEYS, FEED_RULES, time, signals)
        ambient = self.signal_section(doc, "ambient", AMBIENT_KEYS, AMBIENT_RULES, time, signals)
        dryer = self.dryer_section(doc.get("dryer"))
        initial_spec, initial_state = self.initial_section(_table(doc, "initial_state"), dryer)
        tolerances = self.tolerance_section(_table(doc, "balance_tolerances"))
        if isinstance(flue_gas_spec, BoilerFlueGasSpec):
            self.coupled_rules(doc, boiler_house, dryer)

        if self.issues:
            raise ScenarioValidationError(self.issues)
        assert time is not None and supply is not None
        if boiler_house is not None and isinstance(supply, ExternallySetFlueGasSupply):
            supply.input_breakpoints = _signal_breakpoints(signals, "boiler_house.")
        spec = ScenarioSpec(
            schema_version=1,
            name=name,
            time=time,
            flue_gas=flue_gas_spec,
            dilution_air=dilution_spec,
            product_feed=ProductFeedSpec(**feed) if feed else None,
            ambient=AmbientSpec(**ambient) if ambient else None,
            dryer=dryer,
            initial_state=initial_spec,
            balance_tolerances=tolerances,
            boiler_house=boiler_house,
        )
        return LoadedScenario(
            path=self.path,
            spec=spec,
            flue_gas=supply,
            signals=signals,
            input_files=self.input_files,
            initial_state=initial_state,
            config_warnings=(dryer.validated_range_violations() if dryer else [])
            + (boiler_house.config.validated_range_violations() if boiler_house else []),
        )

    def coupled_rules(
        self, doc: Mapping[str, Any], boiler_house: Any, dryer: DryerConfiguration | None
    ) -> None:
        """Rules of a coupled run: flue_gas.source = "boiler_house" (feature 002, T053)."""
        if dryer is None:
            self.add("dryer", "", "required for a coupled run", "[dryer.*] sections",
                     self.locate("flue_gas", "source"))  # fmt: skip
        if "dilution_air" in doc:
            self.add("dilution_air", "", "dilution air is set by the drum inlet controller",
                     "remove [dilution_air]; set the drum inlet loop's max_dilution_air",
                     self.locate("dilution_air"))  # fmt: skip
        if boiler_house is None:
            return
        drum = boiler_house.controllers.drum_inlet_temperature
        loop = "boiler_house.controllers.drum_inlet_temperature"
        if drum is None:
            self.add(loop, "", "required for a coupled run", "a drum inlet controller section",
                     self.locate("boiler_house"))  # fmt: skip
        elif drum.max_dilution_air is None:
            self.add(f"{loop}.max_dilution_air", "", "required for a coupled run", "> 0 kg/s",
                     self.locate(loop))  # fmt: skip

    def boiler_flue_gas(
        self, doc: Mapping[str, Any], time: TimeSettings | None
    ) -> tuple[FlueGasSpec | None, FlueGasSupply | None]:
        """Flue gas of a scenario with a [boiler_house] section (feature 002)."""
        table = doc.get("flue_gas")
        start = time.start if time is not None else datetime(2000, 1, 1, tzinfo=UTC)
        supply = ExternallySetFlueGasSupply(start=start)
        if table is None:
            return None, supply  # boiler-house-only run
        if not isinstance(table, dict) or table.get("source") != "boiler_house":
            self.add(
                "flue_gas.source",
                table.get("source", "") if isinstance(table, dict) else table,
                "ambiguous: [boiler_house] together with a flue gas source",
                'source = "boiler_house" or remove [boiler_house]',
                self.locate("flue_gas", "source"),
            )
            return None, supply
        self.unknown_keys(table, "flue_gas", ("source",))
        return BoilerFlueGasSpec(), supply

    def signal_section(
        self,
        doc: Mapping[str, Any],
        section: str,
        keys: tuple[str, ...],
        rules: Mapping[str, Rule],
        time: TimeSettings | None,
        signals: dict[str, Signal],
    ) -> dict[str, SignalSpec] | None:
        """A section whose values are each a constant or a time series column."""
        if section not in doc:
            return None
        table = _table(doc, section)
        self.unknown_keys(table, section, keys)
        specs: dict[str, SignalSpec] = {}
        for key in keys:
            dimension, lo, hi, hi_inclusive, allowed = rules[key]
            if key not in table:
                self.add(f"{section}.{key}", "", "required", allowed, self.locate(section))
                continue
            check = _range_check(lo, hi, hi_inclusive, allowed)
            spec, sig = self.signal(table, section, key, dimension, time, check=check)
            if spec is not None and sig is not None:
                specs[key] = spec
                signals[f"{section}.{key}"] = sig
        return specs if len(specs) == len(keys) else None

    def dryer_section(self, raw: object) -> DryerConfiguration | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            self.add("dryer", raw, "invalid value", "[dryer.*] tables", self.locate("dryer"))
            return None
        self.unknown_keys(raw, "dryer", DRYER_GROUPS)
        values: dict[str, Any] = {}
        before = len(self.issues)
        for group in DRYER_GROUPS:
            table = _table(raw, group)
            section = f"dryer.{group}"
            self.unknown_keys(table, section, DRYER_KEYS[group])
            for key in DRYER_KEYS[group]:
                if key == "gas_flow_direction":
                    if key in table:
                        values[key] = self.choice(
                            table, section, key, ("co-current",), "co-current"
                        )
                    continue
                spec = DRYER_FIELDS[key]
                if key not in table:
                    if spec.default is None:
                        allowed = f"a {spec.dimension} value"
                        self.add(f"{section}.{key}", "", "required", allowed, self.locate(section))
                    continue
                value = self.quantity(
                    table, section, key, spec.dimension, check=_physical_check(spec)
                )
                if value is None:
                    continue
                if key == "n_cells":
                    if value != int(value):
                        where = self.locate(section, key)
                        self.add(
                            f"{section}.{key}", table[key], "must be an integer", "10-40", where
                        )
                        continue
                    value = int(value)
                values[key] = value
        if len(self.issues) > before:
            return None
        return DryerConfiguration(**values)

    def initial_section(
        self, table: Mapping[str, Any], dryer: DryerConfiguration | None
    ) -> tuple[InitialStateSpec, DryerState | None]:
        section = "initial_state"
        self.unknown_keys(table, section, INITIAL_KEYS)
        kinds = ("cold_empty", "steady_state", "explicit")
        kind = self.choice(table, section, "kind", kinds, "cold_empty")
        if kind != "explicit":
            return InitialStateSpec(kind=kind), None
        if "file" not in table:
            allowed = "final_state.json of an earlier run"
            self.add("initial_state.file", "", "required", allowed, self.locate(section))
            return InitialStateSpec(kind="explicit"), None
        path = (self.path.parent / str(table["file"])).resolve()
        where = self.locate(section, "file")
        if not path.is_file():
            self.add(
                "initial_state.file",
                table["file"],
                "file not found",
                "an existing JSON file",
                where,
            )
            return InitialStateSpec(kind="explicit"), None
        try:
            state = DryerState.load(path)
        except (ValueError, KeyError) as exc:
            self.add(
                "initial_state.file",
                table["file"],
                f"invalid state: {exc}",
                "final_state.json",
                where,
            )
            return InitialStateSpec(kind="explicit"), None
        if dryer is not None and state.n_cells != dryer.n_cells:
            reason = f"state has {state.n_cells} cells, dryer has {dryer.n_cells}"
            self.add("initial_state.file", table["file"], reason, "same n_cells", where)
        sha = sha256_of(path)
        self.input_files[str(path)] = sha
        return InitialStateSpec(kind="explicit", file=str(table["file"]), sha256=sha), state

    def tolerance_section(self, table: Mapping[str, Any]) -> BalanceTolerances:
        section = "balance_tolerances"
        self.unknown_keys(table, section, TOLERANCE_KEYS)
        values: dict[str, float] = {}
        check = _range_check(0.0, 1.0, False, "0 < tolerance < 1")
        for key in TOLERANCE_KEYS:
            if key in table:
                v = self.quantity(table, section, key, "fraction", check=check)
                if v is not None and v > 0:
                    values[key] = v
        return BalanceTolerances(**values)

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
        if table.get("source") == "boiler_house":
            self.add(
                "flue_gas.source",
                "boiler_house",
                "requires a [boiler_house] section",
                "[boiler_house.*] sections, or constant | timeseries",
                self.locate(section, "source"),
            )
            return None, None
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


def _signal_breakpoints(signals: Mapping[str, Signal], prefix: str) -> Any:
    import numpy as np

    points = [s.breakpoints() for name, s in signals.items() if name.startswith(prefix)]
    return np.unique(np.concatenate(points)) if points else np.empty(0)


def _table(doc: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = doc.get(key, {})
    return value if isinstance(value, dict) else {}
