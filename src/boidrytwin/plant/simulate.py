"""Plant simulation driver (feature 002; feature-001 pattern of dryer/simulate.py).

The plant state (subsystems plus controller states) is integrated with scipy ``solve_ivp``
(BDF) on states scaled to order one, restarting at every input breakpoint. Cumulative
boundary flows are integrated alongside (two accumulators per quantity), so the balances
close to the solver tolerance. A steady-state start marches with frozen inputs, first
loosely, then polishes with a root solve.
"""

from __future__ import annotations

import time as wallclock
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.optimize import root
from scipy.optimize._numdiff import approx_derivative
from scipy.sparse import csc_matrix, csr_matrix, hstack, vstack
from scipy.sparse.linalg import splu

from boidrytwin.boiler_house.ranges import boiler_range_warnings, flags
from boidrytwin.boiler_house.state import BoilerHouseState
from boidrytwin.checks.plant_balances import (
    PlantBalanceReport,
    plant_entry,
    subsystem_entry,
)
from boidrytwin.checks.ranges import range_warnings as dryer_range_warnings
from boidrytwin.control.pi import not_reached_mask
from boidrytwin.dryer.recirculation import loop_balance, loop_flags, loop_warnings
from boidrytwin.dryer.simulate import steady_state as dryer_steady_state
from boidrytwin.dryer.state import DryerState
from boidrytwin.errors import SimulationError
from boidrytwin.interface.composition import KEYS
from boidrytwin.interface.flue_gas import T_MAX, T_MIN
from boidrytwin.logging import get_logger
from boidrytwin.plant.model import (
    BOILER_QUANTITIES,
    DRYER_QUANTITIES,
    INTERFACE_QUANTITIES,
    Plant,
)
from boidrytwin.progress import Progress, ProgressReporter
from boidrytwin.properties.gas import FloatArray
from boidrytwin.range_warnings import RangeWarning, detect_periods, out_of_range_mask
from boidrytwin.scenario.loader import LoadedScenario

log = get_logger("plant")

STEADY_MARCH_FIRST = 4 * 3600.0  # s, loose-tolerance march into the basin of the root solve
STEADY_LOOSE_RTOL = 1e-4
STEADY_MARCH = 6 * 3600.0
STEADY_MARCH_MAX = 72 * 3600.0
METHOD = "BDF"
NEWTON_MAX = 30  # iterations of the joint steady-state polish (feature 004)
NEWTON_TOL = 1e-11  # largest scaled derivative accepted as steady
NEWTON_MIN_STEP = 1e-3
NEWTON_CHORD_RATE = 0.1  # keep the Jacobian while each step cuts the residual tenfold
SATURATION_MARGIN = 1e-6  # relative to the output span
ENERGY_FLOWS = ("energy", "dryer.energy", "interface.energy", "oil.heat")


@dataclass
class PlantSimulationResult:
    loaded: LoadedScenario
    plant: Plant
    times: FloatArray  # s since scenario start
    results: pd.DataFrame  # boiler house results, index: UTC timestamps
    flue_gas_to_dryer: pd.DataFrame
    initial_state: BoilerHouseState
    final_state: BoilerHouseState
    initial_internal: FloatArray
    final_internal: FloatArray
    cumulative_flows: dict[str, tuple[float, float]]
    balance: PlantBalanceReport
    range_warnings: list[RangeWarning]
    solver_stats: dict[str, Any] = field(default_factory=dict)
    # coupled runs only
    dryer_results: pd.DataFrame | None = None
    dryer_profiles: pd.DataFrame | None = None
    dilution_air: pd.DataFrame | None = None
    dryer_initial_state: DryerState | None = None
    dryer_final_state: DryerState | None = None
    loop_balance: dict[str, Any] | None = None  # mixing chamber check (feature 004)

    @property
    def controller_settings(self) -> dict[str, Any]:
        return self.plant.controller_settings()


def flow_keys(plant: Plant) -> tuple[str, ...]:
    return (*plant.flow_keys, "oil.heat")


