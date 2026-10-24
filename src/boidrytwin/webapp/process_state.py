"""Values of a run at one output time, for the process drawings (FR-025).

Result values come from the run's tables (``boiler_results.csv``, ``results.csv``, and
``profiles.csv`` if present). Inputs the tables do not hold (oil return temperature and flow,
fuel moisture, product feed, set points) come from the run's scenario at that time, falling
back to the constants in the run record when the scenario file is gone. Everything is in
display units; nothing is computed here except unit conversions and sums of existing values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from boidrytwin.webapp.run_view import RunData

# viridis (colour-blind-safe sequential)
VIRIDIS = ("#440154", "#3b528b", "#21918c", "#5ec962", "#fde725")
GREY = "#9aa0a6"
GAS_RANGE = (100.0, 1000.0)  # °C
OIL_RANGE = (200.0, 300.0)
SOLIDS_RANGE = (0.0, 120.0)
MOISTURE_RANGE = (0.0, 60.0)  # %


def colour(value: float | None, lo: float, hi: float) -> str:
    if value is None or not math.isfinite(value):
        return GREY
    u = min(1.0, max(0.0, (value - lo) / (hi - lo))) * (len(VIRIDIS) - 1)
    i = min(len(VIRIDIS) - 2, int(u))
    f = u - i
    a = [int(VIRIDIS[i][k : k + 2], 16) for k in (1, 3, 5)]
    b = [int(VIRIDIS[i + 1][k : k + 2], 16) for k in (1, 3, 5)]
    return "rgb({})".format(
        ",".join(str(round(x + f * (y - x))) for x, y in zip(a, b, strict=True))
    )


@dataclass
class Value:
    value: float | None
    unit: str
    digits: int = 1
    colour: str | None = None

    @property
    def text(self) -> str:
        if self.value is None or not math.isfinite(self.value):
            return "–"
        return f"{self.value:.{self.digits}f} {self.unit}".strip()

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "unit": self.unit, "text": self.text, "colour": self.colour}


@dataclass
class HeaterState:
    n: int
    kind: str
    gas_in: Value
    gas_out: Value
    oil_in: Value
    oil_out: Value
    duty: Value
    gas_flow: Value

    def as_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "kind": self.kind,
            **{
                k: getattr(self, k).as_dict()
                for k in ("gas_in", "gas_out", "oil_in", "oil_out", "duty", "gas_flow")
            },
        }


@dataclass
class ProcessState:
    run_id: str
    scenario_name: str
    time: str
    times: list[str]
    boiler: dict[str, Value] | None
    heaters: list[HeaterState] = field(default_factory=list)
    bypass_after: int | None = None
    dryer: dict[str, Value] | None = None
    profile: dict[str, list[float]] | None = None
    flags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_name": self.scenario_name,
            "time": self.time,
            "times": self.times,
            "boiler": {k: v.as_dict() for k, v in self.boiler.items()} if self.boiler else None,
            "heaters": [h.as_dict() for h in self.heaters],
            "bypass_after": self.bypass_after,
            "dryer": {k: v.as_dict() for k, v in self.dryer.items()} if self.dryer else None,
            "profile": self.profile,
            "flags": self.flags,
        }


def _iso(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# --- inputs from the scenario -------------------------------------------------------------

_SIGNALS: dict[tuple[str, float], Any] = {}


def _signals(run: RunData) -> Any:
    path = Path(str(run.record.get("scenario_file", "")))
    if not path.is_file():
        return None
    key = (str(path), path.stat().st_mtime)
    if key not in _SIGNALS:
        from boidrytwin.scenario.loader import load_scenario

        try:
            _SIGNALS[key] = load_scenario(path).signals
        except Exception:  # a moved data file: fall back to the record
            _SIGNALS[key] = None
    return _SIGNALS[key]


def _record_constant(run: RunData, name: str) -> float | None:
    sc = run.record.get("scenario") or {}
    if name.startswith("boiler_house."):
        spec = ((sc.get("boiler_house") or {}).get("signals") or {}).get(name)
    else:
        section, _, key = name.partition(".")
        spec = (sc.get(section) or {}).get(key)
    if isinstance(spec, dict) and spec.get("constant") is not None:
        return float(spec["constant"])
    return None


def _input(run: RunData, name: str, seconds: float) -> float | None:
    signals = _signals(run)
    if signals is not None and name in signals:
        return float(signals[name].value_at(seconds))
    return _record_constant(run, name)


# --- snapshot -----------------------------------------------------------------------------


def _at(run: RunData, table: str, index: int, column: str) -> float | None:
    t = run.tables.get(table)
    if t is None or column not in t.frame.columns:
        return None
    v = pd.to_numeric(t.frame[column].iloc[index : index + 1], errors="coerce").iloc[0]
    return None if pd.isna(v) else float(v)


def _celsius(k: float | None) -> float | None:
    return None if k is None else k - 273.15


def _scale(v: float | None, f: float) -> float | None:
    return None if v is None else v * f


def snapshot(run: RunData, time: str | None) -> ProcessState:
    master = "boiler_results.csv" if "boiler_results.csv" in run.tables else "results.csv"
    frame = run.tables[master].frame
    index_times = pd.DatetimeIndex(frame.index)
    if time:
        target = pd.Timestamp(time)
        target = target.tz_localize("UTC") if target.tzinfo is None else target.tz_convert("UTC")
        i = int(np.argmin(np.abs((index_times - target).total_seconds())))
    else:
        i = len(index_times) - 1
    stamp = index_times[i]
    seconds = float((stamp - index_times[0]).total_seconds())
    start = (run.record.get("scenario") or {}).get("time", {}).get("start")
    if start:
        seconds = float(
            (
                stamp - pd.Timestamp(datetime.fromisoformat(str(start).replace("Z", "+00:00")))
            ).total_seconds()
        )
    state = ProcessState(
        run_id=run.summary.run_id,
        scenario_name=run.summary.scenario_name,
        time=_iso(stamp),
        times=[_iso(t) for t in index_times],
        boiler=None,
    )

    B = "boiler_results.csv"
    if B in run.tables:

        def b(col: str) -> float | None:
            return _at(run, B, i, col)

        def gas(col: str) -> Value:
            v = _celsius(b(col))
            return Value(v, "°C", 0, colour(v, *GAS_RANGE))

        def oil(v: float | None) -> Value:
            return Value(v, "°C", 1, colour(v, *OIL_RANGE))

        oil_return = _celsius(_input(run, "boiler_house.thermal_oil.return_temperature", seconds))
        sp_oil = _celsius(_input(run, "boiler_house.controllers.oil_temperature.setpoint", seconds))
        sp_drum = _celsius(
            _input(run, "boiler_house.controllers.drum_inlet_temperature.setpoint", seconds)
        )
        moisture = _input(run, "boiler_house.fuel.moisture_wet_basis", seconds)
        state.boiler = {
            "fuel_feed": Value(_scale(b("fuel_feed"), 3.6), "t/h", 2),
            "fuel_moisture": Value(_scale(moisture, 100.0), "%", 1),
            "load": Value(_scale(b("load_fraction"), 100.0), "%", 0),
            "heat_released": Value(_scale(b("heat_released"), 1e-6), "MW", 2),
            "furnace": gas("furnace_temperature"),
            "o2": Value(_scale(b("o2_dry_measured"), 100.0), "%", 1),
            "excess_air": Value(b("excess_air_ratio"), "", 2),
            "air_flow": Value(b("combustion_air_flow"), "kg/s", 2),
            "oil_supply": oil(_celsius(b("oil_outlet_temperature"))),
            "oil_setpoint": oil(sp_oil),
            "oil_return": oil(oil_return),
            "oil_flow": Value(
                _input(run, "boiler_house.thermal_oil.mass_flow", seconds), "kg/s", 1
            ),
            "heat_to_oil": Value(_scale(b("heat_to_oil"), 1e-6), "MW", 2),
            "film": oil(_celsius(b("max_film_temperature"))),
            "oil_velocity": Value(b("min_oil_velocity"), "m/s", 2),
            "losses": Value(_scale(b("losses"), 1e-6), "MW", 2),
            "bypass": Value(_scale(b("bypass_position"), 100.0), "%", 1),
            "flue_flow": Value(b("flue_gas_to_dryer_mass_flow"), "kg/s", 2),
            "flue_temperature": gas("flue_gas_to_dryer_temperature"),
            "dilution": Value(b("dilution_air_flow"), "kg/s", 2),
            "drum_setpoint": Value(sp_drum, "°C", 0, colour(sp_drum, *GAS_RANGE)),
        }
        heaters_cfg = ((run.record.get("scenario") or {}).get("boiler_house") or {}).get(
            "config", {}
        )
        kinds = [h.get("type", "convective") for h in heaters_cfg.get("heaters", [])]
        state.bypass_after = (heaters_cfg.get("bypass") or {}).get("starts_after_heater")
        flue = b("flue_gas_to_dryer_mass_flow")
        bypass = b("bypass_position") or 0.0
        for n, kind in enumerate(kinds, start=1):
            gas_in = gas(
                "furnace_temperature" if n == 1 else f"gas_temperature_after_heater_{n - 1}"
            )
            through = (
                flue
                if state.bypass_after is None or n <= state.bypass_after
                else _scale(flue, 1 - bypass)
            )
            oil_in = oil(
                _celsius(b(f"oil_temperature_after_heater_{n + 1}"))
                if n < len(kinds)
                else oil_return
            )
            state.heaters.append(
                HeaterState(
                    n=n,
                    kind=kind,
                    gas_in=gas_in,
                    gas_out=gas(f"gas_temperature_after_heater_{n}"),
                    oil_in=oil_in,
                    oil_out=oil(_celsius(b(f"oil_temperature_after_heater_{n}"))),
                    duty=Value(_scale(b(f"heat_to_oil_{n}"), 1e-6), "MW", 2),
                    gas_flow=Value(through, "kg/s", 2),
                )
            )

    D = "results.csv"
    if D in run.tables:

        def d(col: str) -> float | None:
            return _at(run, D, i, col)

        inlet = _celsius(d("drum_inlet_gas_temperature"))
        exhaust = _celsius(d("exhaust_temperature"))
        product_t = _celsius(d("product_temperature"))
        feed_w = _input(run, "product_feed.moisture_wet_basis", seconds)
        feed_t = _celsius(_input(run, "product_feed.temperature", seconds))
        state.dryer = {
            "drum_inlet": Value(inlet, "°C", 0, colour(inlet, *GAS_RANGE)),
            "exhaust": Value(exhaust, "°C", 0, colour(exhaust, *GAS_RANGE)),
            "exhaust_flow": Value(d("exhaust_mass_flow"), "kg/s", 2),
            "exhaust_humidity": Value(_scale(d("exhaust_humidity"), 1000.0), "g/kg", 0),
            "feed_flow": Value(
                _scale(_input(run, "product_feed.mass_flow_wet", seconds), 3.6), "t/h", 1
            ),
            "feed_moisture": Value(
                _scale(feed_w, 100.0), "%", 1, colour(_scale(feed_w, 100.0), *MOISTURE_RANGE)
            ),
            "feed_temperature": Value(feed_t, "°C", 0, colour(feed_t, *SOLIDS_RANGE)),
            "product_moisture": Value(
                _scale(d("product_moisture_wet_basis"), 100.0),
                "%",
                1,
                colour(_scale(d("product_moisture_wet_basis"), 100.0), *MOISTURE_RANGE),
            ),
            "product_temperature": Value(product_t, "°C", 0, colour(product_t, *SOLIDS_RANGE)),
            "product_flow": Value(_scale(d("product_dry_mass_flow"), 3.6), "t/h", 2),
            "evaporation": Value(_scale(d("evaporation_rate"), 3.6), "t/h", 2),
            "heat_supplied": Value(_scale(d("heat_supplied"), 1e-6), "MW", 2),
            "specific_energy": Value(_scale(d("specific_energy"), 1e-6), "MJ/kg", 2),
            "shell_loss": Value(_scale(d("shell_heat_loss"), 1e-3), "kW", 0),
            "holdup": Value(_scale(d("solids_holdup"), 1e-3), "t", 1),
        }
        profiles = run.profiles()
        if profiles is not None:
            pf = profiles.frame
            ptimes = pd.DatetimeIndex(pf.index.unique())
            at = ptimes[int(np.argmin(np.abs((ptimes - stamp).total_seconds())))]
            rows = pf.loc[[at]]
            state.profile = {
                "gas_temperature": [float(v) - 273.15 for v in rows["gas_temperature"]],
                "solids_temperature": [float(v) - 273.15 for v in rows["solids_temperature"]],
                "moisture": [
                    100.0 * float(v) if pd.notna(v) else float("nan")
                    for v in rows["moisture_wet_basis"]
                ],
            }
    for p in run.flag_periods():
        if p.start <= stamp <= p.end:
            state.flags.append(p.flag)
    for w in run.warnings():
        s, e = pd.Timestamp(w["period_start"]), pd.Timestamp(w["period_end"])
        if s <= stamp <= e:
            state.flags.append(f"{w['quantity']} {w['limit_type']} {w['limit']:g}")
    state.flags = sorted(set(state.flags))
    return state
