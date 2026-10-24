"""Plant simulation driver (feature 002; feature-001 pattern of dryer/simulate.py).

The plant state (subsystems plus controller integrals) is integrated with scipy
``solve_ivp`` (BDF) on states scaled to order one, restarting at every input breakpoint.
Cumulative boundary flows are integrated alongside (two accumulators per quantity), so the
balances close to the solver tolerance. A steady-state start marches with frozen inputs,
first loosely, then polishes with a root solve.
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
from scipy.sparse import csr_matrix, hstack, vstack

from boidrytwin.boiler_house.ranges import boiler_range_warnings, flags
from boidrytwin.boiler_house.state import BoilerHouseState
from boidrytwin.checks.plant_balances import PlantBalanceReport, subsystem_entry
from boidrytwin.control.pi import not_reached_mask
from boidrytwin.errors import SimulationError
from boidrytwin.interface.composition import KEYS
from boidrytwin.logging import get_logger
from boidrytwin.plant.model import BOILER_QUANTITIES, LOOPS, Plant
from boidrytwin.properties.gas import FloatArray
from boidrytwin.range_warnings import RangeWarning, out_of_range_mask
from boidrytwin.scenario.loader import LoadedScenario

log = get_logger("plant")

N_ACC = 2 * len(BOILER_QUANTITIES)
STEADY_MARCH_FIRST = 4 * 3600.0  # s, loose-tolerance march into the basin of the root solve
STEADY_LOOSE_RTOL = 1e-4
STEADY_MARCH = 6 * 3600.0
STEADY_MARCH_MAX = 72 * 3600.0
METHOD = "BDF"
SATURATION_MARGIN = 1e-6  # relative to the output span


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

    @property
    def controller_settings(self) -> dict[str, Any]:
        return self.plant.controller_settings()


class _Scaled:
    """Plant plus flow accumulators on order-one scaled states."""

    def __init__(self, plant: Plant, frozen_at: float | None = None) -> None:
        self.plant = plant
        self.frozen_at = frozen_at
        rated = plant.spec.config.furnace.rated_fuel_power
        mass_ref = rated / 1e7 * 10.0 * 3600.0  # ~ flue gas kg/h at rated load
        energy_ref = rated * 3600.0
        oil_ref = max(plant._value("boiler_house.thermal_oil.mass_flow", 0.0), 1.0) * 5e5 * 3600.0
        acc = []
        for q in BOILER_QUANTITIES:
            ref = energy_ref if q == "energy" else oil_ref if q == "oil_energy" else mass_ref
            acc += [ref, ref]
        self.n = plant.size
        self.scale = np.concatenate([plant.scales(), acc])

    def rhs(self, t: float, z: FloatArray) -> FloatArray:
        tt = t if self.frozen_at is None else self.frozen_at
        y = z[: self.n] * self.scale[: self.n]
        deriv, flows = self.plant.rhs_and_flows(tt, y)
        acc = np.array([v for q in BOILER_QUANTITIES for v in flows[q]])
        return np.asarray(np.concatenate([deriv, acc]) / self.scale)

    def sparsity(self) -> csr_matrix:
        # accumulator rows never feed back; leave them out of the Jacobian pattern
        core = self.plant.jac_sparsity()
        right = csr_matrix((self.n, N_ACC), dtype=np.int8)
        bottom = csr_matrix((N_ACC, self.n + N_ACC), dtype=np.int8)
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


def steady_state(plant: Plant, t: float, rtol: float, atol: float) -> FloatArray:
    """Steady state of the plant (controllers included) for the inputs at time ``t``."""
    sys = _Scaled(plant, frozen_at=t)
    z = np.concatenate([plant.initial_cold(t), np.zeros(N_ACC)]) / sys.scale
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
            lay = plant.boiler.layout
            x = sol.x * sys.scale[:n]
            if res_root < res_march and x[lay.bed_water] >= 0 and x[lay.bed_dry] >= 0:
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
    z = np.zeros(plant.size)
    z[: plant.nb] = plant.boiler.to_internal(
        state, plant.boiler_inputs(0.0, z, plant.initial_outputs())
    )
    integrals = state.extra.get("controller_integrals")
    if integrals:
        for name in LOOPS:
            z[plant.index[name]] = float(integrals[name])
        return z
    return plant.with_integrals(0.0, z, plant.initial_outputs())


def _to_state(plant: Plant, t: float, z: FloatArray) -> BoilerHouseState:
    ev = plant.evaluate(t, z)
    inputs = plant.boiler_inputs(t, z, {k: v["output"] for k, v in ev.controller.items()})
    state = plant.boiler.to_state(z[: plant.nb], inputs)
    state.extra["controller_integrals"] = {name: float(z[plant.index[name]]) for name in LOOPS}
    state.extra["time"] = t
    return state


def _rows(
    plant: Plant, t_all: FloatArray, z_all: FloatArray
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows, flue = [], []
    for i, t in enumerate(t_all):
        z = z_all[:, i]
        ev = plant.evaluate(float(t), z)
        row = dict(ev.boiler.results)
        row["dilution_air_flow"] = 0.0  # boiler-house-only: no drum inlet loop
        for name, loop in plant.loops.items():
            c = ev.controller[name]
            row[f"controller_output_{name}"] = c["output"]
            row[f"controller_mode_{name}"] = loop.spec.mode
            row[f"_v_{name}"] = c["unsaturated"]
            row[f"_e_{name}"] = c["setpoint"] - c["measurement"]
        rows.append(row)
        g = ev.boiler.flue_gas_to_dryer
        entry = {"mass_flow": g.mass_flow, "temperature": g.temperature, "pressure": g.pressure}
        entry.update({k: float(v) for k, v in zip(KEYS, g.x, strict=True)})
        flue.append(entry)
    return rows, flue


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
    return PlantBalanceReport(
        entries={
            "boiler_house": subsystem_entry(cumulative, start, end, boiler_q, tol),
            "oil_circuit": subsystem_entry(
                cumulative, start, end, ["oil_energy"], tol, rename={"oil_energy": "energy"}
            ),
        }
    )


def simulate_plant(loaded: LoadedScenario) -> PlantSimulationResult:
    """Run a scenario with a boiler house. Raises :class:`SimulationError` on solver failure."""
    if loaded.spec.boiler_house is None:
        raise SimulationError("scenario has no [boiler_house] section")
    if loaded.spec.dryer is not None:
        raise SimulationError("coupled boiler house and dryer runs are not implemented yet (US2)")
    plant = Plant(loaded)
    ts = loaded.spec.time
    duration, dt = ts.duration, ts.output_interval
    log.info("plant_run_started", subsystems=["boiler_house"], simulated_s=duration,
             initial_state=plant.spec.initial_state.kind)  # fmt: skip
    t_out = np.arange(0.0, duration + 0.5 * dt, dt)
    t_out = t_out[t_out <= duration + 1e-9]
    if t_out[-1] < duration:
        t_out = np.append(t_out, duration)

    started = wallclock.perf_counter()
    z0 = initial_state(plant, loaded)
    sys = _Scaled(plant)
    z = np.concatenate([z0, np.zeros(N_ACC)]) / sys.scale
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

    t_all = np.concatenate(times)
    y_all = np.concatenate(states, axis=1) * sys.scale[:, None]
    n = sys.n
    rows, flue = _rows(plant, t_all, y_all[:n])
    index = pd.DatetimeIndex([ts.start + timedelta(seconds=float(t)) for t in t_all], name="time")
    results = pd.DataFrame(rows, index=index)
    flue_frame = pd.DataFrame(flue, index=index)

    oil = plant.boiler.oil
    max_bulk = plant.spec.max_bulk_temperature or oil.max_bulk_temperature
    max_film = plant.spec.max_film_temperature or oil.max_film_temperature
    results = results.join(flags(results, max_bulk=max_bulk, max_film=max_film))
    _controller_flags(plant, t_all, results)
    warnings = boiler_range_warnings(results, max_bulk=max_bulk, max_film=max_film)
    for v in loaded.config_warnings:
        warnings.append(RangeWarning(
            quantity=f"boiler_house.{v.field}", limit_type=v.limit_type, limit=v.limit,
            observed_extreme=v.value, period_start=index[0].to_pydatetime(),
            period_end=index[-1].to_pydatetime(),
        ))  # fmt: skip
    results["out_of_range"] = out_of_range_mask(index, warnings)
    results = results.drop(columns=[c for c in results.columns if c.startswith("_")])

    acc = y_all[n:, -1]
    cumulative = {
        q: (float(acc[2 * i]), float(acc[2 * i + 1])) for i, q in enumerate(BOILER_QUANTITIES)
    }
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
    )