class _Scaled:
    """Plant plus flow accumulators on order-one scaled states.

    ``upstream=True``: only the boiler house and controller states, no accumulators (the
    first stage of a coupled steady state).
    """

    def __init__(
        self, plant: Plant, t0: float = 0.0, frozen_at: float | None = None,
        *, upstream: bool = False,
    ) -> None:  # fmt: skip
        self.plant = plant
        self.frozen_at = frozen_at
        self.upstream = upstream
        self.keys = flow_keys(plant)
        rated = plant.spec.config.furnace.rated_fuel_power
        mass_ref = rated / 1e7 * 10.0 * 3600.0  # ~ flue gas kg/h at rated load
        energy_ref = rated * 3600.0
        oil_ref = max(plant._value("boiler_house.thermal_oil.mass_flow", 0.0), 1.0) * 5e5 * 3600.0
        acc = []
        for q in self.keys:
            ref = oil_ref if q == "oil_energy" else energy_ref if q in ENERGY_FLOWS else mass_ref
            acc += [ref, ref]
        if upstream:
            self.n = plant.n_upstream
            self.n_acc = 0
            self.scale = plant.scales(t0)[: self.n]
            self.pad = np.zeros(plant.size - self.n)
        else:
            self.n = plant.size
            self.n_acc = len(acc)
            self.scale = np.concatenate([plant.scales(t0), acc])

    def rhs(self, t: float, z: FloatArray) -> FloatArray:
        tt = t if self.frozen_at is None else self.frozen_at
        y = z[: self.n] * self.scale[: self.n]
        if self.upstream:
            ev = self.plant.evaluate(tt, np.concatenate([y, self.pad]), with_dryer=False)
            return np.asarray(ev.dz[: self.n] / self.scale)
        ev = self.plant.evaluate(tt, y)
        flows = dict(ev.flows)
        heat = float(ev.boiler.results["heat_to_oil"])
        flows["oil.heat"] = (heat, heat)
        acc = np.array([v for q in self.keys for v in flows[q]])
        return np.asarray(np.concatenate([ev.dz, acc]) / self.scale)

    def sparsity(self) -> csr_matrix:
        # accumulator rows never feed back; leave them out of the Jacobian pattern
        core = self.plant.jac_sparsity()
        if self.upstream:
            return csr_matrix(core[: self.n, : self.n])
        right = csr_matrix((self.n, self.n_acc), dtype=np.int8)
        bottom = csr_matrix((self.n_acc, self.n + self.n_acc), dtype=np.int8)
        return csr_matrix(vstack([hstack([core, right]), bottom]))


def _integrate(
    sys: _Scaled, z0: FloatArray, t_span: tuple[float, float], t_eval: FloatArray | None,
    rtol: float, atol: float, stats: dict[str, Any],
) -> tuple[FloatArray, FloatArray]:  # fmt: skip
    sol = solve_ivp(
        sys.rhs, t_span, z0, method=METHOD, t_eval=t_eval, rtol=rtol, atol=atol,
        jac_sparsity=sys.sparsity(),
    )  # fmt: skip
    stats["nfev"] += int(sol.nfev)
    stats["njev"] += int(sol.njev)
    stats["nlu"] += int(sol.nlu)
    stats["segments"] += 1
    if not sol.success:
        raise SimulationError(f"solver failed at t = {sol.t[-1]:.1f} s: {sol.message}")
    return sol.t, sol.y


def _physical(plant: Plant, x: FloatArray, *, upstream: bool = False) -> bool:
    lay = plant.boiler.layout
    ok = bool(x[lay.bed_water] >= 0 and x[lay.bed_dry] >= 0)
    if plant.coupled and plant.dryer is not None and not upstream:
        masses = plant.dryer.solids_masses(x[plant.dryer_slice])
        ok = ok and bool(np.all(masses >= -1e-9))
    return ok


