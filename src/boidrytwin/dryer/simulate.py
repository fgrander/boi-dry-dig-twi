"""Simulation driver: initial states, ODE integration and output sampling (research.md R7).

The model is integrated with scipy ``solve_ivp`` (BDF) on states scaled to order one, with
the banded Jacobian pattern of :meth:`DrumDryerModel.jac_sparsity`. The integration restarts
at every input breakpoint (where a time series changes slope) instead of limiting the step.
Cumulative boundary flows are integrated alongside the model (8 accumulator states) so that
the balance check (US3) is exact to the solver tolerance.
"""

from __future__ import annotations

import math
import time as wallclock
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.optimize import root
from scipy.sparse import csr_matrix, hstack, vstack

from boidrytwin.dryer.model import DrumDryerModel, ModelInputs
from boidrytwin.dryer.state import DryerState
from boidrytwin.errors import SimulationError
from boidrytwin.logging import get_logger
from boidrytwin.properties.gas import FloatArray
from boidrytwin.scenario.loader import LoadedScenario, require_runnable

log = get_logger("dryer")

QUANTITIES = ("dry_solids", "water", "gas", "energy")
N_ACC = 2 * len(QUANTITIES)  # inflow and outflow per quantity
STEADY_MARCH_FIRST = 2 * 3600.0  # s, loose-tolerance march into the basin of the root solve
STEADY_LOOSE_RTOL = 1e-3
STEADY_MARCH = 6 * 3600.0  # s per further full-tolerance march if the polish fails
STEADY_MARCH_MAX = 96 * 3600.0
METHOD = "BDF"


@dataclass
class SimulationResult:
    loaded: LoadedScenario
    model: DrumDryerModel
    times: FloatArray  # s since scenario start
    results: pd.DataFrame  # index: UTC timestamps
    profiles: pd.DataFrame | None
    initial_state: DryerState
    final_state: DryerState
    initial_internal: FloatArray
    final_internal: FloatArray
    cumulative_flows: dict[str, tuple[float, float]]  # quantity -> (in, out) over the run
    solver_stats: dict[str, Any] = field(default_factory=dict)

    @property
    def time_constants(self) -> tuple[float, float]:
        """(mean solids residence time, shell time constant), s, at the final state."""
        return self.model.time_constants(self.times[-1], self.final_internal)


def build_model(loaded: LoadedScenario) -> DrumDryerModel:
    require_runnable(loaded)
    assert loaded.spec.dryer is not None
    sig = loaded.signals
    inputs = ModelInputs(
        flue_gas=loaded.flue_gas,
        dilution_air=sig["dilution_air.mass_flow"],
        feed_mass_flow_wet=sig["product_feed.mass_flow_wet"],
        feed_moisture_wet=sig["product_feed.moisture_wet_basis"],
        feed_temperature=sig["product_feed.temperature"],
        ambient_temperature=sig["ambient.temperature"],
        ambient_relative_humidity=sig["ambient.relative_humidity"],
        ambient_pressure=sig["ambient.pressure"],
    )
    return DrumDryerModel(loaded.spec.dryer, inputs)


def _breakpoints(model: DrumDryerModel, duration: float) -> FloatArray:
    inp = model.inputs
    points = [inp.flue_gas.breakpoints()]
    for name in ModelInputs.__dataclass_fields__:
        if name != "flue_gas":
            points.append(getattr(inp, name).breakpoints())
    allp = np.unique(np.concatenate(points)) if points else np.empty(0)
    return np.asarray(allp[(allp > 0.0) & (allp < duration)], dtype=float)


class _Scaled:
    """Model plus flow accumulators on order-one scaled states."""

    def __init__(self, model: DrumDryerModel, t0: float, frozen_at: float | None = None) -> None:
        self.model = model
        self.frozen_at = frozen_at
        inlet = model.inlet(t0)
        flow_ref = max(inlet.feed_dry + inlet.feed_water + inlet.dry_gas_flow, 1.0) * 3600.0
        energy_ref = max(abs(inlet.heat_supplied), 1e5) * 3600.0
        acc = np.array([flow_ref, flow_ref] * 3 + [energy_ref, energy_ref])
        self.n_model = model.n * 8
        self.scale = np.concatenate([model.scales(t0), acc])

    def rhs(self, t: float, z: FloatArray) -> FloatArray:
        tt = t if self.frozen_at is None else self.frozen_at
        y = z[: self.n_model] * self.scale[: self.n_model]
        deriv, flows = self.model.rhs_and_flows(tt, y)
        acc = np.array([v for q in QUANTITIES for v in flows[q]])
        return np.asarray(np.concatenate([deriv, acc]) / self.scale)

    def sparsity(self) -> csr_matrix:
        # accumulator rows are pure quadrature of the boundary flows and never feed back;
        # leaving them out of the pattern keeps the finite-difference Jacobian banded
        core = self.model.jac_sparsity()
        n = self.n_model
        right = csr_matrix((n, N_ACC), dtype=np.int8)
        bottom = csr_matrix((N_ACC, n + N_ACC), dtype=np.int8)
        return csr_matrix(vstack([hstack([core, right]), bottom]))


