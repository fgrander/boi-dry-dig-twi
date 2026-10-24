"""The ``[recirculation]`` scenario section (feature 004, contracts/scenario-file-recirculation.md).

Read by :mod:`boidrytwin.scenario.loader` with its reader, so every issue carries field,
value, reason, allowed range and file/line like the other sections.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from boidrytwin.fields import RangeViolation
from boidrytwin.scenario.boiler_sections import CONTROLLER_KEYS, _model
from boidrytwin.scenario.schema import (
    ControllerSpec,
    DamperSpec,
    ExhaustFanSpec,
    RecirculationSpec,
    ResistancePoint,
    ResistancesSpec,
    SignalSpec,
    TimeSettings,
    characteristic_problem,
)
from boidrytwin.scenario.timeseries import Signal
from boidrytwin.units import QuantityError, parse_quantity

if TYPE_CHECKING:
    from boidrytwin.scenario.loader import _Reader

SECTION = "recirculation"
KEYS = (
    "pressure_sensor_time_constant",
    "duct_heat_loss",
    "max_share",
    "dew_point_margin",
    "damper",
    "exhaust_fan",
    "resistances",
    "controller",
)
DAMPER_KEYS = (
    "open_mass_flow",
    "design_pressure_drop",
    "design_temperature",
    "characteristic",
    "leakage",
)
FAN_KEYS = ("curve", "nominal_speed", "speed", "curve_temperature")
RESISTANCE_KEYS = ("mass_flow", "pressure_drop", "temperature")
NOT_FOR_PRESSURE_LOOP = ("split_value", "max_dilution_air")
GAS_TEMPERATURE = (250.0, 900.0)  # K, design and curve temperatures (-23 to 627 degC)
SETPOINT = (-2000.0, 0.0)  # Pa, physical
SETPOINT_VALIDATED = (-1000.0, -20.0)  # Pa
SPEED_VALIDATED = (0.3, 1.1)  # of nominal
SENSOR_VALIDATED = (0.5, 30.0)  # s
DUCT_LOSS_VALIDATED = 1e4  # W/K


def _between(
    lo: float, hi: float, allowed: str, *, lo_open: bool = False, hi_open: bool = False
) -> Any:
    def check(v: float) -> tuple[str, str] | None:
        ok = (v > lo if lo_open else v >= lo) and (v < hi if hi_open else v <= hi)
        return None if ok else ("outside physical range", allowed)

    return check


POSITIVE = _between(0.0, float("inf"), "> 0", lo_open=True)
TEMPERATURE = _between(*GAS_TEMPERATURE, "250-900 K (-23 to 627 °C)", lo_open=True, hi_open=True)


def read_recirculation(
    r: _Reader,
    doc: Mapping[str, Any],
    time: TimeSettings | None,
    signals: dict[str, Signal],
    *,
    has_dryer: bool,
) -> tuple[RecirculationSpec | None, list[RangeViolation]]:
    raw = doc.get(SECTION)
    if raw is None:
        return None, []
    where = r.locate(SECTION)
    if not isinstance(raw, dict):
        r.add(SECTION, raw, "must be a table", "a [recirculation] section", where)
        return None, []
    if not has_dryer:
        r.add(SECTION, "", "needs a dryer", "[dryer.*] sections (dryer-only or coupled run)", where)
        return None, []
    r.unknown_keys(raw, SECTION, KEYS)
    before = len(r.issues)
    warnings: list[RangeViolation] = []

    def sub(
        name: str, parent: Mapping[str, Any] = raw, prefix: str = SECTION
    ) -> Mapping[str, Any] | None:
        table = parent.get(name)
        if not isinstance(table, dict):
            r.add(
                f"{prefix}.{name}", "", "required", f"a [{prefix}.{name}] section", r.locate(prefix)
            )
            return None
        return table

    def warn(field: str, value: float | Signal | None, lo: float, hi: float) -> None:
        """One range warning for a value, or for the first sample of a series outside."""
        if isinstance(value, Signal):
            samples = [value.constant] if value.constant is not None else value.all_values()
        else:
            samples = [] if value is None else [value]
        for v in map(float, samples):
            if v < lo:
                warnings.append(RangeViolation(field, v, "min", lo))
                return
            if v > hi:
                warnings.append(RangeViolation(field, v, "max", hi))
                return

    s = SECTION
    sensor = r.quantity(
        raw,
        s,
        "pressure_sensor_time_constant",
        "time",
        default=2.0,
        check=_between(0.0, 600.0, "0 < τ ≤ 600 s", lo_open=True),
    )
    warn(f"{s}.pressure_sensor_time_constant", sensor, *SENSOR_VALIDATED)
    duct = r.quantity(
        raw,
        s,
        "duct_heat_loss",
        "thermal_conductance",
        default=0.0,
        check=_between(0.0, float("inf"), "≥ 0 W/K"),
    )
    warn(f"{s}.duct_heat_loss", duct, 0.0, DUCT_LOSS_VALIDATED)
    max_share = r.quantity(
        raw,
        s,
        "max_share",
        "fraction",
        default=0.7,
        check=_between(0.0, 1.0, "0 < share < 100 %", lo_open=True, hi_open=True),
    )
    margin = r.quantity(
        raw,
        s,
        "dew_point_margin",
        "temperature_difference",
        default=10.0,
        check=_between(0.0, 100.0, "0-100 K"),
    )

    damper = _damper(r, sub("damper"))
    fan = _fan(r, sub("exhaust_fan"), time, signals, warn)
    res_table = sub("resistances")
    resistances = None
    if res_table is not None:
        p = f"{s}.resistances"
        r.unknown_keys(res_table, p, ("drum_path", "stack"))
        points = {k: _point(r, sub(k, res_table, p), f"{p}.{k}") for k in ("drum_path", "stack")}
        if points["drum_path"] is not None and points["stack"] is not None:
            resistances = ResistancesSpec(drum_path=points["drum_path"], stack=points["stack"])
    controller = _controller(r, sub("controller"), time, signals, warn)

    if len(r.issues) > before or None in (damper, fan, resistances, controller):
        return None, []
    assert damper and fan and resistances and controller
    spec = _model(
        r,
        RecirculationSpec,
        {
            "damper": damper,
            "exhaust_fan": fan,
            "resistances": resistances,
            "controller": controller,
            "pressure_sensor_time_constant": sensor,
            "duct_heat_loss": duct,
            "max_share": max_share,
            "dew_point_margin": margin,
        },
        SECTION,
        where,
    )
    return spec, warnings if spec is not None else []


def _damper(r: _Reader, t: Mapping[str, Any] | None) -> DamperSpec | None:
    if t is None:
        return None
    s = f"{SECTION}.damper"
    r.unknown_keys(t, s, DAMPER_KEYS)
    values: dict[str, Any] = {
        "open_mass_flow": r.quantity(t, s, "open_mass_flow", "mass_flow", check=POSITIVE),
        "design_pressure_drop": r.quantity(
            t, s, "design_pressure_drop", "pressure", check=POSITIVE
        ),
        "design_temperature": r.quantity(
            t, s, "design_temperature", "temperature", check=TEMPERATURE
        ),
        "leakage": r.quantity(
            t, s, "leakage", "fraction", default=0.01, check=_between(0.0, 0.2, "0-20 %")
        ),
    }
    if "characteristic" in t:
        table = _pairs(r, t, s, "characteristic", ("fraction", "fraction"))
        if table is not None:
            problem = characteristic_problem(table)
            if problem:
                r.add(
                    f"{s}.characteristic",
                    t["characteristic"],
                    problem,
                    "[[0, f0], …, [1, 1]] with increasing positions",
                    r.locate(s, "characteristic"),
                )
            else:
                values["characteristic"] = table
    if any(v is None for v in values.values()):
        return None
    return _model(r, DamperSpec, values, s, r.locate(s))  # type: ignore[no-any-return]


def _fan(
    r: _Reader,
    t: Mapping[str, Any] | None,
    time: TimeSettings | None,
    signals: dict[str, Signal],
    warn: Any,
) -> ExhaustFanSpec | None:
    if t is None:
        return None
    s = f"{SECTION}.exhaust_fan"
    r.unknown_keys(t, s, FAN_KEYS)
    nominal = r.quantity(t, s, "nominal_speed", "angular_velocity", check=POSITIVE)
    curve_t = r.quantity(
        t, s, "curve_temperature", "temperature", default=293.15, check=TEMPERATURE
    )
    curve = None
    where = r.locate(s, "curve")
    if "curve" not in t:
        r.add(f"{s}.curve", "", "required", "3 points [volume flow, pressure rise]", where)
    else:
        pts = _pairs(r, t, s, "curve", ("volume_flow", "pressure"))
        if pts is not None:
            problem = _curve_problem(pts)
            if problem:
                r.add(
                    f"{s}.curve",
                    t["curve"],
                    problem,
                    "3 points, flow rising, pressure falling",
                    where,
                )
            else:
                curve = pts
    speed = None
    if nominal is not None:
        hi = 2.0 * nominal
        spec, sig = r.signal(
            t,
            s,
            "speed",
            "angular_velocity",
            time,
            default=nominal,
            check=_between(0.0, hi, f"0-{hi:g} rad/s (2 × nominal)"),
        )
        if spec is not None and sig is not None:
            speed = spec
            signals[f"{s}.speed"] = sig
            warn(f"{s}.speed", sig, SPEED_VALIDATED[0] * nominal, SPEED_VALIDATED[1] * nominal)
    if nominal is None or curve_t is None or curve is None or speed is None:
        return None
    return _model(  # type: ignore[no-any-return]
        r,
        ExhaustFanSpec,
        {"curve": curve, "nominal_speed": nominal, "curve_temperature": curve_t, "speed": speed},
        s,
        r.locate(s),
    )


def _curve_problem(pts: tuple[tuple[float, float], ...]) -> str | None:
    if len(pts) != 3:
        return "needs exactly 3 points"
    (v1, p1), (v2, p2), (v3, p3) = pts
    if not (v1 < v2 < v3):
        return "volume flows must increase"
    if not (p1 > p2 > p3):
        return "pressure rise must fall with the flow"
    a2 = ((p3 - p2) / (v3 - v2) - (p2 - p1) / (v2 - v1)) / (v3 - v1)
    if a2 >= 0.0:
        return "the curve must fall ever more steeply (concave)"
    return None


def _point(r: _Reader, t: Mapping[str, Any] | None, s: str) -> ResistancePoint | None:
    if t is None:
        return None
    r.unknown_keys(t, s, RESISTANCE_KEYS)
    values = {
        "mass_flow": r.quantity(t, s, "mass_flow", "mass_flow", check=POSITIVE),
        "pressure_drop": r.quantity(t, s, "pressure_drop", "pressure", check=POSITIVE),
        "temperature": r.quantity(t, s, "temperature", "temperature", check=TEMPERATURE),
    }
    if any(v is None for v in values.values()):
        return None
    return _model(r, ResistancePoint, values, s, r.locate(s))  # type: ignore[no-any-return]


def _pairs(
    r: _Reader, t: Mapping[str, Any], s: str, key: str, dims: tuple[str, str]
) -> tuple[tuple[float, float], ...] | None:
    raw = t[key]
    where = r.locate(s, key)
    if not isinstance(raw, list) or not all(isinstance(p, list) and len(p) == 2 for p in raw):
        r.add(f"{s}.{key}", raw, "must be a list of [x, y] pairs", "[[x1, y1], [x2, y2], …]", where)
        return None
    out = []
    for pair in raw:
        try:
            out.append((parse_quantity(pair[0], dims[0]), parse_quantity(pair[1], dims[1])))
        except QuantityError as exc:
            r.add(f"{s}.{key}", pair, exc.reason, exc.allowed, where)
            return None
    return tuple(out)


def _controller(
    r: _Reader,
    t: Mapping[str, Any] | None,
    time: TimeSettings | None,
    signals: dict[str, Signal],
    warn: Any,
) -> ControllerSpec | None:
    if t is None:
        return None
    s = f"{SECTION}.controller"
    r.unknown_keys(t, s, CONTROLLER_KEYS)
    for key in NOT_FOR_PRESSURE_LOOP:
        if key in t:
            r.add(
                f"{s}.{key}",
                t[key],
                "not allowed for the pressure loop",
                "remove it (split range belongs to the drum inlet loop)",
                r.locate(s, key),
            )
    values: dict[str, Any] = {"not_reached_band": 50.0, "not_reached_hold": 600.0}
    fraction = _between(0.0, 1.0, "0-100 %")
    dims = {
        "gain": ("per_pressure", POSITIVE),
        "integral_time": ("time", POSITIVE),
        "tracking_time": ("time", POSITIVE),
        "output_min": ("fraction", fraction),
        "output_max": ("fraction", fraction),
        "smoothing": ("fraction", None),
        "not_reached_band": ("pressure", POSITIVE),
        "not_reached_hold": ("time", None),
    }
    for key, (dim, check) in dims.items():
        required = key in ("gain", "integral_time", "output_min", "output_max")
        if key in t or required:
            v = r.quantity(t, s, key, dim, check=check)
            if v is not None:
                values[key] = v
    values["mode"] = r.choice(t, s, "mode", ("automatic", "manual"), "automatic")
    values["action"] = r.choice(t, s, "action", ("reverse", "direct"), "reverse")
    if "exact" in t:
        values["exact"] = bool(t["exact"])
    automatic = values["mode"] == "automatic"
    sp_spec, sp_sig = None, None
    if "setpoint" in t or automatic:
        if "setpoint" not in t:
            r.add(
                f"{s}.setpoint",
                "",
                "required",
                "a mixing chamber pressure, e.g. -200 Pa",
                r.locate(s),
            )
        else:
            sp_spec, sp_sig = r.signal(
                t, s, "setpoint", "pressure", time, check=_between(*SETPOINT, "-2000 to 0 Pa")
            )
            if sp_sig is not None:
                signals[f"{s}.setpoint"] = sp_sig
                warn(f"{s}.setpoint", sp_sig, *SETPOINT_VALIDATED)
    manual = None
    if "manual_output" in t:
        m_spec, m_sig = r.signal(t, s, "manual_output", "fraction", time, check=fraction)
        if m_spec is not None and m_sig is not None:
            manual = m_spec
            if m_spec.constant is not None:
                values["manual_output"] = m_spec.constant
            else:
                signals[f"{s}.manual_output"] = m_sig
    elif not automatic:
        r.add(f"{s}.manual_output", "", "required in manual mode", "a damper position", r.locate(s))
    if any(k not in values for k in ("gain", "integral_time", "output_min", "output_max")):
        return None
    return _model(  # type: ignore[no-any-return]
        r,
        ControllerSpec,
        {
            **values,
            "setpoint": sp_spec or SignalSpec(constant=0.0),
            "manual_signal": manual if manual is not None and manual.constant is None else None,
        },
        s,
        r.locate(s),
    )