def steady_state(plant: Plant, t: float, rtol: float, atol: float) -> FloatArray:
    """Steady state of the plant (controllers included) for the inputs at time ``t``.

    Coupled plants in two stages, because nothing upstream depends on the dryer: the boiler
    house with all loops first, then the dryer for the resulting inlet (feature-001 solver).
    """
    z_cold = plant.initial_cold(t)
    if not plant.coupled:
        return _march_and_polish(plant, _Scaled(plant, t, frozen_at=t), z_cold, t, rtol, atol)
    assert plant.dryer is not None
    n_up = plant.n_upstream
    # with a recirculation, stage 1 lets the drum inlet loop see the fresh gas only
    plant.fresh_inlet_only = not plant.upstream_independent
    try:
        up = _march_and_polish(plant, _Scaled(plant, t, frozen_at=t, upstream=True),
                               z_cold[:n_up], t, rtol, atol)  # fmt: skip
    finally:
        plant.fresh_inlet_only = False
    z = z_cold.copy()
    z[:n_up] = up
    plant.evaluate(t, z, with_dryer=False)  # sets the dryer's inlet to the steady values
    z[plant.dryer_slice] = dryer_steady_state(plant.dryer, t, rtol, atol)
    if plant.upstream_independent:
        return z
    # recirculation: the dryer outlet feeds the drum inlet loop back; polish the whole plant
    # from the two-stage result by Newton, else march (research R6)
    z = plant.with_integrals(t, z, plant.controllers(t, z)[0])
    sys = _Scaled(plant, t, frozen_at=t)
    polished = _newton(plant, sys, z, t)
    if polished is not None:
        return polished
    log.warning("steady_state_newton_failed", fallback="march")
    return _march_and_polish(plant, sys, z, t, rtol, atol)


def _newton(plant: Plant, sys: _Scaled, z: FloatArray, t: float) -> FloatArray | None:
    """Damped Newton on the scaled plant state with a sparse finite-difference Jacobian
    (the plant's sparsity pattern); None if it does not converge."""
    n = sys.n
    acc = np.zeros(sys.n_acc)

    def f(x: FloatArray) -> FloatArray:
        return np.asarray(sys.rhs(t, np.concatenate([x, acc]))[:n])

    x = z / sys.scale[:n]
    F = f(x)
    pattern = plant.jac_sparsity()
    lu = None  # factorised Jacobian, kept while full steps converge fast (chord steps)
    for _ in range(NEWTON_MAX):
        res = float(np.max(np.abs(F)))
        if res < NEWTON_TOL:
            out = x * sys.scale[:n]
            return out if _physical(plant, out) else None
        fresh = lu is None
        if lu is None:
            lu = splu(csc_matrix(approx_derivative(f, x, sparsity=pattern, f0=F)))
        dx = lu.solve(-F)
        lam = 1.0
        while lam >= NEWTON_MIN_STEP:
            x_new = x + lam * dx
            F_new = f(x_new)
            if np.all(np.isfinite(F_new)) and float(np.max(np.abs(F_new))) < res:
                break
            lam *= 0.5
        else:
            if fresh:
                return None
            lu = None  # the old Jacobian no longer points downhill: rebuild it
            continue
        if lam < 1.0 or float(np.max(np.abs(F_new))) > NEWTON_CHORD_RATE * res:
            lu = None
        x, F = x_new, F_new
    return None


def _march_and_polish(
    plant: Plant, sys: _Scaled, z_start: FloatArray, t: float, rtol: float, atol: float
) -> FloatArray:
    z_cold = z_start
    z = np.concatenate([z_cold, np.zeros(sys.n_acc)]) / sys.scale
    stats = {"nfev": 0, "njev": 0, "nlu": 0, "segments": 0}
    n = sys.n

    def residual(zm: FloatArray) -> FloatArray:
        return sys.rhs(t, np.concatenate([zm, z[n:]]))[:n]

    marched = 0.0
    best = z[:n]
    while marched < STEADY_MARCH_MAX:
        first = marched == 0.0
        span = STEADY_MARCH_FIRST if first else STEADY_MARCH
        tol = (STEADY_LOOSE_RTOL, STEADY_LOOSE_RTOL * 1e-2) if first else (rtol, atol)
        _, ys = _integrate(sys, z, (0.0, span), None, tol[0], tol[1], stats)
        z = ys[:, -1]
        marched += span
        best = z[:n]
        sol = root(residual, best, method="hybr", options={"xtol": 1e-12})
        res_march = float(np.max(np.abs(residual(best))))
        if sol.success and np.all(np.isfinite(sol.x)):
            res_root = float(np.max(np.abs(residual(sol.x))))
            x = sol.x * sys.scale[:n]
            if res_root < res_march and _physical(plant, x, upstream=sys.upstream):
                return np.asarray(x)
        if not first and res_march * STEADY_MARCH < 1e-6:
            break
    return np.asarray(best * sys.scale[:n])