def _integrate(
    sys: _Scaled, z0: FloatArray, t_span: tuple[float, float], t_eval: FloatArray | None,
    rtol: float, atol: float, stats: dict[str, Any],
) -> tuple[FloatArray, FloatArray]:  # fmt: skip
    sol = solve_ivp(
        sys.rhs,
        t_span,
        z0,
        method=METHOD,
        t_eval=t_eval,
        rtol=rtol,
        atol=atol,
        jac_sparsity=sys.sparsity(),
    )
    stats["nfev"] += int(sol.nfev)
    stats["njev"] += int(sol.njev)
    stats["nlu"] += int(sol.nlu)
    stats["segments"] += 1
    if not sol.success:
        raise SimulationError(f"solver failed at t = {sol.t[-1]:.1f} s: {sol.message}")
    return sol.t, sol.y


def steady_state(model: DrumDryerModel, t: float, rtol: float, atol: float) -> FloatArray:
    """Steady state for the inputs at time ``t`` (internal, unscaled model state).

    Marches with frozen inputs (first loosely, only to get close), then polishes with a
    Newton-type root solve to machine precision; if the polish fails, marches further at
    full tolerance and keeps the marched state when the polish does not improve it.
    """
    sys = _Scaled(model, t, frozen_at=t)
    z = np.concatenate([model.initial_cold_empty(t), np.zeros(N_ACC)]) / sys.scale
    stats = {"nfev": 0, "njev": 0, "nlu": 0, "segments": 0}
    n = sys.n_model

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
            masses = (sol.x * sys.scale[:n]).reshape(model.n, 8)[:, :4]
            if res_root < res_march and np.all(masses >= -1e-9):
                return np.asarray(sol.x * sys.scale[:n])
        if not first and res_march * STEADY_MARCH < 1e-6:
            break
    return np.asarray(best * sys.scale[:n])


def simulate(loaded: LoadedScenario, *, profiles: bool = False) -> SimulationResult:
    """Run the scenario. Raises :class:`SimulationError` if the solver fails."""
    model = build_model(loaded)
    ts = loaded.spec.time
    duration = ts.duration
    dt = ts.output_interval
    t_out = np.arange(0.0, duration + 0.5 * dt, dt)
    t_out = t_out[t_out <= duration + 1e-9]
    if t_out[-1] < duration:
        t_out = np.append(t_out, duration)

    kind = loaded.spec.initial_state.kind
    if kind == "cold_empty":
        y0 = model.initial_cold_empty(0.0)
    elif kind == "steady_state":
        y0 = steady_state(model, 0.0, ts.rtol, ts.atol)
    else:
        assert loaded.initial_state is not None
        y0 = model.to_internal(loaded.initial_state, 0.0)

    sys = _Scaled(model, 0.0)
    z = np.concatenate([y0, np.zeros(N_ACC)]) / sys.scale
    stats: dict[str, Any] = {"method": METHOD, "rtol": ts.rtol, "atol": ts.atol}
    stats.update(nfev=0, njev=0, nlu=0, segments=0)
    edges = np.concatenate([[0.0], _breakpoints(model, duration), [duration]])
    times: list[FloatArray] = []
    states: list[FloatArray] = []
    started = wallclock.perf_counter()
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
    z_all = np.concatenate(states, axis=1)
    y_all = z_all * sys.scale[:, None]
    n = sys.n_model
    rows = [model.diagnostics(t, y_all[:n, i]) for i, t in enumerate(t_all)]
    index = pd.DatetimeIndex([ts.start + timedelta(seconds=float(t)) for t in t_all], name="time")
    results = pd.DataFrame(rows, index=index)

    profile_frame = None
    if profiles:
        frames = []
        for i, t in enumerate(t_all):
            prof = model.profiles(t, y_all[:n, i])
            frame = pd.DataFrame(prof)
            frame.insert(0, "cell", np.arange(model.n))
            frame.insert(0, "time", index[i])
            frames.append(frame)
        profile_frame = pd.concat(frames).set_index(["time", "cell"])

    acc = y_all[n:, -1]
    cumulative = {q: (float(acc[2 * i]), float(acc[2 * i + 1])) for i, q in enumerate(QUANTITIES)}
    y_final = y_all[:n, -1]
    log.info(
        "simulation_completed",
        simulated_s=duration,
        wall_time_s=round(stats["wall_time_s"], 3),
        nfev=stats["nfev"],
        segments=stats["segments"],
    )
    return SimulationResult(
        loaded=loaded,
        model=model,
        times=t_all,
        results=results,
        profiles=profile_frame,
        initial_state=model.to_state(y0, 0.0),
        final_state=model.to_state(y_final, float(t_all[-1])),
        initial_internal=y0,
        final_internal=y_final,
        cumulative_flows=cumulative,
        solver_stats=stats,
    )


def mean_residence_time(model: DrumDryerModel, t: float, y: FloatArray) -> float:
    """Dry solids hold-up divided by dry feed rate, s (inf without feed)."""
    feed = model.inlet(t).feed_dry
    holdup = model.storage(y)["dry_solids"]
    return holdup / feed if feed > 0 else math.inf
