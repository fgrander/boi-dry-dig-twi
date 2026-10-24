"""Loading of the [boiler_house] sections (contracts/scenario-file-boiler.md).

Uses the feature-001 reader (units, issues with file and line, time series signals). Every
problem is collected; nothing is raised here except through the reader's issue list.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from boidrytwin.boiler_house.config import (
    FURNACE_FIELDS,
    BoilerHouseConfiguration,
    BypassConfig,
    ConvectiveHeater,
    FurnaceConfig,
    RadiantHeater,
)
from boidrytwin.errors import ScenarioValidationError
from boidrytwin.fields import FieldSpec
from boidrytwin.properties.fuel import FuelComposition
from boidrytwin.scenario.schema import (
    BoilerControllers,
    BoilerHouseSpec,
    BoilerInitialStateSpec,
    ControllerSpec,
    SignalSpec,
    TimeSettings,
)
from boidrytwin.scenario.timeseries import Signal

if TYPE_CHECKING:
    from boidrytwin.scenario.loader import _Reader

SECTION = "boiler_house"
SECTIONS = (
    "fuel",
    "combustion_air",
    "furnace",
    "heaters",
    "bypass",
    "thermal_oil",
    "controllers",
    "initial_state",
)
INT_FIELDS = {"n_cells", "n_rows", "tubes_per_row", "n_parallel_passes"}

# loop -> (measurement dimension, output dimension, gain dimension, band dimension, defaults)
# defaults of the oil and O2 loops: SIMC from scripts/tune_controllers.py on the reference
LOOPS: dict[str, tuple[str, str, str, str, dict[str, Any]]] = {
    "oil_temperature": ("temperature", "mass_flow", "mass_flow_per_temperature", "temperature_difference",
                        {"setpoint": 555.15, "gain": 0.191, "integral_time": 1157.0, "output_min": 0.47,
                         "output_max": 2.2, "not_reached_band": 2.0}),
    "oxygen": ("fraction", "dimensionless", "dimensionless", "fraction",
               {"setpoint": 0.07, "gain": 32.1, "integral_time": 30.0, "output_min": 1.1,
                "output_max": 2.5, "not_reached_band": 0.005}),
    "drum_inlet_temperature": ("temperature", "dimensionless", "per_temperature", "temperature_difference",
                               {"action": "direct", "gain": 0.004, "integral_time": 300.0, "output_min": 0.0,
                                "output_max": 1.0, "not_reached_band": 5.0}),
}  # fmt: skip
CONTROLLER_KEYS = (
    "mode", "action", "setpoint", "gain", "integral_time", "tracking_time", "output_min", "output_max",
    "manual_output", "smoothing", "exact", "not_reached_band", "not_reached_hold", "split_value",
    "max_dilution_air",
)  # fmt: skip


def _check(spec: FieldSpec) -> Any:
    lo, hi = spec.physical

    def check(v: float) -> tuple[str, str] | None:
        ok = (v >= lo if spec.lower_inclusive else v > lo) and v <= hi
        return None if ok else ("outside physical range", f"[{lo:g}, {hi:g}] (SI)")

    return check


def _fields(
    r: _Reader, table: Mapping[str, Any], section: str, fields: Mapping[str, FieldSpec]
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, spec in fields.items():
        if key not in table:
            continue
        value = r.quantity(table, section, key, spec.dimension, check=_check(spec))
        if value is None:
            continue
        if key in INT_FIELDS:
            if value != int(value):
                r.add(
                    f"{section}.{key}",
                    table[key],
                    "must be an integer",
                    "an integer",
                    r.locate(section, key),
                )
                continue
            value = int(value)
        values[key] = value
    return values


def _model(r: _Reader, cls: Any, values: dict[str, Any], field: str, where: str) -> Any:
    try:
        return cls(**values)
    except ValidationError as exc:
        for err in exc.errors():
            r.add(
                field,
                str(values),
                err["msg"].removeprefix("Value error, "),
                "see data-model.md",
                where,
            )
        return None


def read_boiler_house(
    r: _Reader, doc: Mapping[str, Any], time: TimeSettings | None, signals: dict[str, Signal]
) -> BoilerHouseSpec | None:
    raw = doc.get(SECTION)
    if not isinstance(raw, dict):
        return None
    r.unknown_keys(raw, SECTION, SECTIONS)
    before = len(r.issues)

    def table(name: str) -> Mapping[str, Any]:
        value = raw.get(name, {})
        return value if isinstance(value, dict) else {}

    # fuel
    s = f"{SECTION}.fuel"
    ft = table("fuel")
    r.unknown_keys(
        ft,
        s,
        (
            "kind",
            "C",
            "H",
            "N",
            "S",
            "ash",
            "O",
            "hhv_dry",
            "lhv_dry",
            "moisture_wet_basis",
            "temperature",
        ),
    )
    kind = r.choice(ft, s, "kind", ("wood_chips", "bark", "custom"), "wood_chips")
    comp: dict[str, Any] = {}
    for key in ("C", "H", "N", "S", "ash", "O"):
        if key in ft:
            comp[key] = r.quantity(ft, s, key, "fraction")
    for key in ("hhv_dry", "lhv_dry"):
        if key in ft:
            comp[key] = r.quantity(ft, s, key, "specific_energy")
    fuel: FuelComposition | None = None
    if all(v is not None for v in comp.values()):
        try:
            fuel = FuelComposition.from_input(
                kind=kind,  # type: ignore[arg-type]
                field_prefix=s,
                location=r.locate(s),
                **comp,
            )
        except ScenarioValidationError as exc:
            r.add_issues(exc.issues)
    specs: dict[str, SignalSpec] = {}

    def signal(tbl: Mapping[str, Any], section: str, key: str, dim: str, lo: float, hi: float, allowed: str,
               *, default: float | None = None, required: bool = True) -> None:  # fmt: skip
        if key not in tbl and default is None:
            if required:
                r.add(f"{section}.{key}", "", "required", allowed, r.locate(section))
            return

        def check(v: float) -> tuple[str, str] | None:
            return None if lo <= v <= hi else ("out of range", allowed)

        spec, sig = r.signal(tbl, section, key, dim, time, default=default, check=check)
        if spec is not None and sig is not None:
            specs[f"{section}.{key}"] = spec
            signals[f"{section}.{key}"] = sig

    signal(ft, s, "moisture_wet_basis", "fraction", 0.0, 0.699, "0 ≤ w < 0.70")
    signal(ft, s, "temperature", "temperature", 253.15, 333.15, "253.15-333.15 K")

    # combustion air
    s = f"{SECTION}.combustion_air"
    at = table("combustion_air")
    r.unknown_keys(at, s, ("temperature", "relative_humidity", "mass_flow"))
    signal(at, s, "temperature", "temperature", 253.15, 573.15, "253.15-573.15 K")
    signal(at, s, "relative_humidity", "fraction", 0.0, 1.0, "0-1", required=False)
    signal(at, s, "mass_flow", "mass_flow", 0.0, 1e4, "≥ 0 kg/s", required=False)

    # furnace, heaters, bypass
    s = f"{SECTION}.furnace"
    fu = table("furnace")
    r.unknown_keys(fu, s, tuple(FURNACE_FIELDS))
    furnace = _model(r, FurnaceConfig, _fields(r, fu, s, FURNACE_FIELDS), s, r.locate(s))
    heaters: list[Any] = []
    raw_heaters = raw.get("heaters", [])
    if not isinstance(raw_heaters, list) or not raw_heaters:
        r.add(
            f"{SECTION}.heaters",
            "",
            "required",
            "[[boiler_house.heaters]] tables",
            r.locate(SECTION),
        )
        raw_heaters = []
    for i, ht in enumerate(raw_heaters):
        s = f"{SECTION}.heaters[{i}]"
        htype = ht.get("type", "convective")
        cls = RadiantHeater if htype == "radiant" else ConvectiveHeater
        if htype not in ("radiant", "convective"):
            r.add(
                f"{s}.type",
                htype,
                "invalid value",
                "radiant | convective",
                r.locate("[" + SECTION + ".heaters]"),
            )
        r.unknown_keys(ht, s, ("type", *cls.FIELDS))
        hvalues = _fields(r, ht, s, cls.FIELDS)
        heaters.append(_model(r, cls, hvalues, s, r.locate(f"[{SECTION}.heaters]")))
    s = f"{SECTION}.bypass"
    bt = table("bypass")
    r.unknown_keys(bt, s, ("starts_after_heater", "duct_loss_ua", "position"))
    bvalues = _fields(r, bt, s, BypassConfig.FIELDS)
    if "starts_after_heater" in bt:
        bvalues["starts_after_heater"] = int(bt["starts_after_heater"])
    signal(bt, s, "position", "fraction", 0.0, 1.0, "0-1", default=0.0)
    bvalues.pop("position", None)
    bypass = _model(r, BypassConfig, bvalues, s, r.locate(s))
    config = None
    if (
        furnace is not None
        and bypass is not None
        and heaters
        and all(h is not None for h in heaters)
    ):
        config = _model(r, BoilerHouseConfiguration, {"furnace": furnace, "heaters": heaters, "bypass": bypass},
                        SECTION, r.locate(SECTION))  # fmt: skip

    # thermal oil
    s = f"{SECTION}.thermal_oil"
    ot = table("thermal_oil")
    r.unknown_keys(
        ot,
        s,
        (
            "oil",
            "mass_flow",
            "return_temperature",
            "max_bulk_temperature",
            "max_film_temperature",
            "min_velocity",
        ),
    )
    oil = r.choice(ot, s, "oil", ("shell_s2", "therminol_66"), "shell_s2")
    signal(ot, s, "mass_flow", "mass_flow", 0.0, 1e4, "≥ 0 kg/s")
    signal(ot, s, "return_temperature", "temperature", 273.15, 623.15, "273.15-623.15 K")
    limits = {
        k: r.quantity(ot, s, k, "temperature")
        for k in ("max_bulk_temperature", "max_film_temperature")
        if k in ot
    }
    min_velocity = r.quantity(ot, s, "min_velocity", "velocity", default=2.0) or 2.0

    # controllers
    ct = table("controllers")
    r.unknown_keys(ct, f"{SECTION}.controllers", tuple(LOOPS))
    loops: dict[str, ControllerSpec | None] = {}
    for loop, (meas_dim, out_dim, gain_dim, band_dim, defaults) in LOOPS.items():
        s = f"{SECTION}.controllers.{loop}"
        lt = ct.get(loop)
        if lt is None and loop == "drum_inlet_temperature":
            loops[loop] = None
            continue
        lt = lt if isinstance(lt, dict) else {}
        r.unknown_keys(lt, s, CONTROLLER_KEYS)
        values: dict[str, Any] = {k: v for k, v in defaults.items() if k != "setpoint"}
        dims = {"gain": gain_dim, "integral_time": "time", "tracking_time": "time", "output_min": out_dim,
                "output_max": out_dim, "smoothing": "fraction", "not_reached_band": band_dim,
                "not_reached_hold": "time", "split_value": "fraction", "max_dilution_air": "mass_flow"}  # fmt: skip
        for key, dim in dims.items():
            if key in lt:
                v = r.quantity(lt, s, key, dim)
                if v is not None:
                    values[key] = v
        values["mode"] = r.choice(lt, s, "mode", ("automatic", "manual"), "automatic")
        values["action"] = r.choice(
            lt, s, "action", ("reverse", "direct"), values.get("action", "reverse")
        )
        if "exact" in lt:
            values["exact"] = bool(lt["exact"])
        sp_default = defaults.get("setpoint")
        signal(lt, s, "setpoint", meas_dim, 0.0, 2000.0, "a set point", default=sp_default,
               required=loop != "drum_inlet_temperature" or values["mode"] == "automatic")  # fmt: skip
        if "manual_output" in lt:
            signal(lt, s, "manual_output", out_dim, -1e9, 1e9, "inside the output limits")
        sp_spec = specs.get(f"{s}.setpoint", SignalSpec(constant=0.0))
        manual = specs.get(f"{s}.manual_output")
        if manual is not None and manual.constant is not None:
            values["manual_output"] = manual.constant
        if (
            values["mode"] == "manual"
            and manual is None
            and not (loop == "oxygen" and f"{SECTION}.combustion_air.mass_flow" in specs)
        ):
            r.add(
                f"{s}.manual_output", "", "required in manual mode", "a manual output", r.locate(s)
            )
        loops[loop] = _model(
            r,
            ControllerSpec,
            {**values, "setpoint": sp_spec, "manual_signal": manual},
            s,
            r.locate(s),
        )
        if loops[loop] is None:
            continue
    o2 = loops.get("oxygen")
    if f"{SECTION}.combustion_air.mass_flow" in specs and o2 is not None and o2.mode == "automatic":
        r.add(f"{SECTION}.combustion_air.mass_flow", "", "combustion_air.mass_flow is allowed only with the oxygen loop in manual",
              "remove it or set controllers.oxygen.mode = \"manual\"", r.locate(f"{SECTION}.combustion_air", "mass_flow"))  # fmt: skip

    # initial state
    s = f"{SECTION}.initial_state"
    it = table("initial_state")
    r.unknown_keys(it, s, ("kind", "file"))
    ikind = r.choice(it, s, "kind", ("cold", "steady_state", "explicit"), "steady_state")
    initial = BoilerInitialStateSpec(kind=ikind, file=str(it["file"]) if "file" in it else None)

    if len(r.issues) > before or config is None or fuel is None:
        return None
    oil_ctrl, o2_ctrl = loops.get("oil_temperature"), loops.get("oxygen")
    if oil_ctrl is None or o2_ctrl is None:
        return None
    return BoilerHouseSpec(
        config=config,
        fuel=fuel,
        oil=oil,
        max_bulk_temperature=limits.get("max_bulk_temperature"),
        max_film_temperature=limits.get("max_film_temperature"),
        min_velocity=min_velocity,
        signals=specs,
        controllers=BoilerControllers(
            oil_temperature=oil_ctrl,
            oxygen=o2_ctrl,
            drum_inlet_temperature=loops.get("drum_inlet_temperature"),
        ),
        initial_state=initial,
    )