def initial_state(plant: Plant, loaded: LoadedScenario) -> FloatArray:
    ts = loaded.spec.time
    init = plant.spec.initial_state
    if init.kind == "cold":
        return plant.initial_cold(0.0)
    if init.kind == "steady_state":
        return steady_state(plant, 0.0, ts.rtol, ts.atol)
    assert init.file is not None
    path = Path(init.file)
    if not path.is_absolute():
        path = Path(loaded.path).parent / path
    state = BoilerHouseState.load(path)
    if state.layout != plant.boiler.layout:
        raise SimulationError(f"initial state {path.name} does not match the heater arrangement")
    u0 = plant.initial_outputs()
    z = np.zeros(plant.size)
    z[: plant.nb] = plant.boiler.to_internal(state, plant.boiler_inputs(0.0, z, u0))
    if plant.coupled:
        assert plant.dryer is not None
        if loaded.initial_state is None:
            raise SimulationError(
                'explicit coupled start needs the dryer state: [initial_state] kind = "explicit"'
            )
        plant.prepare_dryer(0.0, z, u0)
        z[plant.dryer_slice] = plant.dryer.to_internal(loaded.initial_state, 0.0)
        z[plant.i_drum_meas] = float(
            state.extra.get("drum_inlet_measured", plant.dryer.inlet(0.0).temperature)
        )
    integrals = state.extra.get("controller_integrals")
    if integrals and all(name in integrals for name in plant.loops):
        for name in plant.loops:
            z[plant.index[name]] = float(integrals[name])
        return z
    return plant.with_integrals(0.0, z, u0)


def _to_state(plant: Plant, t: float, z: FloatArray) -> BoilerHouseState:
    ev = plant.evaluate(t, z)
    inputs = plant.boiler_inputs(t, z, {k: v["output"] for k, v in ev.controller.items()})
    state = plant.boiler.to_state(z[: plant.nb], inputs)
    state.extra["controller_integrals"] = {
        name: float(z[plant.index[name]]) for name in plant.loops
    }
    if plant.coupled:
        state.extra["drum_inlet_measured"] = float(z[plant.i_drum_meas])
    state.extra["time"] = t
    return state


@dataclass
class _Rows:
    boiler: list[dict[str, Any]] = field(default_factory=list)
    flue: list[dict[str, Any]] = field(default_factory=list)
    dilution: list[dict[str, Any]] = field(default_factory=list)
    dryer: list[dict[str, Any]] = field(default_factory=list)
    profiles: list[pd.DataFrame] = field(default_factory=list)


