"""SIMC tuning of the boiler house loops from step tests on the twin (T040, research.md R8).

For each loop, the twin is run from its steady state with both loops in manual, and the
loop's output is stepped. A second-order-plus-dead-time model is fitted to the response and
reduced to first order plus dead time with Skogestad's half rule (τ₁ + τ₂/2, θ + τ₂/2).
SIMC with τ_c = θ then gives K_c = τ₁ / (k (τ_c + θ)) and T_i = min(τ₁, 4 (τ_c + θ)).
τ_c is not set below ``MIN_TAU_C``: the twin has no analyser or sampling dead time, so the
fitted θ of the O2 loop is close to zero and τ_c = θ alone would give an unrealistically
aggressive loop (VERIFY against the plant's analyser delay).

Feature 004 adds the mixing chamber pressure loop: from the steady start of
``plant_recirculation.toml`` the recirculation damper is put in manual and stepped by
``PRESSURE_STEP``; the response of the measured pressure (static gas path behind the 2 s
transmitter lag) is fitted the same way, over ``PRESSURE_WINDOW`` only (afterwards the dryer's
slow thermal response moves the pressure), with τ_c not below ``MIN_TAU_C_PRESSURE``.

Writes ``examples/data/controller_tuning.json`` and prints the TOML snippets.

Usage: ``uv run python scripts/tune_controllers.py`` (boiler house loops) or
``uv run python scripts/tune_controllers.py pressure`` (mixing chamber pressure loop).
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from boidrytwin import load_scenario
from boidrytwin.logging import configure_logging
from boidrytwin.plant.simulate import simulate_plant

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "examples" / "boiler_house_only.toml"
OUTPUT = ROOT / "examples" / "data" / "controller_tuning.json"
STEP_AT = 600.0  # s after the start
MIN_TAU_C = 10.0  # s, stands in for the unmodelled analyser / sampling dead time

# loop: (measurement column, output column, relative step, duration, output interval)
TESTS = {
    "oil_temperature": (
        "oil_outlet_temperature", "controller_output_oil_temperature", 0.05, "12:00", "1 min"
    ),
    "oxygen": ("o2_dry_measured", "controller_output_oxygen", 0.03, "01:00", "5 s"),
}  # fmt: skip
UNITS = {"oil_temperature": ("kg/s", "kg/(s*K)"), "oxygen": ("", "")}
PLANT_RECIRCULATION = ROOT / "examples" / "plant_recirculation.toml"
PRESSURE_STEP = 0.05  # damper position step (absolute)
PRESSURE_WINDOW = 60.0  # s fitted after the step
MIN_TAU_C_PRESSURE = 5.0  # s, stands in for the damper actuator (VERIFY against the plant)


def _manual(text: str, loop: str, value: str) -> str:
    """Put a loop in manual with the given manual output (TOML value)."""
    header = f'[boiler_house.controllers.{loop}]\nmode = "automatic"'
    assert header in text
    return text.replace(
        header, f'[boiler_house.controllers.{loop}]\nmode = "manual"\nmanual_output = {value}'
    )


def _scenario(
    folder: Path, outputs: dict[str, float], loop: str, step: float, end: str, dt: str
) -> Path:
    text = BASE.read_text(encoding="utf-8")
    text = re.sub(r'end = "[^"]+"', f'end = "2026-01-01T{end}:00Z"', text, count=1)
    text = re.sub(r'output_interval = "[^"]+"', f'output_interval = "{dt}"', text, count=1)
    for name, u in outputs.items():
        unit = UNITS[name][0]
        if name == loop:
            csv = folder / f"{name}.csv"
            u1 = u * (1 + step)
            csv.write_text(
                f"time,u\nunit,{unit or '1'}\n2026-01-01T00:00:00Z,{u!r}\n"
                f"2026-01-01T00:10:00Z,{u!r}\n2026-01-01T00:10:01Z,{u1!r}\n2026-01-01T{end}:00Z,{u1!r}\n",
                encoding="utf-8",
            )
            value = f'{{ file = "{csv.as_posix()}", column = "u" }}'
        else:
            value = f'"{u!r} {unit}"' if unit else repr(u)
        text = _manual(text, name, value)
    path = folder / f"step_{loop}.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _sopdt(p: np.ndarray, t: np.ndarray) -> np.ndarray:
    k, tau1, tau2, theta = p
    s = np.maximum(t - theta, 0.0)
    if abs(tau1 - tau2) < 1e-6 * tau1:
        return k * (1 - (1 + s / tau1) * np.exp(-s / tau1))
    return k * (1 - (tau1 * np.exp(-s / tau1) - tau2 * np.exp(-s / tau2)) / (tau1 - tau2))


def fit(t: np.ndarray, dy: np.ndarray, du: float) -> dict[str, float]:
    """SOPDT least-squares fit, reduced to FOPDT by the half rule."""
    k0 = dy[-1] / du
    t63 = float(t[np.argmax(np.abs(dy) >= 0.632 * abs(dy[-1]))])
    p0 = np.array([k0, 0.8 * t63, 0.1 * t63, 0.05 * t63])
    res = least_squares(
        lambda p: _sopdt(p, t) - dy / du,
        p0,
        bounds=([-np.inf, 1e-3, 1e-3, 0.0], [np.inf, 1e6, 1e6, 1e5]),
    )
    k, a, b, theta = res.x
    tau1, tau2 = max(a, b), min(a, b)
    return {
        "k": float(k),
        "tau1": float(tau1 + tau2 / 2),
        "theta": float(theta + tau2 / 2),
        "sopdt": {"tau1": float(tau1), "tau2": float(tau2), "theta": float(theta)},
        "fit_rms": float(np.sqrt(np.mean(res.fun**2))),
    }  # type: ignore[dict-item]


def simc(model: dict[str, float]) -> dict[str, float]:
    theta = model["theta"]
    tau_c = max(theta, MIN_TAU_C)
    gain = model["tau1"] / (abs(model["k"]) * (tau_c + theta))
    return {"tau_c": tau_c, "gain": gain, "integral_time": min(model["tau1"], 4 * (tau_c + theta))}


def tune_pressure_loop() -> dict[str, object]:
    """Step test of the recirculation damper in the coupled plant (feature 004)."""
    base = PLANT_RECIRCULATION.read_text(encoding="utf-8")
    steady = simulate_plant(load_scenario(PLANT_RECIRCULATION))
    assert steady.dryer_results is not None
    u0 = float(steady.dryer_results["recirculation_damper_position"].iloc[0])
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        csv = folder / "damper.csv"
        u1 = u0 + PRESSURE_STEP
        csv.write_text(
            f"time,u\nunit,1\n2026-01-01T00:00:00Z,{u0!r}\n2026-01-01T00:10:00Z,{u0!r}\n"
            f"2026-01-01T00:10:01Z,{u1!r}\n2026-01-01T00:20:00Z,{u1!r}\n",
            encoding="utf-8",
        )
        text = re.sub(r'end = "[^"]+"', 'end = "2026-01-01T00:20:00Z"', base, count=1)
        text = re.sub(r'output_interval = "[^"]+"', 'output_interval = "1 s"', text, count=1)
        head, tail = text.rsplit("[recirculation.controller]", 1)
        manual = f'mode = "manual"\nmanual_output = {{ file = "{csv.as_posix()}", column = "u" }}'
        tail = tail.replace('mode = "automatic"', manual, 1)
        path = folder / "step_pressure.toml"
        path.write_text(head + "[recirculation.controller]" + tail, encoding="utf-8")
        sim = simulate_plant(load_scenario(path))
    assert sim.dryer_results is not None
    t = sim.times
    y = sim.dryer_results["mixing_chamber_pressure_measured"].to_numpy()
    after = (t >= STEP_AT + 1.0) & (t <= STEP_AT + 1.0 + PRESSURE_WINDOW)
    before = y[t < STEP_AT][-1]
    model = fit(t[after] - STEP_AT - 1.0, y[after] - before, PRESSURE_STEP)
    theta = model["theta"]
    tau_c = max(theta, MIN_TAU_C_PRESSURE)
    tuning = {
        "tau_c": tau_c,
        "gain": model["tau1"] / (abs(model["k"]) * (tau_c + theta)),
        "integral_time": min(model["tau1"], 4 * (tau_c + theta)),
    }
    return {"operating_output": u0, "step": PRESSURE_STEP, **model, **tuning}


def main_pressure() -> None:
    configure_logging(level="WARNING")
    record = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.is_file() else {}
    r = tune_pressure_loop()
    record["mixing_chamber_pressure"] = r
    OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"# k = {r['k']:.4g} Pa, tau1 = {r['tau1']:.2f} s, theta = {r['theta']:.2f} s")
    print("[recirculation.controller]")
    print(f'gain = "{r["gain"]:.3g} 1/Pa"')
    print(f'integral_time = "{r["integral_time"]:.3g} s"')


def main() -> None:
    configure_logging(level="WARNING")
    steady = simulate_plant(load_scenario(BASE))
    outputs = {name: float(steady.results[TESTS[name][1]].iloc[-1]) for name in TESTS}
    record: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for loop, (meas, _, step, end, dt) in TESTS.items():
            path = _scenario(Path(tmp), outputs, loop, step, end, dt)
            sim = simulate_plant(load_scenario(path))
            t = sim.times
            y = sim.results[meas].to_numpy()
            after = t >= STEP_AT
            model = fit(t[after] - STEP_AT, y[after] - y[~after][-1], outputs[loop] * step)
            tuning = simc(model)
            record[loop] = {
                "operating_output": outputs[loop],
                "step": outputs[loop] * step,
                **model,
                **tuning,
            }
    OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    for loop, r in record.items():
        unit = UNITS[loop][1]
        gain = f'"{r["gain"]:.3g} {unit}"' if unit else f"{r['gain']:.3g}"
        print(f"# k = {r['k']:.4g}, tau1 = {r['tau1']:.0f} s, theta = {r['theta']:.0f} s")
        print(f"[boiler_house.controllers.{loop}]")
        print(f"gain = {gain}")
        print(f'integral_time = "{r["integral_time"]:.0f} s"\n')


if __name__ == "__main__":
    main_pressure() if sys.argv[1:] == ["pressure"] else main()
