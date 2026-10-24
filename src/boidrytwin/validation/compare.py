"""Comparison of model results with measured time series (FR-016, SC-003; data-model.md §5).

The measured CSV has the time series format of the scenario inputs; its columns are named
after ``results.csv`` outputs (e.g. ``exhaust_temperature``). Model results are linearly
interpolated to the measurement times. Values with quality ``missing``, ``bad`` or
``stale``, empty values and times outside the simulated period are excluded and listed,
never counted as passes or failures.

Pass/fail (SC-003) uses steady operation only: a sample is steady when the model prediction
for that output stayed within its tolerance band over the preceding ``steady_window``. An
output with a tolerance passes when at least ``required_fraction`` of its steady compared
samples are within tolerance; outputs without a tolerance get statistics only.

Boiler house outputs (``boiler_results.csv``, feature 002) can be compared the same way, in
boiler-only and coupled runs; their default tolerances follow SC-008.
"""

from __future__ import annotations

import csv
import tomllib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from boidrytwin.errors import ScenarioValidationError, ValidationIssue
from boidrytwin.properties.gas import FloatArray
from boidrytwin.scenario.timeseries import read_timeseries_csv
from boidrytwin.units import QuantityError, parse_quantity

# results.csv outputs that can be compared, with their dimension
OUTPUT_DIMENSIONS: dict[str, str] = {
    "product_dry_mass_flow": "mass_flow",
    "product_moisture_wet_basis": "fraction",
    "product_temperature": "temperature",
    "evaporation_rate": "mass_flow",
    "exhaust_mass_flow": "mass_flow",
    "exhaust_temperature": "temperature",
    "exhaust_humidity": "fraction",
    "exhaust_dew_point": "temperature",
    "drum_inlet_gas_temperature": "temperature",
    "heat_supplied": "power",
    "heat_used_for_drying": "power",
    "shell_heat_loss": "power",
    "specific_energy": "specific_energy",
    "solids_holdup": "mass",
    # with a recirculation (feature 004)
    "mixing_chamber_pressure": "pressure",
    "recirculation_damper_position": "fraction",
    "recirculation_mass_flow": "mass_flow",
}
MAX_HEATERS = 9
BOILER_OUTPUT_DIMENSIONS: dict[str, str] = {
    "fuel_feed": "mass_flow",
    "fuel_burnout_dry": "mass_flow",
    "heat_released": "power",
    "excess_air_ratio": "dimensionless",
    "o2_dry": "fraction",
    "o2_dry_measured": "fraction",
    "combustion_air_flow": "mass_flow",
    "furnace_temperature": "temperature",
    "oil_outlet_temperature": "temperature",
    "heat_to_oil": "power",
    "max_film_temperature": "temperature",
    "bypass_position": "fraction",
    "dilution_air_flow": "mass_flow",
    "flue_gas_to_dryer_mass_flow": "mass_flow",
    "flue_gas_to_dryer_temperature": "temperature",
    **{f"gas_temperature_after_heater_{i}": "temperature" for i in range(1, MAX_HEATERS + 1)},
    **{f"oil_temperature_after_heater_{i}": "temperature" for i in range(1, MAX_HEATERS + 1)},
    **{f"heat_to_oil_{i}": "power" for i in range(1, MAX_HEATERS + 1)},
}
OUTPUT_DIMENSIONS.update(BOILER_OUTPUT_DIMENSIONS)
TOLERANCE_DIMENSIONS = {
    k: ("temperature_difference" if v == "temperature" else v) for k, v in OUTPUT_DIMENSIONS.items()
}
DEFAULT_TOLERANCES: dict[str, float] = {
    "product_moisture_wet_basis": 0.01,  # ±1 percentage point, wet basis (SC-003)
    "exhaust_temperature": 5.0,  # ±5 K
}
# SC-008: O2 ±0.5 vol% dry, flue gas temperatures ±10 K, oil outlet ±2 K
BOILER_DEFAULT_TOLERANCES: dict[str, float] = {
    "o2_dry": 0.005,
    "o2_dry_measured": 0.005,
    "furnace_temperature": 10.0,
    "flue_gas_to_dryer_temperature": 10.0,
    **{f"gas_temperature_after_heater_{i}": 10.0 for i in range(1, MAX_HEATERS + 1)},
    "oil_outlet_temperature": 2.0,
}
EXCLUDED_QUALITY = ("missing", "bad", "stale")


class ComparisonSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    tolerances: dict[str, float] = Field(
        default_factory=lambda: {**DEFAULT_TOLERANCES, **BOILER_DEFAULT_TOLERANCES}
    )
    required_fraction: float = Field(default=0.9, gt=0.0, le=1.0)
    steady_window: float = Field(default=1800.0, ge=0.0)  # s