def _rows(
    plant: Plant, t_all: FloatArray, z_all: FloatArray, index: pd.DatetimeIndex, profiles: bool
) -> _Rows:
    out = _Rows()
    for i, t in enumerate(t_all):
        z = z_all[:, i]
        ev = plant.evaluate(float(t), z)
        row = dict(ev.boiler.results)
        row["dilution_air_flow"] = ev.dilution_air
        for name, loop in plant.loops.items():
            c = ev.controller[name]
            row[f"controller_output_{name}"] = c["output"]
            row[f"controller_mode_{name}"] = loop.spec.mode
            row[f"_v_{name}"] = c["unsaturated"]
            row[f"_e_{name}"] = c["setpoint"] - c["measurement"]
        if ev.drum_inlet_temperature is not None:
            row["drum_inlet_temperature_measured"] = ev.controller["drum_inlet_temperature"][
                "measurement"
            ]
        out.boiler.append(row)
        g = ev.boiler.flue_gas_to_dryer
        entry: dict[str, Any] = {
            "mass_flow": g.mass_flow,
            "temperature": g.temperature,
            "pressure": g.pressure,
        }
        entry.update({k: float(v) for k, v in zip(KEYS, g.x, strict=True)})
        entry["quality"] = g.quality
        out.flue.append(entry)
        if plant.coupled:
            assert plant.dryer is not None
            # the plant evaluation above set the dryer's interfaces for this time
            y_d = z[plant.dryer_slice]
            out.dilution.append({"dilution": ev.dilution_air})
            out.dryer.append(plant.dryer.diagnostics(float(t), y_d))
            if profiles:
                frame = pd.DataFrame(plant.dryer.profiles(float(t), y_d))
                frame.insert(0, "cell", np.arange(plant.dryer.n))
                frame.insert(0, "time", index[i])
                out.profiles.append(frame)
    return out


def _controller_flags(plant: Plant, t_all: FloatArray, results: pd.DataFrame) -> None:
    saturated = np.zeros(len(results), dtype=bool)
    not_reached = np.zeros(len(results), dtype=bool)
    for name, loop in plant.loops.items():
        s = loop.spec
        v = results[f"_v_{name}"].to_numpy(dtype=float)
        margin = SATURATION_MARGIN * (s.output_max - s.output_min)
        sat = (v > s.output_max + margin) | (v < s.output_min - margin)
        if s.mode == "automatic":
            saturated |= sat
            _log_periods("controller_saturated", name, results.index, sat)
        nr = not_reached_mask(
            t_all, results[f"_e_{name}"].to_numpy(), s.not_reached_band, s.not_reached_hold
        )
        not_reached |= nr
        _log_periods("setpoint_not_reached", name, results.index, nr)
    results["controller_saturated"] = saturated
    results["setpoint_not_reached"] = not_reached


def _log_periods(event: str, loop: str, index: pd.Index, mask: np.ndarray) -> None:
    if not mask.any():
        return
    edges = np.flatnonzero(np.diff(np.concatenate([[0], mask.astype(int), [0]])))
    for a, b in zip(edges[::2], edges[1::2], strict=True):
        log.warning(event, loop=loop, period_start=str(index[a]), period_end=str(index[b - 1]))


def balance_report(
    plant: Plant, loaded: LoadedScenario, cumulative: dict[str, tuple[float, float]],
    z0: FloatArray, z1: FloatArray,
) -> PlantBalanceReport:  # fmt: skip
    tol = loaded.spec.balance_tolerances
    start, end = plant.storage(z0), plant.storage(z1)
    boiler_q = [q for q in BOILER_QUANTITIES if q != "oil_energy"]
    entries = {
        "boiler_house": subsystem_entry(cumulative, start, end, boiler_q, tol),
        "oil_circuit": subsystem_entry(
            cumulative, start, end, ["oil_energy"], tol, rename={"oil_energy": "energy"}
        ),
    }
    if plant.coupled:
        dryer_q = [f"dryer.{q}" for q in DRYER_QUANTITIES]
        entries["dryer"] = subsystem_entry(
            cumulative, start, end, dryer_q, tol, rename={k: k.split(".", 1)[1] for k in dryer_q}
        )
        iface_q = [f"interface.{q}" for q in INTERFACE_QUANTITIES]
        zero = dict.fromkeys(iface_q, 0.0)
        entries["interface"] = subsystem_entry(
            cumulative, zero, zero, iface_q, tol, rename={k: k.split(".", 1)[1] for k in iface_q}
        )
        entries["plant"] = plant_entry(cumulative, start, end, tol)
    return PlantBalanceReport(entries=entries)


def _range_warnings(
    plant: Plant, results: pd.DataFrame, max_bulk: float, max_film: float
) -> list[RangeWarning]:
    index = pd.DatetimeIndex(results.index)
    warnings = boiler_range_warnings(results, max_bulk=max_bulk, max_film=max_film)
    for v in plant.spec.config.validated_range_violations():
        warnings.append(RangeWarning(
            quantity=f"boiler_house.{v.field}", limit_type=v.limit_type, limit=v.limit,
            observed_extreme=v.value, period_start=index[0].to_pydatetime(),
            period_end=index[-1].to_pydatetime(),
        ))  # fmt: skip
    return warnings


def _interface_warnings(flue: pd.DataFrame) -> list[RangeWarning]:
    """The boiler outlet against the interface ranges: a warning, never an exception."""
    index = pd.DatetimeIndex(flue.index)
    T = flue["temperature"].to_numpy()
    out = detect_periods(
        index, T, limit=T_MAX, limit_type="max", quantity="flue_gas_to_dryer_temperature"
    )
    out += detect_periods(
        index, T, limit=T_MIN, limit_type="min", quantity="flue_gas_to_dryer_temperature"
    )
    return out


def simulate_plant(
    loaded: LoadedScenario, *, profiles: bool = False, progress: Progress | None = None
) -> PlantSimulationResult:
    """Run a scenario with a boiler house. Raises :class:`SimulationError` on solver failure.

    ``progress`` (optional) only observes the solver; see :mod:`boidrytwin.progress`.
    """
    if loaded.spec.boiler_house is None:
        raise SimulationError("scenario has no [boiler_house] section")
    plant = Plant(loaded)
    ts = loaded.spec.time
    duration, dt = ts.duration, ts.output_interval
    subsystems = ["boiler_house", "dryer"] if plant.coupled else ["boiler_house"]
    log.info("plant_run_started", subsystems=subsystems, simulated_s=duration,
             initial_state=plant.spec.initial_state.kind)  # fmt: skip
    t_out = np.arange(0.0, duration + 0.5 * dt, dt)
    t_out = t_out[t_out <= duration + 1e-9]
    if t_out[-1] < duration:
        t_out = np.append(t_out, duration)

    started = wallclock.perf_counter()
    reporter = ProgressReporter(progress, duration)
    if plant.spec.initial_state.kind == "steady_state":
        reporter.phase("initialising")
    z0 = initial_state(plant, loaded)
    sys = _Scaled(plant, 0.0)
    reporter.phase("simulating", 0.0)
    sys.rhs = reporter.wrap(sys.rhs)  # type: ignore[method-assign]
    z = np.concatenate([z0, np.zeros(sys.n_acc)]) / sys.scale
    stats: dict[str, Any] = {"method": METHOD, "rtol": ts.rtol, "atol": ts.atol}
    stats.update(nfev=0, njev=0, nlu=0, segments=0)
    bp = plant.breakpoints()
    bp = bp[(bp > 0.0) & (bp < duration)]
    edges = np.concatenate([[0.0], bp, [duration]])
    times: list[FloatArray] = []
    states: list[FloatArray] = []
    for k in range(len(edges) - 1):
        a, b = edges[k], edges[k + 1]
        last = k == len(edges) - 2
        inside = t_out[(t_out >= a) & ((t_out <= b) if last else (t_out < b))]
        eval_points = np.unique(np.concatenate([inside, [b]]))
        tt, yy = _integrate(sys, z, (a, b), eval_points, ts.rtol, ts.atol, stats)
        z = yy[:, -1]
        keep = np.isin(tt, inside)
        times.append(tt[keep])
        states.append(yy[:, keep])
    stats["wall_time_s"] = wallclock.perf_counter() - started
    reporter.seen(duration, force=True)
    reporter.phase("writing")

    t_all = np.concatenate(times)
    y_all = np.concatenate(states, axis=1) * sys.scale[:, None]
    n = sys.n
    index = pd.DatetimeIndex([ts.start + timedelta(seconds=float(t)) for t in t_all], name="time")
    rows = _rows(plant, t_all, y_all[:n], index, profiles)
    results = pd.DataFrame(rows.boiler, index=index)
    flue_frame = pd.DataFrame(rows.flue, index=index)

    oil = plant.boiler.oil
    max_bulk = plant.spec.max_bulk_temperature or oil.max_bulk_temperature
    max_film = plant.spec.max_film_temperature or oil.max_film_temperature
    results = results.join(flags(results, max_bulk=max_bulk, max_film=max_film))
    _controller_flags(plant, t_all, results)
    warnings = _range_warnings(plant, results, max_bulk, max_film)
    results["out_of_range"] = out_of_range_mask(index, warnings)
    results = results.drop(columns=[c for c in results.columns if c.startswith("_")])

    dryer_results = dryer_profiles = dilution = None
    loop_report = None
    if plant.coupled:
        assert plant.dryer is not None
        dryer_results = pd.DataFrame(rows.dryer, index=index)
        recirculation_violations = [
            v for v in loaded.config_warnings if v.field.startswith("recirculation.")
        ]
        dryer_warnings = dryer_range_warnings(
            dryer_results,
            plant.dryer.config,
            plant.dryer.config.validated_range_violations() + recirculation_violations,
        )
        dryer_warnings += _interface_warnings(flue_frame)
        loop = plant.dryer.recirculation
        if loop is not None:
            loop_flags(loop, t_all, dryer_results)
            dryer_warnings += loop_warnings(loop, dryer_results)
            loop_report = loop_balance(dryer_results, loaded.spec.balance_tolerances)
            # the dryer's pressure loop counts like the plant loops (FR-008)
            for flag in ("controller_saturated", "setpoint_not_reached"):
                results[flag] = results[flag].to_numpy() | dryer_results[flag].to_numpy()
        dryer_results["out_of_range"] = out_of_range_mask(index, dryer_warnings)
        dryer_results = dryer_results.drop(
            columns=[c for c in dryer_results.columns if c.startswith("_")]
        )
        warnings += dryer_warnings
        dilution = pd.DataFrame(rows.dilution, index=index)
        if profiles:
            dryer_profiles = pd.concat(rows.profiles).set_index(["time", "cell"])

    acc = y_all[n:, -1]
    cumulative = {q: (float(acc[2 * i]), float(acc[2 * i + 1])) for i, q in enumerate(sys.keys)}
    z_final = y_all[:n, -1]
    balance = balance_report(plant, loaded, cumulative, z0, z_final)
    residuals = {
        f"residual_{name}_{q}": b.relative_residual
        for name, entry in balance.entries.items()
        for q, b in entry.items()
    }
    log.info(
        "checks_completed",
        balances_passed=balance.passed,
        range_warnings=len(warnings),
        **residuals,
    )
    log.info(
        "simulation_completed",
        simulated_s=duration,
        wall_time_s=round(stats["wall_time_s"], 3),
        nfev=stats["nfev"],
        segments=stats["segments"],
    )
    dryer_initial = dryer_final = None
    if plant.coupled:
        assert plant.dryer is not None
        plant.evaluate(0.0, z0)
        dryer_initial = plant.dryer.to_state(z0[plant.dryer_slice], 0.0)
        plant.evaluate(float(t_all[-1]), z_final)
        dryer_final = plant.dryer.to_state(z_final[plant.dryer_slice], float(t_all[-1]))
    return PlantSimulationResult(
        loaded=loaded,
        plant=plant,
        times=t_all,
        results=results,
        flue_gas_to_dryer=flue_frame,
        initial_state=_to_state(plant, 0.0, z0),
        final_state=_to_state(plant, float(t_all[-1]), z_final),
        initial_internal=z0,
        final_internal=z_final,
        cumulative_flows=cumulative,
        balance=balance,
        range_warnings=warnings,
        solver_stats=stats,
        dryer_results=dryer_results,
        dryer_profiles=dryer_profiles,
        dilution_air=dilution,
        dryer_initial_state=dryer_initial,
        dryer_final_state=dryer_final,
        loop_balance=loop_report,
    )