class OutputComparison(BaseModel):
    n_compared: int
    n_excluded: int
    bias: float  # mean(predicted - measured)
    mae: float
    rmse: float
    max_abs_error: float
    n_steady: int
    fraction_within_tolerance: float | None
    tolerance: float | None
    passed: bool | None


class Excluded(BaseModel):
    time: AwareDatetime
    output: str
    reason: str


class Period(BaseModel):
    start: AwareDatetime
    end: AwareDatetime


class ValidationReport(BaseModel):
    run_id: str
    outputs: dict[str, OutputComparison]
    required_fraction: float
    steady_window: float
    steady_periods: list[Period]
    excluded: list[Excluded]

    @property
    def passed(self) -> bool:
        return all(o.passed is not False for o in self.outputs.values())

    def to_dict(self) -> dict[str, Any]:
        return {**self.model_dump(mode="json"), "passed": self.passed}


def load_settings(path: str | Path | None) -> ComparisonSettings:
    """Read a tolerance file; unspecified values keep their defaults."""
    if path is None:
        return ComparisonSettings()
    p = Path(path)
    issues: list[ValidationIssue] = []

    def issue(fieldname: str, value: object, reason: str, allowed: str) -> None:
        issues.append(
            ValidationIssue(
                field=fieldname, value=str(value), reason=reason, allowed=allowed, location=p.name
            )
        )

    if not p.is_file():
        issue("tolerances", str(p), "file not found", "an existing TOML file")
        raise ScenarioValidationError(issues)
    doc = tomllib.loads(p.read_text(encoding="utf-8"))
    tolerances = {**DEFAULT_TOLERANCES, **BOILER_DEFAULT_TOLERANCES}
    for key, raw in doc.get("tolerances", {}).items():
        if key not in TOLERANCE_DIMENSIONS:
            issue(f"tolerances.{key}", key, "unknown output", ", ".join(TOLERANCE_DIMENSIONS))
            continue
        try:
            tolerances[key] = parse_quantity(raw, TOLERANCE_DIMENSIONS[key])
        except QuantityError as exc:
            issue(f"tolerances.{key}", raw, exc.reason, exc.allowed)
    kwargs: dict[str, Any] = {"tolerances": tolerances}
    for key, dimension in (("required_fraction", "fraction"), ("steady_window", "time")):
        if key in doc:
            try:
                kwargs[key] = parse_quantity(doc[key], dimension)
            except QuantityError as exc:
                issue(key, doc[key], exc.reason, exc.allowed)
    unknown = set(doc) - {"tolerances", "required_fraction", "steady_window"}
    for key in sorted(unknown):
        issue(key, key, "unknown key", "tolerances, required_fraction, steady_window")
    if issues:
        raise ScenarioValidationError(issues)
    return ComparisonSettings(**kwargs)


def read_measured(path: str | Path) -> pd.DataFrame:
    """Read a measured time series (SI, UTC index, ``quality`` column)."""
    p = Path(path)
    if not p.is_file():
        raise ScenarioValidationError(
            [
                ValidationIssue(
                    field="measured",
                    value=str(p),
                    reason="file not found",
                    allowed="an existing CSV file",
                    location=None,
                )
            ]
        )
    with p.open(newline="", encoding="utf-8-sig") as handle:
        header = [h.strip() for h in next(csv.reader(handle), [])]
    columns = [h for h in header if h not in ("time", "quality")]
    unknown = [c for c in columns if c not in OUTPUT_DIMENSIONS]
    if unknown:
        raise ScenarioValidationError(
            ValidationIssue(
                field=f"measured.{c}",
                value=c,
                reason="unknown output column",
                allowed=", ".join(OUTPUT_DIMENSIONS),
                location=f"{p.name}:line 1",
            )
            for c in unknown
        )
    series = read_timeseries_csv(
        p, {c: OUTPUT_DIMENSIONS[c] for c in columns}, field_prefix="measured."
    )
    return series.frame


def steady_mask(predicted: pd.Series, window: float, band: float) -> FloatArray:
    """True where the prediction stayed within ``band`` over the preceding ``window`` (s)."""
    t = np.asarray(
        (pd.DatetimeIndex(predicted.index) - predicted.index[0]).total_seconds(), dtype=float
    )
    v = predicted.to_numpy(dtype=float)
    mask = np.zeros(len(v), dtype=bool)
    start = 0
    for i in range(len(v)):
        while t[i] - t[start] > window:
            start += 1
        if t[i] - t[0] < window or np.isnan(v[i]):
            continue
        segment = v[start : i + 1]
        mask[i] = bool(np.nanmax(segment) - np.nanmin(segment) <= band)
    return mask


def _seconds(index: pd.DatetimeIndex, origin: pd.Timestamp) -> FloatArray:
    return np.asarray((index - origin).total_seconds(), dtype=float)


def compare_frames(
    predicted: pd.DataFrame,
    measured: pd.DataFrame,
    settings: ComparisonSettings,
    run_id: str,
) -> tuple[ValidationReport, pd.DataFrame]:
    """Compare model results (UTC index) with measurements; returns report and long table."""
    origin = pd.Timestamp(predicted.index[0])
    t_pred = _seconds(pd.DatetimeIndex(predicted.index), origin)
    t_meas = _seconds(pd.DatetimeIndex(measured.index), origin)
    inside = (t_meas >= t_pred[0] - 1e-9) & (t_meas <= t_pred[-1] + 1e-9)
    quality = (
        measured["quality"].to_numpy(dtype=object)
        if "quality" in measured
        else np.full(len(measured), "good", dtype=object)
    )

    outputs: dict[str, OutputComparison] = {}
    excluded: list[Excluded] = []
    rows: list[pd.DataFrame] = []
    steady_all = np.ones(len(measured), dtype=bool)
    for name in [c for c in measured.columns if c != "quality"]:
        measured_v = measured[name].to_numpy(dtype=float)
        if name in predicted.columns:
            pred_series = predicted[name].astype(float)
            pred_v = np.interp(t_meas, t_pred, pred_series.to_numpy(dtype=float))
        else:
            pred_series = None
            pred_v = np.full(len(measured), np.nan)
        reason = np.full(len(measured), "", dtype=object)
        for q in EXCLUDED_QUALITY:
            reason[(quality == q) & (reason == "")] = q
        reason[(np.isnan(measured_v)) & (reason == "")] = "missing"
        reason[(~inside) & (reason == "")] = "outside simulated period"
        reason[(np.isnan(pred_v)) & (reason == "")] = "no model value"
        included = reason == ""
        tolerance = settings.tolerances.get(name)
        if pred_series is not None and settings.steady_window > 0:
            band = tolerance if tolerance is not None else np.inf
            mask_pred = steady_mask(pred_series, settings.steady_window, band)
            steady = np.interp(t_meas, t_pred, mask_pred.astype(float)) >= 1.0
        else:
            steady = np.ones(len(measured), dtype=bool)
        steady_all &= steady | ~included

        dev = pred_v - measured_v
        d = dev[included]
        within = None
        passed = None
        n_steady = int((included & steady).sum())
        if tolerance is not None:
            ds = dev[included & steady]
            within = float(np.mean(np.abs(ds) <= tolerance)) if len(ds) else None
            passed = within is not None and within >= settings.required_fraction
        outputs[name] = OutputComparison(
            n_compared=int(included.sum()),
            n_excluded=int((~included).sum()),
            bias=float(d.mean()) if len(d) else float("nan"),
            mae=float(np.abs(d).mean()) if len(d) else float("nan"),
            rmse=float(np.sqrt((d**2).mean())) if len(d) else float("nan"),
            max_abs_error=float(np.abs(d).max()) if len(d) else float("nan"),
            n_steady=n_steady,
            fraction_within_tolerance=within,
            tolerance=tolerance,
            passed=passed,
        )
        for i in np.flatnonzero(~included).tolist():
            excluded.append(
                Excluded(time=measured.index[i].to_pydatetime(), output=name, reason=str(reason[i]))
            )
        rows.append(
            pd.DataFrame(
                {
                    "time": measured.index,
                    "output": name,
                    "predicted": pred_v,
                    "measured": measured_v,
                    "deviation": dev,
                    "included": included,
                    "steady": steady,
                    "reason": reason,
                }
            )
        )
    table = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    report = ValidationReport(
        run_id=run_id,
        outputs=outputs,
        required_fraction=settings.required_fraction,
        steady_window=settings.steady_window,
        steady_periods=_periods(pd.DatetimeIndex(measured.index), steady_all & inside),
        excluded=excluded,
    )
    return report, table


def _periods(index: pd.DatetimeIndex, mask: FloatArray) -> list[Period]:
    periods: list[Period] = []
    i, n = 0, len(mask)
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and mask[j + 1]:
            j += 1
        periods.append(Period(start=index[i].to_pydatetime(), end=index[j].to_pydatetime()))
        i = j + 1
    return periods
